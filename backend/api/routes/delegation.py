"""Smart delegation routes"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from services.auth import get_current_user_id
from services.smart_delegation import get_smart_delegator
from config import get_settings

router = APIRouter(prefix="/api/delegation", tags=["delegation"])


class ProposeRequest(BaseModel):
    task: str
    to_user_id: Optional[str] = None


class RejectRequest(BaseModel):
    note: str = ""


@router.post("/propose")
def propose_delegation(req: ProposeRequest, user_id: str = Depends(get_current_user_id)):
    delegator = get_smart_delegator()
    analysis = delegator.analyze_task(req.task)

    if req.to_user_id:
        candidates = delegator.find_best_delegate(user_id, analysis)
        match_data = next((c for c in candidates if c["user_id"] == req.to_user_id), None)
        return delegator.propose_delegation(user_id, req.to_user_id, req.task, match_data)

    # Auto-pick best candidate
    candidates = delegator.find_best_delegate(user_id, analysis)
    if not candidates:
        return {"error": "No available delegates found"}
    best = candidates[0]
    return delegator.propose_delegation(user_id, best["user_id"], req.task, best)


@router.get("/candidates")
def get_candidates(task: str = Query(...), user_id: str = Depends(get_current_user_id)):
    delegator = get_smart_delegator()
    analysis = delegator.analyze_task(task)
    return delegator.find_best_delegate(user_id, analysis)


@router.get("/")
def list_delegations(user_id: str = Depends(get_current_user_id)):
    delegator = get_smart_delegator()
    return delegator.get_delegations(user_id)


@router.post("/{delegation_id}/accept")
def accept_delegation(delegation_id: str, user_id: str = Depends(get_current_user_id)):
    delegator = get_smart_delegator()
    return delegator.accept_delegation(delegation_id)


@router.post("/{delegation_id}/reject")
def reject_delegation(delegation_id: str, req: RejectRequest, user_id: str = Depends(get_current_user_id)):
    delegator = get_smart_delegator()
    return delegator.reject_delegation(delegation_id, req.note)


@router.post("/{delegation_id}/complete")
def complete_delegation(delegation_id: str, user_id: str = Depends(get_current_user_id)):
    delegator = get_smart_delegator()
    return delegator.complete_delegation(delegation_id)


@router.get("/stats")
def delegation_stats(user_id: str = Depends(get_current_user_id)):
    delegator = get_smart_delegator()
    return delegator.get_stats(user_id)
