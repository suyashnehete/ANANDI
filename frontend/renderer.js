/* ===== ANANDI — Autonomous Natural Agent for Navigating Daily Intelligence ===== */

let api = null;

let voiceEnabled = true;
let recognition = null;
let synthesis = window.speechSynthesis;
let availableVoices = [];
let currentSettings = null;
let baseStatusText = 'Ready';
let panelOpen = false;
let proactiveTimer = null;
let entityState = 'idle'; // idle, thinking, speaking, listening

// ────────────────────────────────────────
// Particles.js Background
// ────────────────────────────────────────

function initParticlesBackground() {
  if (typeof particlesJS === 'undefined') {
    console.warn('particles.js not loaded');
    return;
  }

  particlesJS('particles-js', {
    particles: {
      number: { value: 140, density: { enable: true, value_area: 900 } },
      color: { value: ['#667eea', '#764ba2', '#ec4899', '#818cf8', '#a78bfa'] },
      shape: { type: 'circle' },
      opacity: {
        value: 0.5,
        random: true,
        anim: { enable: true, speed: 0.8, opacity_min: 0.1, sync: false }
      },
      size: {
        value: 3,
        random: true,
        anim: { enable: true, speed: 2, size_min: 0.5, sync: false }
      },
      line_linked: {
        enable: true,
        distance: 150,
        color: '#667eea',
        opacity: 0.18,
        width: 1
      },
      move: {
        enable: true,
        speed: 1.2,
        direction: 'none',
        random: true,
        straight: false,
        out_mode: 'out',
        bounce: false,
        attract: { enable: true, rotateX: 600, rotateY: 1200 }
      }
    },
    interactivity: {
      detect_on: 'canvas',
      events: {
        onhover: { enable: true, mode: 'grab' },
        onclick: { enable: true, mode: 'push' },
        resize: true
      },
      modes: {
        grab: { distance: 200, line_linked: { opacity: 0.45 } },
        push: { particles_nb: 4 }
      }
    },
    retina_detect: true
  });
}

// ────────────────────────────────────────
// Entity State Control
// ────────────────────────────────────────

function setBrainState(state) {
  entityState = state;
  const pulse = document.querySelector('.status-pulse');
  if (!pulse) return;
  if (state === 'thinking') {
    pulse.style.background = '#818cf8';
    pulse.style.boxShadow = '0 0 12px rgba(129,140,248,0.8)';
  } else if (state === 'speaking') {
    pulse.style.background = '#ec4899';
    pulse.style.boxShadow = '0 0 12px rgba(236,72,153,0.8)';
  } else if (state === 'listening') {
    pulse.style.background = '#f59e0b';
    pulse.style.boxShadow = '0 0 12px rgba(245,158,11,0.8)';
  } else {
    pulse.style.background = '#4ade80';
    pulse.style.boxShadow = '0 0 12px rgba(74,222,128,0.8)';
  }
}

function showThought(text) {
  const bubble = document.getElementById('thoughtBubble');
  bubble.textContent = text;
  bubble.classList.remove('visible');
  void bubble.offsetWidth; // force reflow
  bubble.classList.add('visible');
  setTimeout(() => bubble.classList.remove('visible'), 6000);
}

// ────────────────────────────────────────
// Proactive AI — Anandi Starts Conversations
// ────────────────────────────────────────

async function triggerProactiveThought() {
  try {
    const response = await api.proactiveThought();
    if (response) {
      showThought(response);
      addMessage(response, 'assistant');
      if (voiceEnabled) speak(response);
    }
  } catch {
    // Silently fail — proactive thoughts are optional
  }
}

function startProactiveLoop() {
  // First proactive thought after 3 seconds
  setTimeout(() => triggerProactiveThought(), 3000);

  // Then every 15 minutes, Anandi may share a thought
  proactiveTimer = setInterval(() => {
    triggerProactiveThought();
  }, 15 * 60 * 1000);
}

// ────────────────────────────────────────
// Activity Messages
// ────────────────────────────────────────

const ACTIVITY_MESSAGES = {
  water: [
    'Hydration logged. Nice work.',
    'Water added. Keeps the energy steady.',
    'Logged. Small wins add up.'
  ],
  break: [
    'Break logged. A short reset helps.',
    'Nice call on the break.',
    'Break recorded.'
  ],
  meal: [
    'Meal logged. Good timing.',
    'Meal recorded. Protecting your energy.',
    'Logged.'
  ],
  exercise: [
    'Exercise logged. Strong move.',
    'Activity recorded.',
    'Logged. Movement helps everything.'
  ]
};

