import threading
from datetime import datetime


class SchedulerService:
    def __init__(self, ollama, calendar, database, notify=None):
        self.ollama = ollama
        self.calendar = calendar
        self.database = database
        self.notify = notify or (lambda title, body: None)
        self._stop_event = threading.Event()
        self._thread = None
        self.settings = {}
        self.last_daily_checks = {
            'wakeup': None, 'bedtime': None, 'breakfast': None,
            'lunch': None, 'dinner': None, 'morning': None, 'evening': None
        }
        self.last_interval_checks: dict[str, datetime | None] = {
            'break': None, 'water': None, 'posture': None
        }

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print('Unified scheduler started')

    def stop(self):
        self._stop_event.set()
        print('Scheduler stopped')

    def update_schedule(self, settings: dict):
        self.settings = dict(settings)
        if settings.get('model'):
            self.ollama.set_model(settings['model'])
        print('Schedule settings updated')

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._check_all_reminders()
            except Exception as e:
                print(f'Scheduler error: {e}')
            # Sleep until the next minute boundary
            now = datetime.now()
            seconds_remaining = 60 - now.second
            self._stop_event.wait(seconds_remaining)

    def _format_time(self, dt: datetime) -> str:
        return f'{dt.hour:02d}:{dt.minute:02d}'

    def _to_minutes(self, time_str) -> int | None:
        if not isinstance(time_str, str) or ':' not in time_str:
            return None
        try:
            hour, minute = int(time_str.split(':')[0]), int(time_str.split(':')[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None
            return hour * 60 + minute
        except (ValueError, IndexError):
            return None

    def _is_within_range(self, current: int, start: int, end: int) -> bool:
        if start <= end:
            return start <= current < end
        return current >= start or current < end

    def _is_quiet_hours(self, current_minutes: int) -> bool:
        quiet_start = self._to_minutes(self.settings.get('quietHoursStart'))
        quiet_end = self._to_minutes(self.settings.get('quietHoursEnd'))
        if quiet_start is None or quiet_end is None:
            return False
        return self._is_within_range(current_minutes, quiet_start, quiet_end)

    def _is_weekend(self, dt: datetime) -> bool:
        return dt.weekday() >= 5

    def _should_trigger_daily(self, type_: str, today: str) -> bool:
        return self.last_daily_checks.get(type_) != today

    def _should_trigger_interval(self, type_: str, interval_minutes, now: datetime) -> bool:
        interval = interval_minutes if isinstance(interval_minutes, (int, float)) and interval_minutes > 0 else 60
        last = self.last_interval_checks.get(type_)
        if last is None:
            self.last_interval_checks[type_] = now
            return False
        if (now - last).total_seconds() / 60 >= interval:
            self.last_interval_checks[type_] = now
            return True
        return False

    def _check_all_reminders(self):
        now = datetime.now()
        today = now.date().isoformat()
        current_time = self._format_time(now)
        current_minutes = now.hour * 60 + now.minute
        weekend_paused = self._is_weekend(now) and not self.settings.get('weekendReminders', False)
        quiet_hours = self._is_quiet_hours(current_minutes)

        def handle_exact(type_: str, time_key: str, action):
            expected = self.settings.get(time_key)
            if not expected or not self._should_trigger_daily(type_, today):
                return
            if current_time == expected:
                try:
                    action()
                except Exception as e:
                    print(f'Reminder error ({type_}): {e}')
                self.last_daily_checks[type_] = today

        if not weekend_paused:
            handle_exact('wakeup', 'wakeUpTime', self._send_wakeup_reminder)

        if not weekend_paused and not quiet_hours and self.settings.get('morningOverviewEnabled'):
            handle_exact('morning', 'morningOverviewTime', self._send_morning_overview)

        if not weekend_paused and not quiet_hours and self.settings.get('mealRemindersEnabled'):
            handle_exact('breakfast', 'breakfastTime', lambda: self._send_meal_reminder('breakfast'))
            handle_exact('lunch', 'lunchTime', lambda: self._send_meal_reminder('lunch'))
            handle_exact('dinner', 'dinnerTime', lambda: self._send_meal_reminder('dinner'))

        work_start = self._to_minutes(self.settings.get('workStart'))
        work_end = self._to_minutes(self.settings.get('workEnd'))
        within_work = (
            work_start is not None and work_end is not None
            and self._is_within_range(current_minutes, work_start, work_end)
        )

        if (not weekend_paused and not quiet_hours and within_work
                and self.settings.get('breakRemindersEnabled')
                and self._should_trigger_interval('break', self.settings.get('breakInterval', 60), now)):
            try:
                self._send_break_reminder()
            except Exception as e:
                print(f'Break reminder error: {e}')

        if (not weekend_paused and not quiet_hours
                and self.settings.get('waterRemindersEnabled')
                and self._should_trigger_interval('water', self.settings.get('waterInterval', 120), now)):
            try:
                self._send_water_reminder()
            except Exception as e:
                print(f'Water reminder error: {e}')

        if (not weekend_paused and not quiet_hours and within_work
                and self.settings.get('postureRemindersEnabled')
                and self._should_trigger_interval('posture', self.settings.get('postureInterval', 90), now)):
            try:
                self._send_posture_reminder()
            except Exception as e:
                print(f'Posture reminder error: {e}')

        if not weekend_paused and not quiet_hours and self.settings.get('eveningReflectionEnabled'):
            handle_exact('evening', 'eveningReflectionTime', self._send_evening_reflection)

        if not weekend_paused:
            bedtime_minutes = self._to_minutes(self.settings.get('bedTime'))
            if (bedtime_minutes is not None
                    and abs(current_minutes - bedtime_minutes) <= 30
                    and self._should_trigger_daily('bedtime', today)):
                try:
                    self._send_bedtime_reminder()
                except Exception as e:
                    print(f'Bedtime reminder error: {e}')
                self.last_daily_checks['bedtime'] = today

    def _get_profile_context(self) -> dict:
        return {
            'displayName': self.settings.get('displayName', ''),
            'currentFocus': self.settings.get('currentFocus', ''),
            'coachingStyle': self.settings.get('coachingStyle', 'balanced'),
            'supportNotes': self.settings.get('supportNotes', '')
        }

    def _send_wakeup_reminder(self):
        schedule = self.calendar.get_today_events()
        message = self.ollama.generate_reminder('wakeup', {'schedule': schedule, 'profile': self._get_profile_context()})
        self.notify('Good Morning', message)

    def _send_bedtime_reminder(self):
        stats = self.database.get_today_stats()
        message = self.ollama.generate_reminder('bedtime', {'stats': stats, 'profile': self._get_profile_context()})
        self.notify('Time to Wind Down', message)

    def _send_break_reminder(self):
        stats = self.database.get_today_stats()
        message = self.ollama.generate_reminder('break', {'stats': stats, 'profile': self._get_profile_context()})
        self.notify('Take a Break', message)

    def _send_meal_reminder(self, meal_type: str):
        message = self.ollama.generate_reminder('meal', {'mealType': meal_type, 'profile': self._get_profile_context()})
        titles = {'breakfast': 'Breakfast Time', 'lunch': 'Lunch Time', 'dinner': 'Dinner Time'}
        self.notify(titles.get(meal_type, 'Meal Time'), message)

    def _send_water_reminder(self):
        stats = self.database.get_today_stats()
        goal = self.settings.get('waterGoal', 8)
        if stats.get('water', 0) < goal:
            message = self.ollama.generate_reminder(
                'water',
                {'current': stats.get('water', 0), 'goal': goal, 'profile': self._get_profile_context()}
            )
            self.notify('Hydration Check', message)

    def _send_posture_reminder(self):
        message = self.ollama.generate_reminder('posture', {'profile': self._get_profile_context()})
        self.notify('Posture Check', message)

    def _send_morning_overview(self):
        schedule = self.calendar.get_today_events()
        stats = self.database.get_today_stats()
        message = self.ollama.chat(
            'Give a brief professional morning overview. Summarize the day ahead and suggest one clear priority. Keep it to 3 sentences.',
            {'schedule': schedule, 'stats': stats, 'profile': self._get_profile_context()}
        )
        self.notify('Daily Briefing', message)

    def _send_evening_reflection(self):
        stats = self.database.get_today_stats()
        message = self.ollama.chat(
            'Give a short evening reflection based on the user stats. Acknowledge progress and suggest one restful next step. Keep it to 2 sentences.',
            {'stats': stats, 'profile': self._get_profile_context()}
        )
        self.notify('Daily Reflection', message)
