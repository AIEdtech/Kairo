"""
NLP Command endpoint — lightweight text-based command interface.
Includes: command dispatch, one-sentence agent setup, proactive push.
"""

import re
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.auth import get_current_user_id
from voice.command_dispatch import (
    dispatch_command, detect_language, parse_command,
    CommandType, COMMAND_ROUTE_MAP, _t,
)

logger = logging.getLogger("kairo.nlp")

router = APIRouter(prefix="/api/nlp", tags=["NLP"])


# ──────────────────────────────────────────
# Request / Response Models
# ──────────────────────────────────────────

class NLPCommandRequest(BaseModel):
    text: str
    language: Optional[str] = "auto"


class NLPCommandResponse(BaseModel):
    response: str
    command_type: str
    navigateTo: Optional[str] = None


# ──────────────────────────────────────────
# NLP Agent Setup Parser
# ──────────────────────────────────────────

def parse_agent_setup_intent(text: str) -> dict:
    """
    Extract agent configuration from a natural language sentence.
    Returns a dict of config params to apply.
    """
    config = {}
    text_lower = text.lower()

    # Integrations
    integrations = []
    for keyword, integration in [
        ("gmail", "gmail"), ("email", "gmail"), ("mail", "gmail"),
        ("slack", "slack"), ("calendar", "calendar"), ("cal", "calendar"),
        ("teams", "teams"), ("github", "github"),
    ]:
        if keyword in text_lower:
            integrations.append(integration)
    if integrations:
        config["integrations"] = list(set(integrations))

    # Deep work / protect mornings
    morning_match = re.search(r"(?i)(protect|block|keep|hold|reserve|free)\s+(my\s+)?(morning|afternoon|evening)s?", text)
    if morning_match:
        period = morning_match.group(3).lower()
        if period == "morning":
            config["deep_work_start"] = "09:00"
            config["deep_work_end"] = "12:00"
        elif period == "afternoon":
            config["deep_work_start"] = "13:00"
            config["deep_work_end"] = "17:00"
        elif period == "evening":
            config["deep_work_start"] = "17:00"
            config["deep_work_end"] = "20:00"

    # Specific time ranges
    time_match = re.search(r"(?i)(?:deep work|focus|protect)\s+(\d{1,2})(?::(\d{2}))?\s*(?:am|pm|to|-)\s*(\d{1,2})(?::(\d{2}))?\s*(?:am|pm)?", text)
    if time_match:
        start_h = int(time_match.group(1))
        end_h = int(time_match.group(3))
        if "pm" in text_lower and start_h < 12:
            start_h += 12
        if "pm" in text_lower and end_h < 12:
            end_h += 12
        config["deep_work_start"] = f"{start_h:02d}:00"
        config["deep_work_end"] = f"{end_h:02d}:00"

    # Ghost mode
    if any(kw in text_lower for kw in ["auto-reply", "auto reply", "auto-handle", "handle everything",
                                        "manage my email", "manage my inbox", "autopilot",
                                        "handle routine", "auto respond"]):
        config["ghost_mode"] = True

    # Confidence threshold
    conf_match = re.search(r"(?i)(\d{2,3})\s*%?\s*(confidence|threshold|certainty)", text)
    if conf_match:
        config["confidence_threshold"] = min(int(conf_match.group(1)), 99) / 100.0

    # VIP contacts
    vip_match = re.search(r"(?i)(?:except|but not|always escalate|never auto.?reply to|vip|important)\s*(?:contacts?|people|persons?)?\s*(?:is|are|:)?\s*(?:for\s+)?(.+?)(?:\.|$)", text)
    if vip_match:
        names = [n.strip().rstrip(".") for n in re.split(r",| and ", vip_match.group(1)) if n.strip()]
        if names:
            config["vip_contacts"] = names

    # Language preference
    if "hindi" in text_lower or "hi" in text_lower.split():
        config["voice_language"] = "hi"
    elif "english" in text_lower:
        config["voice_language"] = "en"

    # Agent name
    name_match = re.search(r"(?i)(?:name|call)\s+(?:it|my agent|him|her)\s+[\"']?(.+?)[\"']?(?:\.|,|$)", text)
    if name_match:
        config["agent_name"] = name_match.group(1).strip()

    return config


