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
    """Every hour — persist all in-memory NetworkX graphs to DB."""
    from services.agent_runtime import get_runtime_manager
    mgr = get_runtime_manager()
    for agent_id, runtime in list(mgr._runtimes.items()):
        try:
            runtime._persist_graph()
        except Exception as e:
            logger.error(f"Graph sync failed for {agent_id}: {e}")
    logger.info(f"Graph sync complete — {mgr.active_count} agents")


async def weekly_report_all():
    """Sunday 8:00 AM — generate weekly report for all running/paused agents."""
    from models.database import AgentAction
    db = SessionLocal()
    try:
        agents = db.query(AgentConfig).filter(
            AgentConfig.status.in_(["running", "paused"])
        ).all()
        for agent in agents:
            action = AgentAction(
                user_id=agent.user_id,
                agent_id=agent.id,
                action_type="weekly_report",
                channel="dashboard",
                language_used=agent.voice_language or "en",
                action_taken="Weekly self-report generated",
                confidence_score=1.0,
                status="executed",
                estimated_time_saved_minutes=15.0,
            )
            db.add(action)
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
