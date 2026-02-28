"""Relationship graph routes — NetworkX-powered endpoints"""

from datetime import datetime
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from typing import Optional
from services.auth import get_current_user_id
from services.relationship_graph import get_relationship_graph
from models.database import (
    get_engine, create_session_factory,
    AgentConfig, ContactRelationship, Commitment,
)
from config import get_settings

router = APIRouter(prefix="/api/relationships", tags=["relationships"])

settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ContactUpdate(BaseModel):
    importance_score: Optional[float] = None
    is_vip: Optional[bool] = None


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


@router.patch("/contacts/{contact_id}")
def update_contact(
    contact_id: str,
    data: ContactUpdate,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Update importance_score and/or VIP status for a contact."""
    graph = get_relationship_graph(user_id)

    # Update NetworkX node
    if graph.G.has_node(contact_id):
        if data.importance_score is not None:
            graph.G.nodes[contact_id]["importance_score"] = data.importance_score

    # Update ContactRelationship row
    cr = db.query(ContactRelationship).filter(
        ContactRelationship.user_id == user_id,
        ContactRelationship.contact_name == contact_id,
    ).first()
    if cr and data.importance_score is not None:
        cr.importance_score = data.importance_score

    # Update VIP list on AgentConfig
    agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
    if agent and data.is_vip is not None:
        vip_list = list(agent.ghost_mode_vip_contacts or [])
        if data.is_vip and contact_id not in vip_list:
            vip_list.append(contact_id)
        elif not data.is_vip and contact_id in vip_list:
            vip_list.remove(contact_id)
        agent.ghost_mode_vip_contacts = vip_list

    # Persist graph to DB
    if agent:
        agent.relationship_graph_data = graph.export_for_frontend()

    db.commit()

    return {"status": "updated", "contact_id": contact_id}


@router.get("/contacts/{contact_id}/detail")
def get_contact_detail(
    contact_id: str,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Full contact info: node data, edge data, VIP status, commitments."""
    graph = get_relationship_graph(user_id)

    # Node data
    node_data = {}
    if graph.G.has_node(contact_id):
        node_data = dict(graph.G.nodes[contact_id])

    # Edge data
    edge_data = {}
    if graph.G.has_edge(user_id, contact_id):
        edge_data = dict(graph.G[user_id][contact_id])
        # Keep last 5 sentiment scores for display
        edge_data["sentiment_scores"] = edge_data.get("sentiment_scores", [])[-5:]

    # VIP status
    agent = db.query(AgentConfig).filter(AgentConfig.user_id == user_id).first()
    is_vip = False
    if agent:
        is_vip = contact_id in (agent.ghost_mode_vip_contacts or [])

    # Commitments for this contact
    contact_commitments = db.query(Commitment).filter(
        Commitment.user_id == user_id,
        Commitment.target_contact == contact_id,
    ).order_by(Commitment.detected_at.desc()).limit(20).all()

    commitments_list = [
        {
            "id": c.id,
            "parsed_commitment": c.parsed_commitment,
            "raw_text": c.raw_text,
            "status": c.status,
            "deadline": c.deadline.isoformat() if c.deadline else None,
            "detected_at": c.detected_at.isoformat() if c.detected_at else None,
            "channel": c.channel,
        }
        for c in contact_commitments
    ]

    return {
        "contact_id": contact_id,
        "node": node_data,
        "edge": edge_data,
        "is_vip": is_vip,
        "commitments": commitments_list,
    }


@router.get("/attention")
def get_attention_feed(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    """Merged attention feed: overdue commitments + neglected VIPs + declining tone."""
    items = []

    # 1. Overdue commitments
    overdue = db.query(Commitment).filter(
        Commitment.user_id == user_id,
        Commitment.status.in_(["active", "overdue"]),
        Commitment.deadline < datetime.utcnow(),
    ).all()
    for c in overdue:
        items.append({
            "type": "overdue_commitment",
            "priority": 1,
            "contact_id": c.target_contact,
            "contact_name": c.target_contact,
            "message": f"Overdue: {c.parsed_commitment or c.raw_text}",
            "deadline": c.deadline.isoformat() if c.deadline else None,
            "commitment_id": c.id,
        })

    # 2. Neglected VIP contacts
    graph = get_relationship_graph(user_id)
    neglected = graph.find_neglected_relationships(days=7)
    for n in neglected:
        items.append({
            "type": "neglected_contact",
            "priority": 2,
            "contact_id": n.get("contact_id", ""),
            "contact_name": n.get("name", ""),
            "message": f"No contact for {n.get('days_since_contact', '?')} days",
            "importance": n.get("importance", 0),
        })

    # 3. Declining tone shifts
    tone_shifts = graph.detect_tone_shifts()
    for t in tone_shifts:
        if t.get("direction") == "declining":
            items.append({
                "type": "tone_decline",
                "priority": 3,
                "contact_id": t.get("contact_id", ""),
                "contact_name": t.get("name", ""),
                "message": f"Tone declining (delta: {t.get('delta', 0)})",
                "delta": t.get("delta", 0),
            })

    items.sort(key=lambda x: x["priority"])
    return items
