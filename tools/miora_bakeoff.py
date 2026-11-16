def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--models", nargs="+", default=["all"])
    parser.add_argument("--modes", nargs="+", default=["all"],
                        help=f"Prompt modes: {', '.join(MODES)} or all")
    parser.add_argument("--transcripts", nargs="+", default=["all"])
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--output", default="ab_results.jsonl")
    parser.add_argument("--summary", default="ab_summary.json")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: set OPENROUTER_API_KEY in your environment.", file=sys.stderr)
        return 2
    models = MODELS if args.models == ["all"] else args.models
    modes = MODES if args.modes == ["all"] else args.modes
    unknown_modes = sorted(set(modes) - set(MODES))
    if unknown_modes:
        parser.error(f"unknown mode(s): {', '.join(unknown_modes)}")
    names = list(TRANSCRIPTS) if args.transcripts == ["all"] else args.transcripts
    unknown = sorted(set(names) - set(TRANSCRIPTS))
    if unknown:
        parser.error(f"unknown transcript(s): {', '.join(unknown)}")
    turns_per_run = sum(
        sum(
            role == "user" and not (
                index + 1 < len(TRANSCRIPTS[name])
                and TRANSCRIPTS[name][index + 1][0] == "assistant"
            )
            for index, (role, _) in enumerate(TRANSCRIPTS[name])
        )
        for name in names
    )
    total_calls = len(models) * len(modes) * args.samples * turns_per_run
    print(f"Planned model requests: {total_calls}")
    print(f"Models: {len(models)} | Prompt modes: {', '.join(modes)} | Scenarios: {len(names)}")
    print("All scenarios use correct speaker roles. Synthetic data only.")
    summaries: dict[str, Any] = {}
    with httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
        for model in models:
            for mode in modes:
                records = []
                with open(args.output, "a", encoding="utf-8") as output:
                    for name in names:
                        for sample in range(1, args.samples + 1):
                            print(f"Running {model} | {mode} | {name} | sample {sample}/{args.samples}")
                            result = run_one(client, model, mode, TRANSCRIPTS[name])
                            record = {
                                "model": model, "mode": mode, "transcript": name,
                                "sample": sample, **result,
                            }
                            output.write(json.dumps(record, ensure_ascii=False) + "\\n")
                            output.flush()
                            records.append(result)
                            if args.delay:
                                time.sleep(args.delay)
                summaries[f"{model} | {mode}"] = aggregate(records)
    Path(args.summary).write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8"
    )
    print("\\nSUMMARY")
    print(json.dumps(summaries, indent=2))
    print(f"\\nDetailed results: {args.output}")
    print(f"Summary: {args.summary}")
    return 0
#!/usr/bin/env python3
"""Miora model bake-off with role-correct synthetic conversations.

Compares the same conversations across OpenRouter models. Scripted assistant
messages are replayed as assistant messages; only user messages trigger a model
response. This tests a short comparison prompt, not Miora's production prompt.

Use synthetic conversations only. Never send private user conversations here.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Free endpoints only: "--models all" must never incur API charges.
# Keep synthetic test conversations only. Do not send real or sensitive Miora chats
# to free NVIDIA endpoints; their OpenRouter pages carry a data-use notice.
MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "dots-studio/dots-3-note-preview:free",
]

PROMPTS = {
    "A_plain": """You are Miora, a warm, plain-spoken conversational companion.
Respond naturally to what the person actually said. Do not assume history,
motives or feelings they have not stated. If they dodge a question, don't
repeat it; respond to what they did say. Do not turn every reply into a
question. Avoid stock phrases and repeated reflections. Be concise and
conversational. Reply only with the message you would say to the person.""",
    "B_reply_json": """You are Miora, a warm, plain-spoken conversational companion.
Respond naturally to what the person actually said. Do not assume history,
motives or feelings they have not stated. If they dodge a question, don't
repeat it; respond to what they did say. Do not turn every reply into a
question. Avoid stock phrases and repeated reflections. Be concise and
conversational.

Return only this JSON object: {"reply": "your message to the person"}.
Do not include analysis, a ledger, or any other fields.""",
    "C_full_ledger": """You are Miora, a warm, plain-spoken conversational companion.
Respond to what the person actually said, in natural language. Do not assume
history, motives or feelings they have not stated; ask or wonder instead.
If they dodge a question, don't repeat it; respond to what they did say.
Do not turn every reply into a question. Avoid stock phrases and repeated
reflections. Be concise and conversational.

