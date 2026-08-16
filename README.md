# CASCADE

CASCADE is an AI-led, human-governed demonstration for recovering from cascading
port disruptions. This foundation uses synthetic data, mocked tools, and visible
agent events. It does not contact operational systems.

## Prerequisites

- Node.js 20 or later
- `uv`

## Setup

```powershell
uv sync
npm install
npm run generate:types
```

## Run

```powershell
npm run dev
```

Open `http://localhost:5173`. The API runs on `http://localhost:8000`.

## Validate

```powershell
npm run check
```

The foundation is credential-free. A later live Gemini path will read
`GEMINI_API_KEY` from a local `.env` file.

