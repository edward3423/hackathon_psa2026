# CASCADE

CASCADE is a control room for port disruptions. When something goes wrong,
such as a ship arriving late, a team of AI agents measures the damage,
builds recovery plans, and explains the trade-offs. You watch the AI work,
and you stay in charge: nothing is carried out without your approval.

The current build is a demonstration platform. It runs on synthetic
(made-up) example data and mocked (pretend) actions, so nothing you click
can affect the real world.

## The problem it solves

Ports run on tight schedules. Many containers arrive on one ship and leave
on another, like a traveler changing planes. If the first ship is late,
containers can miss their next ship.

Transshipment means a container arrives on one ship and leaves on another
ship. It is like changing buses. If the first bus is late, you can miss the
second bus.

A cascading disruption is one delay causing more delays. Containers that
miss their ship must wait in the storage yard. A crowded yard makes all the
other work slower, which causes even more delays.

When a disruption hits, a human controller has minutes to answer hard
questions. CASCADE answers them quickly and clearly:

- Which containers will miss their next ship?
- Which cargo needs help first? Refrigerated medicine usually comes top. A
  reefer is a refrigerated container that needs electric power to stay cold.
- Will the storage yard get too full, and when?
- What are the best recovery options, and what does each one cost?
- Which option is recommended, and why?

Then it stops and asks a human to approve before anything is carried out.

## Who does what

Five AI agents work together, and you can watch them on screen:

- The Coordinator reads the alert, sets the objective, and hands out work.
- The Impact agent finds containers in danger of missing their connection.
- The Yard agent checks storage space and power plugs for reefers.
- The Recovery agent builds competing recovery plans and compares them.
- The Execution agent prepares the work orders after you approve.

The AI never does the math. Fixed, predictable calculation tools produce
every number; the agents read those results, argue about what they mean,
and propose options. Agents cannot change calculated values, invent data,
or skip your approval.

Sometimes two agents disagree. For example, one wants to rush all the
refrigerated containers, but another warns there are not enough power
plugs. When that happens, CASCADE pauses and asks you to decide. Your
decision becomes a rule the plans must follow.

CASCADE is also honest about bad information. If a data source fails or
times out, it says so on screen, falls back to older saved data with a
clear label, lowers its stated confidence, and refuses to act on unverified
assumptions.

## Using the app

1. Ask a technical teammate to start the app (instructions below), then
   open `http://localhost:5620` in a web browser.
2. Review the incoming disruption alert, adjust the scenario controls if
   you want, and press Start Run.
3. Watch the agents work in the center of the screen. The map on the left
   shows which container groups are safe, at risk, or missed.
4. If a dispute panel appears, read both sides and pick the rule you want
   the plans to follow.
5. Compare the plan cards on the right, then approve or reject in the bar
   at the bottom. Approving produces work orders and receipts.
6. Press Reset at any time to return to a clean starting state.

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

Then open `http://localhost:5620`. Optional live services are configured in a
local `.env` file:

```dotenv
GEMINI_API_KEY=
AISSTREAM_API_KEY=
VITE_MAPBOX_ACCESS_TOKEN=
```

`AISSTREAM_API_KEY` supplies real AIS (Automatic Identification System) ship
positions through the backend. `VITE_MAPBOX_ACCESS_TOKEN` supplies the Mapbox
basemap and should be a public token restricted to the deployed site URL. The
route simulation and local world map still work when these keys are absent.

## Good to know

- All data in this build is synthetic (made up) and all costs are
  illustrative (rough example numbers, not real prices).
- The AI never acts on its own. Every plan waits for a human approval.
- Nothing connects to real port, terminal, or carrier systems.
