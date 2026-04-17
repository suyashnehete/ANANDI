import json
from datetime import date, datetime
from pathlib import Path

import webview

DEFAULT_SETTINGS = {
    'wakeUpTime': '07:00',
    'morningOverviewTime': '07:30',
    'breakfastTime': '08:00',
    'lunchTime': '13:00',
    'dinnerTime': '20:00',
    'eveningReflectionTime': '21:00',
    'bedTime': '23:00',
    'workStart': '09:00',
    'workEnd': '18:00',
    'quietHoursStart': '22:30',
    'quietHoursEnd': '07:00',
    'breakInterval': 60,
    'waterInterval': 120,
    'postureInterval': 90,
    'waterGoal': 8,
    'weekendReminders': False,
    'morningOverviewEnabled': True,
    'eveningReflectionEnabled': True,
    'mealRemindersEnabled': True,
    'breakRemindersEnabled': True,
    'waterRemindersEnabled': True,
    'postureRemindersEnabled': True,
    'displayName': '',
    'currentFocus': '',
    'coachingStyle': 'balanced',
    'supportNotes': '',
    'model': 'llama3.2:3b',
    'voiceName': ''
}

TIME_SETTING_KEYS = [
    'wakeUpTime', 'morningOverviewTime', 'breakfastTime', 'lunchTime',
    'dinnerTime', 'eveningReflectionTime', 'bedTime', 'workStart', 'workEnd',
    'quietHoursStart', 'quietHoursEnd'
]

NUMBER_SETTING_RULES = {
    'breakInterval': {'fallback': 60, 'min': 15, 'max': 180},
    'waterInterval': {'fallback': 120, 'min': 30, 'max': 300},
    'postureInterval': {'fallback': 90, 'min': 30, 'max': 180},
    'waterGoal': {'fallback': 8, 'min': 1, 'max': 20}
}

BOOLEAN_SETTING_KEYS = [
    'weekendReminders', 'morningOverviewEnabled', 'eveningReflectionEnabled',
    'mealRemindersEnabled', 'breakRemindersEnabled', 'waterRemindersEnabled',
    'postureRemindersEnabled'
]


