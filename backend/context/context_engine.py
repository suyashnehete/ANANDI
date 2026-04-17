"""
Context Engine v1 — Assembles the LLM context window from multiple tiers.

Tier 0: System prompt + agent identity (always present)
Tier 1: CAG hot cache — current time, user profile, today's stats, active tasks
Tier 3: RAG retrieved — semantically relevant memories from ChromaDB
Tier 4: Conversation tail — recent messages not already in cache

(Tier 2 — CAG warm cache — added in later phases)
"""

from datetime import datetime, timezone, timedelta

from backend.prompts import SYSTEM_PROMPT

IST = timezone(timedelta(hours=5, minutes=30))


class ContextEngine:
    """
    Builds the messages array for the LLM from multiple context tiers.
    """

    def __init__(self, memory_service=None, database=None):
        self._memory = memory_service
        self._db = database
        self._rag = None
        if memory_service:
            from backend.context.rag_pipeline import RAGPipeline
            self._rag = RAGPipeline(memory_service)

    def build_messages(
        self,
        user_message: str,
        context: dict,
        conversation_history: list[dict] | None = None,
    ) -> list[dict]:
        """
        Assemble full message list for LLM.

        Returns: list of {role, content} dicts ready for Ollama.
        """
        messages = []

        # ── Tier 0: System prompt ────────────────────────────────────────────
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

        # ── Tier 1: CAG hot cache ────────────────────────────────────────────
        hot_context = self._build_hot_context(context)
        if hot_context:
            messages.append({"role": "system", "content": hot_context})

        # ── Tier 3: RAG retrieved memories ───────────────────────────────────
        rag_context = self._build_rag_context(user_message)
        if rag_context:
            messages.append({"role": "system", "content": rag_context})

        # ── Tier 4: Conversation tail ────────────────────────────────────────
        if conversation_history:
            # Use last N messages from persistent history
            tail = conversation_history[-20:]
            for msg in tail:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        # ── Current user message ─────────────────────────────────────────────
        messages.append({"role": "user", "content": user_message})

        return messages

    def _build_hot_context(self, context: dict) -> str:
        """Tier 1 — Always-loaded real-time context."""
        parts = []
        now_ist = datetime.now(IST)
        parts.append(f"Current time: {now_ist.strftime('%I:%M %p')} IST, {now_ist.strftime('%A %d %B %Y')}")

        stats = context.get("stats")
        if stats:
            stat_parts = [f"{stats.get('water', 0)} glasses of water", f"{stats.get('breaks', 0)} breaks"]
            if stats.get("sleep", 0) > 0:
                stat_parts.append(f"{stats['sleep']} hours of sleep")
            if stats.get("mood"):
                stat_parts.append(f"mood {stats['mood']}")
            if stats.get("exercise", 0) > 0:
                stat_parts.append(f"{stats['exercise']} exercise sessions")
            parts.append(f"Today so far: {', '.join(stat_parts)}")

        schedule = context.get("schedule", [])
        if schedule:
            event_strs = [f"{e['time']}: {e['title']}" for e in schedule]
            parts.append(f"Today's schedule: {', '.join(event_strs)}")

        habits = context.get("habits", [])
        if habits:
            habit_strs = [
                f"{h['name']} ({'done' if h.get('completed') else 'pending'}, "
                f"{h.get('streak', 0)}-day streak)"
                for h in habits
            ]
            parts.append(f"Active habits: {', '.join(habit_strs)}")

        recent_journal = context.get("recentJournal", [])
        if recent_journal:
            latest = recent_journal[0]
            content = latest.get("content", "")
            truncated = content[:100] + ("..." if len(content) > 100 else "")
            parts.append(f"Latest reflection: \"{truncated}\"")

        profile = context.get("profile", {})
        if profile:
            profile_parts = []
            if profile.get("displayName"):
                profile_parts.append(f"preferred name: {profile['displayName']}")
            if profile.get("currentFocus"):
                profile_parts.append(f"current focus: {profile['currentFocus']}")
            if profile.get("coachingStyle"):
                profile_parts.append(f"coaching style: {profile['coachingStyle']}")
            if profile.get("supportNotes"):
                profile_parts.append(f"support notes: {profile['supportNotes']}")
            if profile_parts:
                parts.append(f"User profile: {', '.join(profile_parts)}")

        if not parts:
            return ""
        return "[Real-time context]\n" + "\n".join(f"- {p}" for p in parts)

    def _build_rag_context(self, query: str) -> str:
        """Tier 3 — Retrieve relevant memories via RAG pipeline."""
        if not self._rag:
            return ""
        try:
            formatted = self._rag.format_for_context(query, n_results=5, max_tokens=2000)
            if not formatted:
                return ""
            return "[Relevant memories]\n" + formatted
        except Exception as e:
            print(f"[ContextEngine] RAG retrieval error: {e}")
            return ""
