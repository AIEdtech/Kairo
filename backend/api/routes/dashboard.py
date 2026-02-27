"""Dashboard routes — decision log, stats, weekly report"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from datetime import datetime, timedelta, timezone
from services.auth import get_current_user_id
from models.database import AgentAction, AgentConfig, ActionStatus, UserPreference, ContactRelationship, get_engine, create_session_factory
from config import get_settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/stats")
def get_dashboard_stats(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    """Overview stats for the dashboard home page."""
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_actions = db.query(AgentAction).filter(
        AgentAction.user_id == user_id,
        AgentAction.timestamp >= week_ago,
    ).count()

    auto_handled = db.query(AgentAction).filter(
        AgentAction.user_id == user_id,
        AgentAction.timestamp >= week_ago,
        AgentAction.status == ActionStatus.EXECUTED,
    ).count()

    time_saved = db.query(func.sum(AgentAction.estimated_time_saved_minutes)).filter(
        AgentAction.user_id == user_id,
        AgentAction.timestamp >= week_ago,
    ).scalar() or 0

    money_spent = db.query(func.sum(AgentAction.amount_spent)).filter(
        AgentAction.user_id == user_id,
        AgentAction.timestamp >= week_ago,
        AgentAction.amount_spent > 0,
    ).scalar() or 0

    accuracy = 0
    if auto_handled > 0:
        approved = db.query(AgentAction).filter(
            AgentAction.user_id == user_id,
            AgentAction.timestamp >= week_ago,
            AgentAction.status == ActionStatus.EXECUTED,
            AgentAction.user_feedback == "approved",
        ).count()
        accuracy = round((approved / auto_handled) * 100, 1)

    # Agent status
    agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()

    return {
        "period": "last_7_days",
        "total_actions": total_actions,
        "auto_handled": auto_handled,
        "time_saved_minutes": round(time_saved, 1),
        "time_saved_hours": round(time_saved / 60, 1),
        "money_spent": round(money_spent, 2),
        "ghost_mode_accuracy": accuracy,
        "agent_status": agent.status if agent else "no_agent",
        "ghost_mode_enabled": agent.ghost_mode_enabled if agent else False,
    }


@router.get("/decisions")
def get_decision_log(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    status_filter: str = Query(default="all"),
    channel_filter: str = Query(default="all"),
    db=Depends(get_db),
):
    """Paginated decision log with filters."""
    query = db.query(AgentAction).filter(AgentAction.user_id == user_id)

    if status_filter != "all":
        query = query.filter(AgentAction.status == status_filter)
    if channel_filter != "all":
        query = query.filter(AgentAction.channel == channel_filter)

    total = query.count()
    actions = query.order_by(AgentAction.timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "actions": [_action_to_dict(a) for a in actions],
    }


@router.post("/decisions/{action_id}/feedback")
def submit_feedback(
    action_id: str,
    feedback: dict,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """User approves, edits, or rejects an action — feeds the learning loop."""
    action = db.query(AgentAction).filter(
        AgentAction.id == action_id, AgentAction.user_id == user_id
    ).first()
    if not action:
        return {"error": "Action not found"}

    action.user_feedback = feedback.get("type", "approved")  # approved, edited, rejected
    if feedback.get("edited_content"):
        action.edited_content = feedback["edited_content"]
        action.status = ActionStatus.OVERRIDDEN

    db.commit()

    # Feed the learning loop — update UserPreference based on feedback patterns
    _process_feedback_learning(
        db, user_id, action,
        feedback.get("type", "approved"),
        feedback.get("edited_content"),
    )

    return {"message": "Feedback recorded", "action_id": action_id}


@router.get("/weekly-report")
def get_weekly_report(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    """Generate weekly self-report data."""
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    actions = db.query(AgentAction).filter(
        AgentAction.user_id == user_id,
        AgentAction.timestamp >= week_ago,
    ).all()

    # Channel breakdown
    channels = {}
    languages = {}
    action_types = {}

    for a in actions:
        channels[a.channel] = channels.get(a.channel, 0) + 1
        languages[a.language_used] = languages.get(a.language_used, 0) + 1
        action_types[a.action_type] = action_types.get(a.action_type, 0) + 1

    total_time = sum(a.estimated_time_saved_minutes for a in actions)
    total_spent = sum(a.amount_spent for a in actions if a.amount_spent)
    executed = [a for a in actions if a.status == ActionStatus.EXECUTED]
    approved = [a for a in executed if a.user_feedback == "approved"]
    rejected = [a for a in actions if a.user_feedback == "rejected"]
    edited = [a for a in actions if a.user_feedback == "edited"]

    return {
        "period": {
            "start": week_ago.isoformat(),
            "end": datetime.now(timezone.utc).isoformat(),
        },
        "headline": f"Kairo saved you {round(total_time / 60, 1)} hours this week",
        "time_saved": {
            "total_minutes": round(total_time, 1),
            "total_hours": round(total_time / 60, 1),
            "breakdown": action_types,
        },
        "ghost_mode": {
            "total_actions": len(executed),
            "approved": len(approved),
            "edited": len(edited),
            "rejected": len(rejected),
            "accuracy": round(len(approved) / max(len(executed), 1) * 100, 1),
        },
        "channels": channels,
        "languages": languages,
        "spending": {
            "total": round(total_spent, 2),
            "transactions": len([a for a in actions if a.amount_spent and a.amount_spent > 0]),
        },
    }


def _process_feedback_learning(db, user_id: str, action: AgentAction, feedback_type: str, edited_content: str = None):
    """
    Update UserPreference table based on feedback patterns.
    Called after every feedback submission to continuously improve agent behaviour.
    """
    contact = action.target_contact or ""

    def _upsert_preference(key: str, value: str, confidence_delta: float = 0.1):
        """Create or update a single UserPreference row."""
        pref = db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.preference_key == key,
        ).first()
        if pref:
            pref.preference_value = value
            pref.confidence = min(1.0, pref.confidence + confidence_delta)
            pref.learned_from_count += 1
            pref.source = "learned"
        else:
            pref = UserPreference(
                user_id=user_id,
                preference_key=key,
                preference_value=value,
                confidence=max(0.1, 0.5 + confidence_delta),
                source="learned",
                learned_from_count=1,
            )
            db.add(pref)

    try:
        if feedback_type == "edited" and edited_content:
            # Language change detection — if original draft language differs from edit
            original_lang = action.language_used or "en"
            # Simple heuristic: if edited content has Devanagari characters, language changed to Hindi
            has_devanagari = any("\u0900" <= ch <= "\u097F" for ch in (edited_content or ""))
            original_has_devanagari = any("\u0900" <= ch <= "\u097F" for ch in (action.draft_content or ""))

            if has_devanagari and not original_has_devanagari:
                _upsert_preference(f"language_{contact}", "hi", 0.15)
            elif not has_devanagari and original_has_devanagari:
                _upsert_preference(f"language_{contact}", "en", 0.15)

            # Message length preference — if edit changed length significantly (>30% difference)
            original_len = len(action.draft_content or "")
            edited_len = len(edited_content)
            if original_len > 0:
                length_ratio = edited_len / original_len
                if length_ratio < 0.7:
                    _upsert_preference(f"msg_length_{contact}", "shorter", 0.1)
                elif length_ratio > 1.3:
                    _upsert_preference(f"msg_length_{contact}", "longer", 0.1)

        elif feedback_type == "rejected":
            # If a meeting decline was rejected, lower decline aggressiveness
            if action.action_type and "decline" in action.action_type:
                _upsert_preference("decline_aggressiveness", "lower", -0.15)

        elif feedback_type == "approved":
            # Increment confidence for existing preferences related to this contact
            existing_prefs = db.query(UserPreference).filter(
                UserPreference.user_id == user_id,
                UserPreference.preference_key.like(f"%{contact}%"),
            ).all()
            for pref in existing_prefs:
                pref.confidence = min(1.0, pref.confidence + 0.05)
                pref.learned_from_count += 1

        db.commit()
    except Exception:
        db.rollback()


@router.get("/cross-context-alerts")
def get_cross_context_alerts(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    """Return cross-context alerts (work vs personal, wellness nudges, conflicts)."""
    from services.agent_runtime import get_runtime_manager

    manager = get_runtime_manager()
    runtime = manager.get_runtime_by_user(user_id)

    if not runtime or not runtime.is_running:
        return {"alerts": [], "message": "Agent not running"}

    alerts = runtime._check_cross_context(user_id)
    return {"alerts": alerts}


def _action_to_dict(action: AgentAction) -> dict:
    return {
        "id": action.id,
        "timestamp": action.timestamp.isoformat() if action.timestamp else "",
        "action_type": action.action_type,
        "channel": action.channel,
        "target_contact": action.target_contact,
        "language_used": action.language_used,
        "original_message_summary": action.original_message_summary,
        "action_taken": action.action_taken,
        "draft_content": action.draft_content,
        "confidence_score": action.confidence_score,
        "reasoning": action.reasoning,
        "factors": action.factors or [],
        "status": action.status,
        "user_feedback": action.user_feedback,
        "edited_content": action.edited_content,
        "amount_spent": action.amount_spent,
        "estimated_time_saved_minutes": action.estimated_time_saved_minutes,
    }
