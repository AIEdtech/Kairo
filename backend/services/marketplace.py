"""
Marketplace service — buy and sell agent capabilities via Skyfire payments.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from config import get_settings
from models.database import (
    AgentAction, AgentConfig, MarketplaceListing, MarketplaceTransaction,
    ListingStatus, TransactionStatus, User,
    get_engine, create_session_factory, generate_id,
)
from services.skyfire_client import get_skyfire_client

settings = get_settings()
logger = logging.getLogger("kairo.marketplace")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

PLATFORM_FEE_RATE = 0.10
CATEGORIES = [
    "communication",      # Email/Slack/Teams auto-reply style configs
    "scheduling",         # Deep work protection, meeting mgmt, auto-decline rules
    "relationship_intel", # Tone tracking, sentiment analysis, contact prioritization
    "ghost_mode",         # Autonomous triage presets with tuned thresholds
    "cross_context",      # Work/personal bridging, wellness nudge configs
    "mesh_coordination",  # Agent-to-agent scheduling & task handoff setups
]


class MarketplaceService:

    def create_listing(
        self,
        seller_user_id: str,
        agent_id: str,
        title: str,
        description: str,
        category: str,
        capability_type: str,
        price_per_use: float,
        tags: list[str] | None = None,
    ) -> dict:
        db = SessionLocal()
        try:
            agent = db.query(AgentConfig).filter(
                AgentConfig.id == agent_id,
                AgentConfig.user_id == seller_user_id,
            ).first()
            if not agent:
                raise ValueError("Agent not found or doesn't belong to you")

            if category not in CATEGORIES:
                raise ValueError(f"Invalid category. Must be one of: {CATEGORIES}")

            listing = MarketplaceListing(
                seller_user_id=seller_user_id,
                agent_id=agent_id,
                title=title,
                description=description,
                category=category,
                capability_type=capability_type,
                price_per_use=price_per_use,
                tags=tags or [],
            )
            db.add(listing)
            db.commit()
            db.refresh(listing)
            return self._listing_to_dict(listing, db)
        finally:
            db.close()

    def update_listing(self, listing_id: str, seller_user_id: str, updates: dict) -> dict:
        db = SessionLocal()
        try:
            listing = db.query(MarketplaceListing).filter(
                MarketplaceListing.id == listing_id,
                MarketplaceListing.seller_user_id == seller_user_id,
            ).first()
            if not listing:
                raise ValueError("Listing not found or you don't own it")

            allowed = {"title", "description", "category", "capability_type", "price_per_use", "tags"}
            for key, value in updates.items():
                if key in allowed:
                    setattr(listing, key, value)

            db.commit()
            db.refresh(listing)
            return self._listing_to_dict(listing, db)
        finally:
            db.close()

    def pause_listing(self, listing_id: str, seller_user_id: str) -> dict:
        return self._set_listing_status(listing_id, seller_user_id, ListingStatus.PAUSED)

    def activate_listing(self, listing_id: str, seller_user_id: str) -> dict:
        return self._set_listing_status(listing_id, seller_user_id, ListingStatus.ACTIVE)

    def _set_listing_status(self, listing_id: str, seller_user_id: str, status: str) -> dict:
        db = SessionLocal()
        try:
            listing = db.query(MarketplaceListing).filter(
                MarketplaceListing.id == listing_id,
                MarketplaceListing.seller_user_id == seller_user_id,
            ).first()
            if not listing:
                raise ValueError("Listing not found or you don't own it")
            listing.status = status
            db.commit()
            db.refresh(listing)
            return self._listing_to_dict(listing, db)
        finally:
            db.close()

    def get_listings(
        self,
        category: str | None = None,
        search: str | None = None,
        sort_by: str = "newest",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        db = SessionLocal()
        try:
            q = db.query(MarketplaceListing).filter(
                MarketplaceListing.status == ListingStatus.ACTIVE
            )
            if category:
                q = q.filter(MarketplaceListing.category == category)
            if search:
                q = q.filter(
                    MarketplaceListing.title.ilike(f"%{search}%")
                    | MarketplaceListing.description.ilike(f"%{search}%")
                )

            if sort_by == "popular":
                q = q.order_by(MarketplaceListing.total_purchases.desc())
            elif sort_by == "price_low":
                q = q.order_by(MarketplaceListing.price_per_use.asc())
            elif sort_by == "price_high":
                q = q.order_by(MarketplaceListing.price_per_use.desc())
            elif sort_by == "top_rated":
                q = q.order_by(MarketplaceListing.avg_rating.desc())
            else:  # newest
                q = q.order_by(MarketplaceListing.created_at.desc())

            listings = q.offset(offset).limit(limit).all()
            return [self._listing_to_dict(l, db) for l in listings]
        finally:
            db.close()

    def get_listing_detail(self, listing_id: str) -> dict:
        db = SessionLocal()
        try:
            listing = db.query(MarketplaceListing).filter(
                MarketplaceListing.id == listing_id
            ).first()
            if not listing:
                raise ValueError("Listing not found")

            result = self._listing_to_dict(listing, db)

            # Include reviews
            transactions = db.query(MarketplaceTransaction).filter(
                MarketplaceTransaction.listing_id == listing_id,
                MarketplaceTransaction.rating.isnot(None),
            ).order_by(MarketplaceTransaction.created_at.desc()).limit(20).all()

            result["reviews"] = [
                {
                    "rating": t.rating,
                    "review_text": t.review_text,
                    "buyer_name": db.query(User).filter(User.id == t.buyer_user_id).first().full_name if db.query(User).filter(User.id == t.buyer_user_id).first() else "Unknown",
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in transactions
            ]
            return result
        finally:
            db.close()

    def get_my_listings(self, user_id: str) -> list[dict]:
        db = SessionLocal()
        try:
            listings = db.query(MarketplaceListing).filter(
                MarketplaceListing.seller_user_id == user_id,
                MarketplaceListing.status != ListingStatus.REMOVED,
            ).order_by(MarketplaceListing.created_at.desc()).all()
            return [self._listing_to_dict(l, db) for l in listings]
        finally:
            db.close()

    async def purchase_capability(
        self,
        buyer_user_id: str,
        buyer_agent_id: str,
        listing_id: str,
        task_description: str = "",
    ) -> dict:
        db = SessionLocal()
        try:
            listing = db.query(MarketplaceListing).filter(
                MarketplaceListing.id == listing_id,
                MarketplaceListing.status == ListingStatus.ACTIVE,
            ).first()
            if not listing:
                raise ValueError("Listing not found or not active")

            if listing.seller_user_id == buyer_user_id:
                raise ValueError("Cannot purchase your own listing")

            # Verify buyer agent
            buyer_agent = db.query(AgentConfig).filter(
                AgentConfig.id == buyer_agent_id,
                AgentConfig.user_id == buyer_user_id,
            ).first()
            if not buyer_agent:
                raise ValueError("Buyer agent not found")

            amount = listing.price_per_use
            platform_fee = round(amount * PLATFORM_FEE_RATE, 2)
            seller_earnings = round(amount - platform_fee, 2)

            # Process payment via Skyfire
            skyfire = get_skyfire_client()
            payment = await skyfire.execute_marketplace_payment(
                user_id=buyer_user_id,
                agent_id=buyer_agent_id,
                amount=amount,
                description=f"Marketplace: {listing.title}",
                vendor=listing.seller_user_id,
            )

            if not payment["success"]:
                raise ValueError(f"Payment failed: {payment['reason']}")

            # Create transaction
            txn = MarketplaceTransaction(
                listing_id=listing_id,
                buyer_user_id=buyer_user_id,
                seller_user_id=listing.seller_user_id,
                buyer_agent_id=buyer_agent_id,
                amount=amount,
                skyfire_transaction_id=payment.get("transaction_id", ""),
                platform_fee=platform_fee,
                seller_earnings=seller_earnings,
                status=TransactionStatus.COMPLETED,
                task_description=task_description,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(txn)

            # Update listing stats
            listing.total_purchases += 1
            listing.total_earnings += seller_earnings

            # Log buyer action
            db.add(AgentAction(
                user_id=buyer_user_id,
                agent_id=buyer_agent_id,
                action_type="marketplace_purchase",
                channel="marketplace",
                target_contact=listing.title,
                action_taken=f"Purchased '{listing.title}' for ${amount:.2f}",
                confidence_score=1.0,
                reasoning=f"Marketplace purchase from seller {listing.seller_user_id}",
                factors=["marketplace_purchase", "user_initiated"],
                status="executed",
                amount_spent=amount,
                estimated_time_saved_minutes=5.0,
            ))

            # Log seller action
            db.add(AgentAction(
                user_id=listing.seller_user_id,
                agent_id=listing.agent_id,
                action_type="marketplace_sale",
                channel="marketplace",
                target_contact=listing.title,
                action_taken=f"Sold '{listing.title}' — earned ${seller_earnings:.2f}",
                confidence_score=1.0,
                reasoning=f"Marketplace sale to buyer {buyer_user_id}",
                factors=["marketplace_sale", "automatic"],
                status="executed",
                amount_spent=0,
                estimated_time_saved_minutes=0,
            ))

            db.commit()
            db.refresh(txn)

            return {
                "transaction_id": txn.id,
                "listing_title": listing.title,
                "amount": amount,
                "platform_fee": platform_fee,
                "seller_earnings": seller_earnings,
                "skyfire_transaction_id": payment.get("transaction_id", ""),
                "status": txn.status,
            }
        finally:
            db.close()

    def submit_review(
        self,
        transaction_id: str,
        buyer_user_id: str,
        rating: int,
        review_text: str = "",
    ) -> dict:
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        db = SessionLocal()
        try:
            txn = db.query(MarketplaceTransaction).filter(
                MarketplaceTransaction.id == transaction_id,
                MarketplaceTransaction.buyer_user_id == buyer_user_id,
            ).first()
            if not txn:
                raise ValueError("Transaction not found or you didn't make this purchase")
            if txn.rating is not None:
                raise ValueError("You already reviewed this purchase")

            txn.rating = rating
            txn.review_text = review_text

            # Recalculate avg rating for the listing
            listing = db.query(MarketplaceListing).filter(
                MarketplaceListing.id == txn.listing_id
            ).first()
            if listing:
                all_ratings = [
                    t.rating for t in db.query(MarketplaceTransaction).filter(
                        MarketplaceTransaction.listing_id == listing.id,
                        MarketplaceTransaction.rating.isnot(None),
                    ).all()
                ]
                # Include the current rating being submitted
                if rating not in all_ratings:
                    all_ratings.append(rating)
                listing.avg_rating = round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else 0.0
                listing.total_reviews = len(all_ratings)

            db.commit()
            return {"status": "ok", "avg_rating": listing.avg_rating if listing else 0, "total_reviews": listing.total_reviews if listing else 0}
        finally:
            db.close()

    def get_seller_dashboard(self, user_id: str) -> dict:
        db = SessionLocal()
        try:
            listings = db.query(MarketplaceListing).filter(
                MarketplaceListing.seller_user_id == user_id,
                MarketplaceListing.status != ListingStatus.REMOVED,
            ).all()

            total_earnings = sum(l.total_earnings for l in listings)
            total_sales = sum(l.total_purchases for l in listings)
            active_count = sum(1 for l in listings if l.status == ListingStatus.ACTIVE)

            return {
                "total_earnings": round(total_earnings, 2),
                "total_sales": total_sales,
                "active_listings": active_count,
            }
        finally:
            db.close()

    def get_purchase_history(self, user_id: str) -> list[dict]:
        db = SessionLocal()
        try:
            txns = db.query(MarketplaceTransaction).filter(
                MarketplaceTransaction.buyer_user_id == user_id,
            ).order_by(MarketplaceTransaction.created_at.desc()).all()

            result = []
            for t in txns:
                listing = db.query(MarketplaceListing).filter(
                    MarketplaceListing.id == t.listing_id
                ).first()
                seller = db.query(User).filter(User.id == t.seller_user_id).first()
                result.append({
                    "id": t.id,
                    "listing_id": t.listing_id,
                    "listing_title": listing.title if listing else "Unknown",
                    "seller_name": seller.full_name if seller else "Unknown",
                    "amount": t.amount,
                    "status": t.status,
                    "task_description": t.task_description,
                    "rating": t.rating,
                    "review_text": t.review_text,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                })
            return result
        finally:
            db.close()

    def _listing_to_dict(self, listing: MarketplaceListing, db) -> dict:
        seller = db.query(User).filter(User.id == listing.seller_user_id).first()
        return {
            "id": listing.id,
            "seller_user_id": listing.seller_user_id,
            "seller_name": seller.full_name if seller else "Unknown",
            "agent_id": listing.agent_id,
            "title": listing.title,
            "description": listing.description,
            "category": listing.category,
            "tags": listing.tags or [],
            "capability_type": listing.capability_type,
            "price_per_use": listing.price_per_use,
            "currency": listing.currency,
            "status": listing.status,
            "is_featured": listing.is_featured,
            "total_purchases": listing.total_purchases,
            "avg_rating": listing.avg_rating,
            "total_reviews": listing.total_reviews,
            "total_earnings": listing.total_earnings,
            "created_at": listing.created_at.isoformat() if listing.created_at else None,
        }


# ── Singleton ──

_marketplace_service: Optional[MarketplaceService] = None


def get_marketplace_service() -> MarketplaceService:
    global _marketplace_service
    if _marketplace_service is None:
        _marketplace_service = MarketplaceService()
    return _marketplace_service
