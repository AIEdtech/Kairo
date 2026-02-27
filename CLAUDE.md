# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (FastAPI + Python 3.11+)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```
API docs at `http://localhost:8000/docs`.

### Frontend (Next.js 15 + React 19)
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
```

### Demo Data
```bash
cd backend && python scripts/seed_demo.py
# Creates users: demo@kairo.ai / demo1234, gaurav@kairo.ai / demo1234, phani@kairo.ai / demo1234
```

### Voice Agent (optional)
```bash
cd backend && python -m voice.kairo_voice_agent
```

## Architecture

Kairo is an AI personal agent that autonomously manages communications (email, Slack, Teams, calendar) using an **Observe → Reason → Act** pipeline powered by CrewAI + Claude Sonnet.

### Backend (`backend/`)

**Entry point:** `api/main.py` — FastAPI app with REST routes, WebSocket (`/ws/{user_id}`), and webhook receivers.

**Agent pipeline** (`agents/crew.py`): 8 CrewAI agents form the pipeline:
- **Observers**: `relationship_observer` (tone/sentiment tracking), `scheduling_observer` (calendar/energy patterns)
- **Reasoning**: `reasoning_agent` (decision engine), `cross_context_agent` (work/personal bridging)
- **Execution**: `voice_matcher_agent` (style-matched replies), `ghost_mode_agent` (autonomous autopilot)
- **Learning**: `learning_agent` (feedback → preference updates), `report_agent` (weekly analytics)

**Runtime isolation** (`services/agent_runtime.py`): `RuntimeManager` (singleton) manages per-user `AgentRuntime` instances. Each runtime is fully isolated with its own Composio OAuth tokens, NetworkX graph, CrewAI crew, and scheduled jobs. On server restart, `recover_running_agents()` re-launches agents with `status="running"`.

**Key services:**
- `services/relationship_graph.py` — NetworkX directed graph per user tracking contacts, tone, sentiment, interaction patterns
- `services/composio_tools.py` — OAuth-managed integrations (Gmail, Calendar, Slack, Teams, GitHub)
- `services/mesh_coordinator.py` — Multi-agent coordination between users' agents (scheduling, task handoff)
- `services/skyfire_client.py` — Autonomous payments with per-action/per-day spend limits
- `services/snowflake_client.py` — Optional cloud memory layer (falls back to SQLite)
- `services/scheduler.py` — APScheduler for per-user briefings and system-wide jobs
- `services/auth.py` — JWT authentication + bcrypt password hashing

**Routes:** `api/routes/` — `auth.py`, `agents.py`, `dashboard.py`, `relationships.py`, `mesh.py`

**Database:** SQLAlchemy models in `models/database.py` — 5 tables: `User`, `AgentConfig`, `AgentAction`, `ContactRelationship`, `UserPreference`. SQLite locally, PostgreSQL on Railway.

**Webhooks:** `webhooks/handlers.py` — Composio webhook handlers route incoming events to the agent runtime.

### Frontend (`frontend/`)

**Pages** (Next.js App Router in `src/app/`): Landing (`page.tsx`), Auth (`auth/`), Dashboard (`dashboard/` with sub-pages: agents, decisions, settings, report, mesh).

**State:** Zustand auth store in `src/lib/store.ts` (token in localStorage).

**API client:** Typed fetch wrapper in `src/lib/api.ts` with auto Bearer token injection.

**Styling:** Tailwind CSS with custom Kairo theme — primary color `#d78232` (orange), dark mode. Fonts: DM Serif Display (headings), DM Sans (body).

**Dev config:** `next.config.js` has `devIndicators: false` to suppress the Next.js dev error overlay badge.

**Hydration note:** Avoid non-deterministic values (e.g. `Math.random()`, `Date.now()`) and unrounded floats in SSR-rendered inline styles — they cause server/client hydration mismatches. Round computed pixel values with `Math.round()` when used in `style` props.

### Configuration

- `backend/config.py` — Pydantic Settings class loading from `.env` (cached via `@lru_cache`)
- `.env.example` — Template with all environment variables
- `frontend/next.config.js` — `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`

### Ghost Mode

When enabled on an agent, the `ghost_mode_agent` autonomously handles communications: auto-replies when confidence ≥ threshold (default 85%), queues uncertain items for review, always escalates VIP contacts. All actions logged to `AgentAction` with reasoning traces.

### Deployment

- **Backend → Railway**: `Procfile` runs uvicorn, `railway.toml` configures healthcheck at `/health`
- **Frontend → Vercel**: Set `NEXT_PUBLIC_API_URL` to Railway backend URL
