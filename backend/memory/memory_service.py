"""
Memory Service — Unified interface managing all memory types.

API: store(), recall(), search(), forget()
Orchestrates episodic, semantic, and relational memory subsystems.
Integrates with ChromaDB (vectors) and the event bus.
"""

import os
from pathlib import Path

import chromadb

from backend.events import EventBus, Event, EventType
from backend.memory.embeddings import EmbeddingService
from backend.memory.episodic import EpisodicMemory
from backend.memory.semantic import SemanticMemory


class MemoryService:
    """Unified memory facade — stores and retrieves across all memory types."""

    def __init__(
        self,
        data_dir: Path,
        event_bus: EventBus | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self._data_dir = data_dir
        self._event_bus = event_bus

        # Embedding pipeline
        self._embeddings = embedding_service or EmbeddingService()

        # ChromaDB — server mode if CHROMA_SERVER_URL is set, else embedded
        chroma_server_url = os.environ.get("CHROMA_SERVER_URL")
        if chroma_server_url:
            self._chroma = chromadb.HttpClient(host=chroma_server_url.rstrip("/").split("://")[-1].split(":")[0],
                                               port=int(chroma_server_url.rstrip("/").split(":")[-1] or 8000))
        else:
            chroma_path = str(data_dir / "chromadb")
            self._chroma = chromadb.PersistentClient(path=chroma_path)

        # Memory subsystems
        self.episodic = EpisodicMemory(self._chroma, self._embeddings)
        self.semantic = SemanticMemory(self._chroma, self._embeddings)

        # Knowledge graph loaded separately (see relational.py)
        self.graph = None

    def set_graph(self, graph):
        """Attach the knowledge graph after initialization."""
        self.graph = graph

    # ── Public API ───────────────────────────────────────────────────────────

    def store(self, text: str, memory_type: str = "episodic", metadata: dict | None = None):
        """
        Store a memory.
        memory_type: 'episodic' | 'semantic' | 'both'
        """
        if memory_type in ("episodic", "both"):
            self.episodic.store(text, metadata)
        if memory_type in ("semantic", "both"):
            self.semantic.store(text, metadata)

        if self._event_bus:
            self._event_bus.emit(Event(
                type=EventType.MEMORY_STORED,
                data={"text": text[:200], "memory_type": memory_type},
                source="memory_service",
            ))

    def store_conversation_turn(self, role: str, content: str, session_id: str = ""):
        """Store a conversation turn as episodic memory."""
        self.episodic.store(
            f"[{role}] {content}",
            metadata={
                "type": "conversation",
                "role": role,
                "session_id": session_id,
            },
        )

    def recall(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Recall relevant memories across all types.
        Returns merged + ranked results.
        """
        results = []

        # Search episodic
        episodic_results = self.episodic.search(query, n_results=n_results)
        for r in episodic_results:
            r["source"] = "episodic"
            results.append(r)

        # Search semantic
        semantic_results = self.semantic.search(query, n_results=n_results)
        for r in semantic_results:
            r["source"] = "semantic"
            results.append(r)

        # Search knowledge graph
        if self.graph:
            graph_results = self.graph.search(query, n_results=n_results)
            for r in graph_results:
                r["source"] = "relational"
                results.append(r)

        # Deduplicate by source + full text hash and sort by relevance
        seen_keys = set()
        unique = []
        for r in results:
            dedup_key = (r.get("source", ""), hash(r["text"]))
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                unique.append(r)
        unique.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        if self._event_bus:
            self._event_bus.emit(Event(
                type=EventType.MEMORY_RECALLED,
                data={"query": query[:200], "result_count": len(unique)},
                source="memory_service",
            ))

        return unique[:n_results]

    def search(self, query: str, memory_type: str = "all", n_results: int = 5) -> list[dict]:
        """
        Search a specific memory type.
        memory_type: 'episodic' | 'semantic' | 'all'
        """
        if memory_type == "episodic":
            return self.episodic.search(query, n_results)
        elif memory_type == "semantic":
            return self.semantic.search(query, n_results)
        else:
            return self.recall(query, n_results)

    def forget(self, query: str, memory_type: str = "semantic") -> int:
        """Remove memories matching the query. Returns count removed."""
        if memory_type == "semantic":
            return self.semantic.forget(query)
        return 0

    def get_status(self) -> dict:
        return {
            "embeddings": self._embeddings.get_status(),
            "episodic_count": self.episodic.count(),
            "semantic_count": self.semantic.count(),
            "graph_nodes": self.graph.node_count() if self.graph else 0,
        }
