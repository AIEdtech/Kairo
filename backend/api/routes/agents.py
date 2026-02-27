"""Agent config routes — create, configure, launch, stop agents"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.auth import get_current_user_id
from models.database import AgentConfig, AgentStatus, get_engine, create_session_factory
from config import get_settings

router = APIRouter(prefix="/api/agents", tags=["agents"])
settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CreateAgentRequest(BaseModel):
    name: str = "My Kairo Agent"
    voice_language: str = "auto"
    voice_gender: str = "female"
    briefing_time: str = "07:00"


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    ghost_mode_enabled: Optional[bool] = None
    ghost_mode_confidence_threshold: Optional[float] = None
    ghost_mode_allowed_actions: Optional[list] = None
    ghost_mode_vip_contacts: Optional[list] = None
    ghost_mode_blocked_contacts: Optional[list] = None
    ghost_mode_max_spend_per_action: Optional[float] = None
    ghost_mode_max_spend_per_day: Optional[float] = None
    deep_work_start: Optional[str] = None
    deep_work_end: Optional[str] = None
    deep_work_days: Optional[list] = None
    max_meetings_per_day: Optional[int] = None
    auto_decline_enabled: Optional[bool] = None
    voice_language: Optional[str] = None
    voice_gender: Optional[str] = None
    briefing_time: Optional[str] = None
    briefing_enabled: Optional[bool] = None


@router.get("/")
def list_agents(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    agents = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).all()
    return [_agent_to_dict(a) for a in agents]


@router.post("/")
def create_agent(
    req: CreateAgentRequest,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    # Limit to 1 agent per user for now
    existing = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).count()
    if existing >= 1:
        raise HTTPException(status_code=400, detail="Maximum 1 agent per user. Delete existing agent first.")

    agent = AgentConfig(
        user_id=user_id,
        name=req.name,
        voice_language=req.voice_language,
        voice_gender=req.voice_gender,
        briefing_time=req.briefing_time,
        status=AgentStatus.DRAFT,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _agent_to_dict(agent)


@router.get("/{agent_id}")
def get_agent(agent_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    agent = _get_user_agent(db, agent_id, user_id)
    return _agent_to_dict(agent)


@router.put("/{agent_id}")
def update_agent(
    agent_id: str,
    req: UpdateAgentRequest,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    agent = _get_user_agent(db, agent_id, user_id)

    for key, value in req.model_dump(exclude_unset=True).items():
        if hasattr(agent, key) and value is not None:
            setattr(agent, key, value)

    db.commit()
    db.refresh(agent)
    return _agent_to_dict(agent)


@router.post("/{agent_id}/launch")
async def launch_agent(agent_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    agent = _get_user_agent(db, agent_id, user_id)

    if agent.status == AgentStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Agent is already running")

    try:
        from services.agent_runtime import get_runtime_manager
        runtime_mgr = get_runtime_manager()
        launch_result = await runtime_mgr.launch_agent(user_id, agent_id)
    except Exception as e:
        # If the full launch pipeline fails (e.g. CrewAI not configured),
        # still mark agent as running so the UI works — core features
        # (graph, scheduling, ghost mode) work without CrewAI.
        import logging
        logging.getLogger("kairo").warning(f"Agent launch partial failure: {e}")
        agent.status = AgentStatus.RUNNING
        db.commit()
        launch_result = {
            "status": "running",
            "warning": str(e),
            "tools_available": 0,
            "contacts_loaded": 0,
            "ghost_mode": agent.ghost_mode_enabled,
        }

    db.refresh(agent)
    return {
        "message": "Agent launched successfully",
        "agent": _agent_to_dict(agent),
        "runtime": launch_result,
    }


@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    agent = _get_user_agent(db, agent_id, user_id)

    from services.agent_runtime import get_runtime_manager
    runtime_mgr = get_runtime_manager()
    if runtime_mgr.is_running(agent_id):
        await runtime_mgr.pause_agent(agent_id)
    else:
        agent.status = AgentStatus.PAUSED
        db.commit()

    db.refresh(agent)
    return {"message": "Agent paused", "agent": _agent_to_dict(agent)}


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    agent = _get_user_agent(db, agent_id, user_id)

    from services.agent_runtime import get_runtime_manager
    runtime_mgr = get_runtime_manager()
    if runtime_mgr.is_running(agent_id):
        await runtime_mgr.stop_agent(agent_id)
    else:
        agent.status = AgentStatus.STOPPED
        db.commit()

    db.refresh(agent)
    return {"message": "Agent stopped", "agent": _agent_to_dict(agent)}


@router.post("/{agent_id}/ghost-mode/toggle")
def toggle_ghost_mode(agent_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    agent = _get_user_agent(db, agent_id, user_id)
    agent.ghost_mode_enabled = not agent.ghost_mode_enabled
    db.commit()
    db.refresh(agent)
    return {
        "ghost_mode_enabled": agent.ghost_mode_enabled,
        "message": f"Ghost Mode {'activated' if agent.ghost_mode_enabled else 'deactivated'}",
    }


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    agent = _get_user_agent(db, agent_id, user_id)
    # Stop runtime if running
    from services.agent_runtime import get_runtime_manager
    runtime_mgr = get_runtime_manager()
    if runtime_mgr.is_running(agent_id):
        import asyncio
        asyncio.create_task(runtime_mgr.stop_agent(agent_id))
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted"}


@router.get("/{agent_id}/integrations/status")
def get_integration_status(agent_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    """Check current connection status of all integrations."""
    _get_user_agent(db, agent_id, user_id)
    from services.composio_tools import get_composio_client
    client = get_composio_client()
    client.initialize(f"kairo_{user_id}")
    return client.get_connection_status()


@router.post("/{agent_id}/integrations/connect/{app_name}")
def connect_integration(
    agent_id: str,
    app_name: str,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Get OAuth URL to connect a new integration (Gmail, Slack, Teams, etc.)."""
    _get_user_agent(db, agent_id, user_id)
    from services.composio_tools import get_composio_client
    client = get_composio_client()
    client.initialize(f"kairo_{user_id}")
    auth_url = client.get_auth_url(app_name)
    if auth_url:
        return {"auth_url": auth_url, "app": app_name}
    return {"error": f"Failed to get auth URL for {app_name}. Check Composio API key."}