async def setup_agent_from_nlp(user_id: str, text: str, lang: str) -> str:
    """
    Create or update an agent from a natural language description.
    Returns a human-readable confirmation.
    """
    from models.database import get_engine, create_session_factory, AgentConfig, User
    from config import get_settings
    import uuid

    config = parse_agent_setup_intent(text)
    s = get_settings()
    engine = get_engine(s.database_url)
    SessionLocal = create_session_factory(engine)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.id == user_id).first()
        agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
        created_new = False

        if not agent:
            agent = AgentConfig(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=config.get("agent_name", f"{user.full_name or user.username}'s Kairo Agent"),
                status="running",
            )
            db.add(agent)
            created_new = True

        # Apply parsed config
        if config.get("agent_name"):
            agent.name = config["agent_name"]
        if config.get("ghost_mode"):
            agent.ghost_mode_enabled = True
        if config.get("confidence_threshold"):
            agent.ghost_mode_confidence_threshold = config["confidence_threshold"]
        if config.get("vip_contacts"):
            existing = agent.ghost_mode_vip_contacts or []
            agent.ghost_mode_vip_contacts = list(set(existing + config["vip_contacts"]))
        if config.get("deep_work_start"):
            agent.deep_work_start = config["deep_work_start"]
        if config.get("deep_work_end"):
            agent.deep_work_end = config["deep_work_end"]
        if config.get("voice_language"):
            agent.voice_language = config["voice_language"]

        # Always set status to running
        agent.status = "running"

        db.commit()

        # Build confirmation message
        parts = []
        if created_new:
            parts.append(_t(lang,
                en=f"Agent '{agent.name}' created and launched!",
                hi=f"Agent '{agent.name}' ban gaya aur chalu ho gaya!"))
        else:
            parts.append(_t(lang,
                en=f"Agent '{agent.name}' updated!",
                hi=f"Agent '{agent.name}' update ho gaya!"))

        if config.get("ghost_mode"):
            threshold = int((config.get("confidence_threshold") or agent.ghost_mode_confidence_threshold or 0.85) * 100)
            parts.append(_t(lang,
                en=f"Ghost mode ON at {threshold}% confidence.",
                hi=f"Ghost mode chalu hai {threshold}% confidence pe."))

        if config.get("vip_contacts"):
            names = ", ".join(config["vip_contacts"])
            parts.append(_t(lang,
                en=f"VIP contacts: {names} — always escalated.",
                hi=f"VIP contacts: {names} — hamesha escalate honge."))

        if config.get("deep_work_start"):
            parts.append(_t(lang,
                en=f"Deep work protected: {config['deep_work_start']}–{config['deep_work_end']}.",
                hi=f"Deep work protected: {config['deep_work_start']}–{config['deep_work_end']}."))

        if config.get("integrations"):
            int_list = ", ".join(config["integrations"])
            parts.append(_t(lang,
                en=f"Connect {int_list} from Settings to complete setup.",
                hi=f"Setup complete karne ke liye Settings mein {int_list} connect karein."))

        return " ".join(parts)

    except Exception as e:
        logger.error(f"Agent setup failed: {e}")
        return _t(lang,
            en="Sorry, I couldn't set up the agent. Please try again.",
            hi="Agent setup nahi ho paaya. Phir se try karein.")
    finally:
        db.close()


# ──────────────────────────────────────────
# Backend Adapter (direct DB, no HTTP roundtrip)
# ──────────────────────────────────────────

class NLPBackendAdapter:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def _get_db(self):
        from models.database import get_engine, create_session_factory
        from config import get_settings
        s = get_settings()
        engine = get_engine(s.database_url)
        return create_session_factory(engine)()

    async def get_stats(self) -> dict:
        from models.database import AgentConfig, AgentAction
        from datetime import timedelta
        db = self._get_db()
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.user_id == self.user_id).first()
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            actions = db.query(AgentAction).filter(
                AgentAction.user_id == self.user_id,
                AgentAction.created_at >= week_ago
            ).all()
            total = len(actions)
            auto = sum(1 for a in actions if a.status == "executed")
            return {
                "total_actions": total, "auto_handled": auto,
                "time_saved_hours": round(total * 0.15, 1),
                "ghost_mode_enabled": agent.ghost_mode_enabled if agent else False,
            }
        finally:
            db.close()

    async def get_decisions(self, limit: int = 20, status_filter: str = "all") -> dict:
        from models.database import AgentAction
        db = self._get_db()
        try:
            query = db.query(AgentAction).filter(AgentAction.user_id == self.user_id)
            if status_filter != "all":
                query = query.filter(AgentAction.status == status_filter)
            actions = query.order_by(AgentAction.created_at.desc()).limit(limit).all()
            return {
                "actions": [{"id": str(a.id), "action_type": a.action_type, "action_taken": a.action_taken,
                             "channel": a.channel, "status": a.status, "confidence": a.confidence} for a in actions],
                "total": len(actions),
            }
        finally:
            db.close()

    async def get_weekly_report(self) -> dict:
        stats = await self.get_stats()
        decisions = await self.get_decisions(limit=50)
        channels: dict[str, int] = {}
        for a in decisions.get("actions", []):
            ch = a.get("channel", "other")
            channels[ch] = channels.get(ch, 0) + 1
        return {
            "headline": f"This week: {stats['total_actions']} actions processed",
            "time_saved": {"total_hours": stats["time_saved_hours"]},
            "ghost_mode": {"total_actions": stats["auto_handled"], "accuracy": 92},
            "channels": channels,
        }

    async def get_tone_shifts(self) -> list:
        return []

    async def get_neglected_contacts(self) -> list:
        return []

    async def get_agents(self) -> list:
        from models.database import AgentConfig
        db = self._get_db()
        try:
            agents = db.query(AgentConfig).filter(AgentConfig.user_id == self.user_id).all()
            return [{"id": str(a.id), "name": a.name, "ghost_mode_enabled": a.ghost_mode_enabled} for a in agents]
        finally:
            db.close()

    async def toggle_ghost_mode(self, agent_id: str) -> dict:
        from models.database import AgentConfig
        db = self._get_db()
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id, AgentConfig.user_id == self.user_id).first()
            if not agent:
                return {"error": "Agent not found", "ghost_mode_enabled": False}
            agent.ghost_mode_enabled = not agent.ghost_mode_enabled
            db.commit()
            return {"ghost_mode_enabled": agent.ghost_mode_enabled}
        finally:
            db.close()


