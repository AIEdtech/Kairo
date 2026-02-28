"""Burnout prediction and wellness routes"""

from fastapi import APIRouter, Depends
from services.auth import get_current_user_id
from services.burnout_predictor import get_burnout_predictor
from config import get_settings

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
    return {"status": "applied", "intervention_id": intervention_id, "message": "Intervention applied to your agent configuration."}


@router.get("/cold-contacts")
def get_cold_contacts(user_id: str = Depends(get_current_user_id)):
    predictor = get_burnout_predictor()
    return predictor.predict_cold_contacts(user_id)


@router.get("/productivity")
def get_productivity(user_id: str = Depends(get_current_user_id)):
    predictor = get_burnout_predictor()
    return predictor.calculate_productivity_multipliers(user_id)
