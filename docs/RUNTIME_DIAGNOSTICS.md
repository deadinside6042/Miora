# Runtime diagnostics (opt-in)

This branch adds temporary, privacy-conscious tracing to the `/chat` path.

## What it records

When `MIORA_DIAGNOSTICS=1` is set on the backend, each chat request emits two JSON log events:

- `miora_diagnostic_request`: configured model, sampling settings, conversation message counts, the deterministic judgment snapshot, prompt section character counts, and a SHA-256 fingerprint of the assembled system prompt.
- `miora_diagnostic_response`: provider-reported model, finish reason, and token usage when the provider returns it.

The events share a `diagnostic_id` so request and response can be paired.

## What it deliberately does not record

It does not log user or assistant message text, profile/memory content, retrieved knowledge text, live research text, API keys, or the assembled prompt itself. Render logs are not a suitable place to store private conversations. The fingerprint and size/section metadata let us confirm whether the prompt changed without exposing its contents.

## How to use safely

1. Review and merge this diagnostics-only pull request first.
2. In the Render backend service environment, temporarily set `MIORA_DIAGNOSTICS=1`.
3. Deploy/restart the backend, then reproduce the work-mistake conversation once using a test conversation with no sensitive personal details.
4. In Render logs, find the paired JSON events by `diagnostic_id`. Share those events here after removing any identifiers you do not want to share.
5. Turn diagnostics off by removing the variable or setting it to `0`.

Do not enable raw prompt or conversation logging in production. If Claude needs the exact fully assembled prompt, capture it only in a controlled local test using synthetic messages and a test profile, not from real user conversations.

## Current known issue to validate

The judgment classifier marks a message as `contextual_follow_through` whenever the previous assistant message ends in a question mark. It does not verify that the user's next message actually answers that question. The diagnostic snapshot makes this classification visible on the live request so we can test the hypothesis before changing behaviour.
