"""Commitment tracking routes"""

from fastapi import APIRouter, Depends, Query
from services.auth import get_current_user_id
from services.commitment_tracker import get_commitment_tracker
from models.database import get_engine, create_session_factory
from config import get_settings

router = APIRouter(prefix="/api/commitments", tags=["commitments"])
settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def list_commitments(
    status: str = Query(default="all"),
    contact: str = Query(default=""),
    user_id: str = Depends(get_current_user_id),
):
    tracker = get_commitment_tracker()
    commitments = tracker.get_user_commitments(user_id, status=status)
    if contact:
        commitments = [c for c in commitments if contact.lower() in c.get("target_contact", "").lower()]
    return commitments


@router.get("/stats")
def commitment_stats(user_id: str = Depends(get_current_user_id)):
    tracker = get_commitment_tracker()
    return tracker.get_reliability_score(user_id)


@router.get("/{commitment_id}")
def get_commitment(commitment_id: str, user_id: str = Depends(get_current_user_id)):
    tracker = get_commitment_tracker()
    result = tracker.get_commitment_detail(commitment_id)
    if not result or result.get("user_id") != user_id:
        return {"error": "Not found"}
    return result


@router.post("/{commitment_id}/fulfill")
def fulfill_commitment(commitment_id: str, user_id: str = Depends(get_current_user_id)):
    tracker = get_commitment_tracker()
    tracker.mark_fulfilled(commitment_id)
    return {"status": "fulfilled", "id": commitment_id}


@router.post("/{commitment_id}/cancel")
def cancel_commitment(commitment_id: str, user_id: str = Depends(get_current_user_id)):
    tracker = get_commitment_tracker()
    tracker.cancel_commitment(commitment_id)
    return {"status": "cancelled", "id": commitment_id}


@router.post("/{commitment_id}/snooze")
def snooze_commitment(commitment_id: str, hours: int = Query(default=24), user_id: str = Depends(get_current_user_id)):
    tracker = get_commitment_tracker()
    tracker.snooze_commitment(commitment_id, hours=hours)
    return {"status": "snoozed", "id": commitment_id, "hours": hours}


@router.get("/correlation/{contact}")
def commitment_correlation(contact: str, user_id: str = Depends(get_current_user_id)):
    tracker = get_commitment_tracker()
    return tracker.get_sentiment_correlation(user_id, contact)