# ──────────────────────────────────────────
# NLP Command Endpoint
# ──────────────────────────────────────────

@router.post("/command", response_model=NLPCommandResponse)
async def nlp_command(req: NLPCommandRequest, user_id: str = Depends(get_current_user_id)):
    """Process a natural language command from the command bar."""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty command")

    lang = req.language if req.language and req.language != "auto" else detect_language(text)
    adapter = NLPBackendAdapter(user_id=user_id)

    # Check for agent setup intent first
    cmd_type, params = parse_command(text)
    if cmd_type == CommandType.SETUP_AGENT:
        response = await setup_agent_from_nlp(user_id, text, lang)
        return NLPCommandResponse(
            response=response,
            command_type=cmd_type,
            navigateTo="/dashboard/agents",
        )

    # Regular command dispatch
    response, cmd_type = await dispatch_command(adapter, text, lang)

    if response is None:
        response = _t(lang,
            en="I'm not sure how to handle that. Try asking about your schedule, commitments, or say 'set up my agent'.",
            hi="Yeh samajh nahi aaya. Schedule, commitments ke baare mein poochein, ya 'agent setup karo' bolein.")

    return NLPCommandResponse(
        response=response,
        command_type=cmd_type,
        navigateTo=COMMAND_ROUTE_MAP.get(cmd_type),
    )


# ──────────────────────────────────────────
# Proactive Push Endpoint
# ──────────────────────────────────────────

@router.get("/nudges")
async def get_nudges(user_id: str = Depends(get_current_user_id)):
    """
    Returns proactive nudges for the current user.
    Called periodically by the CommandBar to surface timely alerts.
    """
    from models.database import AgentConfig, AgentAction, Commitment
    from config import get_settings
    from datetime import timedelta

    s = get_settings()
    from models.database import get_engine, create_session_factory
    engine = get_engine(s.database_url)
    SessionLocal = create_session_factory(engine)
    db = SessionLocal()

    nudges = []
    now = datetime.now(timezone.utc)

    try:
        # 1. Pending reviews
        pending_count = db.query(AgentAction).filter(
            AgentAction.user_id == user_id,
            AgentAction.status == "queued_for_review",
        ).count()
        if pending_count > 0:
            nudges.append({
                "type": "pending_review",
                "message": f"You have {pending_count} item{'s' if pending_count != 1 else ''} waiting for your review.",
                "navigateTo": "/dashboard/decisions",
                "priority": "high" if pending_count >= 3 else "medium",
            })

        # 2. Overdue commitments
        try:
            overdue = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.status == "active",
                Commitment.deadline < now,
            ).all()
            if overdue:
                names = [c.contact_name or "someone" for c in overdue[:3]]
                nudges.append({
                    "type": "overdue_commitment",
                    "message": f"You have {len(overdue)} overdue commitment{'s' if len(overdue) != 1 else ''} — promises to {', '.join(names)}.",
                    "navigateTo": "/dashboard/commitments",
                    "priority": "high",
                })
        except Exception:
            pass

        # 3. Agent not running
        agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
        if not agent:
            nudges.append({
                "type": "no_agent",
                "message": "You don't have an agent yet. Say 'set up my agent' to get started in seconds.",
                "navigateTo": None,
                "priority": "low",
            })
        elif agent.status != "running":
            nudges.append({
                "type": "agent_stopped",
                "message": f"Your agent '{agent.name}' is {agent.status}. Want me to launch it?",
                "navigateTo": "/dashboard/agents",
                "priority": "medium",
            })

        # 4. Ghost mode not enabled (agent running but ghost off)
        if agent and agent.status == "running" and not agent.ghost_mode_enabled:
            recent_actions = db.query(AgentAction).filter(
                AgentAction.user_id == user_id,
                AgentAction.created_at >= now - timedelta(hours=24),
            ).count()
            if recent_actions >= 5:
                nudges.append({
                    "type": "ghost_suggestion",
                    "message": f"You had {recent_actions} items in the last 24h. Enable ghost mode to auto-handle routine ones?",
                    "navigateTo": None,
                    "priority": "low",
                })

        return {"nudges": nudges, "timestamp": now.isoformat()}

    except Exception as e:
        logger.error(f"Nudges error: {e}")
        return {"nudges": [], "timestamp": now.isoformat()}
    finally:
        db.close()
