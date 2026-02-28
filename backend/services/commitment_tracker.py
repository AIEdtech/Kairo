"""
Commitment Tracker — detects promises in outgoing messages and tracks fulfillment.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import get_settings
from models.database import (
    Commitment, AgentAction, CommitmentStatus,
    get_engine, create_session_factory,
)

settings = get_settings()
logger = logging.getLogger("kairo.commitments")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class CommitmentTracker:
    """Scans outgoing messages for promises and tracks fulfillment."""

    COMMITMENT_PATTERNS = [
        re.compile(r"(?i)i'?ll\s+(send|share|review|write|submit|prepare|finish|complete|get back|follow up)"),
        re.compile(r"(?i)i\s+will\s+(send|share|review|write|submit|prepare|finish|complete|get back|follow up)"),
        re.compile(r"(?i)(let me|allow me to)\s+(send|share|review|check|look into)"),
        re.compile(r"(?i)by\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|end of day|eod|eow|end of week)"),
        re.compile(r"(?i)(maine|main)\s+(bhej|kar|de)\s*(dunga|dungi|deta|deti)"),
        re.compile(r"(?i)(kal tak|aaj tak|friday tak)\s+(bhej|kar|de)"),
    ]

    DAY_MAP = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }

    def scan_outgoing_message(self, user_id: str, agent_id: str,
                               message_text: str, target_contact: str,
                               channel: str) -> list[Commitment]:
        """Scan a message for commitments. Returns list of detected commitments."""
        detected = []
        for pattern in self.COMMITMENT_PATTERNS:
            if pattern.search(message_text):
                deadline = self.extract_deadline(message_text, datetime.now(timezone.utc))
                commitment = Commitment(
                    user_id=user_id,
                    agent_id=agent_id,
                    raw_text=message_text[:500],
                    parsed_commitment=message_text[:200],
                    target_contact=target_contact,
                    channel=channel,
                    deadline=deadline,
                    deadline_source="extracted" if deadline else "none",
                    status=CommitmentStatus.ACTIVE,
                )
                detected.append(commitment)
                break  # One commitment per message
        return detected

    def extract_deadline(self, text: str, reference_date: datetime) -> Optional[datetime]:
        """Extract deadline from natural language."""
        text_lower = text.lower()

        if "tomorrow" in text_lower or "kal tak" in text_lower:
            return reference_date + timedelta(days=1)
        if "tonight" in text_lower or "end of day" in text_lower or "eod" in text_lower or "aaj tak" in text_lower:
            return reference_date.replace(hour=23, minute=59)
        if "end of week" in text_lower or "eow" in text_lower:
            days_until_friday = (4 - reference_date.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            return reference_date + timedelta(days=days_until_friday)

        for day_name, day_num in self.DAY_MAP.items():
            if day_name in text_lower or f"{day_name} tak" in text_lower:
                days_ahead = (day_num - reference_date.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return reference_date + timedelta(days=days_ahead)

        return None

    def check_overdue(self, user_id: str) -> list[dict]:
        """Find all active commitments past their deadline."""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            overdue = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.status == CommitmentStatus.ACTIVE,
                Commitment.deadline != None,
                Commitment.deadline < now,
            ).all()
            return [self._to_dict(c) for c in overdue]
        finally:
            db.close()

    def get_user_commitments(self, user_id: str, status: str = "all") -> list[dict]:
        """Return all commitments for dashboard display."""
        db = SessionLocal()
        try:
            q = db.query(Commitment).filter(Commitment.user_id == user_id)
            if status != "all":
                q = q.filter(Commitment.status == status)
            commitments = q.order_by(Commitment.created_at.desc()).all()
            return [self._to_dict(c) for c in commitments]
        finally:
            db.close()

    def get_commitment_detail(self, commitment_id: str) -> Optional[dict]:
        db = SessionLocal()
        try:
            c = db.query(Commitment).filter(Commitment.id == commitment_id).first()
            return self._to_dict(c) if c else None
        finally:
            db.close()

    def mark_fulfilled(self, commitment_id: str, action_id: str = None):
        """Mark a commitment as fulfilled."""
        db = SessionLocal()
        try:
            c = db.query(Commitment).filter(Commitment.id == commitment_id).first()
            if c:
                c.status = CommitmentStatus.FULFILLED
                c.fulfilled_at = datetime.now(timezone.utc)
                if action_id:
                    c.related_action_id = action_id
                db.commit()
        finally:
            db.close()

    def cancel_commitment(self, commitment_id: str):
        db = SessionLocal()
        try:
            c = db.query(Commitment).filter(Commitment.id == commitment_id).first()
            if c:
                c.status = CommitmentStatus.CANCELLED
                db.commit()
        finally:
            db.close()

    def snooze_commitment(self, commitment_id: str, hours: int = 24):
        db = SessionLocal()
        try:
            c = db.query(Commitment).filter(Commitment.id == commitment_id).first()
            if c and c.deadline:
                c.deadline = c.deadline + timedelta(hours=hours)
                if c.status == CommitmentStatus.OVERDUE:
                    c.status = CommitmentStatus.ACTIVE
                db.commit()
        finally:
            db.close()

    def get_reliability_score(self, user_id: str) -> dict:
        """Calculate user's commitment reliability."""
        db = SessionLocal()
        try:
            total = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.status != CommitmentStatus.CANCELLED,
            ).count()
            fulfilled = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.status == CommitmentStatus.FULFILLED,
            ).count()
            overdue = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.status.in_([CommitmentStatus.OVERDUE, CommitmentStatus.BROKEN]),
            ).count()
            active = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.status == CommitmentStatus.ACTIVE,
            ).count()

            score = round((fulfilled / max(total, 1)) * 100, 1)
            return {
                "total": total,
                "fulfilled": fulfilled,
                "overdue": overdue,
                "active": active,
                "reliability_score": score,
            }
        finally:
            db.close()

    def get_sentiment_correlation(self, user_id: str, contact: str) -> dict:
        """Correlate broken commitments with sentiment for a contact."""
        db = SessionLocal()
        try:
            broken = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.target_contact == contact,
                Commitment.status.in_([CommitmentStatus.BROKEN, CommitmentStatus.OVERDUE]),
            ).all()
            total_impact = sum(c.sentiment_impact for c in broken)
            return {
                "contact": contact,
                "broken_commitments": len(broken),
                "total_sentiment_impact": round(total_impact, 3),
                "details": [{"commitment": c.parsed_commitment, "impact": c.sentiment_impact} for c in broken],
            }
        finally:
            db.close()

    def nudge_upcoming(self, user_id: str, hours_before: int = 4) -> list[dict]:
        """Find commitments due within N hours that haven't been fulfilled."""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            cutoff = now + timedelta(hours=hours_before)
            upcoming = db.query(Commitment).filter(
                Commitment.user_id == user_id,
                Commitment.status == CommitmentStatus.ACTIVE,
                Commitment.deadline != None,
                Commitment.deadline <= cutoff,
                Commitment.deadline > now,
            ).all()
            return [self._to_dict(c) for c in upcoming]
        finally:
            db.close()

    def _to_dict(self, c: Commitment) -> dict:
        return {
            "id": c.id,
            "user_id": c.user_id,
            "agent_id": c.agent_id,
            "raw_text": c.raw_text,
            "parsed_commitment": c.parsed_commitment,
            "target_contact": c.target_contact,
            "channel": c.channel,
            "detected_at": c.detected_at.isoformat() if c.detected_at else "",
            "deadline": c.deadline.isoformat() if c.deadline else None,
            "deadline_source": c.deadline_source,
            "status": c.status,
            "fulfilled_at": c.fulfilled_at.isoformat() if c.fulfilled_at else None,
            "related_action_id": c.related_action_id,
            "sentiment_impact": c.sentiment_impact,
            "ghost_fulfillable": c.ghost_fulfillable,
            "ghost_action_type": c.ghost_action_type,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }


_tracker = None


def get_commitment_tracker() -> CommitmentTracker:
    global _tracker
    if _tracker is None:
        _tracker = CommitmentTracker()
    return _tracker
