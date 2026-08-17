# Decision notes

Working decisions that are not part of the PRD but shape the current build.
Newest first.

## Live-brain feasibility briefing (2026-08-17)

Bug: live LIVE_CLAUDE runs looped on plug rejections ("block YB3 needs 9
reefer plugs but has 6") until failure. Root cause: PlanAction has no block
field - the engine maps rush counts onto containers in fixed priority order
(assign_plan_actions) and those containers sit in fixed yard blocks, but the
model was never told the block layout or plug headroom, so feasible counts
were unknowable to it. Fix: PlanningFacts (contracts) computed by
engine.plans.planning_facts and exposed via ToolBox.planning_facts; the plan
briefing embeds crane surge allowance, free plugs per block, and each
affected group's rush order (yard block per slot, * = consumes a plug) into
proposal and revision messages. ScriptedBrain ignores it; live brains can
now compute feasibility before proposing.

## Claude calls pinned to Sonnet 5 low effort (2026-08-17)

All `claude -p` calls run with `--model claude-sonnet-5 --effort low`
(user decision). CASCADE_CLAUDE_MODEL / CASCADE_CLAUDE_EFFORT override.

## Model-call transparency and per-run logs (2026-08-17)

Every live brain call (Claude CLI and Gemini) is captured as a ModelExchange
(provider, model, effort, agent, full prompt, raw response, duration). The
stage machine drains the buffer into the next TraceEvent's model_exchanges
field, so the UI execution trace shows the exact prompt and response behind
each event. Each run also appends every trace event to a JSONL debug log at
logs/runs/<run_id>.jsonl (gitignored; header line carries run mode and
controls) for post-hoc analysis of stuck or failed runs.

## Light minimalist UI theme (2026-08-17)

The dashboard switched from the dark control-room theme to a light
minimalist one (user decision): white panels, hairline borders, one teal
accent (#0e7490), darkened semantic status colors for contrast, monospace
kept only for figures, status codes, and micro-labels.

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
