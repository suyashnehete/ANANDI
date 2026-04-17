"""
End-of-Day Consolidation — Background job that processes the day's
conversations into durable memories.

1. Summarize day's conversations into episodic chunks
2. Extract facts into semantic memory
3. Extract entities into knowledge graph
4. Embed unembedded messages
"""

import threading
from datetime import datetime

from backend.events import EventBus, Event, EventType


class ConsolidationService:
    """
    Runs consolidation as a scheduled background job.
    Called by scheduler at the configured evening reflection time.
    """

    def __init__(self, memory_service, database, ollama, event_bus: EventBus | None = None):
        self._memory = memory_service
        self._db = database
        self._ollama = ollama
        self._event_bus = event_bus
        self._lock = threading.Lock()

    def run_consolidation(self):
        """
        Full end-of-day consolidation. Thread-safe — only one runs at a time.
        """
        if not self._lock.acquire(blocking=False):
            print("[Consolidation] Already running, skipping")
            return
        try:
            print("[Consolidation] Starting end-of-day consolidation...")
            self._embed_new_messages()
            self._summarize_today()
            self._extract_facts()
            self._extract_entities()
            print("[Consolidation] Complete")

            if self._event_bus:
                self._event_bus.emit(Event(
                    type=EventType.CONSOLIDATION_COMPLETED,
                    data={"date": datetime.now().date().isoformat()},
                    source="consolidation",
                ))
        except Exception as e:
            print(f"[Consolidation] Error: {e}")
        finally:
            self._lock.release()

    def _embed_new_messages(self):
        """Embed conversation messages that haven't been embedded yet."""
        messages = self._db.get_unembedded_messages(limit=200)
        if not messages:
            return

        items = []
        msg_ids = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content.strip():
                continue
            items.append({
                "text": f"[{role}] {content}",
                "metadata": {
                    "type": "conversation",
                    "role": role,
                    "session_id": msg.get("session_id", ""),
                    "timestamp": msg.get("timestamp", ""),
                },
            })
            msg_ids.append(msg["id"])

        if items:
            self._memory.episodic.store_batch(items)
            self._db.mark_messages_embedded(msg_ids)
            print(f"[Consolidation] Embedded {len(items)} messages")

    def _summarize_today(self):
        """Summarize today's conversations into an episodic chunk."""
        conversations = self._db.get_today_conversations()
        if len(conversations) < 4:
            return  # Not enough to summarize

        # Build conversation text for summarization
        conv_text = ""
        for msg in conversations:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conv_text += f"{role}: {content}\n"

        if len(conv_text) < 100:
            return

        # Truncate if very long
        if len(conv_text) > 3000:
            conv_text = conv_text[:3000] + "\n[truncated]"

        try:
            summary = self._ollama.chat(
                f"Summarize the key points from today's conversations in 3-5 bullet points. "
                f"Focus on: decisions made, tasks discussed, facts learned, mood/feelings expressed.\n\n"
                f"{conv_text}",
                {},
            )
            today = datetime.now().date().isoformat()
            self._memory.store(
                f"Daily summary ({today}): {summary}",
                memory_type="episodic",
                metadata={"type": "daily_summary", "date": today},
            )
            print(f"[Consolidation] Created daily summary")
        except Exception as e:
            print(f"[Consolidation] Summary error: {e}")

    def _extract_facts(self):
        """Extract semantic facts from today's conversations."""
        conversations = self._db.get_today_conversations()
        if len(conversations) < 2:
            return

        user_messages = [
            msg["content"] for msg in conversations
            if msg.get("role") == "user" and msg.get("content")
        ]
        if not user_messages:
            return

        # Limit to avoid overwhelming the LLM
        msgs_text = "\n".join(user_messages[:20])
        if len(msgs_text) > 2000:
            msgs_text = msgs_text[:2000]

        try:
            facts_str = self._ollama.chat(
                "Extract any factual information the user revealed about themselves "
                "from these messages. List only concrete facts (preferences, personal info, "
                "work details, routines) — one per line. If no facts, respond with 'none'.\n\n"
                f"{msgs_text}",
                {},
            )
            if facts_str and facts_str.strip().lower() != "none":
                for line in facts_str.strip().split("\n"):
                    line = line.strip().lstrip("•-* ")
                    if line and len(line) > 10:
                        self._memory.store(line, memory_type="semantic", metadata={"type": "extracted_fact"})
                print(f"[Consolidation] Extracted semantic facts")
        except Exception as e:
            print(f"[Consolidation] Fact extraction error: {e}")

    def _extract_entities(self):
        """Extract entities from today's conversations into the knowledge graph."""
        if not self._memory.graph:
            return

        conversations = self._db.get_today_conversations()
        for msg in conversations:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    self._memory.graph.extract_and_store(content)
        print(f"[Consolidation] Entity extraction complete")