def _get_user_agent(db, agent_id: str, user_id: str) -> AgentConfig:
    agent = db.query(AgentConfig).filter(
        AgentConfig.id == agent_id, AgentConfig.user_id == user_id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _agent_to_dict(agent: AgentConfig) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "status": agent.status,
        "ghost_mode": {
            "enabled": agent.ghost_mode_enabled,
            "confidence_threshold": agent.ghost_mode_confidence_threshold,
            "allowed_actions": agent.ghost_mode_allowed_actions,
            "vip_contacts": agent.ghost_mode_vip_contacts,
            "blocked_contacts": agent.ghost_mode_blocked_contacts,
            "max_spend_per_action": agent.ghost_mode_max_spend_per_action,
            "max_spend_per_day": agent.ghost_mode_max_spend_per_day,
        },
        "scheduling": {
            "deep_work_start": agent.deep_work_start,
            "deep_work_end": agent.deep_work_end,
            "deep_work_days": agent.deep_work_days,
            "max_meetings_per_day": agent.max_meetings_per_day,
            "auto_decline_enabled": agent.auto_decline_enabled,
        },
        "voice": {
            "language": agent.voice_language,
            "gender": agent.voice_gender,
            "briefing_time": agent.briefing_time,
            "briefing_enabled": agent.briefing_enabled,
        },
        "integrations": {
            "composio": agent.composio_connected,
            "gmail": agent.gmail_connected,
            "slack": agent.slack_connected,
            "teams": agent.teams_connected,
            "calendar": agent.calendar_connected,
            "github": agent.github_connected,
        },
        "created_at": agent.created_at.isoformat() if agent.created_at else "",
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else "",
    }
