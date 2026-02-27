"""Relationship graph routes — NetworkX-powered endpoints"""

from fastapi import APIRouter, Depends
from services.auth import get_current_user_id
from services.relationship_graph import get_relationship_graph

router = APIRouter(prefix="/api/relationships", tags=["relationships"])


@router.get("/graph")
def get_graph(user_id: str = Depends(get_current_user_id)):
    """Return full graph as JSON for D3.js frontend rendering."""
    graph = get_relationship_graph(user_id)
    return graph.export_for_frontend()


@router.get("/tone-shifts")
def get_tone_shifts(user_id: str = Depends(get_current_user_id)):
    graph = get_relationship_graph(user_id)
    return graph.detect_tone_shifts()


@router.get("/neglected")
def get_neglected(user_id: str = Depends(get_current_user_id)):
    graph = get_relationship_graph(user_id)
    return graph.find_neglected_relationships()


@router.get("/key-contacts")
def get_key_contacts(user_id: str = Depends(get_current_user_id)):
    graph = get_relationship_graph(user_id)
    return graph.get_key_contacts()


@router.get("/clusters")
def get_clusters(user_id: str = Depends(get_current_user_id)):
    graph = get_relationship_graph(user_id)
    return graph.get_communication_clusters()
