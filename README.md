# CASCADE

CASCADE is a demonstration app that shows how AI agents can help a port
recover when a ship arrives late. You watch the AI do the analysis, and you
stay in charge: nothing happens without your approval.

Everything in CASCADE is pretend. The ships, containers, and costs are
made-up example data. The app never talks to real port systems, so nothing
you click can affect the real world.

## The story it tells

A big ship is 18 hours late. Some containers on that ship were supposed to
move onto other ships, like a traveler changing planes. Because the first
ship is late, some containers will miss their next ship.

Transshipment means a container arrives on one ship and leaves on another
ship. It is like changing buses. If the first bus is late, you can miss the
second bus.

A cascading disruption is one delay causing more delays. Containers that
miss their ship must wait in the storage yard. A crowded yard makes all the
other work slower, which causes even more delays.

CASCADE looks at the late ship and answers, in a few minutes:

- Which containers will miss their next ship?
- Which cargo needs help first? (Refrigerated medicine gets top priority. A
  reefer is a refrigerated container that needs electric power to stay cold.)
- Will the storage yard get too full?
- What are the three best recovery options, and what does each one cost?
- Which option does the AI recommend, and why?

Then it stops and asks you to approve before it pretends to carry out the
plan.

## Who does what

Five AI agents work together, and you can watch them on screen:

- The Coordinator reads the alert and hands out the work.
- The Impact agent finds containers that will miss their next ship.
- The Yard agent checks storage space and power plugs for reefers.
- The Recovery agent builds three recovery plans and compares them.
- The Execution agent prepares the pretend work orders after you approve.

Sometimes two agents disagree. For example, one wants to rush all the
refrigerated containers, but another warns there are not enough power plugs.
When that happens, CASCADE pauses and asks you to decide. Your decision
becomes a rule the plans must follow.

## Using the app

1. Ask a technical teammate to start the app (instructions below), then open
   `http://localhost:5173` in a web browser.
2. Press Start Run. You can first adjust the delay (6 to 24 hours), choose
   what to prioritize, and switch the practice "tool failure" on or off.
3. Watch the agents work in the center of the screen. The map on the left
   shows which container groups are safe, at risk, or missed.
4. When the dispute panel appears, read both sides and pick the rule you
   want the plans to follow.
5. Compare the three plan cards on the right, then approve or reject in the
   bar at the bottom. Approving produces pretend work orders and receipts.
6. Press Reset at any time to start the whole story over from the beginning.

The app also practices handling a broken tool: one lookup times out on
purpose, and CASCADE falls back to older saved data, clearly labeled, and
lowers its own confidence to MEDIUM. This shows the AI being honest when
its information is not fresh.

If the live AI service is unavailable, a presenter can switch to Replay
Mode, which plays back a recording of an earlier real run. The screen shows
a DEMO REPLAY label the whole time so nobody mistakes it for a live run.

## Starting the app (one-time technical setup)

These steps need a helper who is comfortable with a terminal. Install
Node.js 20 or later and the `uv` tool, then run:

```powershell
uv sync
npm install
npm run generate:types
npm run dev
```

Then open `http://localhost:5173`. The live AI mode needs a `GEMINI_API_KEY`
in a local `.env` file; without it the app still runs in offline demo modes.

## Good to know

- All data is synthetic (made up for the demo) and all costs are
  illustrative (rough example numbers, not real prices).
- The AI never acts on its own. Every plan waits for a human approval.
- The AI cannot change the calculated numbers. Fixed, predictable computer
  code does the math; the AI reads the results and explains the options.
