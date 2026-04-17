"""
RAG Pipeline — Query → Embed → Search ChromaDB → Re-rank → Return.

Used by ContextEngine to inject relevant memories into LLM context.
"""


class RAGPipeline:
    """
    Retrieval-augmented generation pipeline.
    On each chat: embed user query → search ChromaDB for top-N → return
    formatted context for injection into Tier 3.
    """

    def __init__(self, memory_service):
        self._memory = memory_service

    def retrieve(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Retrieve relevant memories for a query.
        Returns list of {text, source, relevance, metadata}.
        """
        results = self._memory.recall(query, n_results=n_results)
        # Filter low-relevance noise
        return [r for r in results if r.get("relevance", 0) >= 0.25]

    def format_for_context(self, query: str, n_results: int = 5, max_tokens: int = 2000) -> str:
        """
        Retrieve and format memories as a context string.
        Respects approximate token budget.
        """
        results = self.retrieve(query, n_results)
        if not results:
            return ""

        lines = []
        char_budget = max_tokens * 4  # rough chars-to-tokens
        chars_used = 0
        for r in results:
            text = r.get("text", "")
            source = r.get("source", "memory")
            line = f"[{source}] {text}"
            if chars_used + len(line) > char_budget:
                break
            lines.append(line)
            chars_used += len(line)

        if not lines:
            return ""
        return "\n".join(lines)
