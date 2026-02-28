"""Burnout prediction and wellness routes"""

import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm.attributes import flag_modified
from services.auth import get_current_user_id
from services.burnout_predictor import get_burnout_predictor
from models.database import AgentConfig, BurnoutSnapshot, get_engine, create_session_factory
from config import get_settings

settings = get_settings()
_engine = get_engine(settings.database_url)
_Session = create_session_factory(_engine)

router = APIRouter(prefix="/api/burnout", tags=["burnout"])


@router.get("/current")
def get_current_burnout(user_id: str = Depends(get_current_user_id)):
    predictor = get_burnout_predictor()
    snapshot = predictor.get_latest_snapshot(user_id)
    if not snapshot:
        # Generate on-the-fly if no snapshot exists
        return predictor.take_snapshot(user_id)
    return snapshot


@router.get("/trend")
def get_burnout_trend(user_id: str = Depends(get_current_user_id)):
    predictor = get_burnout_predictor()
    return predictor.get_trend(user_id)


@router.get("/interventions")
def get_interventions(user_id: str = Depends(get_current_user_id)):
    predictor = get_burnout_predictor()
    snapshot = predictor.get_latest_snapshot(user_id)
    if snapshot:
        return snapshot.get("recommended_interventions", [])
    burnout = predictor.calculate_burnout_risk(user_id)
    return predictor.generate_interventions(user_id, burnout)


@router.post("/interventions/{intervention_id}/apply")
def apply_intervention(intervention_id: str, user_id: str = Depends(get_current_user_id)):
    db = _Session()
    try:
        agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
        changes = {}

        if agent:
            if intervention_id == "int-meetings":
                agent.max_meetings_per_day = min(agent.max_meetings_per_day or 6, 3)
                agent.auto_decline_enabled = True
                changes = {"max_meetings_per_day": agent.max_meetings_per_day, "auto_decline_enabled": True}
            elif intervention_id == "int-afterhours":
                agent.deep_work_end = "18:00"
                changes = {"deep_work_end": "18:00"}
            elif intervention_id == "int-deepwork":
                agent.flow_guardian_enabled = True
                changes = {"flow_guardian_enabled": True}
            else:
                agent.flow_guardian_enabled = True
                changes = {"flow_guardian_enabled": True}

        # Mark the intervention as applied in the latest BurnoutSnapshot
        snapshot = db.query(BurnoutSnapshot).filter(
            BurnoutSnapshot.user_id == user_id
        ).order_by(BurnoutSnapshot.snapshot_date.desc()).first()

        if snapshot and snapshot.recommended_interventions:
            interventions = snapshot.recommended_interventions
            if isinstance(interventions, str):
                interventions = json.loads(interventions)
            updated = []
            for item in interventions:
                if isinstance(item, dict) and item.get("id") == intervention_id:
                    item["applied"] = True
                updated.append(item)
            snapshot.recommended_interventions = updated
            flag_modified(snapshot, "recommended_interventions")

        db.commit()
        return {
            "status": "applied",
            "intervention_id": intervention_id,
            "changes": changes,
            "message": "Intervention applied to your agent configuration.",
        }
    finally:
        db.close()


@router.get("/cold-contacts")
def get_cold_contacts(user_id: str = Depends(get_current_user_id)):
    predictor = get_burnout_predictor()
    return predictor.predict_cold_contacts(user_id)


@router.get("/productivity")
def get_productivity(user_id: str = Depends(get_current_user_id)):
    predictor = get_burnout_predictor()
    return predictor.calculate_productivity_multipliers(user_id)
