"""Mesh routes — multi-agent coordination API"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.mesh_coordinator import get_mesh_coordinator

router = APIRouter(prefix="/api/mesh", tags=["mesh"])


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
