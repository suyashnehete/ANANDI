import json
import os
import platform
import sys
from pathlib import Path

import webview

from backend.api import API
from backend.context.context_engine import ContextEngine
from backend.events import EventBus
from backend.memory.consolidation import ConsolidationService
from backend.memory.embeddings import EmbeddingService
from backend.memory.memory_service import MemoryService
from backend.memory.relational import KnowledgeGraph
from backend.services.calendar_service import CalendarService
from backend.services.database import DatabaseService
from backend.services.ollama import OllamaService
from backend.services.scheduler import SchedulerService


def get_app_data_dir() -> Path:
    # Allow override via env var (Docker / custom deployments)
    env_dir = os.environ.get('ANANDI_DATA_DIR')
    if env_dir:
        return Path(env_dir)
    system = platform.system()
    if system == 'Darwin':
        return Path.home() / 'Library' / 'Application Support' / 'anandi'
    elif system == 'Windows':
        return Path(os.environ.get('APPDATA', str(Path.home()))) / 'anandi'
    else:
        return Path.home() / '.local' / 'share' / 'anandi'


def main():
    app_data_dir = get_app_data_dir()
    app_data_dir.mkdir(parents=True, exist_ok=True)

    db = DatabaseService(app_data_dir / 'personal-assistant.db')
    db.initialize()

    # ── Event Bus ────────────────────────────────────────────────────────────
    event_bus = EventBus(str(app_data_dir / 'personal-assistant.db'))

    # ── Memory System ────────────────────────────────────────────────────────
    embedding_service = EmbeddingService()
    memory = MemoryService(app_data_dir, event_bus, embedding_service)

    # Knowledge Graph
    graph = KnowledgeGraph(str(app_data_dir / 'personal-assistant.db'))
    memory.set_graph(graph)

    # ── Context Engine ───────────────────────────────────────────────────────
    context_engine = ContextEngine(memory_service=memory, database=db)

    # ── LLM Service ──────────────────────────────────────────────────────────
    ollama = OllamaService()
    ollama.set_context_engine(context_engine)
    ollama.set_database(db)

    # Create a conversation session for this app launch
    session_id = db.create_session()
    ollama.set_session(session_id)

    # ── Consolidation ────────────────────────────────────────────────────────
    consolidation = ConsolidationService(memory, db, ollama, event_bus)

    calendar = CalendarService(app_data_dir)
    calendar.initialize()

    def send_notification(title: str, body: str):
        # Desktop OS notification
        try:
            from plyer import notification as plyer_notification
            plyer_notification.notify(
                title=title,
                message=body,
                app_name='ANANDI',
                timeout=8
            )
        except Exception:
            pass

        # In-app push via JS callback
        if webview.windows:
            payload = json.dumps({'title': title, 'body': body})
            webview.windows[0].evaluate_js(
                f'window.__onNotification && window.__onNotification({payload})'
            )

    scheduler = SchedulerService(ollama, calendar, db, send_notification)
    scheduler.set_consolidation(consolidation)

    api = API(db, ollama, calendar, scheduler, app_data_dir,
              event_bus=event_bus, memory=memory)

    # Apply stored settings to services before the window opens
    stored = api._get_stored_settings()
    api._save_settings_to_disk(stored)
    scheduler.update_schedule(stored)

    window = webview.create_window(
        'ANANDI — Autonomous Natural Agent for Navigating Daily Intelligence',
        'frontend/index.html',
        js_api=api,
        width=1400,
        height=900,
        min_size=(900, 600),
        background_color='#0a0a0f'
    )

    def on_loaded():
        scheduler.start()

    webview.start(on_loaded, debug='--dev' in sys.argv)


if __name__ == '__main__':
    main()
