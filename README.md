# KAIRO — The Right Moment

> **AI That Cares Who You Care About.**

Kairo is a bilingual (English + Hindi) AI personal agent that builds a persistent mental model of you — your relationships, energy patterns, and communication style — and autonomously manages your digital life through an **Observe → Reason → Act** pipeline.

## Live Demo

| | URL |
|---|---|
| **Frontend** | [frontend-zeta-lyart-89.vercel.app](https://frontend-zeta-lyart-89.vercel.app) |
| **Backend API** | [kairo-production-6d1d.up.railway.app](https://kairo-production-6d1d.up.railway.app) |
| **API Docs** | [kairo-production-6d1d.up.railway.app/docs](https://kairo-production-6d1d.up.railway.app/docs) |
| **Health** | [kairo-production-6d1d.up.railway.app/health](https://kairo-production-6d1d.up.railway.app/health) |

**Login**: `demo@kairo.ai` / `demo1234`

---

## Tech Stack

| Layer | Tech | Details |
|-------|------|---------|
| **LLM** | Claude Sonnet 4.6 | `claude-sonnet-4-6-20250220` via Anthropic API |
| **Agent Orchestration** | CrewAI | 8 specialized agents in Observe → Reason → Act pipeline |
| **Integrations** | Composio | OAuth-managed: Gmail, Google Calendar, Slack, Teams, GitHub |
| **Cloud Memory** | Snowflake | Persistent mental model across sessions (falls back to SQLite) |
| **Relationship Graph** | NetworkX | Per-user directed graph: sentiment, tone, interaction patterns |
| **Payments** | Skyfire | Live USDC transactions via token-based flow (buyer → seller) |
| **Voice** | LiveKit + Deepgram Nova-3 + Edge TTS | Real-time STT/TTS with 3 AI personalities |
| **Backend** | FastAPI + APScheduler | Python 3.11+, SQLAlchemy ORM, WebSocket |
| **Frontend** | Next.js 15 + React 19 + Tailwind | App Router, Zustand state, D3.js visualizations |
| **Database** | SQLite (local) / PostgreSQL (Railway) | 12 tables, auto-created on startup |
| **Deployment** | Railway (backend) + Vercel (frontend) | Auto-deploy from GitHub main branch |

---

## Features

### Ghost Mode (Autonomous Autopilot)
When enabled, Kairo autonomously handles incoming communications. Auto-replies when confidence exceeds your threshold (default 85%), queues uncertain items for review, and always escalates VIP contacts. Every action is logged with a full reasoning trace.

### Relationship Intelligence
A per-user NetworkX directed graph tracks every contact: sentiment trends, tone shifts, preferred language, interaction frequency, response times. The D3.js frontend renders the graph with color-coded sentiment edges, importance-sized nodes, and one-click contact detail panels with VIP toggles and star ratings.

- **Tone shift detection** — alerts when a relationship is improving or declining
- **Neglected contacts** — surfaces VIPs you haven't contacted in 7+ days
- **Communication clusters** — groups contacts by type (work team, friends, family, clients)
- **Attention feed** — merged feed of overdue commitments + neglected VIPs + declining tone shifts

### Commitment Tracking
Automatically extracts commitments from emails and Slack messages (NLP parsing), tracks deadlines, and surfaces overdue items. Shows reliability score and sentiment correlation — how your follow-through affects each relationship.

### Burnout & Wellness
Calculates a burnout risk score from meeting load, evening/weekend work, communication volume, and relationship quality. Recommends interventions ("Reduce meetings to 3/day", "Protect evenings", "Enable Flow Guardian") and applies them to your agent config with one click. Predicts which relationships are going cold.

### Flow State Guardian
Detects and protects deep focus time. When activated, blocks interruptions and tracks session duration, tasks completed, and productivity score. Post-session debriefs analyze what you accomplished and when you're most focused.

### Energy-Aware Scheduling
Monitors calendar patterns and automatically declines non-VIP meetings during deep work hours. Enforces a daily meeting cap. Tracks energy patterns by day-of-week and hour to predict optimal work windows.

### Cross-Context Awareness
Bridges work and personal life. Detects when a dentist appointment conflicts with standup, adds travel time between locations, and generates wellness nudges when patterns suggest burnout.

### Decision Log & Learning Loop
Every agent action is logged with reasoning, confidence score, and draft content. Users approve, edit, or reject decisions — each piece of feedback trains the learning agent to update preference vectors (language per contact, message length, tone patterns, decline aggressiveness).

### Decision Replay (Counterfactual Reasoning)
"What if I had handled that email differently?" Generates alternative scenarios for past actions with reasoning about potential outcomes.

### Smart Delegation
Propose task delegation with AI-powered candidate matching. The system ranks potential delegates by skill match, tracks acceptance rates, and manages the full lifecycle (propose → accept → complete).

### Agent Mesh (Multi-Agent Coordination)
Multiple users' agents coordinate: schedule meetings across agents, hand off tasks, and share status. All three demo users are colleagues on the same project — their agents talk to each other. Includes audible agent-to-agent negotiation playback.

### Agent Marketplace (Skyfire-Powered)
Buy and sell agent capabilities with **live USDC transactions** via Skyfire. Sellers list skills with pricing, buyers purchase with real money. The marketplace header shows your live Skyfire wallet balance, which updates in real-time after each purchase. Includes seller analytics dashboard with revenue, ratings, and customer metrics.

### Bilingual Voice Interface
LiveKit-powered real-time voice with three selectable personalities:

| Personality | Style |
|---|---|
| **Atlas** | Direct, analytical, calm — data-driven leadership |
| **Nova** | Warm, proactive — celebrates wins, nudges on loose ends |
| **Sentinel** | Precise, strategic — flags patterns and risks |

Supports natural language commands in English and Hindi:
- "What did I miss?" / "Aaj ka schedule kya hai?"
- "Set up my agent with Gmail and protect my mornings"
- "Toggle ghost mode" / "Weekly summary"

### NLP Command Processing
Natural language commands from the dashboard: "set up my agent with Gmail and protect my mornings" parses into agent config (deep_work_start, VIP contacts, ghost mode threshold). Proactive nudges surface pending reviews, overdue commitments, and agent status.

### Weekly Report
AI-generated weekly analytics via CrewAI: time saved, ghost mode accuracy, relationship health trends, channel/language breakdowns, spending summary, and actionable recommendations.

### Autonomous Payments (Skyfire)
Live USDC payments using Skyfire's token-based flow:
1. **Buyer agent** creates a signed payment token (`POST /api/v1/tokens`)
2. **Seller agent** charges the token (`POST /api/v1/tokens/charge`)
3. Funds transfer instantly — visible on the Skyfire dashboard

Per-action and per-day spend limits enforced as guardrails. The marketplace displays a live wallet balance via `GET /api/v1/agents/balance`. Both buyer and seller keys are held server-side for the demo flow.

### Cloud Memory (Snowflake)
Persistent cloud memory layer stores the user's mental model — communication style, priority weights, language patterns, learned rules — in Snowflake tables. Survives server restarts and redeployments. Falls back to local SQLite when Snowflake is not configured. Connected via Snowflake Connector for Python with warehouse `DEFAULT_WH`.

---

## Architecture

### CrewAI Pipeline — 8 Agents

| Layer | Agent | Role |
|-------|-------|------|
| **Observe** | Relationship Observer | Tracks tone, sentiment, language patterns across all channels |
| **Observe** | Scheduling Observer | Monitors calendar, meeting load, energy patterns |
| **Reason** | Decision Engine | Weighs signals and outputs action + confidence + reasoning |
| **Reason** | Cross-Context Coordinator | Bridges work/personal, generates wellness nudges |
| **Act** | Voice & Style Matcher | Drafts replies matching user's per-contact communication style |
| **Act** | Ghost Mode Controller | Autonomous triage: auto-reply, queue, or escalate |
| **Learn** | Learning Agent | Processes feedback to update preference vectors |
| **Learn** | Report Agent | Compiles weekly analytics into actionable narratives |

All agents are created via factory functions that accept per-user Composio tools (OAuth-scoped), so each user's runtime is fully isolated. Crews are built for specific pipelines: triage, draft, ghost mode, and reporting.

### Runtime Isolation

```
RuntimeManager (singleton, one per server)
  ├── AgentRuntime[user_A]     ← isolated per-user instance
  │     ├── ComposioClient     (user_A's OAuth tokens)
  │     ├── RelationshipGraph  (user_A's NetworkX graph)
  │     ├── CrewAI Crew        (8 agents + user_A's tools)
  │     ├── SkyfireClient      (shared buyer/seller keys, per-user spend limits)
  │     └── UserScheduler      (user_A's briefing time/tz)
  │
  ├── AgentRuntime[user_B]     ← completely separate
  └── ...
```

On server restart, `recover_running_agents()` re-launches all agents with `status="running"`.

### Skyfire Payment Flow

```
Marketplace Purchase
  ├── Frontend: user clicks "Use Capability" → POST /api/marketplace/purchase
  ├── Backend: validates spend limits (per-action + daily)
  ├── Skyfire Step 1: POST /api/v1/tokens (buyer key → signed JWT)
  ├── Skyfire Step 2: POST /api/v1/tokens/charge (seller key → deducts funds)
  ├── Backend: logs transaction, returns result
  └── Frontend: updates wallet balance display
```

### Snowflake Schema

```
Snowflake (kairo.public)
  ├── User preferences     — communication style, priority weights
  ├── Learned rules        — per-contact language, tone, length patterns
  └── Mental model         — aggregated signals from all agent observations
```

Falls back to SQLite (`kairo.db`) with identical schema when `SNOWFLAKE_ACCOUNT` is not set.

---

## API Endpoints

### Auth (`/api/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Create account |
| POST | `/login` | Sign in (JWT) |
| GET | `/me` | Current user profile |
| PUT | `/me` | Update profile |
| POST | `/forgot-password` | Get reset code |
| POST | `/reset-password` | Reset via code |

### Agents (`/api/agents`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List agents |
| POST | `/` | Create agent (max 1 per user) |
| GET | `/{id}` | Get agent config |
| PUT | `/{id}` | Update config |
| POST | `/{id}/launch` | Start agent pipeline |
| POST | `/{id}/pause` | Pause agent |
| POST | `/{id}/stop` | Stop agent |
| POST | `/{id}/ghost-mode/toggle` | Toggle Ghost Mode |
| DELETE | `/{id}` | Delete agent |
| GET | `/{id}/integrations/status` | OAuth connection status |
| POST | `/{id}/integrations/connect/{app}` | Get OAuth URL |

### Dashboard (`/api/dashboard`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats` | Weekly stats overview |
| GET | `/decisions` | Decision log (paginated, filterable) |
| POST | `/decisions/{id}/feedback` | Approve/edit/reject action |
| GET | `/weekly-report` | Weekly analytics report |
| GET | `/cross-context-alerts` | Work/personal conflict alerts |

### Relationships (`/api/relationships`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/graph` | Full graph (D3.js format) |
| GET | `/tone-shifts` | Tone shift alerts |
| GET | `/neglected` | Neglected contacts |
| GET | `/key-contacts` | Top contacts by centrality |
| GET | `/clusters` | Communication clusters |
| PATCH | `/contacts/{id}` | Update importance/VIP |
| GET | `/contacts/{id}/detail` | Full contact profile |
| GET | `/attention` | Attention feed |

### Commitments (`/api/commitments`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List commitments (filterable) |
| GET | `/stats` | Reliability score |
| POST | `/{id}/fulfill` | Mark fulfilled |
| POST | `/{id}/cancel` | Cancel |
| POST | `/{id}/snooze` | Snooze N hours |
| GET | `/correlation/{contact}` | Sentiment correlation |

### Burnout (`/api/burnout`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/current` | Current risk score |
| GET | `/trend` | Trend over time |
| GET | `/interventions` | Recommended actions |
| POST | `/interventions/{id}/apply` | Apply intervention |
| GET | `/cold-contacts` | Declining relationships |
| GET | `/productivity` | Productivity multipliers |

### Flow (`/api/flow`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Current flow state |
| POST | `/signal` | Report flow signal |
| POST | `/activate` | Start flow protection |
| POST | `/end` | End session |
| GET | `/debrief/{id}` | Post-session analysis |
| GET | `/history` | Session history |
| GET | `/stats` | Flow statistics |

### Delegation (`/api/delegation`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/propose` | Propose delegation |
| GET | `/candidates` | Ranked candidates |
| GET | `/` | List requests |
| POST | `/{id}/accept` | Accept task |
| POST | `/{id}/reject` | Reject task |
| POST | `/{id}/complete` | Mark complete |
| GET | `/stats` | Delegation metrics |

### Decision Replay (`/api/replay`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List replays |
| GET | `/weekly` | Weekly replays |
| POST | `/generate/{action_id}` | Generate counterfactual |

### Marketplace (`/api/marketplace`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/balance` | Live Skyfire wallet balance |
| GET | `/listings` | Browse capabilities |
| GET | `/listings/{id}` | Listing detail |
| POST | `/listings` | Create listing |
| PUT | `/listings/{id}` | Update listing |
| POST | `/listings/{id}/pause` | Pause listing |
| POST | `/listings/{id}/activate` | Activate listing |
| POST | `/purchase` | Buy capability (live Skyfire payment) |
| POST | `/transactions/{id}/review` | Rate & review |
| GET | `/my-listings` | Seller's listings |
| GET | `/my-purchases` | Purchase history |
| GET | `/seller-dashboard` | Seller analytics |

### Mesh (`/api/mesh`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Mesh connectivity |
| GET | `/agents` | Connected agents |
| POST | `/meeting` | Request meeting |
| POST | `/handoff` | Hand off task |

### NLP (`/api/nlp`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/command` | Natural language command |
| GET | `/nudges` | Proactive nudges |

### Voice & TTS
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/voice/token` | LiveKit access token |
| GET | `/tts/speak` | Stream Edge TTS audio |

### WebSocket
- `WS /ws/{user_id}` — Real-time updates to frontend

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `ANTHROPIC_MODEL` | No | Model ID (default: `claude-sonnet-4-6-20250220`) |
| `SECRET_KEY` | Yes | App secret for sessions |
| `JWT_SECRET` | Yes | JWT signing key |
| `DATABASE_URL` | No | SQLite (default) or PostgreSQL connection string |
| `COMPOSIO_API_KEY` | No | Composio OAuth integrations (Gmail, Slack, etc.) |
| `SNOWFLAKE_ACCOUNT` | No | Snowflake account identifier |
| `SNOWFLAKE_USER` | No | Snowflake username |
| `SNOWFLAKE_PASSWORD` | No | Snowflake password |
| `SNOWFLAKE_DATABASE` | No | Snowflake database (default: `kairo`) |
| `SNOWFLAKE_WAREHOUSE` | No | Snowflake warehouse (default: `compute_wh`) |
| `SKYFIRE_BUYER_API_KEY` | No | Skyfire buyer agent API key |
| `SKYFIRE_SELLER_API_KEY` | No | Skyfire seller agent API key |
| `SKYFIRE_SELLER_SERVICE_ID` | No | Skyfire seller service ID |
| `LIVEKIT_API_KEY` | No | LiveKit API key (voice agent) |
| `LIVEKIT_API_SECRET` | No | LiveKit API secret |
| `LIVEKIT_URL` | No | LiveKit WebSocket URL |
| `DEEPGRAM_API_KEY` | No | Deepgram STT key (voice agent) |
| `OPENAI_API_KEY` | No | OpenAI TTS key (voice agent fallback) |
| `CORS_ORIGINS` | No | Allowed origins (default: `http://localhost:3000`) |

---

## Local Development

### Prerequisites

```bash
brew install python@3.11 node
```

### 1. Clone & Setup

```bash
git clone https://github.com/AIEdtech/Kairo.git
cd kairo
cp .env.example .env
# Edit .env with your API keys
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
```

### 4. Seed Demo Data (optional)

```bash
cd backend
source .venv/bin/activate
python scripts/seed_demo.py
# Creates 3 users:
#   Demo:   demo@kairo.ai   / demo1234 (Product Manager — best for reviewers)
#   Gaurav: gaurav@kairo.ai / demo1234 (Backend Lead, EN+HI, voice: male)
#   Phani:  phani@kairo.ai  / demo1234 (Frontend Lead, EN, voice: female)
```

### 5. Run

```bash
# Terminal 1 — Backend
cd backend && source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev   # → http://localhost:3000

# Terminal 3 — Voice Agent (optional)
cd backend && source .venv/bin/activate
python -m voice.kairo_voice_agent
```

### 6. Open

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

## Deploy to Production

### Backend → Railway

```bash
brew install railwayapp/tap/railway
railway login
cd kairo
railway init
railway up
# Set env vars in Railway dashboard or via CLI:
# railway variables set ANTHROPIC_API_KEY=sk-ant-... SKYFIRE_BUYER_API_KEY=... etc.
```

Demo data auto-seeds on startup when the DB is empty (handles ephemeral SQLite on Railway redeploys).

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
# Set NEXT_PUBLIC_API_URL = https://kairo-production-6d1d.up.railway.app
```

### Production URLs

| Service | URL |
|---------|-----|
| Frontend | https://frontend-zeta-lyart-89.vercel.app |
| Backend API | https://kairo-production-6d1d.up.railway.app |
| API Docs (Swagger) | https://kairo-production-6d1d.up.railway.app/docs |
| Health Check | https://kairo-production-6d1d.up.railway.app/health |

---

## Project Structure

```
kairo/
├── backend/
│   ├── api/
│   │   ├── main.py                  # FastAPI entry + WebSocket + lifespan
│   │   └── routes/
│   │       ├── auth.py              # Register, login, profile, password reset
│   │       ├── agents.py            # CRUD, launch, stop, ghost mode, integrations
│   │       ├── dashboard.py         # Stats, decision log, weekly report, cross-context
│   │       ├── relationships.py     # NetworkX graph, tone shifts, attention feed
│   │       ├── commitments.py       # Commitment tracking, reliability, correlation
│   │       ├── burnout.py           # Risk score, trend, interventions, productivity
│   │       ├── flow.py              # Flow state guardian, debrief, stats
│   │       ├── delegation.py        # Smart delegation, candidates, lifecycle
│   │       ├── replay.py            # Decision replay, counterfactual reasoning
│   │       ├── marketplace.py       # Listings, purchases, reviews, Skyfire balance
│   │       ├── mesh.py              # Multi-agent coordination, meetings, handoffs
│   │       ├── nlp.py               # Natural language commands, proactive nudges
│   │       └── tts.py               # Edge TTS streaming
│   ├── agents/
│   │   └── crew.py                  # 8 CrewAI agent factories + crew builders
│   ├── services/
│   │   ├── agent_runtime.py         # Per-user runtime isolation + RuntimeManager
│   │   ├── auth.py                  # JWT + bcrypt
│   │   ├── relationship_graph.py    # NetworkX graph engine
│   │   ├── composio_tools.py        # OAuth integrations (Gmail, Slack, etc.)
│   │   ├── burnout_predictor.py     # Risk scoring + interventions
│   │   ├── commitment_tracker.py    # NLP commitment extraction + tracking
│   │   ├── flow_guardian.py         # Deep focus protection
│   │   ├── smart_delegation.py      # Skill-matched task delegation
│   │   ├── decision_replay.py       # Counterfactual reasoning engine
│   │   ├── marketplace.py           # Buy/sell agent capabilities
│   │   ├── mesh_coordinator.py      # Multi-agent coordination
│   │   ├── scheduler.py             # APScheduler (graph sync, weekly reports)
│   │   ├── snowflake_client.py      # Snowflake cloud memory layer
│   │   ├── skyfire_client.py        # Live Skyfire token-based payments
│   │   └── edge_tts_service.py      # Microsoft neural voices
│   ├── models/
│   │   └── database.py              # SQLAlchemy models (12 tables)
│   ├── voice/
│   │   ├── kairo_voice_agent.py     # LiveKit voice agent (3 personalities)
│   │   └── command_dispatch.py      # NLP command parsing + dispatch
│   ├── webhooks/
│   │   └── handlers.py              # Composio webhook routing
│   ├── scripts/
│   │   └── seed_demo.py             # Demo data seeder (3 users)
│   ├── config.py                    # Pydantic Settings
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx             # Landing page
│   │   │   ├── auth/page.tsx        # Login + Register
│   │   │   └── dashboard/
│   │   │       ├── layout.tsx       # Sidebar (4 nav groups, theme toggle, i18n)
│   │   │       ├── page.tsx         # Dashboard home (stats, heatmap, feed)
│   │   │       ├── agents/          # Agent config + integrations
│   │   │       ├── decisions/       # Decision log + feedback
│   │   │       ├── settings/        # Profile + preferences
│   │   │       ├── report/          # Weekly analytics
│   │   │       ├── relationships/   # D3.js graph + contact detail
│   │   │       ├── commitments/     # Commitment tracking
│   │   │       ├── burnout/         # Burnout risk + interventions
│   │   │       ├── flow/            # Flow state guardian
│   │   │       ├── delegation/      # Smart delegation
│   │   │       ├── replay/          # Decision replay
│   │   │       ├── marketplace/     # Agent marketplace + Skyfire wallet
│   │   │       ├── mesh/            # Multi-agent network
│   │   │       └── voice/           # Voice interface
│   │   ├── lib/
│   │   │   ├── api.ts              # Typed API client
│   │   │   ├── store.ts            # Zustand auth store
│   │   │   └── theme.tsx           # Dark mode hook
│   │   └── styles/
│   │       └── globals.css          # Tailwind + Kairo theme
│   ├── package.json
│   └── tailwind.config.js
├── .env.example
├── railway.toml
└── CLAUDE.md
```

---

## Demo Accounts

After running `python scripts/seed_demo.py` (or auto-seeded on Railway):

**Quick start**: Log in with **demo@kairo.ai / demo1234** — full activity across all features.

| | Demo User | Gaurav Gupta | Phani Kulkarni |
|---|---|---|---|
| **Role** | Product Manager | Backend Lead | Frontend Lead |
| **Email** | demo@kairo.ai | gaurav@kairo.ai | phani@kairo.ai |
| **Password** | demo1234 | demo1234 | demo1234 |
| **Language** | English | Auto (EN + HI) | English |
| **Voice** | Female (Aria) | Male (Madhur / Guy) | Female (Aria) |
| **Deep Work** | 2:00–4:00 PM ET | 9:00–11:00 AM IST | 10:00 AM–12:00 PM IST |
| **Ghost Mode** | ON (80% threshold) | ON (85% threshold) | ON (80% threshold) |

All 3 are colleagues on the same project. Their agents coordinate via the Agent Mesh.

---

## Integrations

### Composio (OAuth)
Gmail, Google Calendar, Slack, Microsoft Teams, GitHub — all connected via Composio's OAuth flow. Each user's tokens are isolated in their `AgentRuntime`.

### Snowflake (Cloud Memory)
Persists the user mental model in Snowflake tables. Connected via `snowflake-connector-python`. The client auto-creates the database/schema/warehouse on first connection. Set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and `SNOWFLAKE_PASSWORD` to enable.

### Skyfire (Payments)
Live USDC micropayments for agent marketplace transactions. Uses Skyfire's KYAPay token protocol:
- Buyer creates a signed JWT payment token scoped to a seller service
- Seller charges the token for the purchase amount
- Settlement is instant on the Skyfire network
- Wallet balance displayed in real-time on the marketplace page

Set `SKYFIRE_BUYER_API_KEY`, `SKYFIRE_SELLER_API_KEY`, and `SKYFIRE_SELLER_SERVICE_ID` to enable live payments. Without these, transactions are simulated.

### LiveKit (Voice)
Real-time voice agent with Deepgram Nova-3 for STT, Claude for reasoning, and Edge TTS for synthesis. Three personality modes (Atlas, Nova, Sentinel). Requires `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL`, and `DEEPGRAM_API_KEY`.

---

*Kairo — The right action, at the right moment.*
