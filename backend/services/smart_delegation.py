"""
Smart Delegation — identifies best teammate for tasks and routes via mesh.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from config import get_settings
from models.database import (
    DelegationRequest, DelegationStatus, AgentAction, User,
    get_engine, create_session_factory,
)

settings = get_settings()
logger = logging.getLogger("kairo.delegation")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class SmartDelegator:
    """Identifies best teammate for incoming work and routes via mesh."""

    SKILL_KEYWORDS = {
        "api": ["api", "endpoint", "rest", "graphql", "backend"],
        "frontend": ["react", "component", "css", "ui", "ux", "design", "frontend"],
        "database": ["sql", "database", "query", "migration", "schema"],
        "devops": ["deploy", "ci", "cd", "docker", "kubernetes", "infrastructure"],
        "testing": ["test", "qa", "coverage", "e2e", "unit test"],
        "management": ["sprint", "roadmap", "timeline", "budget", "stakeholder"],
    }

    def analyze_task(self, task_text: str) -> dict:
        """Extract: skill tags, urgency, estimated effort."""
        text_lower = task_text.lower()
        skill_tags = []
        for skill, keywords in self.SKILL_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                skill_tags.append(skill)

        urgency = 0.5
        if any(w in text_lower for w in ["urgent", "asap", "immediately", "critical"]):
            urgency = 0.9
        elif any(w in text_lower for w in ["when you can", "no rush", "whenever"]):
            urgency = 0.3

        return {"skill_tags": skill_tags or ["general"], "urgency": urgency}

    def find_best_delegate(self, from_user_id: str, task_analysis: dict) -> list[dict]:
        """Score all mesh users for delegation suitability."""
        db = SessionLocal()
        try:
            users = db.query(User).filter(User.id != from_user_id, User.is_active == True).all()
            candidates = []
            for user in users:
                expertise = self._score_expertise(db, user.id, task_analysis.get("skill_tags", []))
                bandwidth = self._score_bandwidth(db, user.id)
                relationship = self._score_relationship(db, from_user_id, user.id)
                match_score = expertise * 0.45 + bandwidth * 0.30 + relationship * 0.25

                reasons = []
                if expertise > 0.5:
                    reasons.append(f"expertise: {', '.join(task_analysis.get('skill_tags', []))}")
                if bandwidth > 0.5:
                    reasons.append(f"bandwidth: {bandwidth:.0%} available")
                if relationship > 0.5:
                    reasons.append(f"relationship: {relationship:.0%} strength")

                candidates.append({
                    "user_id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                    "match_score": round(match_score, 3),
                    "expertise_match": round(expertise, 3),
                    "bandwidth_score": round(bandwidth, 3),
                    "relationship_strength": round(relationship, 3),
                    "match_reasons": reasons,
                })

            candidates.sort(key=lambda c: c["match_score"], reverse=True)
            return candidates
        finally:
            db.close()

    def _score_expertise(self, db, user_id: str, skill_tags: list) -> float:
        """Check past actions for relevant skill indicators."""
        actions = db.query(AgentAction).filter(
            AgentAction.user_id == user_id
        ).limit(50).all()
        if not actions:
            return 0.5
        relevant = 0
        for a in actions:
            text = (a.action_taken or "").lower()
            if any(tag in text for tag in skill_tags):
                relevant += 1
        return min(1.0, relevant / max(len(actions) * 0.3, 1))

    def _score_bandwidth(self, db, user_id: str) -> float:
        """Score based on recent action density — fewer recent actions = more bandwidth."""
        from datetime import timedelta
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_actions = db.query(AgentAction).filter(
            AgentAction.user_id == user_id,
            AgentAction.timestamp >= today_start,
            AgentAction.channel == "calendar",
        ).count()
        return max(0.1, 1.0 - (today_actions * 0.15))

    def _score_relationship(self, db, from_user: str, to_user: str) -> float:
        """Use delegation history for relationship strength."""
        past = db.query(DelegationRequest).filter(
            DelegationRequest.from_user_id == from_user,
            DelegationRequest.to_user_id == to_user,
            DelegationRequest.status == DelegationStatus.COMPLETED,
        ).count()
        return min(1.0, 0.5 + past * 0.1)

    def propose_delegation(self, from_user_id: str, to_user_id: str,
                            task: str, match_data: dict = None) -> dict:
        """Create a delegation request."""
        db = SessionLocal()
        try:
            deleg = DelegationRequest(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                task_description=task,
                match_score=match_data.get("match_score", 0) if match_data else 0,
                match_reasons=match_data.get("match_reasons", []) if match_data else [],
                expertise_match=match_data.get("expertise_match", 0) if match_data else 0,
                bandwidth_score=match_data.get("bandwidth_score", 0) if match_data else 0,
                relationship_strength=match_data.get("relationship_strength", 0) if match_data else 0,
                status=DelegationStatus.PROPOSED,
            )
            db.add(deleg)
            db.commit()
            db.refresh(deleg)
            return self._to_dict(deleg)
        finally:
            db.close()

    def accept_delegation(self, delegation_id: str) -> dict:
        db = SessionLocal()
        try:
            d = db.query(DelegationRequest).filter(DelegationRequest.id == delegation_id).first()
            if d:
                d.status = DelegationStatus.IN_PROGRESS
                db.commit()
                return self._to_dict(d)
            return {"error": "Not found"}
        finally:
            db.close()

    def reject_delegation(self, delegation_id: str, note: str = "") -> dict:
        db = SessionLocal()
        try:
            d = db.query(DelegationRequest).filter(DelegationRequest.id == delegation_id).first()
            if d:
                d.status = DelegationStatus.REJECTED
                d.response_note = note
                db.commit()
                return self._to_dict(d)
            return {"error": "Not found"}
        finally:
            db.close()

    def complete_delegation(self, delegation_id: str) -> dict:
        db = SessionLocal()
        try:
            d = db.query(DelegationRequest).filter(DelegationRequest.id == delegation_id).first()
            if d:
                d.status = DelegationStatus.COMPLETED
                d.completed_at = datetime.now(timezone.utc)
                db.commit()
                return self._to_dict(d)
            return {"error": "Not found"}
        finally:
            db.close()

    def get_delegations(self, user_id: str) -> list[dict]:
        """All delegations sent and received."""
        db = SessionLocal()
        try:
            sent = db.query(DelegationRequest).filter(DelegationRequest.from_user_id == user_id).all()
            received = db.query(DelegationRequest).filter(DelegationRequest.to_user_id == user_id).all()
            return {
                "sent": [self._to_dict(d) for d in sent],
                "received": [self._to_dict(d) for d in received],
            }
        finally:
            db.close()

    def get_stats(self, user_id: str) -> dict:
        db = SessionLocal()
        try:
            sent = db.query(DelegationRequest).filter(DelegationRequest.from_user_id == user_id).count()
            received = db.query(DelegationRequest).filter(DelegationRequest.to_user_id == user_id).count()
            completed = db.query(DelegationRequest).filter(
                DelegationRequest.from_user_id == user_id,
                DelegationRequest.status == DelegationStatus.COMPLETED,
            ).count()
            avg_match = 0.0
            all_sent = db.query(DelegationRequest).filter(DelegationRequest.from_user_id == user_id).all()
            if all_sent:
                avg_match = round(sum(d.match_score for d in all_sent) / len(all_sent), 2)
            return {
                "total_sent": sent,
                "total_received": received,
                "completed": completed,
                "success_rate": round(completed / max(sent, 1) * 100, 1),
                "avg_match_score": avg_match,
            }
        finally:
            db.close()

    def _to_dict(self, d: DelegationRequest) -> dict:
        return {
            "id": d.id,
            "from_user_id": d.from_user_id,
            "to_user_id": d.to_user_id,
            "task_description": d.task_description,
            "task_source": d.task_source,
            "source_channel": d.source_channel,
            "original_sender": d.original_sender,
            "match_score": d.match_score,
            "match_reasons": d.match_reasons or [],
            "expertise_match": d.expertise_match,
            "bandwidth_score": d.bandwidth_score,
            "relationship_strength": d.relationship_strength,
            "status": d.status,
            "response_note": d.response_note,
            "deadline": d.deadline.isoformat() if d.deadline else None,
            "completed_at": d.completed_at.isoformat() if d.completed_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        }


_delegator = None


def get_smart_delegator() -> SmartDelegator:
    global _delegator
    if _delegator is None:
        _delegator = SmartDelegator()
    return _delegator
