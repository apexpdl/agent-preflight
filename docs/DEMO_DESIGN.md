# Demo Application Design

## Overview

The Preflight demo is an interactive web application that lets users simulate agent actions and observe the governance pipeline in real time. It communicates the value proposition in under 2 minutes.

---

## Architecture

```
Browser (React + Vite)         Backend (FastAPI)          Preflight Core
        |                            |                         |
        |  POST /api/simulate        |                         |
        |--------------------------->|                         |
        |                            |  ActionEnvelope          |
        |                            |------------------------>|
        |                            |                         |  Risk Engine
        |                            |                         |  Simulation
        |                            |                         |  Drift
        |                            |                         |  Policy
        |                            |                         |  Mirror
        |                            |                         |  Passport
        |                            |  PipelineResult          |
        |                            |<------------------------|
        |  SimulateResponse          |                         |
        |<---------------------------|                         |
        |                            |                         |
        |  Render verdict, risk      |                         |
        |  gauge, passport viewer    |                         |
```

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 19 + TypeScript | UI framework |
| Build | Vite 6 | Dev server and bundler |
| Styling | Tailwind CSS 4 | Utility-first styling |
| HTTP | Axios | API client |
| Backend | FastAPI + Uvicorn | API server |
| Core | agent-preflight | Governance pipeline |

## Folder Structure

```
demo/
  backend/
    __init__.py
    app.py              FastAPI application with /simulate endpoint
    config.py            Environment-based configuration
  frontend/
    index.html           Entry point
    package.json         Dependencies
    tsconfig.json        TypeScript configuration
    vite.config.ts       Vite build configuration
    src/
      main.tsx           React entry point
      App.tsx            Root component
      app.css            Tailwind + custom styles
      types.ts           TypeScript type definitions
      components/
        ActionForm.tsx   Action input form with scenario presets
      hooks/
        useSimulate.ts   API hook for simulation requests
      utils/
        api.ts           Axios instance configuration
```

## UI Layout

```
+----------------------------------------------------------+
|  [P] Preflight                        Agent Governance    |
+----------------------------------------------------------+
|                                                          |
|  +------------------------+  +------------------------+  |
|  |  SIMULATE AGENT ACTION |  |  RESULT                |  |
|  |                        |  |                        |  |
|  |  Quick Scenarios       |  |  [BLOCK]  Risk: 94%   |  |
|  |  [Delete Prod DB]      |  |                        |  |
|  |  [Send Bulk Email]     |  |  ==================    |  |
|  |  [Read Config]         |  |  Risk Score Bar        |  |
|  |  [Transfer $50K]       |  |                        |  |
|  |  [Execute Shell]       |  |  Risk Factors          |  |
|  |                        |  |  [irreversible]        |  |
|  |  Actor: ____________   |  |  [destructive_tool]    |  |
|  |  Action: [dropdown]    |  |  [sensitive_path]      |  |
|  |  Resource: _________   |  |                        |  |
|  |  Payload: __________   |  |  Passport              |  |
|  |  Context: __________   |  |  { ... JSON ... }      |  |
|  |                        |  |                        |  |
|  |  [     SIMULATE     ]  |  |  Pipeline: 4.2ms      |  |
|  +------------------------+  +------------------------+  |
|                                                          |
|  +----------------------------------------------------+  |
|  |  RECENT ACTIVITY                                    |  |
|  |  [green] config-reader  read      ALLOW            |  |
|  |  [red]   deploy-agent   delete    BLOCK            |  |
|  |  [yellow] marketing-bot api_call  WARN             |  |
|  +----------------------------------------------------+  |
|                                                          |
+----------------------------------------------------------+
```

## Key UI Components

### Risk Gauge

A horizontal bar showing the risk score from 0 to 100%. Color transitions:
- 0-30%: Green (Allow)
- 30-60%: Yellow (Warn)
- 60-100%: Red (Block)

### Decision Badge

A pill-shaped badge showing the verdict:
- `ALLOW` -- green background, white text
- `WARN` -- yellow background, dark text
- `BLOCK` -- red background, white text

### Passport Viewer

Collapsible JSON viewer showing the full Action Passport with syntax highlighting. Displays passport_id, signatures, chain hashes, and all risk components.

### History Feed

Reverse-chronological feed of recent simulations with colored status indicators, actor names, action types, and verdicts.

---

## Pre-Built Scenarios

| Scenario | Actor | Action | Risk Level | Expected Verdict |
|---|---|---|---|---|
| Delete Production DB | deploy-agent-7 | delete | Critical | BLOCK |
| Send Bulk Email | marketing-bot | api_call | High | BLOCK |
| Read Config | config-reader | read | Low | ALLOW |
| Transfer $50,000 | finance-agent | execute | Critical | BLOCK |
| Execute Shell Command | ops-agent | shell | Critical | BLOCK |

## Running the Demo

### Development

```bash
# Terminal 1: Backend
cd demo/backend
pip install -e "../../[server]"
uvicorn app:app --reload --port 8100

# Terminal 2: Frontend
cd demo/frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### Production

```bash
# Build frontend
cd demo/frontend && npm run build

# Serve with backend (static files + API)
cd demo/backend
DEMO_MODE=true uvicorn app:app --host 0.0.0.0 --port 8100
```

---

## 2-Minute Demo Script

1. **Open the demo** (5s). "This is Preflight -- the execution governance layer for AI agents."

2. **Click 'Read Config' scenario** (10s). "A config-reader agent wants to read a YAML file. Low risk. Preflight allows it instantly and issues a signed passport."

3. **Click 'Delete Production DB' scenario** (15s). "Now a deploy agent wants to delete all records from the production database. Preflight scores this at 94% risk -- irreversible, destructive, production target -- and blocks it with a correction: use a WHERE clause, try staging first."

4. **Click 'Transfer $50,000' scenario** (15s). "A finance agent wants to wire $50K to an external account. The daily limit is already exceeded. Preflight blocks and explains why."

5. **Show the passport** (20s). "Every decision produces a cryptographically signed Action Passport. Chain-hashed, tamper-proof, designed for regulatory audit."

6. **Show the history** (10s). "Every action is logged. Green for allowed, red for blocked, yellow for warned. Full audit trail."

7. **Close** (5s). "One line of code. Every agent action is governed."

Total: ~80 seconds.
