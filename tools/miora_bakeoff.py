#!/usr/bin/env python3
"""Miora model bake-off: replay synthetic conversations against OpenRouter models.

This isolates model behavior with one deliberately short, consistent prompt.
It does NOT test Miora's full production prompt or backend. Results are raw
evidence for human review; the cheap metrics below are warning signals, not
semantic judgments.

Usage:
  export OPENROUTER_API_KEY="..."
  python -m pip install httpx
  python tools/miora_bakeoff.py --samples 2 --models all
  python tools/miora_bakeoff.py --samples 1 --models anthropic/claude-haiku-5.5

Outputs:
  results.jsonl  One JSON record per model / transcript / sample, including
                 every turn's raw response, parsed output, latency and usage.
  summary.json   Aggregate mechanical metrics.

Use synthetic test conversations only. Do not put private user conversations
or identifying information into a third-party model bake-off.
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

# IDs checked against the OpenRouter model catalogue on 2026-11-15.
# The Nemotron entry is the model currently used by Miora.
MODELS = [
    "anthropic/claude-haiku-5.5",
    "meta-llama/llama-3.3-70b-instruct",
    "google/gemini-3.8-flash",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

SYSTEM = """You are Miora, a warm, plain-spoken conversational companion.
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
"""

# Synthetic scenarios deliberately include ambiguity, a dodge, a correction,
# venting without a request for advice, and a direct answer to a question.
TRANSCRIPTS: dict[str, list[str]] = {
    "work_mistake": [
        "I fucked up at work.",
        "It was such a stupid mistake.",
        "I've done this task a thousand times.",
        "I'm worried my boss is going to think I'm incompetent.",
    ],
    "dodged_question": [
        "I had a horrible day.",
        "What happened?",
        "I don't really want to get into the details.",
        "I'm just tired of everything piling up.",
    ],
    "correction": [
        "My friend hasn't replied all day.",
        "It sounds like you're worried they're upset with you.",
        "No, I'm not worried they're upset. I'm annoyed because they promised to help.",
        "I needed them to show up today.",
    ],
    "vent_no_advice": [
        "My family keeps arguing whenever we're together.",
        "Have you tried setting some ground rules?",
        "I don't want a plan. I'm just sick of it.",
        "It makes me dread seeing them.",
    ],
    "answer_question": [
        "I made a mistake in a meeting.",
        "What happened?",
        "I gave the wrong number to the client, then corrected it ten minutes later.",
        "My manager said it was fine, but I still feel embarrassed.",
    ],
    "ambiguous_statement": [
        "I can't believe she said that.",
        "That sounds hurtful.",
        "It was actually funny. I just wasn't expecting it.",
        "I keep replaying the moment because of how unexpected it was.",
    ],
}

HISTORY_WORDS = re.compile(
    r"\b(again|before|always|as usual|every time|repeated(?:ly)?|"
    r"keep (?:making|doing)|used to)\b",
    re.IGNORECASE,
)


def parse_json(raw: str) -> dict[str, Any] | None:
    """Parse strict JSON, with a fallback for models that wrap it in fences."""
    text = raw.strip()
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        # Recover the first complete JSON object without greedy over-capture.
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


def call_model(
    client: httpx.Client, model: str, messages: list[dict[str, str]]
) -> tuple[str, dict[str, Any], float]:
    started = time.perf_counter()
    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/deadinside6042/Miora",
            "X-Title": "Miora offline model bake-off",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 900,
        },
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter returned no choices: {json.dumps(payload)[:1000]}")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content), payload.get("usage") or {}, elapsed


def score_turn(
    user_message: str,
    all_user_messages: list[str],
    parsed: dict[str, Any] | None,
    previous_move: str | None,
    previous_opener: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {"json_ok": parsed is not None}
    if parsed is None:
        return result

    read = parsed.get("read") if isinstance(parsed.get("read"), dict) else {}
    reply = parsed.get("reply") if isinstance(parsed.get("reply"), str) else ""
    stated = read.get("stated") if isinstance(read.get("stated"), list) else []
    quotes = [
        item.get("quote", "") for item in stated
        if isinstance(item, dict) and isinstance(item.get("quote", ""), str)
    ]
    full_history = "\n".join(all_user_messages).casefold()
    result.update({
        "bad_quotes": sum(1 for quote in quotes if not quote or quote.casefold() not in full_history),
        # A lexical warning only: human review must decide whether the claim
        # is genuinely unsupported in context.
        "unsupported_history_word_flag": bool(HISTORY_WORDS.search(reply))
        and not bool(HISTORY_WORDS.search(full_history)),
        "move": read.get("move"),
        "same_move_as_previous": bool(previous_move and read.get("move") == previous_move),
        "opener_similarity": round(
            difflib.SequenceMatcher(None, opener(reply), previous_opener).ratio()
            if previous_opener and reply else 0.0, 2
        ),
        "question_count": reply.count("?"),
        "reply": reply,
        "last_question_status": read.get("last_question_status"),
    })
    return result


def run_one(
    client: httpx.Client, model: str, turns: list[str]
) -> dict[str, Any]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM}]
    user_history: list[str] = []
    turn_rows: list[dict[str, Any]] = []
    previous_move: str | None = None
    previous_opener = ""

    for turn_index, user_text in enumerate(turns, start=1):
        messages.append({"role": "user", "content": user_text})
        user_history.append(user_text)
        try:
            raw, usage, latency = call_model(client, model, messages)
            parsed = parse_json(raw)
            metrics = score_turn(
                user_text, user_history, parsed, previous_move, previous_opener
            )
            reply = parsed.get("reply", "") if parsed else raw
            if not isinstance(reply, str):
                reply = raw
            if parsed:
                read = parsed.get("read") if isinstance(parsed.get("read"), dict) else {}
                previous_move = read.get("move") if isinstance(read.get("move"), str) else None
                previous_opener = opener(reply)
            messages.append({"role": "assistant", "content": reply})
            turn_rows.append({
                "turn": turn_index,
                "user": user_text,
                "raw": raw,
                "parsed": parsed,
                "latency_seconds": round(latency, 3),
                "usage": usage,
                "metrics": metrics,
                "error": None,
            })
        except Exception as exc:  # preserve failure and continue to next scenario
            turn_rows.append({
                "turn": turn_index,
                "user": user_text,
                "raw": None,
                "parsed": None,
                "latency_seconds": None,
                "usage": {},
                "metrics": {"json_ok": False},
                "error": f"{type(exc).__name__}: {exc}",
            })
            # Keep conversation shape valid after a failed request.
            messages.append({"role": "assistant", "content": "[model request failed]"})

    return {"model": model, "turns": turn_rows}


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "runs": len(records), "turns": 0, "json_ok": 0, "bad_quotes": 0,
        "history_word_flags": 0, "same_move": 0, "high_opener_similarity": 0,
        "errors": 0, "latency_seconds": [], "input_tokens": 0,
        "output_tokens": 0, "reported_cost": 0.0,
    }
    for record in records:
        for turn in record["turns"]:
            totals["turns"] += 1
            if turn.get("error"):
                totals["errors"] += 1
            metrics = turn.get("metrics", {})
            totals["json_ok"] += int(bool(metrics.get("json_ok")))
            totals["bad_quotes"] += int(metrics.get("bad_quotes", 0))
            totals["history_word_flags"] += int(bool(metrics.get("unsupported_history_word_flag")))
            totals["same_move"] += int(bool(metrics.get("same_move_as_previous")))
            totals["high_opener_similarity"] += int(metrics.get("opener_similarity", 0) > 0.75)
            if turn.get("latency_seconds") is not None:
                totals["latency_seconds"].append(turn["latency_seconds"])
            usage = turn.get("usage") or {}
            totals["input_tokens"] += int(usage.get("prompt_tokens") or 0)
            totals["output_tokens"] += int(usage.get("completion_tokens") or 0)
            if usage.get("cost") is not None:
                totals["reported_cost"] += float(usage["cost"])
    latencies = totals["latency_seconds"]
    totals["mean_latency_seconds"] = round(sum(latencies) / len(latencies), 3) if latencies else None
    totals["reported_cost"] = round(totals["reported_cost"], 6)
    del totals["latency_seconds"]
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1, help="repetitions per model and scenario")
    parser.add_argument("--models", nargs="+", default=["all"], help="'all' or one or more OpenRouter model IDs")
    parser.add_argument("--transcripts", nargs="+", default=["all"], help="'all' or scenario names")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between API calls")
    parser.add_argument("--output", default="results.jsonl")
    parser.add_argument("--summary", default="summary.json")
    args = parser.parse_args()

    if args.samples < 1:
        parser.error("--samples must be at least 1")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("ERROR: set OPENROUTER_API_KEY in your environment.", file=sys.stderr)
        return 2

    models = MODELS if args.models == ["all"] else args.models
    names = list(TRANSCRIPTS) if args.transcripts == ["all"] else args.transcripts
    unknown = sorted(set(names) - set(TRANSCRIPTS))
    if unknown:
        parser.error(f"unknown transcript(s): {', '.join(unknown)}")

    total_calls = len(models) * args.samples * sum(len(TRANSCRIPTS[n]) for n in names)
    print(f"Planned calls (upper bound): {total_calls}")
    print("Prompt: short model-comparison prompt; production prompt is not tested.")
    print("Input data: synthetic scenarios only.")

    summaries: dict[str, Any] = {}
    with httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
        for model in models:
            records: list[dict[str, Any]] = []
            with open(args.output, "a", encoding="utf-8") as output:
                for name in names:
                    for sample in range(1, args.samples + 1):
                        print(f"Running {model} | {name} | sample {sample}/{args.samples}")
                        result = run_one(client, model, TRANSCRIPTS[name])
                        record = {
                            "model": model,
                            "transcript": name,
                            "sample": sample,
                            "prompt_variant": "short_grounding_v1",
                            **result,
                        }
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        output.flush()
                        records.append(result)
                        if args.delay:
                            time.sleep(args.delay)
            summaries[model] = aggregate(records)

    Path(args.summary).write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("\nSUMMARY")
    print(json.dumps(summaries, indent=2))
    print(f"\nDetailed results: {args.output}")
    print(f"Summary: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
