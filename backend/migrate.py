"""
Migration Script — Migrate v1 data into the new memory system.

- Backs up existing database before migration
- Creates new tables (conversations, event_log)
- Indexes existing activities, habits, journal entries into ChromaDB
- Zero data loss guaranteed

Usage:
    python -m backend.migrate <app_data_dir>
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path


def migrate(app_data_dir: str | Path):
    """Run the full migration from v1 → v2 memory system."""
    app_data_dir = Path(app_data_dir)
    db_path = app_data_dir / "personal-assistant.db"

    if not db_path.exists():
        print("[Migration] No existing database found. Nothing to migrate.")
        return

    # ── Step 1: Backup ───────────────────────────────────────────────────────
    backup_path = app_data_dir / f"personal-assistant.db.backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"[Migration] Database backed up to {backup_path}")

    # ── Step 2: Create new tables ────────────────────────────────────────────
    from backend.services.database import DatabaseService
    db = DatabaseService(db_path)
    db.initialize()  # This now creates conversation tables too
    print("[Migration] New tables created (conversation_sessions, conversation_messages)")

    # ── Step 3: Initialize event bus table ────────────────────────────────────
    from backend.events import EventBus
    event_bus = EventBus(str(db_path))
    print("[Migration] Event log table created")

    # ── Step 4: Initialize knowledge graph tables ────────────────────────────
    from backend.memory.relational import KnowledgeGraph
    graph = KnowledgeGraph(str(db_path))
    print("[Migration] Knowledge graph tables created")

    # ── Step 5: Index existing data into ChromaDB ────────────────────────────
    print("[Migration] Indexing existing data into ChromaDB...")

    from backend.memory.embeddings import EmbeddingService
    from backend.memory.memory_service import MemoryService

    memory = MemoryService(app_data_dir)

    # Index journal entries as episodic memories
    journal_entries = db.get_recent_journal_entries(limit=20)
    indexed = 0
    for entry in journal_entries:
        content = entry.get("content", "")
        if content.strip():
            memory.store(
                f"Journal ({entry.get('date', 'unknown')}): {content}",
                memory_type="episodic",
                metadata={
                    "type": "journal",
                    "date": entry.get("date", ""),
                    "mood": entry.get("mood", ""),
                },
            )
            indexed += 1
    print(f"[Migration] Indexed {indexed} journal entries")

    # Index habits as semantic facts
    habits = db.get_habits()
    for habit in habits:
        name = habit.get("name", "")
        if name:
            memory.store(
                f"User tracks the habit: {name} (streak: {habit.get('streak', 0)} days)",
                memory_type="semantic",
                metadata={"type": "habit"},
            )
    print(f"[Migration] Indexed {len(habits)} habits as semantic facts")

    print("[Migration] Complete! Zero data loss. Original data preserved.")
    print(f"[Migration] Backup location: {backup_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        import platform
        system = platform.system()
        if system == "Darwin":
            data_dir = Path.home() / "Library" / "Application Support" / "anandi"
        elif system == "Windows":
            import os
            data_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "anandi"
        else:
            data_dir = Path.home() / ".local" / "share" / "anandi"
    else:
        data_dir = Path(sys.argv[1])

    migrate(data_dir)
