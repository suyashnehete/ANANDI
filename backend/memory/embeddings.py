"""
Embedding Pipeline — Local embedding via Ollama (nomic-embed-text) with
sentence-transformers fallback.

Provides embed / batch_embed / similarity_search wrappers.
Lazy-loads the model on first use.
"""

import os
from typing import Sequence

import requests


class EmbeddingService:
    """
    Primary: nomic-embed-text via Ollama (768-dim, Metal-accelerated).
    Fallback: sentence-transformers all-MiniLM-L6-v2 (384-dim) if Ollama unavailable.
    """

    def __init__(self, ollama_base_url: str | None = None):
        self._ollama_url = ollama_base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        )
        self._model = "nomic-embed-text"
        self._dimensions: int | None = None
        self._fallback_model = None  # lazy-loaded sentence-transformers
        self._use_fallback = False
        self._ready = False

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            # Warm up to determine dimensions
            self._warm_up()
        return self._dimensions or 768

    def _warm_up(self):
        """Probe Ollama to confirm the embedding model is available."""
        if self._ready:
            return
        try:
            vec = self._ollama_embed("test")
            self._dimensions = len(vec)
            self._use_fallback = False
            self._ready = True
        except Exception:
            print("[Embeddings] Ollama embedding unavailable, trying sentence-transformers fallback")
            try:
                self._init_fallback()
                self._use_fallback = True
                self._ready = True
            except Exception as e:
                print(f"[Embeddings] Fallback also unavailable: {e}")
                self._dimensions = 768
                self._ready = True

    def _ollama_embed(self, text: str) -> list[float]:
        resp = requests.post(
            f"{self._ollama_url}/api/embed",
            json={"model": self._model, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns {"embeddings": [[...]]}
        return data["embeddings"][0]

    def _init_fallback(self):
        from sentence_transformers import SentenceTransformer

        self._fallback_model = SentenceTransformer("all-MiniLM-L6-v2")
        self._dimensions = 384

    def embed(self, text: str) -> list[float]:
        """Embed a single text string. Returns a float vector."""
        if not self._ready:
            self._warm_up()
        if self._use_fallback and self._fallback_model is not None:
            return self._fallback_model.encode(text).tolist()
        try:
            return self._ollama_embed(text)
        except Exception:
            # If Ollama fails at runtime, try fallback
            if self._fallback_model is None:
                try:
                    self._init_fallback()
                    self._use_fallback = True
                except Exception:
                    pass
            if self._fallback_model is not None:
                self._use_fallback = True
                return self._fallback_model.encode(text).tolist()
            raise

    def batch_embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed multiple texts. Returns list of vectors."""
        if not self._ready:
            self._warm_up()
        if self._use_fallback and self._fallback_model is not None:
            return self._fallback_model.encode(list(texts)).tolist()
        # Ollama /api/embed supports multiple inputs
        try:
            resp = requests.post(
                f"{self._ollama_url}/api/embed",
                json={"model": self._model, "input": list(texts)},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]
        except Exception:
            # Fall back to one-by-one
            return [self.embed(t) for t in texts]

    def get_status(self) -> dict:
        return {
            "ready": self._ready,
            "model": "sentence-transformers/all-MiniLM-L6-v2" if self._use_fallback else self._model,
            "dimensions": self.dimensions,
            "backend": "sentence-transformers" if self._use_fallback else "ollama",
        }
