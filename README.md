# KAIRO — The Right Moment

> **One Agent. Every Context. Always On Time.**

Kairo is a bilingual (English + Hindi) AI personal agent that builds a persistent mental model of you — your relationships, energy patterns, and communication style — and autonomously manages your digital life through an **Observe → Reason → Act** pipeline.

**Live demo**: Log in with `demo@kairo.ai` / `demo1234`

---

## Tech Stack

| Layer | Tech |
|-------|------|
| LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6-20250220`) |
| Agents | CrewAI — 8 agents in Observe → Reason → Act pipeline |
| Integrations | Composio (Gmail, Calendar, Slack, Teams, GitHub) |
| Memory | Snowflake (cloud) + SQLite (local fallback) |
| Graph | NetworkX (relationship intelligence per user) |
| Payments | Skyfire (autonomous transactions with spend limits) |
| Voice | LiveKit + Deepgram Nova-3 + Claude + Edge TTS |
| Backend | FastAPI + APScheduler → Railway |
| Frontend | Next.js 15 + React 19 + Tailwind → Vercel |

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
Multiple users' agents coordinate: schedule meetings across agents, hand off tasks, and share status. All three demo users are colleagues on the same project — their agents talk to each other.

### Agent Marketplace
Buy and sell agent capabilities. Sellers list skills with pricing, buyers purchase and review. Includes seller analytics dashboard with revenue, ratings, and customer metrics.

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
Per-action and per-day spend limits for autonomous transactions. The agent validates every spend before executing.

### Cloud Memory (Snowflake)
Optional cloud memory layer persists the user's mental model (communication style, priority weights, language patterns, learned rules) across sessions. Falls back to local SQLite when not configured.

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

All agents are created via factory functions that accept per-user Composio tools (OAuth-scoped), so each user's runtime is fully isolated.

### Runtime Isolation

```
RuntimeManager (singleton, one per server)
  ├── AgentRuntime[user_A]     ← isolated per-user instance
  │     ├── ComposioClient     (user_A's OAuth tokens)
  │     ├── RelationshipGraph  (user_A's NetworkX graph)
  │     ├── CrewAI Crew        (8 agents + user_A's tools)
  │     ├── SkyfireClient      (user_A's spend limits)
  │     └── UserScheduler      (user_A's briefing time/tz)
  │
  ├── AgentRuntime[user_B]     ← completely separate
  └── ...
```

On server restart, `recover_running_agents()` re-launches all agents with `status="running"`.

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
| GET | `/listings` | Browse capabilities |
| POST | `/listings` | Create listing |
| PUT | `/listings/{id}` | Update listing |
| POST | `/purchase` | Buy capability |
| POST | `/transactions/{id}/review` | Rate & review |
| GET | `/my-listings` | Seller dashboard |
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
# Set env vars in Railway dashboard
```

Demo data auto-seeds on startup when the DB is empty (handles ephemeral SQLite on Railway redeploys).

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
# Set NEXT_PUBLIC_API_URL = https://your-app.up.railway.app
```

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
│   │       ├── marketplace.py       # Listings, purchases, reviews, seller dashboard
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
│   │   ├── snowflake_client.py      # Cloud memory layer
│   │   ├── skyfire_client.py        # Autonomous payments
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
│   │   │       ├── marketplace/     # Agent marketplace
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

*Kairo — The right action, at the right moment.*
