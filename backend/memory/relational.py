"""
Relational Memory — Knowledge Graph v1.

NetworkX graph for entities (people, projects, places) with relationship edges.
Regex-based NER for v1. Persisted to SQLite.
"""

import json
import re
import sqlite3
import threading
from pathlib import Path

import networkx as nx


# ── Regex-based NER (v1) ────────────────────────────────────────────────────

# Patterns for extracting entities from conversation text
_PATTERNS = {
    "person": [
        # "my sister Priya", "my friend Rahul", "my manager John"
        r"\bmy\s+(sister|brother|friend|colleague|manager|boss|wife|husband|"
        r"mother|father|mom|dad|partner|mentor|teacher|roommate|cousin)\s+([A-Z][a-z]+)",
        # Stand-alone capitalized names after certain verbs
        r"\b(?:called|named|know|met|talked to|messaged|emailed)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ],
    "project": [
        # "working on personal-assistant", "the weather-api project"
        r"\b(?:project|repo|repository|codebase)\s+(?:called\s+)?([a-zA-Z0-9_-]+)",
        r"\bworking on\s+([a-zA-Z0-9_-]+)",
    ],
    "place": [
        # "in Mumbai", "at Bangalore", "from Delhi"
        r"\b(?:in|at|from|to|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
    ],
}


def extract_entities(text: str) -> list[dict]:
    """
    Extract named entities from text using regex patterns.
    Returns list of {type, name, relationship (optional)}.
    """
    entities = []
    seen = set()

    for entity_type, patterns in _PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                if entity_type == "person" and len(groups) >= 2:
                    relationship = groups[0]
                    name = groups[1]
                    key = (entity_type, name.lower())
                    if key not in seen:
                        seen.add(key)
                        entities.append({
                            "type": entity_type,
                            "name": name,
                            "relationship": relationship,
                        })
                elif len(groups) >= 1:
                    name = groups[-1]
                    # Filter out common words that aren't entities
                    if name.lower() in _STOPWORDS:
                        continue
                    key = (entity_type, name.lower())
                    if key not in seen:
                        seen.add(key)
                        entities.append({"type": entity_type, "name": name})

    return entities


_STOPWORDS = {
    "the", "this", "that", "what", "when", "where", "which", "how",
    "can", "could", "would", "should", "will", "shall", "may", "might",
    "have", "has", "had", "been", "being", "was", "were", "are",
    "not", "but", "and", "for", "with", "about", "just", "like",
    "today", "tomorrow", "yesterday", "morning", "evening", "night",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "good", "great", "bad", "thanks", "please", "sure", "okay",
    "yes", "hey", "hi", "hello", "bye", "time", "here", "there",
    "done", "take", "make", "let", "also", "well", "need",
}


# ── Knowledge Graph ─────────────────────────────────────────────────────────

class KnowledgeGraph:
    """
    In-memory NetworkX graph persisted to SQLite.

    Node types: person, project, place, app, file, service, goal
    Edge types: KNOWS, WORKS_ON, USES, LOCATED_AT, RELATED_TO, MENTIONED_IN
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._graph = nx.DiGraph()
        self._lock = threading.Lock()
        self._local = threading.local()
        self._init_db()
        self._load_from_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection"):
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
        return self._local.connection

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS graph_edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relationship TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                PRIMARY KEY (source, target, relationship)
            );
        """)
        self._conn.commit()

    def _load_from_db(self):
        """Load graph from SQLite into NetworkX."""
        conn = self._conn
        for row in conn.execute("SELECT * FROM graph_nodes").fetchall():
            props = json.loads(row["properties"])
            self._graph.add_node(
                row["id"],
                type=row["type"],
                name=row["name"],
                **props,
            )
        for row in conn.execute("SELECT * FROM graph_edges").fetchall():
            props = json.loads(row["properties"])
            self._graph.add_edge(
                row["source"],
                row["target"],
                relationship=row["relationship"],
                **props,
            )

    def _node_id(self, entity_type: str, name: str) -> str:
        return f"{entity_type}:{name.lower().replace(' ', '_')}"

    # ── Mutations ────────────────────────────────────────────────────

    def add_entity(self, entity_type: str, name: str, properties: dict | None = None):
        """Add or update an entity node."""
        node_id = self._node_id(entity_type, name)
        props = properties or {}
        with self._lock:
            self._graph.add_node(node_id, type=entity_type, name=name, **props)
            self._conn.execute(
                "INSERT OR REPLACE INTO graph_nodes (id, type, name, properties) VALUES (?, ?, ?, ?)",
                [node_id, entity_type, name, json.dumps(props, default=str)],
            )
            self._conn.commit()

    def add_relationship(self, source_type: str, source_name: str,
                         target_type: str, target_name: str,
                         relationship: str, properties: dict | None = None):
        """Add a relationship edge between two entities."""
        src_id = self._node_id(source_type, source_name)
        tgt_id = self._node_id(target_type, target_name)
        props = properties or {}
        with self._lock:
            # Ensure both nodes exist
            if not self._graph.has_node(src_id):
                self.add_entity(source_type, source_name)
            if not self._graph.has_node(tgt_id):
                self.add_entity(target_type, target_name)
            self._graph.add_edge(src_id, tgt_id, relationship=relationship, **props)
            self._conn.execute(
                "INSERT OR REPLACE INTO graph_edges (source, target, relationship, properties) "
                "VALUES (?, ?, ?, ?)",
                [src_id, tgt_id, relationship, json.dumps(props, default=str)],
            )
            self._conn.commit()

    def extract_and_store(self, text: str):
        """Extract entities from text and add to graph."""
        entities = extract_entities(text)
        for ent in entities:
            props = {}
            if ent.get("relationship"):
                props["relationship_to_user"] = ent["relationship"]
            self.add_entity(ent["type"], ent["name"], props)
            # Link to user node
            if ent.get("relationship"):
                self.add_relationship(
                    "person", "user",
                    ent["type"], ent["name"],
                    ent["relationship"],
                )

    # ── Queries ──────────────────────────────────────────────────────

    def get_entity(self, entity_type: str, name: str) -> dict | None:
        node_id = self._node_id(entity_type, name)
        if not self._graph.has_node(node_id):
            return None
        data = dict(self._graph.nodes[node_id])
        data["id"] = node_id
        data["connections"] = []
        for _, target, edge_data in self._graph.edges(node_id, data=True):
            target_data = self._graph.nodes.get(target, {})
            data["connections"].append({
                "target": target,
                "name": target_data.get("name", target),
                "relationship": edge_data.get("relationship", "RELATED_TO"),
            })
        return data

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search graph nodes by name match (simple substring for v1)."""
        query_lower = query.lower()
        results = []
        for node_id, data in self._graph.nodes(data=True):
            name = data.get("name", "")
            if query_lower in name.lower() or query_lower in node_id:
                node_info = dict(data)
                node_info["id"] = node_id
                # Get connections
                connections = []
                for _, target, edge_data in self._graph.edges(node_id, data=True):
                    target_data = self._graph.nodes.get(target, {})
                    connections.append({
                        "target": target_data.get("name", target),
                        "relationship": edge_data.get("relationship", "RELATED_TO"),
                    })
                conn_text = "; ".join(
                    f"{c['relationship']} → {c['target']}" for c in connections
                )
                text = f"{data.get('type', 'entity')}: {name}"
                if conn_text:
                    text += f" ({conn_text})"
                results.append({
                    "text": text,
                    "relevance": 0.8 if query_lower == name.lower() else 0.5,
                    "metadata": {"type": "graph_entity", "node_id": node_id},
                })
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:n_results]

    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def get_all_entities(self, entity_type: str | None = None) -> list[dict]:
        """List all entities, optionally filtered by type."""
        results = []
        for node_id, data in self._graph.nodes(data=True):
            if entity_type and data.get("type") != entity_type:
                continue
            info = dict(data)
            info["id"] = node_id
            results.append(info)
        return results
