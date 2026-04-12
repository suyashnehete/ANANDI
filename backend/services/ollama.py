import os
from datetime import datetime, timezone, timedelta

import requests

IST = timezone(timedelta(hours=5, minutes=30))

SYSTEM_PROMPT = """You are ANANDI — Autonomous Natural Agent for Navigating Daily Intelligence.

PERSONALITY:
- Professional, warm, and supportive
- Clear and collaborative
- Calm under pressure
- Practical and action-oriented
- Culturally aware — your user is based in India

INDIAN CONTEXT:
- Be aware of Indian festivals (Diwali, Holi, Navratri, Eid, Christmas, Pongal, Onam, etc.), holidays, and cultural customs
- Use Indian English naturally (e.g., "today's schedule looks packed yaar", "chai break?", "good morning!")
- Understand IST timezone context
- Reference Indian food culture when relevant (chai, dosa, roti, biryani, etc.)
- Be mindful of Indian work culture and weekend patterns

COMMUNICATION STYLE:
- Keep most replies to 2-4 concise sentences
- Use plain language and concrete suggestions
- Avoid using emojis in responses
- Be encouraging without sounding childish or condescending

AVAILABLE FEATURES (you can suggest these to the user):
- Water/break/meal/exercise tracking: user can log these via dashboard
- Sleep logging and mood tracking
- Habit creation and daily completion streaks
- Journal/reflection entries
- Google Calendar integration for schedule
- Customizable reminders (break, water, posture, meals)
- Data export/import

When the user asks to perform an action, respond helpfully and guide them. For example:
- "log water" or "I drank water" -> confirm and encourage
- "how much water today" -> reference their stats
- "what's on my schedule" -> reference calendar events
- "create a habit" -> ask what habit they want to track
- "how did my week go" -> reference weekly stats

PRIMARY GOALS:
- Help the user plan their day
- Support healthy routines and habits
- Keep reminders useful and respectful
- Offer context-aware suggestions based on schedule, daily stats, habits, journal, and saved profile preferences

When profile context is available, respect the user's preferred coaching style and current focus."""


class OllamaService:
    def __init__(self):
        self.base_url = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
        self.model = 'llama3.2:3b'
        self.conversation_history = []

    def set_model(self, model: str):
        self.model = model

    def clear_history(self):
        self.conversation_history = []

    def _build_contextual_message(self, message: str, context: dict) -> str:
        result = message
        now_ist = datetime.now(IST)
        result += f'\n\n[Current time: {now_ist.strftime("%I:%M %p")} IST]'

        stats = context.get('stats')
        if stats:
            result += (
                f'\n[Today so far: {stats.get("water", 0)} glasses of water, '
                f'{stats.get("breaks", 0)} breaks'
            )
            if stats.get('sleep', 0) > 0:
                result += f', {stats["sleep"]} hours of sleep'
            if stats.get('mood'):
                result += f', mood {stats["mood"]}'
            result += ']'

        schedule = context.get('schedule', [])
        if schedule:
            event_strs = [f'{e["time"]}: {e["title"]}' for e in schedule]
            result += f'\n[Today\'s schedule: {", ".join(event_strs)}]'

        habits = context.get('habits', [])
        if habits:
            habit_strs = [
                f'{h["name"]} ({"done today" if h.get("completed") else "pending"}, '
                f'{h.get("streak", 0)} day streak)'
                for h in habits
            ]
            result += f'\n[Active habits: {", ".join(habit_strs)}]'

        recent_journal = context.get('recentJournal', [])
        if recent_journal:
            latest = recent_journal[0]
            content = latest.get('content', '')
            truncated = content[:100] + ('...' if len(content) > 100 else '')
            result += f'\n[Latest reflection: "{truncated}"]'

        profile = context.get('profile', {})
        if profile:
            parts = []
            if profile.get('displayName'):
                parts.append(f'preferred name: {profile["displayName"]}')
            if profile.get('currentFocus'):
                parts.append(f'current focus: {profile["currentFocus"]}')
            if profile.get('coachingStyle'):
                parts.append(f'coaching style: {profile["coachingStyle"]}')
            if profile.get('supportNotes'):
                parts.append(f'support notes: {profile["supportNotes"]}')
            if parts:
                result += f'\n[User profile: {", ".join(parts)}]'

        return result

    def chat(self, user_message: str, context: dict = None) -> str:
        context = context or {}
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            *self.conversation_history,
            {'role': 'user', 'content': self._build_contextual_message(user_message, context)}
        ]
        try:
            response = requests.post(
                f'{self.base_url}/api/chat',
                json={
                    'model': self.model,
                    'messages': messages,
                    'stream': False,
                    'options': {'temperature': 0.7, 'top_p': 0.9}
                },
                timeout=30
            )
            response.raise_for_status()
            assistant_message = response.json()['message']['content']

            self.conversation_history.append({'role': 'user', 'content': user_message})
            self.conversation_history.append({'role': 'assistant', 'content': assistant_message})

            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            return assistant_message
        except requests.exceptions.ConnectionError:
            return "I can't reach Ollama right now. Please start it with `ollama serve` and try again."
        except Exception as e:
            print(f'Ollama error: {e}')
            return "I hit a temporary issue while generating that response. Please try again in a moment."

    def generate_reminder(self, type_: str, context: dict = None) -> str:
        context = context or {}
        meal_type = context.get('mealType', 'meal')
        prompts = {
            'wakeup': 'Write a short motivating wake-up reminder for the start of the day. Keep it to 2 sentences.',
            'bedtime': 'Write a gentle bedtime reminder that encourages winding down and resting well. Keep it to 2 sentences.',
            'break': 'Write a quick reminder to step away, stretch, or rest briefly. Keep it to 2 sentences.',
            'meal': f'Write a concise {meal_type} reminder that encourages eating on time. Keep it to 2 sentences.',
            'water': 'Write a short hydration reminder that feels supportive, not nagging. Keep it to 2 sentences.',
            'posture': 'Write a short posture and ergonomics reminder. Keep it to 2 sentences.',
            'exercise': 'Write an encouraging reminder about movement or light exercise. Keep it to 2 sentences.'
        }
        fallbacks = {
            'wakeup': 'Good morning. Start steady, and pick one clear priority for the day.',
            'bedtime': 'It is a good time to wind down and get ready for rest.',
            'break': 'Take a short break and reset before jumping back in.',
            'meal': 'Time for a proper meal. Refuel before the next stretch of the day.',
            'water': 'Quick hydration check. A glass of water would help right now.',
            'posture': 'Check your posture and relax your shoulders for a moment.',
            'exercise': 'A little movement would be a strong reset right now.'
        }
        try:
            return self.chat(prompts.get(type_, prompts['break']), context)
        except Exception:
            return fallbacks.get(type_, fallbacks['break'])

    def get_status(self) -> dict:
        try:
            response = requests.get(f'{self.base_url}/api/tags', timeout=5)
            response.raise_for_status()
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            model_installed = any(
                self.model == m or self.model.split(':')[0] in m
                for m in model_names
            )
            return {
                'available': True,
                'currentModel': self.model,
                'modelInstalled': model_installed,
                'models': model_names
            }
        except Exception as e:
            return {
                'available': False,
                'currentModel': self.model,
                'modelInstalled': False,
                'error': str(e)
            }
