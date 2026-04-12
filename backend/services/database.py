import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path


class DatabaseService:
    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self._local = threading.local()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'connection'):
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
        return self._local.connection

    def initialize(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                date TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                icon TEXT,
                streak INTEGER DEFAULT 0,
                last_completed TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                water INTEGER DEFAULT 0,
                breaks INTEGER DEFAULT 0,
                sleep REAL DEFAULT 0,
                mood TEXT DEFAULT '😊',
                mood_score INTEGER DEFAULT 3,
                exercise INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                mood TEXT,
                date TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()

    def _row_to_dict(self, row) -> dict | None:
        return dict(row) if row is not None else None

    def log_activity(self, activity: dict):
        today = date.today().isoformat()
        conn = self._conn
        conn.execute(
            'INSERT INTO activities (type, value, date) VALUES (?, ?, ?)',
            [activity['type'], activity.get('value'), today]
        )
        conn.commit()
        self._update_daily_stats(activity, today)

    def _update_daily_stats(self, activity: dict, the_date: str):
        conn = self._conn
        conn.execute('INSERT OR IGNORE INTO daily_stats (date) VALUES (?)', [the_date])
        t = activity['type']
        if t == 'water':
            conn.execute('UPDATE daily_stats SET water = water + 1 WHERE date = ?', [the_date])
        elif t == 'break':
            conn.execute('UPDATE daily_stats SET breaks = breaks + 1 WHERE date = ?', [the_date])
        elif t == 'sleep':
            conn.execute('UPDATE daily_stats SET sleep = ? WHERE date = ?', [activity.get('value'), the_date])
        elif t == 'mood':
            conn.execute(
                'UPDATE daily_stats SET mood = ?, mood_score = ? WHERE date = ?',
                [activity.get('value'), activity.get('score'), the_date]
            )
        elif t == 'exercise':
            conn.execute('UPDATE daily_stats SET exercise = exercise + 1 WHERE date = ?', [the_date])
        conn.commit()

    def get_today_stats(self) -> dict:
        today = date.today().isoformat()
        row = self._conn.execute('SELECT * FROM daily_stats WHERE date = ?', [today]).fetchone()
        return self._row_to_dict(row) or {
            'water': 0, 'breaks': 0, 'sleep': 0, 'mood': '😊', 'mood_score': 3, 'exercise': 0
        }

    def get_habits(self) -> list:
        today = date.today().isoformat()
        rows = self._conn.execute('SELECT * FROM habits ORDER BY created_at DESC').fetchall()
        result = []
        for row in rows:
            d = self._row_to_dict(row)
            d['completed'] = d.get('last_completed') == today
            result.append(d)
        return result

    def create_habit(self, habit: dict):
        name = (habit.get('name') or '').strip()
        if not name:
            raise ValueError('Habit name is required.')
        icon = (habit.get('icon') or '✨').strip() or '✨'
        self._conn.execute('INSERT INTO habits (name, icon) VALUES (?, ?)', [name, icon[:4]])
        self._conn.commit()

    def complete_habit(self, habit_id) -> dict:
        habit_id = int(habit_id)
        today = date.today().isoformat()
        conn = self._conn
        row = conn.execute('SELECT * FROM habits WHERE id = ?', [habit_id]).fetchone()
        if not row:
            raise ValueError('Habit not found.')
        habit = self._row_to_dict(row)
        if habit['last_completed'] == today:
            return {'success': True, 'alreadyCompleted': True}
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        next_streak = (habit.get('streak') or 0) + 1 if habit['last_completed'] == yesterday else 1
        conn.execute(
            'UPDATE habits SET streak = ?, last_completed = ? WHERE id = ?',
            [next_streak, today, habit_id]
        )
        conn.commit()
        return {'success': True, 'streak': next_streak}

    def save_journal_entry(self, entry: dict) -> dict:
        content = (entry.get('content') or '').strip()
        if not content:
            raise ValueError('Journal entry cannot be empty.')
        today = date.today().isoformat()
        mood = entry.get('mood')
        conn = self._conn
        cursor = conn.execute(
            'INSERT INTO journal_entries (content, mood, date) VALUES (?, ?, ?)',
            [content, mood, today]
        )
        conn.commit()
        row = conn.execute('SELECT * FROM journal_entries WHERE id = ?', [cursor.lastrowid]).fetchone()
        return self._row_to_dict(row)

    def get_recent_journal_entries(self, limit=6) -> list:
        safe_limit = min(max(int(limit or 6), 1), 20)
        rows = self._conn.execute(
            'SELECT * FROM journal_entries ORDER BY datetime(created_at) DESC LIMIT ?',
            [safe_limit]
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_weekly_stats(self) -> list:
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        rows = self._conn.execute(
            'SELECT * FROM daily_stats WHERE date >= ? ORDER BY date ASC',
            [week_ago]
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def export_data(self) -> dict:
        conn = self._conn
        return {
            'activities': [self._row_to_dict(r) for r in conn.execute('SELECT * FROM activities ORDER BY id ASC').fetchall()],
            'daily_stats': [self._row_to_dict(r) for r in conn.execute('SELECT * FROM daily_stats ORDER BY date ASC').fetchall()],
            'habits': [self._row_to_dict(r) for r in conn.execute('SELECT * FROM habits ORDER BY id ASC').fetchall()],
            'journal_entries': [self._row_to_dict(r) for r in conn.execute('SELECT * FROM journal_entries ORDER BY id ASC').fetchall()],
        }

    def import_data(self, data: dict):
        activities = data.get('activities', [])
        daily_stats = data.get('daily_stats', data.get('dailyStats', []))
        habits = data.get('habits', [])
        journal_entries = data.get('journal_entries', data.get('journalEntries', []))

        conn = self._conn
        now = datetime.now().isoformat()
        today = date.today().isoformat()

        with conn:
            conn.execute('DELETE FROM activities')
            conn.execute('DELETE FROM daily_stats')
            conn.execute('DELETE FROM habits')
            conn.execute('DELETE FROM journal_entries')
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN "
                "('activities', 'daily_stats', 'habits', 'journal_entries')"
            )

            for row in activities:
                conn.execute(
                    'INSERT INTO activities (id, type, value, timestamp, date) VALUES (?, ?, ?, ?, ?)',
                    [row.get('id'), row.get('type', 'note'), row.get('value'),
                     row.get('timestamp', now), row.get('date', today)]
                )
            for row in daily_stats:
                conn.execute(
                    'INSERT INTO daily_stats (id, date, water, breaks, sleep, mood, mood_score, exercise) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    [row.get('id'), row['date'], row.get('water', 0), row.get('breaks', 0),
                     row.get('sleep', 0), row.get('mood', '😊'), row.get('mood_score', 3), row.get('exercise', 0)]
                )
            for row in habits:
                conn.execute(
                    'INSERT INTO habits (id, name, icon, streak, last_completed, created_at) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    [row.get('id'), row.get('name', 'Habit'), row.get('icon', '✨'),
                     row.get('streak', 0), row.get('last_completed'), row.get('created_at', now)]
                )
            for row in journal_entries:
                conn.execute(
                    'INSERT INTO journal_entries (id, content, mood, date, created_at) VALUES (?, ?, ?, ?, ?)',
                    [row.get('id'), row.get('content', ''), row.get('mood'),
                     row.get('date', today), row.get('created_at', now)]
                )
