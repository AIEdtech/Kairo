"""
Decision Replay — counterfactual reasoning engine for past decisions.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from config import get_settings
from models.database import (
    DecisionReplay, AgentAction,
    get_engine, create_session_factory,
)

settings = get_settings()
logger = logging.getLogger("kairo.replay")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class DecisionReplayEngine:
    """Models 'what if' scenarios from past decisions."""

    def get_replays(self, user_id: str, limit: int = 20) -> list[dict]:
        """Pre-generated replays for significant decisions."""
        db = SessionLocal()
        try:
            replays = db.query(DecisionReplay).filter(
                DecisionReplay.user_id == user_id,
            ).order_by(DecisionReplay.created_at.desc()).limit(limit).all()
            return [self._to_dict(r) for r in replays]
        finally:
            db.close()

    def get_replay_detail(self, replay_id: str) -> Optional[dict]:
        db = SessionLocal()
        try:
            r = db.query(DecisionReplay).filter(DecisionReplay.id == replay_id).first()
            return self._to_dict(r) if r else None
        finally:
            db.close()

    def generate_replay(self, user_id: str, action_id: str) -> dict:
        """For a given past action, model the counterfactual."""
        db = SessionLocal()
        try:
            action = db.query(AgentAction).filter(
                AgentAction.id == action_id,
                AgentAction.user_id == user_id,
            ).first()

            if not action:
                return {"error": "Action not found"}

            # Determine the counterfactual
            original = action.action_taken or ""
            counterfactual_decision = self._invert_decision(action)
            cascade = self._trace_cascade(action, counterfactual_decision)
            time_impact = action.estimated_time_saved_minutes or 0
            productivity = min(1.0, time_impact / 60) if time_impact > 0 else -0.3

            verdict = "Good call" if time_impact > 0 else "Could have been better"
            if time_impact > 30:
                verdict = "Excellent call"

            replay = DecisionReplay(
                user_id=user_id,
                source_action_id=action_id,
                original_decision=original,
                original_outcome=f"Action executed: {original}",
                counterfactual_decision=counterfactual_decision,
                counterfactual_cascade=cascade,
                time_impact_minutes=time_impact,
                relationship_impact={action.target_contact: round(-0.05 if "decline" in original.lower() else 0.05, 2)},
                productivity_impact=round(productivity, 2),
                verdict=verdict,
                confidence=0.82,
            )
            db.add(replay)
            db.commit()
            return self._to_dict(replay)
        finally:
            db.close()

    def get_weekly_replays(self, user_id: str) -> list[dict]:
        """Get this week's replays."""
        from datetime import timedelta
        db = SessionLocal()
        try:
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            replays = db.query(DecisionReplay).filter(
                DecisionReplay.user_id == user_id,
                DecisionReplay.created_at >= week_ago,
            ).order_by(DecisionReplay.created_at.desc()).all()
            return [self._to_dict(r) for r in replays]
        finally:
            db.close()

    def _invert_decision(self, action: AgentAction) -> str:
        """Invert the original decision."""
        action_text = (action.action_taken or "").lower()
        if "declined" in action_text or "decline" in action_text:
            return f"Accepted {action.target_contact}'s request instead"
        if "replied" in action_text or "reply" in action_text:
            return f"Didn't respond to {action.target_contact}"
        if "queued" in action_text:
            return f"Auto-handled instead of queuing for review"
        return f"Took the opposite action: skipped {action.action_taken}"

    def _trace_cascade(self, action: AgentAction, inverted: str) -> list[dict]:
        """Build cascade chain of consequences."""
        cascade = []
        action_text = (action.action_taken or "").lower()

        if "decline" in action_text:
            time_saved = action.estimated_time_saved_minutes or 30
            cascade = [
                {"step": 1, "consequence": f"Deep work block preserved ({time_saved:.0f} min saved)", "confidence": 0.92},
                {"step": 2, "consequence": "Current task completed on schedule", "confidence": 0.85},
                {"step": 3, "consequence": "Sprint deadline met without overtime", "confidence": 0.75},
            ]
        elif "reply" in action_text:
            cascade = [
                {"step": 1, "consequence": f"Response sent to {action.target_contact} in their preferred tone", "confidence": 0.93},
                {"step": 2, "consequence": "Conversation progressed without delay", "confidence": 0.88},
                {"step": 3, "consequence": "Relationship maintained at current level", "confidence": 0.80},
            ]
        else:
            cascade = [
                {"step": 1, "consequence": f"Action taken: {action.action_taken}", "confidence": 0.90},
                {"step": 2, "consequence": "Workflow continued as planned", "confidence": 0.85},
            ]

        return cascade

    def _to_dict(self, r: DecisionReplay) -> dict:
        return {
            "id": r.id,
            "user_id": r.user_id,
            "source_action_id": r.source_action_id,
            "original_decision": r.original_decision,
            "original_outcome": r.original_outcome,
            "counterfactual_decision": r.counterfactual_decision,
            "counterfactual_cascade": r.counterfactual_cascade or [],
            "time_impact_minutes": r.time_impact_minutes,
            "relationship_impact": r.relationship_impact or {},
            "productivity_impact": r.productivity_impact,
            "verdict": r.verdict,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }


_engine = None


def get_replay_engine() -> DecisionReplayEngine:
    global _engine
    if _engine is None:
        _engine = DecisionReplayEngine()
    return _engine
