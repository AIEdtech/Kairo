"""
Webhook handlers — receive events from Composio integrations
Routes: POST /webhooks/email, /webhooks/slack, /webhooks/teams, /webhooks/calendar
"""

from fastapi import APIRouter, Request, BackgroundTasks
from datetime import datetime, timezone
import logging

from models.database import AgentAction, AgentConfig, get_engine, create_session_factory
from services.relationship_graph import get_relationship_graph
from config import get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)
logger = logging.getLogger("kairo.webhooks")


async def process_incoming_message(channel: str, payload: dict):
    """Background task: route incoming message through the agent runtime pipeline."""
    db = SessionLocal()
    try:
        user_id = payload.get("user_id")
        if not user_id:
            return

        agent = db.query(AgentConfig).filter(
            AgentConfig.user_id == user_id,
            AgentConfig.status == "running"
        ).first()
        if not agent:
            return

        # Route through the runtime manager → full Observe → Reason → Act pipeline
        from services.agent_runtime import get_runtime_manager
        runtime_mgr = get_runtime_manager()
        runtime = runtime_mgr.get_runtime(agent.id)

        if runtime:
            result = await runtime.process_incoming(channel, payload)
            logger.info(f"Webhook processed via runtime: {channel} → {result.get('action')}")
        else:
            # Runtime not loaded (e.g. server restarted) — fallback to simple logging
            graph = get_relationship_graph(user_id)
            sender = payload.get("sender", "unknown")
            sentiment = payload.get("sentiment", 0.5)
            language = payload.get("language", "en")
            graph.record_interaction(sender, sentiment, channel=channel, language=language)

            action = AgentAction(
                user_id=user_id,
                agent_id=agent.id,
                action_type=f"{channel}_queued",
                channel=channel,
                target_contact=sender,
                language_used=language,
                original_message_summary=payload.get("summary", "")[:500],
                action_taken=f"Queued {channel} from {sender} (runtime not loaded)",
                confidence_score=payload.get("estimated_confidence", 0.5),
                reasoning="Agent runtime not loaded — queued for review",
                status="queued_for_review",
            )
            db.add(action)
            db.commit()
            logger.info(f"Webhook fallback: {channel} from {sender} queued")

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
    finally:
        db.close()


@router.post("/email")
async def email_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(process_incoming_message, "email", payload)
    return {"status": "accepted"}


@router.post("/slack")
async def slack_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(process_incoming_message, "slack", payload)
    return {"status": "accepted"}


@router.post("/teams")
async def teams_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(process_incoming_message, "teams", payload)
    return {"status": "accepted"}


@router.post("/calendar")
async def calendar_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    # Calendar events go to scheduling agent, not message pipeline
    logger.info(f"Calendar event received: {payload.get('event_type', 'unknown')}")
    return {"status": "accepted"}
