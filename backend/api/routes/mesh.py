"""Mesh routes — multi-agent coordination API"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.mesh_coordinator import get_mesh_coordinator
from config import get_settings
import logging

router = APIRouter(prefix="/api/mesh", tags=["mesh"])
logger = logging.getLogger("kairo.mesh")


class MeetingRequest(BaseModel):
    to_user_id: str
    proposed_times: list[str]
    duration_minutes: int = 30
    subject: str = ""


class TaskHandoff(BaseModel):
    to_user_id: str
    description: str


@router.get("/status")
def mesh_status(user_id: str = Depends(get_current_user_id)):
    mesh = get_mesh_coordinator()
    return mesh.get_mesh_status(user_id)


@router.get("/agents")
def connected_agents(user_id: str = Depends(get_current_user_id)):
    mesh = get_mesh_coordinator()
    return mesh.get_connected_agents(user_id)


@router.post("/meeting")
async def request_meeting(req: MeetingRequest, user_id: str = Depends(get_current_user_id)):
    mesh = get_mesh_coordinator()
    return await mesh.request_meeting(user_id, req.to_user_id, req.proposed_times, req.duration_minutes, req.subject)


@router.post("/handoff")
async def handoff_task(req: TaskHandoff, user_id: str = Depends(get_current_user_id)):
    mesh = get_mesh_coordinator()
    return await mesh.handoff_task(user_id, req.to_user_id, req.description)


# ── Agent Negotiation Dialogue ──

AGENT_PERSONAS = {
    "Atlas": {"personality": "analytical, data-driven, strategic", "voice": "en-US-GuyNeural", "gender": "male"},
    "Nova": {"personality": "warm, collaborative, empathetic", "voice": "en-US-AriaNeural", "gender": "female"},
    "Sentinel": {"personality": "precise, security-minded, thorough", "voice": "en-IN-NeerjaNeural", "gender": "female"},
}


class NegotiateRequest(BaseModel):
    negotiation_type: str  # e.g. "sprint_planning", "meeting_scheduling", "task_handoff"
    agent_a: str  # e.g. "Atlas"
    agent_b: str  # e.g. "Nova"
    context: str = ""  # extra context for the scenario


@router.post("/negotiate")
async def negotiate(req: NegotiateRequest, user_id: str = Depends(get_current_user_id)):
    """Generate a dialogue between two agents negotiating a scenario."""
    settings = get_settings()
    persona_a = AGENT_PERSONAS.get(req.agent_a, AGENT_PERSONAS["Atlas"])
    persona_b = AGENT_PERSONAS.get(req.agent_b, AGENT_PERSONAS["Nova"])

    prompt = (
        f"Generate a realistic 6-10 line dialogue between two AI agents negotiating.\n\n"
        f"Agent A: {req.agent_a} — {persona_a['personality']}, {persona_a['gender']} voice\n"
        f"Agent B: {req.agent_b} — {persona_b['personality']}, {persona_b['gender']} voice\n"
        f"Negotiation type: {req.negotiation_type.replace('_', ' ')}\n"
        f"Context: {req.context or 'Standard team coordination'}\n\n"
        f"Rules:\n"
        f"- Each line must be under 30 words\n"
        f"- Agents should reach a resolution by the end\n"
        f"- Show natural back-and-forth with concessions and agreements\n"
        f"- Keep it professional but with distinct personalities\n\n"
        f"Format EXACTLY as:\n"
        f"{req.agent_a}: <text>\n"
        f"{req.agent_b}: <text>\n"
        f"... alternating, ending with a resolution line"
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()

        # Parse dialogue lines
        lines = []
        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            for agent_name in [req.agent_a, req.agent_b]:
                if line.startswith(f"{agent_name}:"):
                    text = line[len(agent_name) + 1:].strip()
                    persona = AGENT_PERSONAS.get(agent_name, AGENT_PERSONAS["Atlas"])
                    lines.append({
                        "speaker": agent_name,
                        "text": text,
                        "voice": persona["voice"],
                    })
                    break

        # Determine outcome from last line
        outcome = lines[-1]["text"] if lines else "Negotiation complete."

        return {
            "negotiation_type": req.negotiation_type,
            "agents": [req.agent_a, req.agent_b],
            "dialogue": lines,
            "outcome": outcome,
        }
    except Exception as e:
        logger.error(f"Negotiate error: {e}")
        return {"error": str(e), "dialogue": []}
