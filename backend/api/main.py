"""
Kairo API — FastAPI entry point
Includes: auth, agents, dashboard, relationships, webhooks, scheduler, WebSocket
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import json

from config import get_settings
from models.database import init_db

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kairo")


# ── WebSocket Manager (real-time updates to frontend) ──

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, user_id: str):
        await ws.accept()
        if user_id not in self.active:
            self.active[user_id] = []
        self.active[user_id].append(ws)

    def disconnect(self, ws: WebSocket, user_id: str):
        if user_id in self.active:
            self.active[user_id] = [w for w in self.active[user_id] if w != ws]

    async def send_to_user(self, user_id: str, data: dict):
        if user_id in self.active:
            for ws in self.active[user_id]:
                try:
                    await ws.send_json(data)
                except Exception:
                    pass

ws_manager = ConnectionManager()


# ── App Lifecycle ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(settings.database_url)
    logger.info(f"✦ Kairo API started — {settings.app_env} mode")
    logger.info(f"✦ LLM: {settings.anthropic_model}")
    logger.info(f"✦ CORS: {settings.cors_origins}")

    try:
        from services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")

    # Connect to Snowflake (cloud memory layer)
    try:
        from services.snowflake_client import get_snowflake_client
        sf = get_snowflake_client()
        if sf._is_snowflake:
            logger.info(f"✦ Snowflake connected: {settings.snowflake_account}")
        else:
            logger.info("✦ Snowflake not configured — using local DB only")
    except Exception as e:
        logger.warning(f"Snowflake init failed: {e}")

    # Recover agents that were running before server restart
    try:
        from services.agent_runtime import get_runtime_manager
        runtime_mgr = get_runtime_manager()
        await runtime_mgr.recover_running_agents()
        logger.info(f"✦ Recovered {runtime_mgr.active_count} running agent(s)")
    except Exception as e:
        logger.warning(f"Agent recovery failed: {e}")

    # Start LiveKit voice agent in background thread
    voice_thread = None
    try:
        import threading
        # Register ALL LiveKit plugins on main thread BEFORE spawning voice agent thread
        # Plugin.register_plugin() requires the main thread — importing triggers registration
        from livekit.plugins import silero
        from livekit.plugins import anthropic as lk_anthropic  # noqa: F811
        from livekit.plugins import deepgram as lk_deepgram  # noqa: F811
        from livekit.plugins import openai as lk_openai  # noqa: F811
        import voice.kairo_voice_agent as voice_mod
        voice_mod._cached_vad = silero.VAD.load()
        voice_mod._lk_anthropic = lk_anthropic
        voice_mod._lk_deepgram = lk_deepgram
        voice_mod._lk_openai = lk_openai
        voice_thread = threading.Thread(target=lambda: voice_mod.run_voice_agent(skip_plugin_load=True), daemon=True, name="voice-agent")
        voice_thread.start()
        logger.info("✦ Voice agent started in background thread")
    except Exception as e:
        logger.warning(f"Voice agent not started: {e}")

    yield
    logger.info("✦ Kairo API shutting down")


app = FastAPI(
    title="Kairo API",
    description="The Right Moment — Cognitive Co-Processor",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──
from api.routes.auth import router as auth_router
from api.routes.agents import router as agents_router
from api.routes.dashboard import router as dashboard_router
from api.routes.relationships import router as relationships_router
from webhooks.handlers import router as webhooks_router
from api.routes.mesh import router as mesh_router
from api.routes.tts import router as tts_router
from api.routes.marketplace import router as marketplace_router
from api.routes.commitments import router as commitments_router
from api.routes.delegation import router as delegation_router
from api.routes.burnout import router as burnout_router
from api.routes.replay import router as replay_router
from api.routes.flow import router as flow_router
from api.routes.nlp import router as nlp_router

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(dashboard_router)
app.include_router(relationships_router)
app.include_router(mesh_router)
app.include_router(webhooks_router)
app.include_router(tts_router)
app.include_router(marketplace_router)
app.include_router(commitments_router)
app.include_router(delegation_router)
app.include_router(burnout_router)
app.include_router(replay_router)
app.include_router(flow_router)
app.include_router(nlp_router)


# ── Seed (one-time, for deployment) ──

@app.post("/seed")
async def seed_demo_data(force: bool = False):
    """Seed demo data — safe to call multiple times (skips if data exists). Use ?force=true to reseed."""
    if force:
        from models.database import (
            User, AgentConfig, AgentAction, UserPreference, ContactRelationship,
            MarketplaceTransaction, MarketplaceListing,
            Commitment, DelegationRequest, BurnoutSnapshot, DecisionReplay, FlowSession,
            get_engine, create_session_factory,
        )
        from config import get_settings
        s = get_settings()
        eng = get_engine(s.database_url)
        Sess = create_session_factory(eng)
        db = Sess()
        db.query(FlowSession).delete()
        db.query(DecisionReplay).delete()
        db.query(BurnoutSnapshot).delete()
        db.query(DelegationRequest).delete()
        db.query(Commitment).delete()
        db.query(MarketplaceTransaction).delete()
        db.query(MarketplaceListing).delete()
        db.query(AgentAction).delete()
        db.query(ContactRelationship).delete()
        db.query(UserPreference).delete()
        db.query(AgentConfig).delete()
        db.query(User).delete()
        db.commit()
        db.close()
    from scripts.seed_demo import seed
    seed()
    return {"status": "ok", "message": "Demo data seeded" + (" (forced)" if force else "")}


# ── WebSocket ──

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            await websocket.send_json({"type": "ack", "received": msg})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)


# ── Root ──

@app.get("/")
def root():
    return {
        "name": "Kairo API",
        "tagline": "The right action, at the right moment.",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "model": settings.anthropic_model}