const MOOD_MESSAGES = {
  '😢': "Thanks for sharing that. I'm here.",
  '😕': 'Noted. Let us keep the next step simple.',
  '😐': 'Steady day. Still progress.',
  '😊': 'Good energy to build on.',
  '😄': 'Excellent momentum.'
};

// ────────────────────────────────────────
// DOMContentLoaded
// ────────────────────────────────────────

// Initialize non-API UI elements immediately when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
  initParticlesBackground();
  registerDomListeners();
  initializeVoices();
  initializeSpeechRecognition();
  setVoiceButtonState();
  updateStatus('Syncing...');
});

// Initialize API-dependent features once pywebview has injected the bridge
window.addEventListener('pywebviewready', async () => {
  api = window.pywebview.api;

  // Callbacks Python can invoke via window.evaluate_js()
  window.__onOpenSettings = () => openSettings();
  window.__onNotification = ({ title, body }) => {
    const message = title ? `${title}: ${body}` : body;
    addMessage(message, 'assistant');
    showThought(body);
    if (voiceEnabled) speak(body);
  };

  await refreshApp();
  updateStatus('Ready');

  startProactiveLoop();

  setInterval(() => refreshStatusPanel(), 30000);

  window.addEventListener('focus', () => refreshStatusPanel());
});

// ────────────────────────────────────────
// DOM Listeners
// ────────────────────────────────────────

function registerDomListeners() {
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeSettings();
      if (panelOpen) togglePanel();
    }
  });

  document.getElementById('settingsModal').addEventListener('click', (event) => {
    if (event.target.id === 'settingsModal') closeSettings();
  });
}

// ────────────────────────────────────────
// Refresh & Status
// ────────────────────────────────────────

async function refreshApp() {
  await loadSettings();
  await Promise.all([
    loadSchedule(),
    loadStats(),
    loadHabits(),
    loadWeeklyOverview(),
    loadCalendarStatus(),
    loadJournalEntries(),
    loadAppStatus()
  ]);
}

function updateStatus(text) {
  document.getElementById('statusText').textContent = text;
}

function setBaseStatus(text) {
  baseStatusText = text;
  updateStatus(text);
}

function restoreStatus() {
  updateStatus(baseStatusText);
}

// ────────────────────────────────────────
// Panel Toggle
// ────────────────────────────────────────

function togglePanel() {
  panelOpen = !panelOpen;
  document.getElementById('sidePanel').classList.toggle('open', panelOpen);
}

// ────────────────────────────────────────
// Speech
// ────────────────────────────────────────

function initializeSpeechRecognition() {
  const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognitionCtor) return;

  recognition = new SpeechRecognitionCtor();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-IN';

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    document.getElementById('messageInput').value = transcript;
    sendMessage();
  };

  recognition.onerror = (e) => {
    document.getElementById('voiceInputBtn').classList.remove('active');
    setBrainState('idle');
    restoreStatus();
    if (e.error === 'not-allowed') {
      addMessage('Microphone access was denied. Please allow microphone in system preferences.', 'assistant');
    }
  };

  recognition.onend = () => {
    document.getElementById('voiceInputBtn').classList.remove('active');
    setBrainState('idle');
    restoreStatus();
  };
}

function startVoiceInput() {
  if (!recognition) {
    addMessage('Voice input is not supported in this environment.', 'assistant');
    return;
  }
  try {
    document.getElementById('voiceInputBtn').classList.add('active');
    setBrainState('listening');
    updateStatus('Listening...');
    recognition.start();
  } catch (e) {
    document.getElementById('voiceInputBtn').classList.remove('active');
    setBrainState('idle');
    restoreStatus();
    addMessage('Microphone is busy or unavailable. Try again.', 'assistant');
  }
}

function initializeVoices() {
  function populateVoices() {
    availableVoices = synthesis.getVoices().filter((v) => v.lang.startsWith('en'));
    const select = document.getElementById('settingsVoiceName');
    select.innerHTML = '';

    if (availableVoices.length === 0) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'System default';
      select.appendChild(option);
      return;
    }

    availableVoices.forEach((voice) => {
      const option = document.createElement('option');
      option.value = voice.name;
      option.textContent = `${voice.name} (${voice.lang})`;
      select.appendChild(option);
    });

    applySavedVoiceSelection();
  }

  populateVoices();
  if (typeof synthesis.onvoiceschanged !== 'undefined') {
    synthesis.onvoiceschanged = populateVoices;
  }
}

