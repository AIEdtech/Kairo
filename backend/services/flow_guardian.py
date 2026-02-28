"""
Flow State Guardian — detects and protects flow state in real-time.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from config import get_settings
from models.database import (
    FlowSession, AgentConfig,
    get_engine, create_session_factory,
)

settings = get_settings()
logger = logging.getLogger("kairo.flow")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class FlowGuardian:
    """Detects and protects flow state in real-time."""

    # Per-user active session tracking (in-memory)
    _active_sessions: dict[str, dict] = {}

    def is_in_flow(self, user_id: str) -> bool:
        """Check if user currently has active flow session."""
        return user_id in self._active_sessions

    def get_status(self, user_id: str) -> dict:
        """Get current flow state."""
        if user_id in self._active_sessions:
            session = self._active_sessions[user_id]
            now = datetime.now(timezone.utc)
            elapsed = (now - session["started_at"]).total_seconds() / 60
            return {
                "in_flow": True,
                "session_id": session.get("session_id"),
                "started_at": session["started_at"].isoformat(),
                "duration_minutes": round(elapsed, 1),
                "messages_held": session.get("messages_held", 0),
                "messages_escalated": session.get("messages_escalated", 0),
                "auto_responses_sent": session.get("auto_responses_sent", 0),
                "flow_score": session.get("flow_score", 0.8),
            }
        # Include last session info for UI context
        db = SessionLocal()
        try:
            last = db.query(FlowSession).filter(
                FlowSession.user_id == user_id,
                FlowSession.ended_at != None,
            ).order_by(FlowSession.ended_at.desc()).first()
            if last:
                return {
                    "in_flow": False,
                    "last_session": {
                        "ended_at": last.ended_at.isoformat() if last.ended_at else None,
                        "duration_minutes": last.duration_minutes,
                        "messages_held": last.messages_held,
                        "flow_score": last.flow_score,
                    },
                }
        finally:
            db.close()
        return {"in_flow": False}

    def activate_protection(self, user_id: str, agent_id: str) -> dict:
        """Start a flow protection session."""
        now = datetime.now(timezone.utc)

        db = SessionLocal()
        try:
            session = FlowSession(
                user_id=user_id,
                agent_id=agent_id,
                started_at=now,
                trigger_signals=["manual_activation"],
                flow_score=0.85,
            )
            db.add(session)
            db.commit()
            session_id = session.id

            self._active_sessions[user_id] = {
                "session_id": session_id,
                "agent_id": agent_id,
                "started_at": now,
                "messages_held": 0,
                "messages_escalated": 0,
                "auto_responses_sent": 0,
                "held_messages": [],
                "flow_score": 0.85,
            }

            logger.info(f"[{user_id}] Flow protection activated, session={session_id}")
            return {"status": "activated", "session_id": session_id}
        finally:
            db.close()

    def hold_message(self, user_id: str, message: dict) -> dict:
        """Incoming message during flow. Hold it unless urgent."""
        if user_id not in self._active_sessions:
            return {"action": "pass_through"}

        session = self._active_sessions[user_id]
        urgency = self._assess_urgency(message, user_id)

        if urgency >= 0.9:
            session["messages_escalated"] = session.get("messages_escalated", 0) + 1
            return {"action": "escalated", "urgency": urgency, "reason": "Urgent message"}

        session["messages_held"] = session.get("messages_held", 0) + 1
        session["auto_responses_sent"] = session.get("auto_responses_sent", 0) + 1
        held = session.get("held_messages", [])
        held.append({
            "from": message.get("sender", "Unknown"),
            "channel": message.get("channel", "unknown"),
            "summary": message.get("summary", message.get("message", "")[:100]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        session["held_messages"] = held

        return {"action": "held", "urgency": urgency}

    def _assess_urgency(self, message: dict, user_id: str) -> float:
        """Score message urgency."""
        text = (message.get("message", "") + " " + message.get("summary", "")).lower()
        sender = message.get("sender", "")

        # VIP check
        db = SessionLocal()
        try:
            agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
            if agent and sender in (agent.ghost_mode_vip_contacts or []):
                return 0.95
        finally:
            db.close()

        if any(w in text for w in ["urgent", "emergency", "asap", "critical", "p0", "incident"]):
            return 0.85
        if any(w in text for w in ["important", "deadline", "blocker"]):
            return 0.6

        return 0.3

    def end_flow_session(self, user_id: str) -> dict:
        """End flow protection and prepare debrief."""
        if user_id not in self._active_sessions:
            return {"error": "No active flow session"}

        session_data = self._active_sessions.pop(user_id)
        now = datetime.now(timezone.utc)
        duration = (now - session_data["started_at"]).total_seconds() / 60

        db = SessionLocal()
        try:
            session = db.query(FlowSession).filter(
                FlowSession.id == session_data["session_id"]
            ).first()
            if session:
                session.ended_at = now
                session.duration_minutes = round(duration, 1)
                session.messages_held = session_data.get("messages_held", 0)
                session.messages_escalated = session_data.get("messages_escalated", 0)
                session.auto_responses_sent = session_data.get("auto_responses_sent", 0)
                session.held_messages = session_data.get("held_messages", [])
                session.debrief_delivered = True
                session.debrief_at = now
                session.estimated_focus_saved_minutes = round(
                    session_data.get("messages_held", 0) * 8, 1  # ~8 min per interruption saved
                )
                db.commit()

            return self.generate_debrief(session_data["session_id"])
        finally:
            db.close()

    def generate_debrief(self, session_id: str) -> dict:
        """Create summary of everything held during flow."""
        db = SessionLocal()
        try:
            session = db.query(FlowSession).filter(FlowSession.id == session_id).first()
            if not session:
                return {"error": "Session not found"}

            return {
                "session_id": session.id,
                "duration_minutes": session.duration_minutes,
                "messages_held": session.messages_held,
                "messages_escalated": session.messages_escalated,
                "auto_responses_sent": session.auto_responses_sent,
                "held_messages": session.held_messages or [],
                "estimated_focus_saved_minutes": session.estimated_focus_saved_minutes,
                "summary": (
                    f"Flow session: {session.duration_minutes:.0f} minutes. "
                    f"{session.messages_held} messages held, "
                    f"{session.messages_escalated} escalated. "
                    f"Estimated {session.estimated_focus_saved_minutes:.0f} minutes of focus saved."
                ),
            }
        finally:
            db.close()

    def get_flow_history(self, user_id: str) -> list[dict]:
        """Past flow sessions with stats."""
        db = SessionLocal()
        try:
            sessions = db.query(FlowSession).filter(
                FlowSession.user_id == user_id,
                FlowSession.ended_at != None,
            ).order_by(FlowSession.started_at.desc()).limit(20).all()
            return [self._to_dict(s) for s in sessions]
        finally:
            db.close()

    def get_flow_stats(self, user_id: str) -> dict:
        """Aggregate flow stats."""
        db = SessionLocal()
        try:
            sessions = db.query(FlowSession).filter(
                FlowSession.user_id == user_id,
                FlowSession.ended_at != None,
            ).all()

            if not sessions:
                return {
                    "total_sessions": 0,
                    "total_flow_hours": 0,
                    "avg_session_minutes": 0,
                    "total_messages_protected": 0,
                    "total_focus_saved_minutes": 0,
                }

            total_duration = sum(s.duration_minutes or 0 for s in sessions)
            total_held = sum(s.messages_held or 0 for s in sessions)
            total_saved = sum(s.estimated_focus_saved_minutes or 0 for s in sessions)

            return {
                "total_sessions": len(sessions),
                "total_flow_hours": round(total_duration / 60, 1),
                "avg_session_minutes": round(total_duration / len(sessions), 1),
                "total_messages_protected": total_held,
                "total_focus_saved_minutes": round(total_saved, 1),
            }
        finally:
            db.close()

    def _to_dict(self, s: FlowSession) -> dict:
        return {
            "id": s.id,
            "user_id": s.user_id,
            "agent_id": s.agent_id,
            "started_at": s.started_at.isoformat() if s.started_at else "",
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_minutes": s.duration_minutes,
            "trigger_signals": s.trigger_signals or [],
            "flow_score": s.flow_score,
            "messages_held": s.messages_held,
            "messages_escalated": s.messages_escalated,
            "auto_responses_sent": s.auto_responses_sent,
            "held_messages": s.held_messages or [],
            "debrief_delivered": s.debrief_delivered,
            "estimated_focus_saved_minutes": s.estimated_focus_saved_minutes,
        }


_guardian = None


def get_flow_guardian() -> FlowGuardian:
    global _guardian
    if _guardian is None:
        _guardian = FlowGuardian()
    return _guardian
