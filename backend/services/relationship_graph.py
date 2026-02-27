"""NetworkX relationship graph service — singleton per user"""

import networkx as nx
import json
from datetime import datetime
from typing import Optional

# In-memory graph store (per user)
_user_graphs: dict[str, "RelationshipGraph"] = {}


def get_relationship_graph(user_id: str) -> "RelationshipGraph":
    if user_id not in _user_graphs:
        _user_graphs[user_id] = RelationshipGraph(user_id)
    return _user_graphs[user_id]


class RelationshipGraph:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.G = nx.DiGraph()
        self.G.add_node(user_id, name="You", type="self", importance=1.0)

    def add_or_update_contact(self, contact_id: str, data: dict):
        self.G.add_node(contact_id, **{
            "name": data.get("name", contact_id),
            "email": data.get("email", ""),
            "relationship_type": data.get("type", "colleague"),
            "importance_score": data.get("importance", 0.5),
            "preferred_channel": data.get("channel", "email"),
            "preferred_language": data.get("language", "en"),
            "tone": data.get("tone", "professional"),
            "formality_score": data.get("formality", 0.5),
            "greeting_style": data.get("greeting", "Hi"),
            "sign_off_style": data.get("sign_off", "Best"),
            "uses_emoji": data.get("emoji", False),
            "avg_message_length": data.get("avg_length", 50),
        })

        if not self.G.has_edge(self.user_id, contact_id):
            self.G.add_edge(self.user_id, contact_id, **{
                "interaction_count": 0,
                "last_interaction": None,
                "sentiment_scores": [],
                "avg_response_time": 0,
            })

    def record_interaction(self, contact_id: str, sentiment: float,
                           response_time: float = 0, channel: str = "email",
                           language: str = "en"):
        if not self.G.has_node(contact_id):
            self.add_or_update_contact(contact_id, {"name": contact_id})

        if not self.G.has_edge(self.user_id, contact_id):
            self.G.add_edge(self.user_id, contact_id, interaction_count=0,
                           sentiment_scores=[], avg_response_time=0, last_interaction=None)

        edge = self.G[self.user_id][contact_id]
        edge["interaction_count"] = edge.get("interaction_count", 0) + 1
        edge["last_interaction"] = datetime.now().isoformat()

        sentiments = edge.get("sentiment_scores", [])
        sentiments.append(sentiment)
        edge["sentiment_scores"] = sentiments[-10:]

        count = edge["interaction_count"]
        old_avg = edge.get("avg_response_time", 0)
        edge["avg_response_time"] = ((old_avg * (count - 1)) + response_time) / count

    def detect_tone_shifts(self, threshold: float = 0.3) -> list:
        alerts = []
        for u, v, data in self.G.edges(data=True):
            sentiments = data.get("sentiment_scores", [])
            if len(sentiments) < 3:
                continue
            recent = sum(sentiments[-3:]) / 3
            historical = sum(sentiments) / len(sentiments)
            delta = historical - recent
            if abs(delta) > threshold:
                name = self.G.nodes[v].get("name", v)
                direction = "declining" if delta > 0 else "improving"
                alerts.append({
                    "contact": name, "contact_id": v,
                    "delta": round(delta, 2), "direction": direction,
                    "recent_avg": round(recent, 2),
                    "historical_avg": round(historical, 2),
                })
        return sorted(alerts, key=lambda x: abs(x["delta"]), reverse=True)

    def find_neglected_relationships(self, days: int = 7) -> list:
        neglected = []
        cutoff = datetime.now().timestamp() - (days * 86400)
        for node, data in self.G.nodes(data=True):
            if node == self.user_id or data.get("importance_score", 0) < 0.6:
                continue
            last = None
            for u, v, ed in self.G.edges(data=True):
                if v == node and ed.get("last_interaction"):
                    try:
                        ts = datetime.fromisoformat(ed["last_interaction"]).timestamp()
                        if last is None or ts > last:
                            last = ts
                    except (ValueError, TypeError):
                        pass
            if last and last < cutoff:
                days_ago = int((datetime.now().timestamp() - last) / 86400)
                neglected.append({
                    "contact": data.get("name", node), "contact_id": node,
                    "importance": data.get("importance_score"),
                    "days_since_contact": days_ago,
                    "channel": data.get("preferred_channel"),
                })
        return sorted(neglected, key=lambda x: x["importance"], reverse=True)

    def get_key_contacts(self, top_n: int = 10) -> list:
        if len(self.G.nodes) < 2:
            return []
        centrality = nx.degree_centrality(self.G)
        contacts = []
        for node, data in self.G.nodes(data=True):
            if node == self.user_id:
                continue
            contacts.append({
                "contact": data.get("name", node), "contact_id": node,
                "centrality": round(centrality.get(node, 0), 3),
                "importance": data.get("importance_score", 0),
                "combined": round(centrality.get(node, 0) * 0.4 + data.get("importance_score", 0) * 0.6, 3),
                "type": data.get("relationship_type"),
            })
        return sorted(contacts, key=lambda x: x["combined"], reverse=True)[:top_n]

    def get_communication_clusters(self) -> list:
        undirected = self.G.to_undirected()
        if len(undirected.nodes) < 3:
            return []
        try:
            communities = nx.community.greedy_modularity_communities(undirected)
            return [
                {"cluster_id": i, "members": [self.G.nodes[n].get("name", n) for n in c if n != self.user_id], "size": len(c) - (1 if self.user_id in c else 0)}
                for i, c in enumerate(communities) if len(c) > 1
            ]
        except Exception:
            return []

    def export_for_frontend(self) -> dict:
        nodes = []
        for node, data in self.G.nodes(data=True):
            sentiment = 0.5
            for u, v, ed in self.G.edges(data=True):
                if v == node and ed.get("sentiment_scores"):
                    sentiment = ed["sentiment_scores"][-1]
                    break
            nodes.append({
                "id": node, "name": data.get("name", node),
                "type": data.get("relationship_type", "self" if node == self.user_id else "unknown"),
                "importance": data.get("importance_score", 0.5),
                "language": data.get("preferred_language", "en"),
                "channel": data.get("preferred_channel", ""),
                "sentiment": sentiment,
            })
        links = []
        for u, v, data in self.G.edges(data=True):
            links.append({
                "source": u, "target": v,
                "weight": data.get("interaction_count", 1),
                "sentiment": data.get("sentiment_scores", [0.5])[-1] if data.get("sentiment_scores") else 0.5,
                "last_interaction": data.get("last_interaction"),
            })
        return {"nodes": nodes, "links": links}

    def to_json(self) -> str:
        return json.dumps(nx.node_link_data(self.G))

    def from_json(self, data: str):
        self.G = nx.node_link_graph(json.loads(data))
