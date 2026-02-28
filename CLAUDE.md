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
npm run lint       # next lint (no custom ESLint config)
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

### Testing
No test suite is configured yet. Neither backend (pytest) nor frontend (jest/vitest) have test infrastructure.

## Architecture

Kairo is an AI personal agent that autonomously manages communications (email, Slack, Teams, calendar) using an **Observe → Reason → Act** pipeline powered by CrewAI + Claude Sonnet.

### Backend (`backend/`)

**Entry point:** `api/main.py` — FastAPI app with REST routes, WebSocket (`/ws/{user_id}`), and webhook receivers. The lifespan handler initializes the DB, starts APScheduler, recovers running agents, and launches the LiveKit voice agent in a background thread.

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

**Routes:** `api/routes/` — auth, agents, dashboard, relationships, mesh, tts, marketplace, commitments, delegation, burnout, replay, flow, nlp, plus webhooks.

**Database:** SQLAlchemy models in `models/database.py` — tables include `User`, `AgentConfig`, `AgentAction`, `ContactRelationship`, `UserPreference`, `MarketplaceListing`, `MarketplaceTransaction`, `Commitment`, `DelegationRequest`, `BurnoutSnapshot`, `DecisionReplay`, `FlowSession`. SQLite locally (`kairo.db`), PostgreSQL on Railway. Schema is auto-created via `Base.metadata.create_all()` on startup (no Alembic migrations configured despite the dependency being installed).

**Webhooks:** `webhooks/handlers.py` — Composio webhook handlers route incoming events to the agent runtime.

### Frontend (`frontend/`)

**Pages** (Next.js App Router in `src/app/`): Landing (`page.tsx`), Auth (`auth/`), Dashboard (`dashboard/` with sub-pages: agents, decisions, settings, report, mesh, relationships, burnout, commitments, delegation, flow, marketplace, replay, voice).

**Dashboard layout** (`src/app/dashboard/layout.tsx`): Fixed 240px sidebar with 4 nav groups (Overview, Autopilot, Insights, Network). Sidebar collapse state persists in localStorage key `kairo_sidebar_collapse`. Theme toggle and language selector (EN/HI/Auto) in the sidebar.

**State:** Zustand auth store in `src/lib/store.ts` (token in localStorage).

**API client:** Typed fetch wrapper in `src/lib/api.ts` with auto Bearer token injection.

**Theme:** Dark mode via `class` strategy in Tailwind. Custom theme hook in `src/lib/theme.tsx` — always check `mounted` state before rendering theme-dependent UI to avoid SSR mismatches. The Tailwind config defines a `kairo` purple color scale and custom font sizes.

**Styling:** Tailwind CSS with custom Kairo theme. Fonts: DM Serif Display (headings), Inter (body), JetBrains Mono (code). Primary accent color `#d78232` (orange) used in components; `kairo` purple scale defined in Tailwind config.

**Build output:** `next.config.js` sets `output: "standalone"` for containerized deployment, `devIndicators: false` to suppress the Next.js dev overlay badge.

**Hydration note:** Avoid non-deterministic values (e.g. `Math.random()`, `Date.now()`) and unrounded floats in SSR-rendered inline styles — they cause server/client hydration mismatches. Round computed pixel values with `Math.round()` when used in `style` props.

### Configuration

- `backend/config.py` — Pydantic Settings class loading from `.env` (cached via `@lru_cache`). Default model: `claude-sonnet-4-6-20250220`.
- `.env.example` — Template with all environment variables
- `frontend/next.config.js` — `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`
- CORS origins configured in backend settings, defaults to `http://localhost:3000`

### Ghost Mode

When enabled on an agent, the `ghost_mode_agent` autonomously handles communications: auto-replies when confidence ≥ threshold (default 85%), queues uncertain items for review, always escalates VIP contacts. All actions logged to `AgentAction` with reasoning traces.

### Deployment

- **Backend → Railway**: `Procfile` runs uvicorn, `railway.toml` configures healthcheck at `/health`
- **Frontend → Vercel**: Set `NEXT_PUBLIC_API_URL` to Railway backend URL
