# ⏳ KAIRO — The Right Moment

> **One Agent. Every Context. Always On Time.**

Kairo is a bilingual (English + Hindi) AI agent that builds a persistent mental model of you — your relationships, energy patterns, and communication style — and autonomously manages your digital life.

## Tech Stack

| Layer | Tech |
|-------|------|
| LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6-20250220`) |
| Agents | CrewAI (Observe → Reason → Act pipeline) |
| Integrations | Composio (Gmail, Calendar, Slack, Teams, GitHub) |
| Memory | Snowflake + SQLite (local) |
| Graph | NetworkX (relationship intelligence) |
| Payments | Skyfire (autonomous transactions) |
| Voice | LiveKit + Deepgram Nova-3 + Edge TTS |
| Backend | FastAPI → Railway |
| Frontend | Next.js → Vercel |

---

## Local Development (macOS)

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
npm install   # or pnpm install
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
# Install Railway CLI
brew install railwayapp/tap/railway
railway login
cd kairo
railway init
railway up
# Set env vars in Railway dashboard
```

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
# Set env vars in Vercel dashboard:
# NEXT_PUBLIC_API_URL = https://your-app.up.railway.app
```

---

## Project Structure

```
kairo/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI entry + WebSocket + CORS
│   │   └── routes/
│   │       ├── auth.py           # Register, login, profile
│   │       ├── agents.py         # CRUD, launch, stop, ghost mode
│   │       ├── dashboard.py      # Stats, decision log, weekly report
│   │       └── relationships.py  # NetworkX graph API
│   ├── agents/
│   │   └── crew.py               # CrewAI agent definitions
│   ├── services/
│   │   ├── auth.py               # JWT, password hashing
│   │   ├── relationship_graph.py # NetworkX graph engine
│   │   ├── edge_tts_service.py   # Free Microsoft neural voices
│   │   └── scheduler.py          # APScheduler cron jobs
│   ├── models/
│   │   └── database.py           # SQLAlchemy models
│   ├── voice/
│   │   └── kairo_voice_agent.py  # LiveKit voice agent
│   ├── webhooks/
│   │   └── handlers.py           # Composio webhook handlers
│   ├── scripts/
│   │   └── seed_demo.py          # Demo data seeder
│   ├── config.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx          # Landing / homepage
│   │   │   ├── auth/page.tsx     # Login + Register
│   │   │   └── dashboard/
│   │   │       ├── layout.tsx    # Sidebar layout
│   │   │       ├── page.tsx      # Dashboard home
│   │   │       ├── agents/       # Create & manage agent
│   │   │       ├── decisions/    # Decision log
│   │   │       ├── settings/     # All settings
│   │   │       └── report/       # Weekly report
│   │   ├── lib/
│   │   │   ├── api.ts            # Typed API client
│   │   │   └── store.ts          # Zustand auth store
│   │   └── styles/
│   │       └── globals.css       # Tailwind + custom styles
│   ├── package.json
│   └── tailwind.config.js
├── .env.example
├── .gitignore
└── railway.toml
```

---

## API Endpoints

### Auth
- `POST /api/auth/register` — Create account
- `POST /api/auth/login` — Sign in
- `GET /api/auth/me` — Current user
- `PUT /api/auth/me` — Update profile

### Agents
- `GET /api/agents/` — List agents
- `POST /api/agents/` — Create agent
- `GET /api/agents/{id}` — Get agent
- `PUT /api/agents/{id}` — Update config
- `POST /api/agents/{id}/launch` — Start agent
- `POST /api/agents/{id}/pause` — Pause agent
- `POST /api/agents/{id}/stop` — Stop agent
- `POST /api/agents/{id}/ghost-mode/toggle` — Toggle Ghost Mode
- `DELETE /api/agents/{id}` — Delete agent

### Dashboard
- `GET /api/dashboard/stats` — Weekly stats
- `GET /api/dashboard/decisions` — Decision log (paginated)
- `POST /api/dashboard/decisions/{id}/feedback` — Submit feedback
- `GET /api/dashboard/weekly-report` — Weekly report

### Relationships (NetworkX)
- `GET /api/relationships/graph` — Full graph (D3.js format)
- `GET /api/relationships/tone-shifts` — Tone shift alerts
- `GET /api/relationships/neglected` — Neglected contacts
- `GET /api/relationships/key-contacts` — Top contacts by centrality
- `GET /api/relationships/clusters` — Communication clusters

### Webhooks (Composio)
- `POST /webhooks/email`
- `POST /webhooks/slack`
- `POST /webhooks/teams`
- `POST /webhooks/calendar`

### WebSocket
- `WS /ws/{user_id}` — Real-time updates

---

## Demo Accounts

After running `python scripts/seed_demo.py`:

### Quick Start (for reviewers)

Log in with **demo@kairo.ai / demo1234** — this account has full activity across all features: dashboard stats, decision log with queued & executed actions, relationship graph with tone-shift alerts, agent mesh coordination, ghost mode, and a weekly report.

### All Accounts

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

*Kairo — The right action, at the right moment. ⏳*
