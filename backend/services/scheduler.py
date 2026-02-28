"""
Scheduler — global APScheduler instance.

Per-user jobs (morning briefing, ghost triage) are registered/deregistered
by each user's AgentRuntime when they launch/stop their agent.

This module only provides:
  - The shared scheduler instance
  - Global maintenance jobs (graph sync, cleanup)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from models.database import AgentConfig, get_engine, create_session_factory
from config import get_settings

settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)
logger = logging.getLogger("kairo.scheduler")

# ── Global scheduler instance (per-user jobs are added by AgentRuntime) ──
scheduler = AsyncIOScheduler()


async def sync_all_graphs():
    """Every hour — persist all in-memory NetworkX graphs to DB and Snowflake."""
    from services.agent_runtime import get_runtime_manager
    from services.snowflake_client import get_snowflake_client
    mgr = get_runtime_manager()
    sf = get_snowflake_client()
    for agent_id, runtime in list(mgr._runtimes.items()):
        try:
            runtime._persist_graph()
            # Also sync to Snowflake
            if runtime._graph:
                graph_json = runtime._graph.to_json()
                sf.save_graph(
                    runtime.user_id, graph_json,
                    node_count=len(runtime._graph.G.nodes),
                    edge_count=len(runtime._graph.G.edges),
                )
        except Exception as e:
            logger.error(f"Graph sync failed for {agent_id}: {e}")
    logger.info(f"Graph sync complete — {mgr.active_count} agents")


async def weekly_report_all():
    """Sunday 8:00 AM — generate weekly report for all running/paused agents."""
    from models.database import AgentAction, ActionStatus
    from services.snowflake_client import get_snowflake_client
    from datetime import datetime, timezone, timedelta
    sf = get_snowflake_client()
    db = SessionLocal()
    try:
        agents = db.query(AgentConfig).filter(
            AgentConfig.status.in_(["running", "paused"])
        ).all()
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        for agent in agents:
            # Try to generate an AI-written report via CrewAI
            ai_summary = "Weekly self-report generated"
            try:
                from agents.crew import create_weekly_report_crew

                actions = db.query(AgentAction).filter(
                    AgentAction.user_id == agent.user_id,
                    AgentAction.timestamp >= week_ago,
                ).all()

                actions_summary = []
                for a in actions:
                    actions_summary.append({
                        "type": a.action_type,
                        "channel": a.channel,
                        "status": a.status,
                        "confidence": a.confidence_score,
                        "time_saved": a.estimated_time_saved_minutes,
                    })

                # Build relationships snapshot from the runtime graph if available
                from services.agent_runtime import get_runtime_manager
                mgr = get_runtime_manager()
                runtime = mgr.get_runtime_by_user(agent.user_id)
                relationships_data = {}
                if runtime and runtime._graph:
                    try:
                        import json
                        relationships_data = json.loads(runtime._graph.to_json())
                    except Exception:
                        pass

                crew = create_weekly_report_crew(actions_summary, relationships_data)
                result = crew.kickoff()
                ai_summary = str(result)[:2000]
                logger.info(f"[{agent.user_id}] AI weekly report generated")

            except Exception as e:
                logger.warning(f"[{agent.user_id}] CrewAI weekly report failed, using fallback: {e}")

            action = AgentAction(
                user_id=agent.user_id,
                agent_id=agent.id,
                action_type="weekly_report",
                channel="dashboard",
                language_used=agent.voice_language or "en",
                action_taken=ai_summary,
                confidence_score=1.0,
                status="executed",
                estimated_time_saved_minutes=15.0,
            )
            db.add(action)

            # Compute and log analytics to Snowflake
            try:
                actions = db.query(AgentAction).filter(
                    AgentAction.user_id == agent.user_id,
                    AgentAction.timestamp >= week_ago,
                ).all()
                channels = {}
                languages = {}
                for a in actions:
                    channels[a.channel] = channels.get(a.channel, 0) + 1
                    languages[a.language_used] = languages.get(a.language_used, 0) + 1
                executed = [a for a in actions if a.status == ActionStatus.EXECUTED]
                approved = [a for a in executed if a.user_feedback == "approved"]
                sf.save_weekly_analytics(agent.user_id, {
                    "total_actions": len(actions),
                    "auto_handled": len(executed),
                    "time_saved": sum(a.estimated_time_saved_minutes for a in actions),
                    "accuracy": round(len(approved) / max(len(executed), 1) * 100, 1),
                    "channels": channels,
                    "languages": languages,
                    "total_spent": sum(a.amount_spent for a in actions if a.amount_spent),
                })
            except Exception as e:
                logger.error(f"Snowflake analytics failed for {agent.user_id}: {e}")

        db.commit()
        logger.info(f"Weekly reports generated for {len(agents)} agents")
    except Exception as e:
        logger.error(f"Weekly report error: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the global scheduler with maintenance jobs only."""
    scheduler.add_job(sync_all_graphs, CronTrigger(minute=0), id="graph_sync", replace_existing=True)
    scheduler.add_job(weekly_report_all, CronTrigger(day_of_week="sun", hour=8), id="weekly_report", replace_existing=True)
    scheduler.start()
    logger.info("Global scheduler started (per-user jobs registered by AgentRuntime)")
