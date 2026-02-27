"""
Predictive Burnout & Workload Forecasting — analyzes patterns to predict burnout risk.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import get_settings
from models.database import (
    BurnoutSnapshot, AgentAction,
    get_engine, create_session_factory,
)

settings = get_settings()
logger = logging.getLogger("kairo.burnout")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class BurnoutPredictor:
    """Analyzes patterns to predict burnout risk. Falls back to local heuristics."""

    def calculate_burnout_risk(self, user_id: str) -> dict:
        """Aggregate signals into burnout risk score (0-100)."""
        db = SessionLocal()
        try:
            ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
            actions = db.query(AgentAction).filter(
                AgentAction.user_id == user_id,
                AgentAction.timestamp >= ninety_days_ago,
            ).all()

            if not actions:
                return {"burnout_risk_score": 0, "factors": {}}

            # Meeting density
            calendar_actions = [a for a in actions if a.channel == "calendar"]
            avg_daily_meetings = len(calendar_actions) / 90.0

            # Message volume
            msg_actions = [a for a in actions if a.channel in ("email", "slack", "teams")]
            messages_daily = len(msg_actions) / 90.0

            # After-hours activity (before 8am or after 6pm UTC)
            after_hours = [a for a in actions if a.timestamp and (a.timestamp.hour < 8 or a.timestamp.hour > 18)]
            after_hours_pct = len(after_hours) / max(len(actions), 1) * 100

            # Score
            risk = 0
            risk += min(30, avg_daily_meetings * 6)  # High meetings = high risk
            risk += min(20, messages_daily * 0.8)
            risk += min(25, after_hours_pct * 0.8)
            risk += min(25, max(0, (len(actions) / 90 - 10) * 2))  # Action overload

            return {
                "burnout_risk_score": round(min(100, risk), 1),
                "avg_daily_meetings": round(avg_daily_meetings, 1),
                "messages_sent_daily": round(messages_daily, 1),
                "after_hours_activity_pct": round(after_hours_pct, 1),
            }
        finally:
            db.close()

    def predict_cold_contacts(self, user_id: str) -> list[dict]:
        """Identify contacts trending toward neglect."""
        db = SessionLocal()
        try:
            two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
            recent = db.query(AgentAction).filter(
                AgentAction.user_id == user_id,
                AgentAction.timestamp >= two_weeks_ago,
                AgentAction.target_contact != "",
            ).all()

            # Count interactions per contact
            contact_counts: dict[str, int] = {}
            contact_last: dict[str, datetime] = {}
            for a in recent:
                c = a.target_contact
                contact_counts[c] = contact_counts.get(c, 0) + 1
                if c not in contact_last or (a.timestamp and a.timestamp > contact_last[c]):
                    contact_last[c] = a.timestamp

            cold = []
            now = datetime.now(timezone.utc)
            for contact, last_time in contact_last.items():
                if last_time:
                    gap_days = (now - last_time).days
                    if gap_days >= 7:
                        cold.append({
                            "contact": contact,
                            "days_until_cold": max(0, 14 - gap_days),
                            "current_interaction_gap": gap_days,
                        })

            cold.sort(key=lambda x: x["current_interaction_gap"], reverse=True)
            return cold[:5]
        finally:
            db.close()

    def calculate_productivity_multipliers(self, user_id: str) -> dict:
        """Analyze action timestamps to find peak productivity windows."""
        db = SessionLocal()
        try:
            actions = db.query(AgentAction).filter(
                AgentAction.user_id == user_id,
            ).all()

            if not actions:
                return {}

            hour_counts: dict[int, int] = {}
            for a in actions:
                if a.timestamp:
                    h = a.timestamp.hour
                    hour_counts[h] = hour_counts.get(h, 0) + 1

            avg = sum(hour_counts.values()) / max(len(hour_counts), 1)
            multipliers = {}
            ranges = [("6-9am", range(6, 9)), ("9-11am", range(9, 11)),
                      ("11am-1pm", range(11, 13)), ("1-3pm", range(13, 15)),
                      ("3-5pm", range(15, 17)), ("5-7pm", range(17, 19))]

            for label, hours in ranges:
                total = sum(hour_counts.get(h, 0) for h in hours)
                block_avg = total / max(len(list(hours)), 1)
                multipliers[label] = round(block_avg / max(avg, 1), 1)

            return multipliers
        finally:
            db.close()

    def generate_interventions(self, user_id: str, burnout_data: dict) -> list[dict]:
        """Generate actionable recommendations."""
        interventions = []

        risk = burnout_data.get("burnout_risk_score", 0)
        meetings = burnout_data.get("avg_daily_meetings", 0)
        after_hours = burnout_data.get("after_hours_activity_pct", 0)

        if meetings > 4:
            interventions.append({
                "id": "int-meetings",
                "action": "Auto-decline meetings before 10am",
                "reason": f"Averaging {meetings:.1f} meetings/day. Morning focus time improves productivity.",
                "impact": "Save ~2.5 hrs/week",
            })

        if after_hours > 20:
            interventions.append({
                "id": "int-afterhours",
                "action": "Block after-hours notifications",
                "reason": f"{after_hours:.0f}% of your activity is outside working hours.",
                "impact": "Better work-life balance",
            })

        if risk > 50:
            interventions.append({
                "id": "int-deepwork",
                "action": "Block Wednesday afternoons for deep work",
                "reason": "High burnout risk. Protected deep work blocks reduce cognitive load.",
                "impact": "Add 3hrs deep work/week",
            })

        return interventions

    def take_snapshot(self, user_id: str) -> dict:
        """Run full analysis and persist as a snapshot."""
        burnout = self.calculate_burnout_risk(user_id)
        cold = self.predict_cold_contacts(user_id)
        productivity = self.calculate_productivity_multipliers(user_id)
        interventions = self.generate_interventions(user_id, burnout)

        db = SessionLocal()
        try:
            snapshot = BurnoutSnapshot(
                user_id=user_id,
                burnout_risk_score=burnout.get("burnout_risk_score", 0),
                workload_score=burnout.get("burnout_risk_score", 0) * 1.2,
                avg_daily_meetings=burnout.get("avg_daily_meetings", 0),
                messages_sent_daily=burnout.get("messages_sent_daily", 0),
                after_hours_activity_pct=burnout.get("after_hours_activity_pct", 0),
                predicted_cold_contacts=cold,
                productivity_multipliers=productivity,
                workload_trajectory="increasing" if burnout.get("burnout_risk_score", 0) > 50 else "stable",
                recommended_interventions=interventions,
            )
            db.add(snapshot)
            db.commit()
            return self._to_dict(snapshot)
        finally:
            db.close()

    def get_latest_snapshot(self, user_id: str) -> Optional[dict]:
        db = SessionLocal()
        try:
            s = db.query(BurnoutSnapshot).filter(
                BurnoutSnapshot.user_id == user_id,
            ).order_by(BurnoutSnapshot.snapshot_date.desc()).first()
            return self._to_dict(s) if s else None
        finally:
            db.close()

    def get_trend(self, user_id: str, snapshots: int = 12) -> list[dict]:
        db = SessionLocal()
        try:
            results = db.query(BurnoutSnapshot).filter(
                BurnoutSnapshot.user_id == user_id,
            ).order_by(BurnoutSnapshot.snapshot_date.desc()).limit(snapshots).all()
            return [self._to_dict(s) for s in reversed(results)]
        finally:
            db.close()

    def _to_dict(self, s: BurnoutSnapshot) -> dict:
        return {
            "id": s.id,
            "user_id": s.user_id,
            "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else "",
            "burnout_risk_score": s.burnout_risk_score,
            "workload_score": s.workload_score,
            "relationship_health_score": s.relationship_health_score,
            "avg_daily_meetings": s.avg_daily_meetings,
            "avg_response_time_hours": s.avg_response_time_hours,
            "deep_work_hours_weekly": s.deep_work_hours_weekly,
            "messages_sent_daily": s.messages_sent_daily,
            "after_hours_activity_pct": s.after_hours_activity_pct,
            "predicted_cold_contacts": s.predicted_cold_contacts or [],
            "productivity_multipliers": s.productivity_multipliers or {},
            "workload_trajectory": s.workload_trajectory,
            "recommended_interventions": s.recommended_interventions or [],
        }


_predictor = None


def get_burnout_predictor() -> BurnoutPredictor:
    global _predictor
    if _predictor is None:
        _predictor = BurnoutPredictor()
    return _predictor
