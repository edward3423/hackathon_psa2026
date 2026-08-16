# Recorded Gemini responses

Owner: Agent 6 (Verification). This directory holds captured live Gemini
responses so deterministic agent tests can replay them without network access
(PRD section 16, "deterministic agent tests using recorded Gemini responses").

Recordings are captured once the live Gemini path (Agent 4 workstream) lands,
by running the golden scenario with recording enabled and committing the
reviewed output here.

## Expected format

One JSON file per recorded run, named:

    <scenario>__<agent-flow>__<yyyymmdd>.json

Example: `golden__full-workflow__20260819.json`.

Each file is a single JSON object:

```json
{
  "recording_id": "golden__full-workflow__20260819",
  "captured_at": "2026-08-19T09:30:00Z",
  "model": "gemini-3.5-flash",
  "scenario_controls": {
    "delay_hours": 18,
    "priority_emphasis": "BALANCED",
    "alternative_sailing_failure": true
  },
  "notes": "Reviewed capture of a valid golden run.",
  "exchanges": [
    {
      "sequence": 1,
      "agent": "Coordinator Agent",
      "request": {
        "system_instruction_sha256": "<hash of the prompt actually sent>",
        "contents_summary": "Alert for MV ATLAS STAR, 18h delay",
        "tools_offered": ["analyse_connections", "simulate_yard"]
      },
      "response": {
        "text": "<verbatim model text, if any>",
        "function_calls": [
          {"name": "analyse_connections", "args": {"delay_hours": 18}}
        ],
        "finish_reason": "STOP",
        "usage": {"prompt_tokens": 0, "response_tokens": 0}
      }
    }
  ]
}
```

Rules:

- `exchanges` is ordered by `sequence` and covers every model call in the run,
  so a replay harness can serve `response` payloads in order and assert the
  workflow makes the same tool choices.
- Store the verbatim response `text` and `function_calls`; store only a hash
  and short summary of the request side so prompts stay versioned in code, not
  duplicated here.
- Never record or commit API keys, headers, or any non-synthetic data.
- Do not display or store hidden chain-of-thought; recordings contain only the
  model output that the application itself would consume.
- Recordings are reviewed before commit: valid delegation, tool selection,
  constraint compliance, and approval gating (the live evaluation criteria).
