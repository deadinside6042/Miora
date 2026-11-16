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
                            output.write(json.dumps(record, ensure_ascii=False) + "\n")
                            output.flush()
                            records.append(result)
                            if args.delay:
                                time.sleep(args.delay)
                summaries[f"{model} | {mode}"] = aggregate(records)
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
