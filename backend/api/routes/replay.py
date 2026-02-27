"""Decision replay (counterfactual reasoning) routes"""

from fastapi import APIRouter, Depends, Query
from services.auth import get_current_user_id
from services.decision_replay import get_replay_engine
from config import get_settings

router = APIRouter(prefix="/api/replay", tags=["replay"])


@router.get("/")
def list_replays(
    limit: int = Query(default=20, le=50),
    user_id: str = Depends(get_current_user_id),
):
    engine = get_replay_engine()
    return engine.get_replays(user_id, limit=limit)


@router.get("/weekly")
def weekly_replays(user_id: str = Depends(get_current_user_id)):
    engine = get_replay_engine()
    return engine.get_weekly_replays(user_id)


@router.get("/{replay_id}")
def get_replay_detail(replay_id: str, user_id: str = Depends(get_current_user_id)):
    engine = get_replay_engine()
    result = engine.get_replay_detail(replay_id)
    if not result or result.get("user_id") != user_id:
        return {"error": "Not found"}
    return result


@router.post("/generate/{action_id}")
def generate_replay(action_id: str, user_id: str = Depends(get_current_user_id)):
    engine = get_replay_engine()
    return engine.generate_replay(user_id, action_id)
