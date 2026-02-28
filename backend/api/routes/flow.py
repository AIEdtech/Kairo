"""Flow State Guardian routes"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from services.auth import get_current_user_id
from services.flow_guardian import get_flow_guardian
from models.database import AgentConfig, get_engine, create_session_factory
from config import get_settings

router = APIRouter(prefix="/api/flow", tags=["flow"])
settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SignalRequest(BaseModel):
    signal_type: str
    metadata: dict = {}


@router.get("/status")
def flow_status(user_id: str = Depends(get_current_user_id)):
    guardian = get_flow_guardian()
    return guardian.get_status(user_id)


@router.post("/signal")
def report_signal(req: SignalRequest, user_id: str = Depends(get_current_user_id)):
    guardian = get_flow_guardian()
    return guardian.detect_flow_signals(user_id, req.signal_type, req.metadata) or {"status": "signal_recorded"}


@router.post("/activate")
def activate_flow(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    guardian = get_flow_guardian()
    agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
    agent_id = agent.id if agent else "unknown"
    return guardian.activate_protection(user_id, agent_id)


@router.post("/end")
def end_flow(user_id: str = Depends(get_current_user_id)):
    guardian = get_flow_guardian()
    return guardian.end_flow_session(user_id)


@router.get("/debrief/{session_id}")
def get_debrief(session_id: str, user_id: str = Depends(get_current_user_id)):
    guardian = get_flow_guardian()
    return guardian.generate_debrief(session_id)


@router.get("/history")
def flow_history(user_id: str = Depends(get_current_user_id)):
    guardian = get_flow_guardian()
    return guardian.get_flow_history(user_id)


@router.get("/stats")
def flow_stats(user_id: str = Depends(get_current_user_id)):
    guardian = get_flow_guardian()
    return guardian.get_flow_stats(user_id)