def _normalize_time(value, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    parts = value.split(':')
    if len(parts) < 2:
        return fallback
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return fallback
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return fallback
    return f'{hour:02d}:{minute:02d}'


def _normalize_number(value, rules: dict):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return rules['fallback']
    return min(max(parsed, rules['min']), rules['max'])


def normalize_settings(settings: dict) -> dict:
    merged = {**DEFAULT_SETTINGS, **settings}
    normalized = dict(merged)
    for key in TIME_SETTING_KEYS:
        normalized[key] = _normalize_time(merged.get(key), DEFAULT_SETTINGS[key])
    for key, rules in NUMBER_SETTING_RULES.items():
        normalized[key] = _normalize_number(merged.get(key), rules)
    for key in BOOLEAN_SETTING_KEYS:
        normalized[key] = bool(merged.get(key))
    normalized['model'] = (merged.get('model') or '').strip() or DEFAULT_SETTINGS['model']
    for key in ('displayName', 'currentFocus', 'supportNotes', 'voiceName'):
        val = merged.get(key, '')
        normalized[key] = val.strip() if isinstance(val, str) else DEFAULT_SETTINGS.get(key, '')
    normalized['coachingStyle'] = (merged.get('coachingStyle') or 'balanced').strip() or 'balanced'
    return normalized


class API:
    def __init__(self, db, ollama, calendar, scheduler, app_data_dir: Path,
                 event_bus=None, memory=None):
        self._db = db
        self._ollama = ollama
        self._calendar = calendar
        self._scheduler = scheduler
        self._settings_path = app_data_dir / 'settings.json'
        self._event_bus = event_bus
        self._memory = memory

    def _get_stored_settings(self) -> dict:
        try:
            if self._settings_path.exists():
                return normalize_settings(json.loads(self._settings_path.read_text()))
        except Exception:
            pass
        return normalize_settings({})

    def _save_settings_to_disk(self, settings: dict):
        self._settings_path.write_text(json.dumps(settings, indent=2))

    def _build_profile_context(self, settings: dict) -> dict:
        return {
            'displayName': settings.get('displayName', ''),
            'currentFocus': settings.get('currentFocus', ''),
            'coachingStyle': settings.get('coachingStyle', 'balanced'),
            'supportNotes': settings.get('supportNotes', '')
        }

    # ── Chat ────────────────────────────────────────────────────────────────

    def chat(self, message):
        try:
            stats = self._db.get_today_stats()
            schedule = self._calendar.get_today_events()
            habits = self._db.get_habits()
            recent_journal = self._db.get_recent_journal_entries(2)
            settings = self._get_stored_settings()

            # Emit user message event
            if self._event_bus:
                from backend.events import Event, EventType
                self._event_bus.emit(Event(
                    type=EventType.USER_MESSAGE,
                    data={'message': message[:500]},
                    source='api',
                ))

            response = self._ollama.chat(message, {
                'stats': stats,
                'schedule': schedule,
                'habits': habits,
                'recentJournal': recent_journal,
                'profile': self._build_profile_context(settings)
            })

            # Extract entities from user message into knowledge graph
            if self._memory and self._memory.graph:
                try:
                    self._memory.graph.extract_and_store(message)
                except Exception as e:
                    print(f'[API] Entity extraction error: {e}')

            return response
        except Exception as e:
            print(f'Chat error: {e}')
            return "I couldn't reach the local model just now. Please make sure Ollama is running."

    def proactiveThought(self):
        try:
            stats = self._db.get_today_stats()
            schedule = self._calendar.get_today_events()
            habits = self._db.get_habits()
            recent_journal = self._db.get_recent_journal_entries(2)
            settings = self._get_stored_settings()

            now = datetime.now()
            hour, minute = now.hour, now.minute
            time_str = f'{hour}:{minute:02d}'

            if 5 <= hour < 9:
                prompt = (f"It's {time_str}. The user just opened the app in the morning. Start a brief, natural "
                          "conversation to help them prepare for the day. Be warm but concise (2-3 sentences). "
                          "If there are calendar events, mention the first one. Don't list everything.")
            elif 9 <= hour < 12:
                prompt = (f"It's {time_str} mid-morning. Proactively check in with one brief observation about "
                          "their day so far — maybe their water intake, focus, or an upcoming event. "
                          "Be natural, 1-2 sentences max.")
            elif 12 <= hour < 14:
                prompt = (f"It's {time_str} around lunch. Casually mention it might be a good time for a break "
                          "or meal. Keep it to 1-2 sentences, natural and unforced.")
            elif 14 <= hour < 17:
                prompt = (f"It's {time_str} in the afternoon. Share one proactive insight — could be "
                          "encouragement, a reminder about remaining schedule, or a gentle nudge about breaks. "
                          "1-2 sentences.")
            elif 17 <= hour < 20:
                prompt = (f"It's {time_str} in the evening. If the workday should be winding down, gently "
                          "acknowledge the transition. 1-2 sentences, natural tone.")
            elif 20 <= hour < 23:
                prompt = (f"It's {time_str} at night. Offer a brief reflection on the day or a gentle "
                          "wind-down suggestion. 1-2 sentences.")
            else:
                prompt = f"It's {time_str}. The user is here late. Acknowledge it briefly with warmth. 1 sentence max."

            return self._ollama.chat(prompt, {
                'stats': stats,
                'schedule': schedule,
                'habits': habits,
                'recentJournal': recent_journal,
                'profile': self._build_profile_context(settings)
            })
        except Exception:
            return None

    # ── Schedule ────────────────────────────────────────────────────────────

    def getSchedule(self):
        return self._calendar.get_today_events()

    # ── Settings ────────────────────────────────────────────────────────────

    def getSettings(self):
        return self._get_stored_settings()

    def saveSettings(self, settings):
        normalized = normalize_settings(settings)
        self._save_settings_to_disk(normalized)
        self._scheduler.update_schedule(normalized)
        return {'success': True, 'settings': normalized}

    # ── Stats & Activities ───────────────────────────────────────────────────

    def getStats(self):
        return self._db.get_today_stats()

    def getWeeklyStats(self):
        return self._db.get_weekly_stats()

    def logActivity(self, activity):
        self._db.log_activity(activity)
        return {'success': True}

    # ── Habits ───────────────────────────────────────────────────────────────

    def getHabits(self):
        return self._db.get_habits()

    def createHabit(self, habit):
        self._db.create_habit(habit)
        return {'success': True}

    def completeHabit(self, habitId):
        return self._db.complete_habit(habitId)

    # ── Journal ──────────────────────────────────────────────────────────────

    def getJournalEntries(self, limit=6):
        return self._db.get_recent_journal_entries(limit)

    def saveJournalEntry(self, entry):
        return self._db.save_journal_entry(entry)

    # ── Calendar ─────────────────────────────────────────────────────────────

    def authorizeCalendar(self):
        return self._calendar.authorize()

    def getCalendarStatus(self):
        return self._calendar.get_status()

    # ── App status ───────────────────────────────────────────────────────────

    def getAppStatus(self):
        settings = self._get_stored_settings()
        ollama_status = self._ollama.get_status()
        calendar_status = self._calendar.get_status()
        habits = self._db.get_habits()
        journal_entries = self._db.get_recent_journal_entries(1)
        memory_status = self._memory.get_status() if self._memory else {}
        return {
            'ollama': ollama_status,
            'calendar': calendar_status,
            'memory': memory_status,
            'checklist': {
                'profileConfigured': bool(
                    settings.get('displayName') or settings.get('currentFocus') or settings.get('supportNotes')
                ),
                'hasHabit': len(habits) > 0,
                'hasJournalEntry': len(journal_entries) > 0,
                'calendarConnected': calendar_status.get('connected', False)
            }
        }

    # ── Data export / import ─────────────────────────────────────────────────

    def exportData(self):
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=str(Path.home() / 'Documents'),
                save_filename=f'Anandi-backup-{date.today().isoformat()}.json',
                file_types=('JSON Files (*.json)',)
            )
            if not result:
                return {'success': False, 'cancelled': True}
            file_path = result[0] if isinstance(result, (list, tuple)) else result
            payload = {
                'version': 1,
                'exportedAt': datetime.now().isoformat(),
                'settings': self._get_stored_settings(),
                'data': self._db.export_data()
            }
            Path(file_path).write_text(json.dumps(payload, indent=2, default=str))
            return {'success': True, 'filePath': file_path}
        except Exception as e:
            print(f'Export error: {e}')
            return {'success': False, 'error': str(e)}

    def importData(self):
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=('JSON Files (*.json)',)
            )
            if not result:
                return {'success': False, 'cancelled': True}
            file_path = result[0] if isinstance(result, (list, tuple)) else result
            raw = json.loads(Path(file_path).read_text())
            imported_settings = normalize_settings(raw.get('settings', {}))
            imported_data = raw.get('data', raw)
            self._db.import_data(imported_data)
            self._save_settings_to_disk(imported_settings)
            self._scheduler.update_schedule(imported_settings)
            self._ollama.clear_history()
            activities = imported_data.get('activities', [])
            habits = imported_data.get('habits', [])
            journal_entries = imported_data.get('journal_entries', imported_data.get('journalEntries', []))
            return {
                'success': True,
                'filePath': file_path,
                'counts': {
                    'activities': len(activities),
                    'habits': len(habits),
                    'journalEntries': len(journal_entries)
                },
                'settings': imported_settings
            }
        except Exception as e:
            print(f'Import error: {e}')
            return {'success': False, 'error': str(e)}