Return ONLY a JSON object in this exact shape:
{
  "read": {
    "stated": [{"claim": "short factual claim", "quote": "exact substring from a user message"}],
    "possible": ["tentative interpretation, clearly uncertain"],
    "unknown": ["important thing not yet known"],
    "last_question_status": "answered|dodged|ignored|none",
    "move": "reflect|ask|offer|reassure|stay_with"
  },
  "reply": "the message Miora says to the person"
}
Quotes must be exact substrings of the user's messages. Do not invent facts.
""",
}
MODES = list(PROMPTS)

# Each item is an actual speaker turn. Scripted assistant turns are fixed
# context, not misrepresented as things the user said.
TRANSCRIPTS: dict[str, list[tuple[str, str]]] = {
    "work_mistake": [
        ("user", "I fucked up at work."),
        ("user", "It was such a stupid mistake."),
        ("user", "I've done this task a thousand times."),
        ("user", "I'm worried my boss is going to think I'm incompetent."),
    ],
    "dodged_question": [
        ("user", "I had a horrible day."),
        ("assistant", "What happened?"),
        ("user", "I don't really want to get into the details."),
        ("user", "I'm just tired of everything piling up."),
    ],
    "correction": [
        ("user", "My friend hasn't replied all day."),
        ("assistant", "It sounds like you're worried they're upset with you."),
        ("user", "No, I'm not worried they're upset. I'm annoyed because they promised to help."),
        ("user", "I needed them to show up today."),
    ],
    "vent_no_advice": [
        ("user", "My family keeps arguing whenever we're together."),
        ("assistant", "Have you tried setting some ground rules?"),
        ("user", "I don't want a plan. I'm just sick of it."),
        ("user", "It makes me dread seeing them."),
    ],
    "answer_question": [
        ("user", "I made a mistake in a meeting."),
        ("assistant", "What happened?"),
        ("user", "I gave the wrong number to the client, then corrected it ten minutes later."),
        ("user", "My manager said it was fine, but I still feel embarrassed."),
    ],
    "ambiguous_statement": [
        ("user", "I can't believe she said that."),
        ("assistant", "That sounds hurtful."),
        ("user", "It was actually funny. I just wasn't expecting it."),
        ("user", "I keep replaying the moment because of how unexpected it was."),
    ],
}

HISTORY_WORDS = re.compile(
    r"\b(again|before|always|as usual|every time|repeated(?:ly)?|"
    r"keep (?:making|doing)|used to)\b",
    re.IGNORECASE,
)


def parse_json(raw: str) -> dict[str, Any] | None:
    text = re.sub(r"^\s*```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = text.find("{")
        if start < 0:
            return None
        try:
            value, _ = decoder.raw_decode(text[start:])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def opener(text: str) -> str:
    pieces = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    return pieces[0].lower() if pieces else ""


def call_model(client: httpx.Client, model: str,
               messages: list[dict[str, str]]) -> tuple[str, dict[str, Any], float]:
    started = time.perf_counter()
    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/deadinside6042/Miora",
            "X-Title": "Miora model bake-off",
        },
        json={"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 900},
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"No model choices returned: {json.dumps(payload)[:800]}")
    message = choices[0].get("message") or {}
    value = message.get("content") or ""
    if isinstance(value, list):
        value = "".join(
            part.get("text", "") for part in value
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(value), payload.get("usage") or {}, elapsed


def score_turn(raw: str, parsed: dict[str, Any] | None, mode: str,
               user_history: list[str], previous_move: str | None,
               previous_opener: str) -> dict[str, Any]:
    # Formatting compliance is reported separately from conversational quality.
    metrics: dict[str, Any] = {
        "json_expected": mode != "A_plain",
        "json_ok": None if mode == "A_plain" else parsed is not None,
        "reply": "",
    }
    if mode == "A_plain":
        reply = raw.strip()
    elif mode == "B_reply_json":
        reply = parsed.get("reply", "") if parsed else ""
    else:
        reply = parsed.get("reply", "") if parsed else ""
    if not isinstance(reply, str):
        reply = ""
    metrics["reply"] = reply
    if mode == "C_full_ledger" and parsed:
        read = parsed.get("read") if isinstance(parsed.get("read"), dict) else {}
        stated = read.get("stated") if isinstance(read.get("stated"), list) else []
        quotes = [
            item.get("quote", "") for item in stated
            if isinstance(item, dict) and isinstance(item.get("quote", ""), str)
        ]
        full_history = "\\n".join(user_history).casefold()
        metrics.update({
            "bad_quotes": sum(1 for q in quotes if not q or q.casefold() not in full_history),
            "unsupported_history_word_flag": bool(HISTORY_WORDS.search(reply))
                and not bool(HISTORY_WORDS.search(full_history)),
            "move": read.get("move"),
            "same_move_as_previous": bool(previous_move and read.get("move") == previous_move),
            "opener_similarity": round(
                difflib.SequenceMatcher(None, opener(reply), previous_opener).ratio()
                if previous_opener and reply else 0.0, 2
            ),
            "last_question_status": read.get("last_question_status"),
        })
    return metrics
def run_one(client: httpx.Client, model: str, mode: str,
            transcript: list[tuple[str, str]]) -> dict[str, Any]:
    messages: list[dict[str, str]] = [{"role": "system", "content": PROMPTS[mode]}]
    user_history: list[str] = []
    rows: list[dict[str, Any]] = []
    previous_move: str | None = None
    previous_opener = ""
    model_turn = 0

    for index, (role, content) in enumerate(transcript):
        if role == "assistant":
            messages.append({"role": "assistant", "content": content})
            continue
        messages.append({"role": "user", "content": content})
        user_history.append(content)
        next_is_scripted_reply = (
            index + 1 < len(transcript) and transcript[index + 1][0] == "assistant"
        )
        if next_is_scripted_reply:
            continue
        model_turn += 1
        try:
            raw, usage, latency = call_model(client, model, messages)
            parsed = parse_json(raw) if mode != "A_plain" else None
            metrics = score_turn(raw, parsed, mode, user_history, previous_move, previous_opener)
            reply = metrics["reply"]
            if mode == "C_full_ledger" and parsed:
                read = parsed.get("read") if isinstance(parsed.get("read"), dict) else {}
                previous_move = read.get("move") if isinstance(read.get("move"), str) else None
            if reply:
                previous_opener = opener(reply)
                messages.append({"role": "assistant", "content": reply})
            else:
                # Preserve the failed output in context so later turns reflect
                # the real consequence of a format failure.
                messages.append({"role": "assistant", "content": raw})
            rows.append({
                "turn": model_turn, "user": content, "raw": raw, "parsed": parsed,
                "latency_seconds": round(latency, 3), "usage": usage,
                "metrics": metrics, "error": None,
            })
        except Exception as exc:
            rows.append({
                "turn": model_turn, "user": content, "raw": None, "parsed": None,
                "latency_seconds": None, "usage": {}, "metrics": {
                    "json_expected": mode != "A_plain",
                    "json_ok": None if mode == "A_plain" else False,
                    "reply": "",
                },
                "error": f"{type(exc).__name__}: {exc}",
            })
            messages.append({"role": "assistant", "content": "[model request failed]"})
    return {"model": model, "mode": mode, "turns": rows}

def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    total: dict[str, Any] = {
        "runs": len(records), "turns": 0, "json_expected_turns": 0,
        "json_ok": 0, "bad_quotes": 0, "history_word_flags": 0,
        "same_move": 0, "high_opener_similarity": 0, "errors": 0,
        "latencies": [], "input_tokens": 0, "output_tokens": 0,
        "reported_cost": 0.0,
    }
    for record in records:
        for turn in record["turns"]:
            total["turns"] += 1
            total["errors"] += int(bool(turn.get("error")))
            metric = turn.get("metrics", {})
            total["json_expected_turns"] += int(bool(metric.get("json_expected")))
            total["json_ok"] += int(metric.get("json_ok") is True)
            total["bad_quotes"] += int(metric.get("bad_quotes", 0))
            total["history_word_flags"] += int(bool(metric.get("unsupported_history_word_flag")))
            total["same_move"] += int(bool(metric.get("same_move_as_previous")))
            total["high_opener_similarity"] += int(metric.get("opener_similarity", 0) > 0.75)
            if turn.get("latency_seconds") is not None:
                total["latencies"].append(turn["latency_seconds"])
            usage = turn.get("usage") or {}
            total["input_tokens"] += int(usage.get("prompt_tokens") or 0)
            total["output_tokens"] += int(usage.get("completion_tokens") or 0)
            if usage.get("cost") is not None:
                total["reported_cost"] += float(usage["cost"])
    latencies = total.pop("latencies")
    total["mean_latency_seconds"] = round(sum(latencies) / len(latencies), 3) if latencies else None
    total["reported_cost"] = round(total["reported_cost"], 6)
    return total

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--models", nargs="+", default=["all"])
    parser.add_argument("--transcripts", nargs="+", default=["all"])
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--output", default="corrected_results.jsonl")
    parser.add_argument("--summary", default="corrected_summary.json")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: set OPENROUTER_API_KEY in your environment.", file=sys.stderr)
        return 2
    models = MODELS if args.models == ["all"] else args.models
    names = list(TRANSCRIPTS) if args.transcripts == ["all"] else args.transcripts
    unknown = sorted(set(names) - set(TRANSCRIPTS))
    if unknown:
        parser.error(f"unknown transcript(s): {', '.join(unknown)}")
    total_calls = len(models) * args.samples * sum(
        sum(
            role == "user" and not (
                index + 1 < len(TRANSCRIPTS[name])
                and TRANSCRIPTS[name][index + 1][0] == "assistant"
            )
            for index, (role, _) in enumerate(TRANSCRIPTS[name])
        )
        for name in names
    )
    print(f"Planned model requests: {total_calls}")
    print("All six scenarios use correct speaker roles. Synthetic data only.")
    summaries: dict[str, Any] = {}
    with httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
        for model in models:
            records = []
            with open(args.output, "a", encoding="utf-8") as output:
                for name in names:
                    for sample in range(1, args.samples + 1):
                        print(f"Running {model} | {name} | sample {sample}/{args.samples}")
                        result = run_one(client, model, TRANSCRIPTS[name])
                        record = {
                            "model": model, "transcript": name, "sample": sample,
                            "prompt_variant": "short_grounding_v2_role_correct",
                            **result,
                        }
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        output.flush()
                        records.append(result)
                        if args.delay:
                            time.sleep(args.delay)
            summaries[model] = aggregate(records)
    Path(args.summary).write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("\nSUMMARY")
    print(json.dumps(summaries, indent=2))
    print(f"\nDetailed results: {args.output}")
    print(f"Summary: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
