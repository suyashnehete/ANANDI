"""
Episodic Memory — What happened. Timestamped records of conversations,
activities, and system events.

Storage: SQLite (structured) + ChromaDB (embedded summaries)
"""

from datetime import datetime


class EpisodicMemory:
    """Manages episodic memories in ChromaDB's episodic_memories collection."""

    COLLECTION = "episodic_memories"

    def __init__(self, chroma_client, embedding_service):
        self._client = chroma_client
        self._embeddings = embedding_service
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, text: str, metadata: dict | None = None):
        """Store an episodic memory (conversation turn, activity, event)."""
        meta = metadata or {}
        meta.setdefault("timestamp", datetime.now().isoformat())
        meta.setdefault("type", "conversation")
        doc_id = f"ep_{meta['timestamp']}_{self._collection.count()}"
        embedding = self._embeddings.embed(text)
        self._collection.add(
            ids=[doc_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[meta],
        )

    def store_batch(self, items: list[dict]):
        """Store multiple episodic memories. Each item: {text, metadata}."""
        if not items:
            return
        texts = [it["text"] for it in items]
        embeddings = self._embeddings.batch_embed(texts)
        ids = []
        metadatas = []
        base_count = self._collection.count()
        for i, it in enumerate(items):
            meta = it.get("metadata", {})
            meta.setdefault("timestamp", datetime.now().isoformat())
            meta.setdefault("type", "conversation")
            ids.append(f"ep_{meta['timestamp']}_{base_count + i}")
            metadatas.append(meta)
        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, query: str, n_results: int = 5, where: dict | None = None) -> list[dict]:
        """Semantic search over episodic memories."""
        query_embedding = self._embeddings.embed(query)
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(max(n_results, 1), 20),
        }
        if where:
            kwargs["where"] = where
        results = self._collection.query(**kwargs)
        memories = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            for doc, meta, dist in zip(docs, metas, dists):
                memories.append({
                    "text": doc,
                    "metadata": meta,
                    "relevance": 1.0 - dist,  # cosine distance → similarity
                })
        return memories

    def count(self) -> int:
        return self._collection.count()
