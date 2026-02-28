"""Marketplace routes — buy and sell agent capabilities"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from services.auth import get_current_user_id
from services.marketplace import get_marketplace_service

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


# ── Request Models ──

class CreateListingRequest(BaseModel):
    agent_id: str
    title: str
    description: str = ""
    category: str = "custom"
    capability_type: str = "task"
    price_per_use: float
    tags: list[str] = []


class UpdateListingRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    capability_type: Optional[str] = None
    price_per_use: Optional[float] = None
    tags: Optional[list[str]] = None


class PurchaseRequest(BaseModel):
    listing_id: str
    task_description: str = ""


class ReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str = ""


# ── Endpoints ──

@router.get("/listings")
def browse_listings(
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "newest",
    limit: int = 20,
    offset: int = 0,
):
    svc = get_marketplace_service()
    return svc.get_listings(category=category, search=search, sort_by=sort_by, limit=limit, offset=offset)


@router.get("/listings/{listing_id}")
def get_listing(listing_id: str):
    svc = get_marketplace_service()
    try:
        return svc.get_listing_detail(listing_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/listings")
def create_listing(req: CreateListingRequest, user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    try:
        return svc.create_listing(
            seller_user_id=user_id,
            agent_id=req.agent_id,
            title=req.title,
            description=req.description,
            category=req.category,
            capability_type=req.capability_type,
            price_per_use=req.price_per_use,
            tags=req.tags,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/listings/{listing_id}")
def update_listing(listing_id: str, req: UpdateListingRequest, user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        return svc.update_listing(listing_id, user_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/listings/{listing_id}/pause")
def pause_listing(listing_id: str, user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    try:
        return svc.pause_listing(listing_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/listings/{listing_id}/activate")
def activate_listing(listing_id: str, user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    try:
        return svc.activate_listing(listing_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/purchase")
async def purchase_capability(req: PurchaseRequest, user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    # Find buyer's agent
    from models.database import AgentConfig, get_engine, create_session_factory
    from config import get_settings
    s = get_settings()
    eng = get_engine(s.database_url)
    Sess = create_session_factory(eng)
    db = Sess()
    try:
        agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
        if not agent:
            raise HTTPException(status_code=400, detail="You need an agent to make purchases")
        buyer_agent_id = agent.id
    finally:
        db.close()

    try:
        return await svc.purchase_capability(
            buyer_user_id=user_id,
            buyer_agent_id=buyer_agent_id,
            listing_id=req.listing_id,
            task_description=req.task_description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transactions/{transaction_id}/review")
def submit_review(transaction_id: str, req: ReviewRequest, user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    try:
        return svc.submit_review(transaction_id, user_id, req.rating, req.review_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-listings")
def my_listings(user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    return svc.get_my_listings(user_id)


@router.get("/my-purchases")
def my_purchases(user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    return svc.get_purchase_history(user_id)


@router.get("/seller-dashboard")
def seller_dashboard(user_id: str = Depends(get_current_user_id)):
    svc = get_marketplace_service()
    return svc.get_seller_dashboard(user_id)