function applySavedVoiceSelection() {
  const select = document.getElementById('settingsVoiceName');
  if (!select) return;

  if (currentSettings?.voiceName && availableVoices.some((v) => v.name === currentSettings.voiceName)) {
    select.value = currentSettings.voiceName;
    return;
  }

  // Prefer Indian English female voices — soft and cute
  const indianFemaleNames = ['Sangeeta', 'Lekha', 'Veena', 'Priya', 'Rishi'];
  // First: try Indian female voices specifically
  let preferredVoice = availableVoices.find((v) => {
    const name = v.name.toLowerCase();
    const isIndian = v.lang.includes('en-IN') || v.lang.includes('en_IN')
      || indianFemaleNames.some((n) => name.includes(n.toLowerCase()));
    const isFemale = !name.includes('rishi') && !name.includes('male');
    return isIndian && isFemale;
  });

  // Fallback: any Indian English voice
  if (!preferredVoice) {
    preferredVoice = availableVoices.find((v) =>
      v.lang.includes('en-IN') || v.lang.includes('en_IN')
      || indianFemaleNames.some((n) => v.name.toLowerCase().includes(n.toLowerCase()))
    );
  }

  // Fallback: any female-sounding English voice
  if (!preferredVoice) {
    preferredVoice = availableVoices.find((v) => {
      const name = v.name.toLowerCase();
      return (name.includes('female') || name.includes('samantha') || name.includes('karen')
        || name.includes('victoria') || name.includes('fiona') || name.includes('moira'));
    });
  }

  if (preferredVoice) select.value = preferredVoice.name;
}

