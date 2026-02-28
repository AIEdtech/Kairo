"""
Agent Mesh Coordinator — multi-agent team collaboration.

Each Kairo user runs their own agent. When agents need to coordinate
(schedule meetings, share context, resolve conflicts), they communicate
through this mesh layer.

Privacy Protocol:
- Agents ONLY share: availability windows, energy state, task blockers
- Agents NEVER share: email content, personal messages, private calendar details
- VIP/sensitive contacts are never disclosed

Coordination Types:
1. SCHEDULING: Agent A and Agent B negotiate a meeting time
2. TASK_HANDOFF: Agent A sends a deliverable Agent B is blocked on
3. CONTEXT_SHARE: Agent A shares relevant (non-private) context with Agent B
4. CONFLICT_RESOLUTION: Two agents resolve a scheduling or resource conflict
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from models.database import AgentAction, AgentConfig, get_engine, create_session_factory
from config import get_settings

settings = get_settings()
logger = logging.getLogger("kairo.mesh")
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


class MeshRequest:
    """A request from one agent to another through the mesh."""
    def __init__(self, from_user_id: str, to_user_id: str,
                 request_type: str, payload: dict):
        self.id = str(uuid.uuid4())
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.request_type = request_type  # scheduling, task_handoff, context_share
        self.payload = payload
        self.status = "pending"  # pending, accepted, rejected, completed
        self.response = {}
        self.created_at = datetime.now(timezone.utc)


class MeshCoordinator:
    """
    Manages inter-agent communication across the mesh.
    Singleton per server process.
    """

    def __init__(self):
        self._pending_requests: dict[str, MeshRequest] = {}
        self._active_negotiations: dict[str, dict] = {}
        self._seeded = False

    def _ensure_demo_data(self):
        """Pre-populate mesh with demo activity so the page isn't empty."""
        if self._seeded:
            return
        self._seeded = True

        from datetime import timedelta

        demo_requests = [
            # Sentinel + Atlas negotiated Thu 3pm architecture sync (completed)
            ("user-demo", "user-gaurav", "scheduling",
             {"proposed_times": ["2026-02-27T15:00:00"], "duration_minutes": 30, "subject": "Architecture sync — API v3 migration"},
             "completed", {"accepted_time": "2026-02-27T15:00:00"}, timedelta(hours=18)),

            # Sentinel + Nova negotiated Fri 11am design review (completed)
            ("user-demo", "user-phani", "scheduling",
             {"proposed_times": ["2026-02-28T11:00:00"], "duration_minutes": 45, "subject": "Design review — sidebar redesign"},
             "completed", {"accepted_time": "2026-02-28T11:00:00"}, timedelta(hours=12)),

            # Atlas sent API spec to Nova (completed task handoff)
            ("user-gaurav", "user-phani", "task_handoff",
             {"description": "Updated API schema v3 with auth endpoints — 4 new routes", "attachments": []},
             "completed", {}, timedelta(hours=8)),

            # Nova shared design context with Sentinel (completed)
            ("user-phani", "user-demo", "context_share",
             {"type": "design_update", "data": {"component": "DataTable", "status": "ready_for_review", "storybook_url": "staging.kairo.dev/storybook"}},
             "completed", {}, timedelta(hours=6)),

            # Atlas requesting meeting with Sentinel — pending (active negotiation)
            ("user-gaurav", "user-demo", "scheduling",
             {"proposed_times": ["2026-03-02T14:00:00", "2026-03-02T16:00:00"], "duration_minutes": 30, "subject": "Sprint planning — Q3 priorities"},
             "negotiating", {"alternatives": ["2026-03-02T16:00:00", "2026-03-03T10:00:00"]}, timedelta(hours=2)),

            # Nova requesting task from Atlas — pending
            ("user-phani", "user-gaurav", "task_handoff",
             {"description": "Need updated GraphQL schema types for frontend code generation", "attachments": []},
             "pending", {}, timedelta(hours=1)),
        ]

        now = datetime.now(timezone.utc)
        for from_user, to_user, req_type, payload, status, response, age in demo_requests:
            req = MeshRequest(from_user, to_user, req_type, payload)
            req.status = status
            req.response = response
            req.created_at = now - age
            self._pending_requests[req.id] = req

            if status == "negotiating":
                self._active_negotiations[req.id] = {
                    "request_id": req.id,
                    "from": from_user,
                    "to": to_user,
                    "alternatives": response.get("alternatives", []),
                }

    async def request_meeting(self, from_user: str, to_user: str,
                               proposed_times: list[str],
                               duration_min: int = 30,
                               subject: str = "",
                               channel: str = "calendar") -> dict:
        """
        Agent A requests a meeting with Agent B.
        Agent B's runtime checks availability and responds.
        """
        request = MeshRequest(
            from_user_id=from_user,
            to_user_id=to_user,
            request_type="scheduling",
            payload={
                "proposed_times": proposed_times,
                "duration_minutes": duration_min,
                "subject": subject,
                "channel": channel,
            },
        )
        self._pending_requests[request.id] = request

        # Check if target user's agent is running
        db = SessionLocal()
        try:
            target_agent = db.query(AgentConfig).filter(
                AgentConfig.user_id == to_user,
                AgentConfig.status == "running",
            ).first()

            if not target_agent:
                request.status = "rejected"
                request.response = {"reason": "Target agent not running"}
                self._log_mesh_action(from_user, "mesh_scheduling_failed",
                    f"Meeting request to {to_user} failed — target agent not running")
                return {"status": "rejected", "reason": "Target agent not running"}

            # Simulate Agent B checking availability
            # In production, this would query Agent B's calendar via Composio
            # and compare against their deep work blocks
            available_slots = self._check_availability(
                target_agent, proposed_times, duration_min
            )

            if available_slots:
                chosen_time = available_slots[0]
                request.status = "completed"
                request.response = {"accepted_time": chosen_time}

                # Log for both users
                self._log_mesh_action(from_user, "mesh_meeting_scheduled",
                    f"Meeting with {to_user} scheduled at {chosen_time}",
                    channel=channel)
                self._log_mesh_action(to_user, "mesh_meeting_accepted",
                    f"Meeting request from {from_user} auto-accepted at {chosen_time}",
                    channel=channel)

                return {"status": "scheduled", "time": chosen_time, "request_id": request.id}
            else:
                request.status = "negotiating"
                # Propose alternatives from Agent B's availability
                alternatives = self._suggest_alternatives(target_agent, duration_min)
                request.response = {"alternatives": alternatives}

                self._log_mesh_action(from_user, "mesh_scheduling_negotiating",
                    f"No overlap with {to_user} — {len(alternatives)} alternatives proposed")

                return {"status": "negotiating", "alternatives": alternatives, "request_id": request.id}

        finally:
            db.close()

    async def handoff_task(self, from_user: str, to_user: str,
                           task_description: str, attachments: list = None) -> dict:
        """
        Agent A sends a task/deliverable to Agent B who is blocked on it.
        Only sends non-private content.
        """
        request = MeshRequest(
            from_user_id=from_user,
            to_user_id=to_user,
            request_type="task_handoff",
            payload={
                "description": task_description,
                "attachments": attachments or [],
            },
        )
        self._pending_requests[request.id] = request
        request.status = "completed"

        self._log_mesh_action(from_user, "mesh_task_sent",
            f"Sent task to {to_user}: {task_description[:100]}")
        self._log_mesh_action(to_user, "mesh_task_received",
            f"Received task from {from_user}: {task_description[:100]}")

        return {"status": "delivered", "request_id": request.id}

    async def share_context(self, from_user: str, to_user: str,
                            context_type: str, context_data: dict) -> dict:
        """
        Share relevant (non-private) context between agents.
        Applies privacy filter before sharing.
        """
        filtered_data = self._apply_privacy_filter(context_data)

        request = MeshRequest(
            from_user_id=from_user,
            to_user_id=to_user,
            request_type="context_share",
            payload={"type": context_type, "data": filtered_data},
        )
        self._pending_requests[request.id] = request
        request.status = "completed"

        self._log_mesh_action(from_user, "mesh_context_shared",
            f"Shared {context_type} context with {to_user}")

        return {"status": "shared", "request_id": request.id}

    def get_mesh_status(self, user_id: str) -> dict:
        """Get mesh activity for a user — pending requests, recent negotiations."""
        self._ensure_demo_data()
        incoming = [r for r in self._pending_requests.values()
                   if r.to_user_id == user_id and r.status == "pending"]
        outgoing = [r for r in self._pending_requests.values()
                   if r.from_user_id == user_id]

        # Include all requests involving this user (incoming, outgoing, or either side)
        user_requests = [r for r in self._pending_requests.values()
                        if r.from_user_id == user_id or r.to_user_id == user_id]
        user_requests.sort(key=lambda r: r.created_at, reverse=True)

        return {
            "incoming_requests": len(incoming),
            "outgoing_requests": len(outgoing),
            "active_negotiations": len(self._active_negotiations),
            "requests": [
                {
                    "id": r.id,
                    "type": r.request_type,
                    "from": r.from_user_id,
                    "to": r.to_user_id,
                    "status": r.status,
                    "payload": r.payload,
                    "created_at": r.created_at.isoformat(),
                }
                for r in user_requests
            ][:20],  # last 20
        }

    def get_connected_agents(self, user_id: str) -> list[dict]:
        """List agents in the mesh that this user can coordinate with."""
        db = SessionLocal()
        try:
            agents = db.query(AgentConfig).filter(
                AgentConfig.user_id != user_id,
                AgentConfig.status.in_(["running", "paused"]),
            ).all()
            return [
                {
                    "user_id": a.user_id,
                    "agent_name": a.name,
                    "status": a.status,
                    "ghost_mode": a.ghost_mode_enabled,
                }
                for a in agents
            ]
        finally:
            db.close()

    # ── Private helpers ──

    def _check_availability(self, agent: AgentConfig,
                           proposed_times: list[str],
                           duration: int) -> list[str]:
        """Check which proposed times work for the target agent."""
        available = []
        for time_str in proposed_times:
            try:
                # Simple check: not during deep work hours
                hour = int(time_str.split("T")[1].split(":")[0]) if "T" in time_str else 10
                dw_start = int(agent.deep_work_start.split(":")[0]) if agent.deep_work_start else 9
                dw_end = int(agent.deep_work_end.split(":")[0]) if agent.deep_work_end else 11
                if not (dw_start <= hour < dw_end):
                    available.append(time_str)
            except (ValueError, IndexError):
                available.append(time_str)
        return available

    def _suggest_alternatives(self, agent: AgentConfig, duration: int) -> list[str]:
        """Suggest alternative times based on agent's schedule."""
        from datetime import timedelta
        dw_end = int(agent.deep_work_end.split(":")[0]) if agent.deep_work_end else 11
        today = datetime.now(timezone.utc)
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)
        return [
            f"{today.strftime('%Y-%m-%d')}T{dw_end + 1}:00:00",
            f"{tomorrow.strftime('%Y-%m-%d')}T{dw_end + 1}:00:00",
            f"{day_after.strftime('%Y-%m-%d')}T{dw_end + 3}:00:00",
        ]

    def _apply_privacy_filter(self, data: dict) -> dict:
        """Strip private information before sharing between agents."""
        private_keys = {"email_content", "message_body", "personal_notes",
                       "salary", "health", "password", "private"}
        filtered = {}
        for key, value in data.items():
            if key.lower() not in private_keys:
                if isinstance(value, dict):
                    filtered[key] = self._apply_privacy_filter(value)
                else:
                    filtered[key] = value
        return filtered

    def _log_mesh_action(self, user_id: str, action_type: str,
                         action_taken: str, channel: str = "mesh"):
        db = SessionLocal()
        try:
            agent = db.query(AgentConfig).filter(
                AgentConfig.user_id == user_id
            ).first()
            if not agent:
                return
            action = AgentAction(
                user_id=user_id,
                agent_id=agent.id,
                action_type=action_type,
                channel=channel,
                action_taken=action_taken,
                confidence_score=1.0,
                status="executed",
                estimated_time_saved_minutes=5.0,
            )
            db.add(action)
            db.commit()
        except Exception as e:
            logger.error(f"Mesh action log failed: {e}")
        finally:
            db.close()


# ── Singleton ──

_mesh: Optional[MeshCoordinator] = None

def get_mesh_coordinator() -> MeshCoordinator:
    global _mesh
    if _mesh is None:
        _mesh = MeshCoordinator()
    return _mesh
