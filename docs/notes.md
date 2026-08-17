# Decision notes

Working decisions that are not part of the PRD but shape the current build.
Newest first.

## Local Claude fallback for live agent calls (2026-08-17)

Decision: for now, live agent calls run through the locally installed Claude
Code CLI in headless mode (`claude -p`) instead of the Gemini API, because
free-tier gemini-3.5-flash allows only 20 requests per day and a fully live
run needs 15-21 calls.

How it works:

- New run mode `LIVE_CLAUDE` (contracts.RunMode), selectable in the UI via
  the "Agent brain" dropdown, or via `POST /api/runs?mode=LIVE_CLAUDE`.
- `ClaudeBrain` (src/cascade/agents/local_claude.py) implements the same
  AgentBrain seam as `GeminiBrain`: identical versioned prompts, identical
  user messages (shared builders in agents/base.py), local pydantic
  validation with the same one-retry policy. The target JSON schema is
  embedded in the prompt because the CLI has no JSON response mode, and the
  reply is sliced to its first JSON object before validation.
- Each brain call is one `claude -p --output-format text` subprocess with
  the prompt on stdin, 300 s timeout. `CASCADE_CLAUDE_MODEL` optionally
  overrides the CLI's default model via `--model`.
- Guards match the Gemini path: `POST /api/runs` returns 409 when the
  `claude` CLI is not on PATH, and `ClaudeBrain.create()` refuses rather
  than impersonate. The stage machine and every figure stay deterministic;
  the brain only words summaries and allocates plans within the three fixed
  archetypes.
- Only synthetic scenario data is sent, the same rule as the Gemini path.
  Calls bill the local Claude Code account/subscription, not an API key.

Status: LIVE_GEMINI remains fully wired and is still the PRD's live path;
LIVE_CLAUDE is the day-to-day live driver while the Gemini quota stays at
20/day. The recorded-response fixtures and their replay tests
(fixtures/recorded_gemini/, tests/test_recorded_gemini.py) remain
Gemini-based.
