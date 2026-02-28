"""
Skyfire payment client — autonomous agent-initiated transactions.
Uses real Skyfire token-based flow: buyer creates token → seller charges token.
Enforces per-action and per-day spending limits set in agent config.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx

from config import get_settings
from models.database import AgentAction, AgentConfig, get_engine, create_session_factory

settings = get_settings()
logger = logging.getLogger("kairo.skyfire")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class SkyfireClient:
    """
    Manages autonomous payments through Skyfire.
    Enforces guardrails: per-action limit, daily limit, requires running agent.
    """

    BASE_URL = "https://api.skyfire.xyz/api/v1"

    def __init__(self):
        # Buyer key: prefer explicit buyer key, fall back to legacy skyfire_api_key
        self.buyer_api_key = settings.skyfire_buyer_api_key or settings.skyfire_api_key
        self.seller_api_key = settings.skyfire_seller_api_key
        self.seller_service_id = settings.skyfire_seller_service_id

    @property
    def configured(self) -> bool:
        return bool(self.buyer_api_key and self.seller_api_key and self.seller_service_id)

    async def execute_payment(
        self,
        user_id: str,
        agent_id: str,
        amount: float,
        description: str,
        vendor: str = "",
    ) -> dict:
        """
        Execute an autonomous payment within agent guardrails.
        Returns: {"success": bool, "reason": str, "transaction_id": str}
        """
        db = SessionLocal()
        try:
            # 1. Verify agent is running and Ghost Mode is on
            agent = db.query(AgentConfig).filter(
                AgentConfig.id == agent_id,
                AgentConfig.user_id == user_id,
            ).first()

            if not agent:
                return {"success": False, "reason": "Agent not found"}
            if agent.status != "running":
                return {"success": False, "reason": "Agent is not running"}
            if not agent.ghost_mode_enabled:
                return {"success": False, "reason": "Ghost Mode is not active — payment requires Ghost Mode"}

            # 2. Check per-action limit
            max_per_action = agent.ghost_mode_max_spend_per_action or 25.0
            if amount > max_per_action:
                return {
                    "success": False,
                    "reason": f"Amount ${amount:.2f} exceeds per-action limit ${max_per_action:.2f}. Queued for review.",
                }

            # 3. Check daily limit
            max_per_day = agent.ghost_mode_max_spend_per_day or 100.0
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
            spent_today = sum(
                a.amount_spent or 0
                for a in db.query(AgentAction).filter(
                    AgentAction.user_id == user_id,
                    AgentAction.timestamp >= today_start,
                    AgentAction.amount_spent > 0,
                    AgentAction.status == "executed",
                ).all()
            )

            if spent_today + amount > max_per_day:
                return {
                    "success": False,
                    "reason": f"Daily limit reached. Spent today: ${spent_today:.2f}, limit: ${max_per_day:.2f}. Queued.",
                }

            # 4. Execute payment via Skyfire API
            if self.configured:
                transaction_id = await self._call_skyfire_api(amount, description, vendor)
            else:
                # Simulated for local dev
                transaction_id = f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                logger.info(f"[SIMULATED] Skyfire payment: ${amount:.2f} for {description}")

            # 5. Log the action
            action = AgentAction(
                user_id=user_id,
                agent_id=agent_id,
                action_type="purchase",
                channel="skyfire",
                target_contact=vendor or description,
                language_used="en",
                action_taken=f"Auto-paid ${amount:.2f} — {description}",
                confidence_score=0.95,
                reasoning=f"Autonomous payment within guardrails. Vendor: {vendor}. Daily total: ${spent_today + amount:.2f}/{max_per_day:.2f}",
                factors=["within_per_action_limit", "within_daily_limit", "ghost_mode_active"],
                status="executed",
                amount_spent=amount,
                estimated_time_saved_minutes=2.0,
            )
            db.add(action)
            db.commit()

            return {
                "success": True,
                "reason": "Payment executed",
                "transaction_id": transaction_id,
                "daily_total": spent_today + amount,
                "daily_limit": max_per_day,
            }

        except Exception as e:
            logger.error(f"Skyfire payment error: {e}")
            return {"success": False, "reason": str(e)}
        finally:
            db.close()

    async def _call_skyfire_api(self, amount: float, description: str, vendor: str) -> str:
        """Execute the real Skyfire token flow: create token (buyer) → charge token (seller)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Buyer creates a payment token
            # tokenAmount is the max the seller can charge; must meet seller service minimum ($1)
            token_amount = max(amount, 1.0)
            create_resp = await client.post(
                f"{self.BASE_URL}/tokens",
                headers={
                    "skyfire-api-key": self.buyer_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "type": "pay",
                    "tokenAmount": str(token_amount),
                    "sellerServiceId": self.seller_service_id,
                },
            )
            create_resp.raise_for_status()
            token_data = create_resp.json()
            payment_token = token_data.get("token") or token_data.get("data", {}).get("token")
            if not payment_token:
                raise ValueError(f"No token in Skyfire response: {token_data}")
            logger.info(f"Skyfire token created for ${amount:.2f}")

            # Step 2: Seller charges the token
            charge_resp = await client.post(
                f"{self.BASE_URL}/tokens/charge",
                headers={
                    "skyfire-api-key": self.seller_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "token": payment_token,
                    "chargeAmount": str(amount),
                },
            )
            charge_resp.raise_for_status()
            charge_data = charge_resp.json()
            logger.info(f"Skyfire token charged: ${amount:.2f} — {charge_data}")

            # Compose a transaction ID from the token prefix + timestamp
            token_prefix = payment_token[:12] if len(payment_token) > 12 else payment_token
            transaction_id = f"sf_{token_prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            return transaction_id

    async def execute_marketplace_payment(
        self,
        user_id: str,
        agent_id: str,
        amount: float,
        description: str,
        vendor: str = "",
    ) -> dict:
        """
        Execute a marketplace payment — explicit user action, does NOT require ghost mode.
        Still enforces per-action and daily spend limits.
        """
        db = SessionLocal()
        try:
            agent = db.query(AgentConfig).filter(
                AgentConfig.id == agent_id,
                AgentConfig.user_id == user_id,
            ).first()

            if not agent:
                return {"success": False, "reason": "Agent not found"}

            # Check per-action limit
            max_per_action = agent.ghost_mode_max_spend_per_action or 25.0
            if amount > max_per_action:
                return {
                    "success": False,
                    "reason": f"Amount ${amount:.2f} exceeds per-action limit ${max_per_action:.2f}.",
                }

            # Check daily limit
            max_per_day = agent.ghost_mode_max_spend_per_day or 100.0
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
            spent_today = sum(
                a.amount_spent or 0
                for a in db.query(AgentAction).filter(
                    AgentAction.user_id == user_id,
                    AgentAction.timestamp >= today_start,
                    AgentAction.amount_spent > 0,
                    AgentAction.status == "executed",
                ).all()
            )

            if spent_today + amount > max_per_day:
                return {
                    "success": False,
                    "reason": f"Daily limit reached. Spent today: ${spent_today:.2f}, limit: ${max_per_day:.2f}.",
                }

            # Execute payment via Skyfire API
            if self.configured:
                transaction_id = await self._call_skyfire_api(amount, description, vendor)
            else:
                transaction_id = f"mkt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                logger.info(f"[SIMULATED] Marketplace payment: ${amount:.2f} for {description}")

            return {
                "success": True,
                "reason": "Payment executed",
                "transaction_id": transaction_id,
                "daily_total": spent_today + amount,
                "daily_limit": max_per_day,
            }

        except Exception as e:
            logger.error(f"Marketplace payment error: {e}")
            return {"success": False, "reason": str(e)}
        finally:
            db.close()

    async def get_balance(self) -> Optional[dict]:
        """Get current Skyfire wallet balance for the buyer agent."""
        if not self.buyer_api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/agents/balance",
                    headers={"skyfire-api-key": self.buyer_api_key},
                )
                response.raise_for_status()
                data = response.json()
                # Normalize — the response may be nested under "data"
                balance_data = data.get("data", data)
                return {
                    "available": balance_data.get("available", balance_data.get("balance", 0)),
                    "held_amount": balance_data.get("heldAmount", 0),
                    "pending_charges": balance_data.get("pendingCharges", 0),
                    "pending_deposits": balance_data.get("pendingDeposits", 0),
                }
        except Exception as e:
            logger.error(f"Get balance failed: {e}")
            return None


# ── Singleton ──

_skyfire_client: Optional[SkyfireClient] = None


def get_skyfire_client() -> SkyfireClient:
    global _skyfire_client
    if _skyfire_client is None:
        _skyfire_client = SkyfireClient()
    return _skyfire_client
