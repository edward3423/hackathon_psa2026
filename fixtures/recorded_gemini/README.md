# Recorded Gemini responses

Owner: Agent 6 (Verification). This directory holds captured live Gemini
responses so deterministic agent tests can replay them without network access
(PRD section 16, "deterministic agent tests using recorded Gemini responses").

Capture with `uv run python scripts/capture_gemini.py` (requires
GEMINI_API_KEY, read from the gitignored .env if not exported) and commit the
reviewed output here.

## Capture profile

Free-tier gemini-3.5-flash allows 20 requests per day, while a fully live
golden run needs 15-21 model calls. Recording therefore uses a capture
profile (`CaptureProfileBrain` in src/cascade/agents/live_gemini.py): the
decision-critical calls - dispute reconciliation, human constraint, plan
proposal, plan revisions, plan comparison, approval request - go to the live
model, and routine step narrations use the scripted brain. A golden run then
costs about 9 requests, hard capped at 18 (`CAPTURE_CALL_BUDGET`).

Consequence: recordings cover every LIVE model call of a capture-profile run,
not of a fully live run. Replay harnesses must serve exchanges for exactly the
steps in `LIVE_CAPTURE_STEPS` plus propose/revise calls.

## Expected format

One JSON file per recorded run, named:

    <scenario>__<agent-flow>__<yyyymmdd>.json

Example: `golden__capture-profile__20260817.json`.

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