function stripEmojis(text) {
  return text
    .replace(/[\u{1F600}-\u{1F64F}]/gu, '')  // emoticons
    .replace(/[\u{1F300}-\u{1F5FF}]/gu, '')  // misc symbols & pictographs
    .replace(/[\u{1F680}-\u{1F6FF}]/gu, '')  // transport & map
    .replace(/[\u{1F1E0}-\u{1F1FF}]/gu, '')  // flags
    .replace(/[\u{2600}-\u{26FF}]/gu, '')     // misc symbols
    .replace(/[\u{2700}-\u{27BF}]/gu, '')     // dingbats
    .replace(/[\u{FE00}-\u{FE0F}]/gu, '')     // variation selectors
    .replace(/[\u{1F900}-\u{1F9FF}]/gu, '')   // supplemental symbols
    .replace(/[\u{1FA00}-\u{1FA6F}]/gu, '')   // chess symbols
    .replace(/[\u{1FA70}-\u{1FAFF}]/gu, '')   // symbols extended-A
    .replace(/[\u{200D}]/gu, '')               // zero-width joiner
    .replace(/[\u{20E3}]/gu, '')               // combining enclosing keycap
    .replace(/[\u{E0020}-\u{E007F}]/gu, '')   // tags
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function speak(text) {
  if (!voiceEnabled || !synthesis || !text) return;
  const cleanText = stripEmojis(text);
  if (!cleanText) return;
  const utterance = new SpeechSynthesisUtterance(cleanText);
  const selectedVoiceName = document.getElementById('settingsVoiceName').value;
  const selectedVoice = availableVoices.find((v) => v.name === selectedVoiceName);
  if (selectedVoice) utterance.voice = selectedVoice;
  utterance.rate = 0.88;
  utterance.pitch = 1.15;
  utterance.volume = 0.9;
  utterance.onstart = () => setBrainState('speaking');
  utterance.onend = () => setBrainState('idle');
  synthesis.cancel();
  synthesis.speak(utterance);
}

function setVoiceButtonState() {
  document.getElementById('voiceBtn').style.opacity = voiceEnabled ? '1' : '0.5';
}

function toggleVoice() {
  voiceEnabled = !voiceEnabled;
  if (!voiceEnabled) synthesis.cancel();
  setVoiceButtonState();
  if (voiceEnabled) speak('Voice enabled.');
}

// ────────────────────────────────────────
// Chat
// ────────────────────────────────────────

async function sendMessage() {
  const input = document.getElementById('messageInput');
  const message = input.value.trim();
  if (!message) return;

  addMessage(message, 'user');
  input.value = '';

  // Handle quick commands locally before sending to AI
  const lower = message.toLowerCase();
  const quickAction = await handleQuickCommand(lower);
  if (quickAction) return;

  showTyping();
  setBrainState('thinking');
  updateStatus('Thinking...');

  try {
    const response = await api.chat(message);
    hideTyping();
    addMessage(response, 'assistant');
    if (voiceEnabled) speak(response);

    // Auto-refresh relevant panels after AI response
    await refreshAfterChat(lower);
  } catch {
    hideTyping();
    addMessage('Something went wrong.', 'assistant');
  } finally {
    setBrainState('idle');
    restoreStatus();
  }
}

async function handleQuickCommand(lower) {
  if (/^(log water|drank water|had water|pani|paani)/.test(lower)) {
    await logWater();
    return true;
  }
  if (/^(log break|take a break|break le|break liya)/.test(lower)) {
    await logBreak();
    return true;
  }
  if (/^(log meal|had food|khana kha|lunch done|dinner done|breakfast done)/.test(lower)) {
    await logMeal();
    return true;
  }
  if (/^(log exercise|worked out|exercise done|walk kiya)/.test(lower)) {
    await logExercise();
    return true;
  }
  if (/^(open settings|settings)$/.test(lower)) {
    openSettings();
    addMessage('Opening settings.', 'assistant');
    return true;
  }
  if (/^(open dashboard|dashboard|panel)$/.test(lower)) {
    if (!panelOpen) togglePanel();
    addMessage('Here is your dashboard.', 'assistant');
    return true;
  }
  return false;
}

async function refreshAfterChat(lower) {
  if (/water|hydrat|drink|pani/.test(lower)) await loadStats();
  if (/break|rest/.test(lower)) await loadStats();
  if (/schedul|calendar|event|meeting/.test(lower)) await loadSchedule();
  if (/habit/.test(lower)) await loadHabits();
  if (/journal|reflect|diary/.test(lower)) await loadJournalEntries();
}

function addMessage(text, sender) {
  const container = document.getElementById('chatContainer');
  const msg = document.createElement('div');
  const body = document.createElement('div');
  const time = document.createElement('div');

  msg.className = `message ${sender}`;
  body.textContent = text;
  time.className = 'message-time';
  time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  msg.appendChild(body);
  msg.appendChild(time);
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function showTyping() {
  const container = document.getElementById('chatContainer');
  const typing = document.createElement('div');
  typing.className = 'message assistant';
  typing.id = 'typing-indicator';
  typing.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
  container.appendChild(typing);
  container.scrollTop = container.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

// ────────────────────────────────────────
// Schedule
// ────────────────────────────────────────

async function loadSchedule() {
  const schedule = await api.getSchedule();
  const div = document.getElementById('schedule');
  div.innerHTML = '';

  if (!schedule.length) {
    const p = document.createElement('p');
    p.className = 'empty-state';
    p.textContent = 'No events today.';
    div.appendChild(p);
    return;
  }

  schedule.forEach((event) => {
    const item = document.createElement('div');
    item.className = 'schedule-item';
    const t = document.createElement('div');
    t.className = 'schedule-time';
    t.textContent = event.time;
    const title = document.createElement('div');
    title.className = 'schedule-title';
    title.textContent = event.title;
    item.appendChild(t);
    item.appendChild(title);
    div.appendChild(item);
  });
}

// ────────────────────────────────────────
// Settings
// ────────────────────────────────────────

function openSettings() {
  document.getElementById('settingsModal').classList.add('show');
}

function closeSettings() {
  document.getElementById('settingsModal').classList.remove('show');
}

async function loadSettings() {
  currentSettings = await api.getSettings();
  applySettingsToForm(currentSettings);
  renderSettingsSummary(currentSettings);
  updateWaterGoal(currentSettings.waterGoal);
  applySavedVoiceSelection();
}

function setCheckboxValue(id, value) {
  document.getElementById(id).checked = Boolean(value);
}

function applySettingsToForm(s) {
  document.getElementById('settingsWakeUpTime').value = s.wakeUpTime;
  document.getElementById('settingsDisplayName').value = s.displayName || '';
  document.getElementById('settingsCurrentFocus').value = s.currentFocus || '';
  document.getElementById('settingsCoachingStyle').value = s.coachingStyle || 'balanced';
  document.getElementById('settingsSupportNotes').value = s.supportNotes || '';
  document.getElementById('settingsMorningOverviewTime').value = s.morningOverviewTime;
  document.getElementById('settingsBreakfastTime').value = s.breakfastTime;
  document.getElementById('settingsLunchTime').value = s.lunchTime;
  document.getElementById('settingsDinnerTime').value = s.dinnerTime;
  document.getElementById('settingsEveningReflectionTime').value = s.eveningReflectionTime;
  document.getElementById('settingsBedTime').value = s.bedTime;
  document.getElementById('settingsWorkStart').value = s.workStart;
  document.getElementById('settingsWorkEnd').value = s.workEnd;
  document.getElementById('settingsQuietHoursStart').value = s.quietHoursStart;
  document.getElementById('settingsQuietHoursEnd').value = s.quietHoursEnd;
  document.getElementById('settingsBreakInterval').value = s.breakInterval;
  document.getElementById('settingsWaterInterval').value = s.waterInterval;
  document.getElementById('settingsPostureInterval').value = s.postureInterval;
  document.getElementById('settingsWaterGoal').value = s.waterGoal;
  document.getElementById('settingsModel').value = s.model;

  setCheckboxValue('settingsWeekendReminders', s.weekendReminders);
  setCheckboxValue('settingsMorningOverviewEnabled', s.morningOverviewEnabled);
  setCheckboxValue('settingsEveningReflectionEnabled', s.eveningReflectionEnabled);
  setCheckboxValue('settingsMealRemindersEnabled', s.mealRemindersEnabled);
  setCheckboxValue('settingsBreakRemindersEnabled', s.breakRemindersEnabled);
  setCheckboxValue('settingsWaterRemindersEnabled', s.waterRemindersEnabled);
  setCheckboxValue('settingsPostureRemindersEnabled', s.postureRemindersEnabled);
}

function readCheckboxValue(id) {
  return document.getElementById(id).checked;
}

function readSettingsForm() {
  return {
    displayName: document.getElementById('settingsDisplayName').value.trim(),
    currentFocus: document.getElementById('settingsCurrentFocus').value.trim(),
    coachingStyle: document.getElementById('settingsCoachingStyle').value,
    supportNotes: document.getElementById('settingsSupportNotes').value.trim(),
    wakeUpTime: document.getElementById('settingsWakeUpTime').value,
    morningOverviewTime: document.getElementById('settingsMorningOverviewTime').value,
    breakfastTime: document.getElementById('settingsBreakfastTime').value,
    lunchTime: document.getElementById('settingsLunchTime').value,
    dinnerTime: document.getElementById('settingsDinnerTime').value,
    eveningReflectionTime: document.getElementById('settingsEveningReflectionTime').value,
    bedTime: document.getElementById('settingsBedTime').value,
    workStart: document.getElementById('settingsWorkStart').value,
    workEnd: document.getElementById('settingsWorkEnd').value,
    quietHoursStart: document.getElementById('settingsQuietHoursStart').value,
    quietHoursEnd: document.getElementById('settingsQuietHoursEnd').value,
    breakInterval: Number.parseInt(document.getElementById('settingsBreakInterval').value, 10),
    waterInterval: Number.parseInt(document.getElementById('settingsWaterInterval').value, 10),
    postureInterval: Number.parseInt(document.getElementById('settingsPostureInterval').value, 10),
    waterGoal: Number.parseInt(document.getElementById('settingsWaterGoal').value, 10),
    weekendReminders: readCheckboxValue('settingsWeekendReminders'),
    morningOverviewEnabled: readCheckboxValue('settingsMorningOverviewEnabled'),
    eveningReflectionEnabled: readCheckboxValue('settingsEveningReflectionEnabled'),
    mealRemindersEnabled: readCheckboxValue('settingsMealRemindersEnabled'),
    breakRemindersEnabled: readCheckboxValue('settingsBreakRemindersEnabled'),
    waterRemindersEnabled: readCheckboxValue('settingsWaterRemindersEnabled'),
    postureRemindersEnabled: readCheckboxValue('settingsPostureRemindersEnabled'),
    model: document.getElementById('settingsModel').value,
    voiceName: document.getElementById('settingsVoiceName').value
  };
}

function renderSettingsSummary(s) {
  const summary = document.getElementById('settingsSummary');
  const weekend = s.weekendReminders ? 'on' : 'off';
  summary.innerHTML = `
    <div class="settings-summary-line">Wake ${s.wakeUpTime} · Bed ${s.bedTime}</div>
    <div class="settings-summary-line">Work ${s.workStart} – ${s.workEnd}</div>
    <div class="settings-summary-line">Quiet ${s.quietHoursStart} – ${s.quietHoursEnd}</div>
    <div class="settings-summary-line">Break/Water/Posture: ${s.breakInterval}/${s.waterInterval}/${s.postureInterval}min</div>
    <div class="settings-summary-line">Water goal: ${s.waterGoal} · Weekend: ${weekend}</div>
  `;
}

async function saveSettingsModal(event) {
  const button = event?.target;
  const originalLabel = button ? button.textContent : '';
  if (button) button.textContent = 'Saving...';

  try {
    const result = await api.saveSettings(readSettingsForm());
    if (result.success) {
      currentSettings = result.settings;
      applySettingsToForm(currentSettings);
      renderSettingsSummary(currentSettings);
      updateWaterGoal(currentSettings.waterGoal);
      await Promise.all([loadStats(), loadAppStatus()]);
      addMessage('Settings saved.', 'assistant');
      if (button) button.textContent = 'Saved';
      setTimeout(() => {
        if (button) button.textContent = originalLabel;
        closeSettings();
      }, 800);
    }
  } catch {
    addMessage('Could not save settings.', 'assistant');
    if (button) button.textContent = originalLabel;
  }
}

// ────────────────────────────────────────
// Data Export / Import
// ────────────────────────────────────────

async function exportData() {
  updateStatus('Exporting...');
  try {
    const result = await api.exportData();
    if (result.cancelled) { updateStatus('Ready'); return; }
    addMessage(`Backup exported to ${result.filePath}.`, 'assistant');
  } catch {
    addMessage('Export failed.', 'assistant');
  } finally {
    restoreStatus();
  }
}

async function importData() {
  const confirmed = window.confirm('This will replace current local data. Continue?');
  if (!confirmed) return;

  updateStatus('Importing...');
  try {
    const result = await api.importData();
    if (result.cancelled) { updateStatus('Ready'); return; }
    currentSettings = result.settings || currentSettings;
    await refreshApp();
    addMessage(`Imported ${result.counts.habits} habits, ${result.counts.journalEntries} journal entries.`, 'assistant');
  } catch {
    addMessage('Import failed.', 'assistant');
  } finally {
    restoreStatus();
  }
}

// ────────────────────────────────────────
// Stats & Activities
// ────────────────────────────────────────

function updateWaterGoal(goal) {
  document.getElementById('waterGoalDisplay').textContent = goal;
}

async function loadStats() {
  const stats = await api.getStats();
  document.getElementById('waterCount').textContent = stats.water || 0;
  document.getElementById('breakCount').textContent = stats.breaks || 0;
  document.getElementById('sleepHours').textContent = stats.sleep || 0;
  document.getElementById('moodScore').textContent = stats.mood || '😊';
  document.getElementById('waterProgress').textContent = stats.water || 0;

  const waterGoal = currentSettings?.waterGoal || 8;
  const pct = Math.min(((stats.water || 0) / waterGoal) * 100, 100);
  document.getElementById('waterProgressBar').style.width = `${pct}%`;
  document.getElementById('sleepInput').value = stats.sleep || '';
  setSelectedMood(stats.mood || '😊');
}

function setSelectedMood(emoji) {
  document.querySelectorAll('.mood-btn').forEach((b) => {
    b.classList.toggle('selected', b.textContent === emoji);
  });
}

function randomMessage(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

async function logWater() {
  await api.logActivity({ type: 'water' });
  await loadStats();
  const msg = randomMessage(ACTIVITY_MESSAGES.water);
  addMessage(msg, 'assistant');
  if (voiceEnabled) speak(msg);
}

async function logBreak() {
  await api.logActivity({ type: 'break' });
  await loadStats();
  const msg = randomMessage(ACTIVITY_MESSAGES.break);
  addMessage(msg, 'assistant');
  if (voiceEnabled) speak(msg);
}

async function logMeal() {
  await api.logActivity({ type: 'meal' });
  const msg = randomMessage(ACTIVITY_MESSAGES.meal);
  addMessage(msg, 'assistant');
  if (voiceEnabled) speak(msg);
}

async function logExercise() {
  await api.logActivity({ type: 'exercise' });
  await loadStats();
  const msg = randomMessage(ACTIVITY_MESSAGES.exercise);
  addMessage(msg, 'assistant');
  if (voiceEnabled) speak(msg);
}

async function logSleep() {
  const hours = Number.parseFloat(document.getElementById('sleepInput').value);
  if (Number.isNaN(hours) || hours <= 0) return;

  await api.logActivity({ type: 'sleep', value: hours });
  await loadStats();

  let msg = 'Sleep logged.';
  if (hours < 6) msg = 'Sleep logged. Try for a bit more tonight.';
  else if (hours < 7) msg = 'Sleep logged. Close to a good range.';
  else if (hours <= 9) msg = 'Sleep logged. Solid rest.';
  else msg = 'Sleep logged. Plenty of rest.';

  addMessage(msg, 'assistant');
  if (voiceEnabled) speak(msg);
}

async function setMood(emoji, score, event) {
  await api.logActivity({ type: 'mood', value: emoji, score });
  await loadStats();
  if (event?.target) setSelectedMood(event.target.textContent);
  const msg = MOOD_MESSAGES[emoji];
  addMessage(msg, 'assistant');
  if (voiceEnabled) speak(msg);
}

// ────────────────────────────────────────
// Journal
// ────────────────────────────────────────

async function saveJournalEntry() {
  const input = document.getElementById('journalEntryInput');
  const content = input.value.trim();
  if (!content) { addMessage('Write something first.', 'assistant'); return; }

  try {
    await api.saveJournalEntry({ content, mood: document.getElementById('moodScore').textContent });
    input.value = '';
    await loadJournalEntries();
    addMessage('Reflection saved.', 'assistant');
  } catch {
    addMessage('Could not save that.', 'assistant');
  }
}

function formatJournalTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

async function loadJournalEntries() {
  const entries = await api.getJournalEntries(6);
  const list = document.getElementById('journalEntriesList');
  list.innerHTML = '';

  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No reflections yet.';
    list.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    const card = document.createElement('div');
    card.className = 'journal-entry';
    const meta = document.createElement('div');
    meta.className = 'journal-meta';
    meta.textContent = `${entry.mood || '📝'} ${formatJournalTimestamp(entry.created_at)}`;
    const body = document.createElement('div');
    body.className = 'journal-body';
    body.textContent = entry.content;
    card.appendChild(meta);
    card.appendChild(body);
    list.appendChild(card);
  });
}

// ────────────────────────────────────────
// App Status / Checklist
// ────────────────────────────────────────

function renderChecklistItem(container, label, complete, detail = '', optional = false) {
  const item = document.createElement('div');
  item.className = `checklist-item ${complete ? 'complete' : ''} ${optional ? 'optional' : ''}`;
  const icon = document.createElement('div');
  icon.className = 'checklist-icon';
  icon.textContent = complete ? '✓' : optional ? '•' : '○';
  const bodyDiv = document.createElement('div');
  const title = document.createElement('div');
  title.className = 'checklist-title';
  title.textContent = label;
  const sub = document.createElement('div');
  sub.className = 'checklist-subtitle';
  sub.textContent = detail;
  bodyDiv.appendChild(title);
  bodyDiv.appendChild(sub);
  item.appendChild(icon);
  item.appendChild(bodyDiv);
  container.appendChild(item);
}

async function loadAppStatus() {
  const checklist = document.getElementById('setupChecklist');
  checklist.innerHTML = '';

  try {
    const status = await api.getAppStatus();
    const ollamaDetail = status.ollama.available
      ? status.ollama.modelInstalled
        ? `${status.ollama.currentModel} ready`
        : `${status.ollama.currentModel} not installed`
      : status.ollama.error || 'Ollama not reachable';

    renderChecklistItem(checklist, 'Model', status.ollama.available && status.ollama.modelInstalled, ollamaDetail);
    renderChecklistItem(checklist, 'Profile', status.checklist.profileConfigured, status.checklist.profileConfigured ? 'Configured' : 'Add name or focus');
    renderChecklistItem(checklist, 'Habit', status.checklist.hasHabit, status.checklist.hasHabit ? 'Active' : 'Add one habit');
    renderChecklistItem(checklist, 'Reflection', status.checklist.hasJournalEntry, status.checklist.hasJournalEntry ? 'Active' : 'Write one');
    renderChecklistItem(checklist, 'Calendar', status.checklist.calendarConnected, status.checklist.calendarConnected ? 'Connected' : 'Optional', true);

    const nextStatus = status.ollama.available
      ? status.ollama.modelInstalled ? 'Online' : 'Model Missing'
      : 'Offline';
    setBaseStatus(nextStatus);
  } catch {
    renderChecklistItem(checklist, 'Status', false, 'Unable to check');
    setBaseStatus('Unknown');
  }
}

async function refreshStatusPanel() {
  updateStatus('Checking...');
  try {
    await Promise.all([loadAppStatus(), loadCalendarStatus()]);
  } finally {
    restoreStatus();
  }
}

// ────────────────────────────────────────
// Habits
// ────────────────────────────────────────

async function loadHabits() {
  const habits = await api.getHabits();
  const list = document.getElementById('habitsList');
  list.innerHTML = '';

  if (!habits.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'Add a habit to start.';
    list.appendChild(empty);
    return;
  }

  habits.forEach((habit) => {
    const row = document.createElement('div');
    row.className = 'habit-row';
    const meta = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'habit-name';
    name.textContent = `${habit.icon || '✨'} ${habit.name}`;
    const sub = document.createElement('div');
    sub.className = 'habit-subtitle';
    sub.textContent = `${habit.streak || 0} day streak`;
    meta.appendChild(name);
    meta.appendChild(sub);

    const btn = document.createElement('button');
    btn.className = 'action-pill habit-complete';
    if (habit.completed) {
      btn.classList.add('completed');
      btn.textContent = 'Done';
      btn.disabled = true;
    } else {
      btn.textContent = 'Complete';
      btn.addEventListener('click', () => completeHabit(habit.id, habit.name));
    }

    row.appendChild(meta);
    row.appendChild(btn);
    list.appendChild(row);
  });
}

async function createHabit() {
  const nameInput = document.getElementById('habitNameInput');
  const iconInput = document.getElementById('habitIconInput');
  const name = nameInput.value.trim();
  if (!name) { addMessage('Name the habit first.', 'assistant'); return; }

  try {
    await api.createHabit({ name, icon: iconInput.value });
    nameInput.value = '';
    await Promise.all([loadHabits(), loadWeeklyOverview()]);
    addMessage(`Habit added: ${name}`, 'assistant');
  } catch (error) {
    addMessage(error.message || 'Could not add habit.', 'assistant');
  }
}

async function completeHabit(habitId, habitName) {
  try {
    const result = await api.completeHabit(habitId);
    await Promise.all([loadHabits(), loadWeeklyOverview()]);
    if (result.alreadyCompleted) {
      addMessage(`${habitName} already done today.`, 'assistant');
      return;
    }
    addMessage(`${habitName} completed.`, 'assistant');
  } catch (error) {
    addMessage(error.message || 'Could not update habit.', 'assistant');
  }
}

async function loadWeeklyOverview() {
  const [rows, habits] = await Promise.all([api.getWeeklyStats(), api.getHabits()]);
  const overview = document.getElementById('weeklyOverview');
  overview.innerHTML = '';

  const totalWater = rows.reduce((s, r) => s + (r.water || 0), 0);
  const totalBreaks = rows.reduce((s, r) => s + (r.breaks || 0), 0);
  const totalExercise = rows.reduce((s, r) => s + (r.exercise || 0), 0);
  const sleepVals = rows.map((r) => r.sleep || 0).filter((v) => v > 0);
  const avgSleep = sleepVals.length ? (sleepVals.reduce((s, v) => s + v, 0) / sleepVals.length).toFixed(1) : '0';

  [
    { title: 'Days', value: `${rows.length}/7` },
    { title: 'Water', value: `${totalWater}` },
    { title: 'Breaks', value: `${totalBreaks}` },
    { title: 'Exercise', value: `${totalExercise}` },
    { title: 'Avg Sleep', value: `${avgSleep}h` },
    { title: 'Habits', value: `${habits.length}` }
  ].forEach((item) => {
    const card = document.createElement('div');
    card.className = 'summary-card';
    const h = document.createElement('h4');
    h.textContent = item.title;
    const p = document.createElement('p');
    p.textContent = item.value;
    card.appendChild(h);
    card.appendChild(p);
    overview.appendChild(card);
  });
}

// ────────────────────────────────────────
// Tabs
// ────────────────────────────────────────

function switchTab(tab, event) {
  document.querySelectorAll('.panel-tab').forEach((b) => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  document.querySelectorAll('.panel-content').forEach((c) => {
    c.classList.toggle('active', c.id === `${tab}-tab`);
  });

  if (tab === 'habits') { loadHabits(); loadWeeklyOverview(); }
  if (tab === 'health') { loadJournalEntries(); }
  if (tab === 'calendar') { loadCalendarStatus(); loadSchedule(); }
  if (event?.target) event.target.blur();
}

// ────────────────────────────────────────
// Calendar
// ────────────────────────────────────────

async function loadCalendarStatus() {
  const status = await api.getCalendarStatus();
  const div = document.getElementById('calendarStatus');

  if (status.connected) {
    div.innerHTML = '<div style="color:#4ade80;padding:8px;background:rgba(74,222,128,0.08);border-radius:8px;font-size:12px;">Connected</div>';
    return;
  }
  if (status.configured) {
    div.innerHTML = '<div style="color:#fbbf24;padding:8px;background:rgba(251,191,36,0.08);border-radius:8px;font-size:12px;">Needs authorization</div>';
    return;
  }
  div.innerHTML = '<div style="color:#f87171;padding:8px;background:rgba(248,113,113,0.06);border-radius:8px;font-size:12px;">credentials.json missing</div>';
}

async function authorizeCalendar() {
  updateStatus('Connecting...');
  try {
    const result = await api.authorizeCalendar();
    await loadCalendarStatus();
    if (result.success) {
      await loadSchedule();
      addMessage(result.message || 'Calendar connected.', 'assistant');
    } else {
      addMessage(result.error || 'Connection failed.', 'assistant');
    }
  } catch (error) {
    addMessage(error.message || 'Connection failed.', 'assistant');
  } finally {
    await loadAppStatus();
    restoreStatus();
  }
}