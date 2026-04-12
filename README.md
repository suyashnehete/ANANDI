# ANANDI
### Autonomous Natural Agent for Navigating Daily Intelligence

> *"Hire a personal assistant — and put her inside your laptop."*

ANANDI is a fully local, privacy-first AI agent that lives on your desktop. She knows your routine, speaks in your language, and proactively helps you navigate your day — like a personal assistant who never clocks out.

---

## What ANANDI Does Today

### AI Conversation
- Powered by local LLMs via **Ollama** (Llama 3.2, Llama 3.1) — fully private, zero cloud
- Context-aware: knows your today's stats, schedule, habits, mood, and journal before you say a word
- Proactive conversations — ANANDI initiates without being prompted, based on time of day
- Indian English voice (`en-IN` speech synthesis) with emoji-free, natural speech
- Voice input with microphone support

### Health & Wellness
- Water, break, meal, exercise, and sleep logging
- Mood tracking with emoji selector and score
- Daily hydration progress with configurable daily goal
- Posture check reminders during work hours

### Habits & Reflection
- Create and track daily habits with streak counters
- Weekly overview of wellness stats (water, breaks, sleep, exercise)
- Journal / reflection entries with mood tagging

### Scheduling
- Google Calendar integration — schedule-aware AI responses
- Morning overview at a configurable time, evening reflection, meal reminders
- Fully configurable quiet hours, work hours, and interval timings for break/water/posture

### UI & Experience
- Native cross-platform desktop window via **pywebview** (WebKit on macOS, WebView2 on Windows, WebKitGTK on Linux)
- Interactive particle network background (particles.js)
- Floating thought bubbles from ANANDI, appearing without prompting
- Glassmorphic side panel with tabbed dashboard
- Voice on/off toggle
- Data export / import (JSON backup)

---

## Getting Started

### Prerequisites
- macOS 12+ / Windows 10+ / Linux (GTK)
- Python 3.10+
- [Ollama](https://ollama.ai) installed and running

### Install & Run

```bash
git clone https://github.com/suyashnehete/anandi.git
cd anandi
./start.sh
```

`start.sh` handles everything automatically:
- Checks Ollama is running (starts it if not)
- Pulls the default model if missing
- Creates a Python virtual environment (`.venv/`)
- Installs dependencies from `requirements.txt`
- Launches the app

To manually run after setup:

```bash
source .venv/bin/activate
python3 app.py

# Debug mode (opens DevTools)
python3 app.py --dev
```

### Google Calendar (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project and enable the **Google Calendar API**
3. Create OAuth 2.0 Desktop credentials
4. Download as `credentials.json` and place it in the project root
5. Click **Connect** in the Calendar tab inside ANANDI — your browser will open for authorization

---

## Project Structure

```
anandi/
├── app.py                         # Entrypoint — window creation, service wiring
├── requirements.txt               # Python dependencies
├── start.sh                       # One-command launcher
├── README.md
├── .venv/                         # Python virtual environment
├── backend/
│   ├── api.py                     # All backend methods exposed to the frontend
│   └── services/
│       ├── database.py            # SQLite — activities, habits, journal, stats
│       ├── ollama.py              # LLM communication, system prompt, context builder
│       ├── calendar_service.py    # Google Calendar OAuth + events
│       └── scheduler.py          # Background reminder engine (threading)
└── frontend/
    ├── index.html                 # App shell
    ├── styles.css                 # UI styles (glassmorphic, transparent)
    └── renderer.js                # All frontend logic — UI, voice, chat, particles
```

---

## Data & Privacy

Everything runs locally on your machine:

| Data | Location |
|---|---|
| Settings | `~/Library/Application Support/anandi/settings.json` (macOS) |
| Database | `~/Library/Application Support/anandi/personal-assistant.db` |
| Calendar token | `~/Library/Application Support/anandi/token.json` |

No telemetry. No cloud sync. No external APIs except Google Calendar (which is entirely optional and OAuth-scoped to read-only).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | pywebview 4+ (native WebKit/WebView2) |
| AI inference | Ollama (local LLMs) |
| LLM models | Llama 3.2 3B / 1B, Llama 3.1 8B |
| Database | SQLite (Python built-in `sqlite3`) |
| Scheduling | Python `threading` (minute-tick loop) |
| Calendar | Google Calendar API (`google-api-python-client`) |
| Notifications | plyer (cross-platform desktop notifications) |
| HTTP client | requests |
| Background FX | particles.js |
| Voice | Web Speech API (en-IN) |

---

## Future Scope — The Autonomous Agent Architecture

ANANDI v1 is a capable personal assistant. The north star is a **fully autonomous cognitive agent** — one that doesn't wait to be asked, but observes, reasons, plans, and acts on your behalf. The architecture below defines the intelligence layers being built toward that goal.

---

### The Cognitive Loop: Observe → Understand → Plan → Act → Evaluate → Adapt

Every autonomous action ANANDI takes will flow through a six-stage cognitive loop — the same feedback cycle that a high-performing human assistant operates on.

```
┌──────────┐    ┌────────────┐    ┌──────────┐
│  OBSERVE │───▶│ UNDERSTAND │───▶│   PLAN   │
└──────────┘    └────────────┘    └──────────┘
      ▲                                 │
      │                                 ▼
┌──────────┐    ┌────────────┐    ┌──────────┐
│  ADAPT   │◀───│  EVALUATE  │◀───│   ACT    │
└──────────┘    └────────────┘    └──────────┘
```

| Stage | What ANANDI Does |
|---|---|
| **Observe** | Continuously monitors inputs: calendar, stats, messages, habits, time of day, focus state, clipboard, and behavioural signals |
| **Understand** | Interprets what those signals mean in context — not just what happened, but *why it matters* to this user right now |
| **Plan** | Decides *what to do next*, weighing priority, timing, user preference, and potential interruption cost |
| **Act** | Executes — sends a message, fires a reminder, logs an activity, drafts a response, or delegates a sub-task |
| **Evaluate** | Measures whether the action had the intended effect (user acknowledged? goal advanced? habit maintained?) |
| **Adapt** | Updates its model of you — what works, what doesn't, when to push, when to stay silent |

---

### Behavioral Memory Engine

> *ANANDI remembers who you are, not just what you said.*

Most AI assistants have amnesia across sessions. The Behavioral Memory Engine builds a persistent, structured model of the user that grows richer over time.

- **Episodic memory** — what happened today, this week, this month
- **Semantic memory** — facts about you: your role, team, goals, recurring commitments, preferences
- **Procedural memory** — how you like things done: tone, timing, level of detail, what you ignore
- **Relational memory** — who matters to you, what they mean to you, when you last connected
- **Emotional memory** — patterns in your mood relative to sleep, workload, schedule density, and time of year

Every other ANANDI subsystem queries this engine, so every decision is informed by *your* history — not a generic user model.

---

### Task Ownership Engine

> *ANANDI doesn't just log tasks — she owns them.*

A task handed to ANANDI is not dropped into a list and forgotten. The Task Ownership Engine tracks every open commitment through its full lifecycle.

- Captures tasks from conversation, email, calendar, voice, or clipboard
- Assigns due dates, priority, and context automatically
- Proactively follows up: *"You mentioned finishing the report by Thursday — it's Wednesday evening"*
- Escalates stalled tasks as deadlines approach without recorded progress
- Closes tasks when it detects completion signals in conversation or behaviour
- Maintains a personal accountability score: tasks completed on time vs. missed, with trends over time

---

### Decision Engine

> *ANANDI knows when to act and when to ask.*

Acting too early is presumptuous. Acting too late is useless. The Decision Engine gives ANANDI the judgment to know the difference.

- **Confidence thresholding** — acts autonomously above a set confidence level; asks below it
- **Permission memory** — remembers which categories of action are pre-authorised vs. which need approval each time
- **Risk assessment** — weighs the reversibility and impact of every action before executing
- **Context arbitration** — when signals conflict (calendar says free but focus music is playing), the engine picks the right interpretation
- **Delegation logic** — decides which sub-tasks to handle directly vs. route to a specialised agent

---

### Interruption Intelligence

> *A brilliant assistant knows when not to speak.*

The most damaging thing a bad assistant does is interrupt at the wrong moment. Interruption Intelligence makes silence as deliberate as speech.

- **Focus state detection** — infers deep work vs. available states from activity patterns, app usage, and calendar
- **Urgency classification** — ranks all pending nudges before deciding whether and when to surface them
- **Batching** — holds low-urgency messages and delivers them as a digest at the next natural break
- **Deferral logic** — queues messages during meetings or calls, then delivers a clean handoff after
- **Do-not-disturb learning** — learns your focus patterns over time so it stops asking and just knows
- **Re-entry prompts** — when you return from focus time: *"You were out for 90 minutes — here's what matters"*

---

### Accountability Layer

> *ANANDI is the only assistant who will call you out — kindly.*

The Accountability Layer is the difference between a tool that enables drift and one that prevents it.

- Tracks commitments made in conversation: *"I'll finish this by end of day"* → ANANDI holds you to it
- Generates a weekly accountability report: goals set, tasks completed, habits maintained, patterns broken
- Identifies drift: *"You've skipped the morning overview 4 days in a row"*
- Offers course corrections, not judgment: *"Want to reschedule, or do you need help breaking this down?"*
- Celebrates genuine progress: streak milestones, consistency wins, hard-won completions
- Optionally shares summaries with a trusted accountability partner

---

### Self-Learning Engine

> *ANANDI gets measurably better at being your assistant the longer she works with you.*

The Self-Learning Engine closes the loop between Evaluate and Adapt in the cognitive cycle.

- **Preference learning** — fine-tunes tone, timing, verbosity, and reminder frequency based on your responses and non-responses
- **Model fine-tuning hooks** — periodically fine-tunes the local LLM on anonymised interaction data to personalise its outputs
- **Routing optimisation** — learns which prompt patterns produce the most useful responses for your specific needs
- **Habit signal detection** — identifies emerging patterns in your behaviour before you do and proposes new habits proactively
- **Negative signal recognition** — learns from what you dismiss, snooze, or ignore — and stops doing those things
- **Longitudinal health modelling** — builds correlations between your sleep, focus, mood, and schedule density over months, surfacing actionable insights

---

## Roadmap

### Near-term (v1.x)
- [ ] Persistent long-term memory across sessions
- [ ] Auto-logging from conversation (*"had chai"* → break logged automatically)
- [ ] Richer Indian context — festival calendar, IST-aware scheduling, regional language support
- [ ] Email integration — read, summarise, and draft replies (Gmail / Outlook)
- [ ] Clipboard and active window awareness for contextual help

### Medium-term (v2)
- [ ] Task Ownership Engine v1 — full task lifecycle tracking and proactive follow-up
- [ ] Interruption Intelligence v1 — focus state detection and smart batching
- [ ] Meeting transcription — join, transcribe, summarise, extract action items
- [ ] Always-on menubar mode — silent until relevant
- [ ] Multi-agent delegation — research agent, writing agent, health agent
- [ ] Web search and live document understanding (PDF, reports)

### Long-term (v3+)
- [ ] Behavioral Memory Engine — episodic, semantic, procedural, relational, and emotional memory
- [ ] Decision Engine — confidence thresholds, permission memory, risk assessment
- [ ] Accountability Layer — weekly reports, commitment tracking, accountability partner mode
- [ ] Self-Learning Engine — preference learning, LLM fine-tuning hooks, longitudinal health modelling
- [ ] Mobile companion app (iOS / Android) synced with the desktop agent
- [ ] Outbound communication — book appointments, send messages via API integrations
- [ ] Custom skill plugins — open SDK (Zomato, Swiggy, Ola, IRCTC, and more)
- [ ] Voice-first mode — always listening (opt-in), fully hands-free
- [ ] Cross-device encrypted memory sync
- [ ] Team / family mode — shared ANANDI instance for households or small teams

---

### The North Star

> ANANDI should feel indistinguishable from having a brilliant, discreet human assistant who knows everything about your life, never forgets, never judges, and is always one thought away.

---

## License

MIT — build on it, ship it, make it yours.
