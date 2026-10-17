/* Focus state contains only booleans and counters. Speech for autonomous events is server-owned. */
const FOCUS_DEBUG_INDENT = 2;
const FOCUS_POLL_MS = 1000;
const FOCUS_SECONDS_PER_MINUTE = 60;
const FOCUS_REQUEST_TIMEOUT_MS = 4000;
const FOCUS_COLLAPSED_KEY = 'jarvis.focus.collapsed.v2';
const FOCUS_ARC_LENGTH = 100;
const FOCUS_DRIFT_TICKS_MAX = 24;
const FOCUS_MORPH_MS = 420;
const FOCUS_MORPH_EASE = 'cubic-bezier(.22,1,.36,1)';
const FOCUS_SVG_NS = 'http://www.w3.org/2000/svg';
const FOCUS_PREFIX = /^(?:(?:hey )?jarvis[, ]+)?(?:please )?/i;
const FOCUS_RETARGET = /^(?:(?:okay|ok)\s+)?(?:(?:i'm|i’m|im|i am) (?:gonna need|going to need|need) you to )?(?:lock (?:on )?this tab|keep me in this tab|this is the tab|stay on this tab)$/i;
const FOCUS_NUMBER = '(?:[0-9]+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|ninety)';
const FOCUS_DURATION = new RegExp(`^${FOCUS_NUMBER}(?:[ -]${FOCUS_NUMBER})? (?:seconds?|minutes?|hours?)(?: on this)?$`, 'i');
const FOCUS_COMMAND = /^(?:[\w\s-]+ (?:seconds?|minutes?|hours?) on this|(?:start )?focus(?: session)?|call me out every .+|(?:give me|snooze(?: for)?) .+|(?:extend(?: focus| the session)?(?: by)?|add) .+|(?:pause|resume|end|finish|abort|cancel)(?: focus| the session)?|(?:it's|its|it is) (?:okay|ok)(?: .*)?)[.!?]*$/i;
(() => {
  const button = document.getElementById('focus');
  const status = document.getElementById('focus-status');
  let pending = false, latest = null, widget = null, collapsed = false;
  try { collapsed = localStorage.getItem(FOCUS_COLLAPSED_KEY) === '1'; } catch (_) {}
  const debugEnabled = new URLSearchParams(location.search).get('focusdebug') === '1';
  const debug = document.getElementById('focus-debug');
  if (debugEnabled) {
    debug.parentElement.open = true;
    document.body.append(debug);
    debug.style.cssText = 'position:fixed;top:12px;right:12px;z-index:100;background:var(--surface-2,#0f1316);color:var(--text-primary,#eceef0);padding:16px;max-height:80vh;overflow:auto;pointer-events:none';
  }
  const time = seconds => {
    const value = Math.max(0, Math.ceil(Number(seconds) || 0));
    return `${Math.floor(value / FOCUS_SECONDS_PER_MINUTE)}:${String(value % FOCUS_SECONDS_PER_MINUTE).padStart(2, '0')}`;
  };
  function setCollapsed(value, save = true) {
    const morphParts = widget && !widget.hidden ? [...widget.querySelectorAll('.focus-material,.focus-dial,.focus-clock')] : [];
    const previous = morphParts.map(part => ({part, rect: part.getBoundingClientRect()}));
    morphParts.forEach(part => part.getAnimations?.().forEach(animation => animation.cancel()));
    collapsed = Boolean(value);
    if (widget) {
      const details = widget.querySelector('.focus-expanded');
      if (collapsed && details.contains(document.activeElement)) widget.querySelector('.focus-toggle').focus();
      widget.dataset.collapsed = String(collapsed);
      const toggle = widget.querySelector('.focus-toggle');
      toggle.setAttribute('aria-expanded', String(!collapsed));
      toggle.setAttribute('aria-label', collapsed ? 'Expand Focus Mode' : 'Collapse Focus Mode');
      toggle.querySelector('.focus-toggle-label').textContent = collapsed ? 'Expand' : 'Collapse';
      details.inert = collapsed;
      details.setAttribute('aria-hidden', String(collapsed));
      if (save && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches && document.documentElement?.dataset.motion !== 'reduced') {
        // FLIP the material and persistent instrument; layout itself never animates.
        previous.forEach(({part, rect}) => {
          const next = part.getBoundingClientRect();
          if (!next.width || !next.height || !part.animate) return;
          const base = getComputedStyle(part).transform;
          const end = base === 'none' ? '' : base;
          const start = `translate(${rect.left-next.left}px,${rect.top-next.top}px) scale(${rect.width/next.width},${rect.height/next.height}) ${end}`;
          part.animate([{transform:start},{transform:end || 'none'}], {duration:FOCUS_MORPH_MS, easing:FOCUS_MORPH_EASE});
        });
      }
    }
    if (save) { try { localStorage.setItem(FOCUS_COLLAPSED_KEY, collapsed ? '1' : '0'); } catch (_) {} }
  }
  function createWidget() {
    // The diagnostic fixture deliberately has no graph surface; keep it hermetic.
    const host = document.getElementById('stage');
    if (!host || !document.createElement) return;
    widget = document.createElement('section');
    widget.className = 'focus-widget';
    widget.setAttribute('aria-label', 'Focus Mode');
    widget.hidden = true;
    widget.innerHTML = `<div class="focus-material" aria-hidden="true"></div><header class="focus-heading"><span class="focus-eyebrow">FOCUS MODE</span><button class="focus-toggle" type="button" aria-controls="focus-expanded"><span class="focus-toggle-label"></span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 10 4-4 4 4"/></svg></button></header><div class="focus-instrument"><svg class="focus-dial" viewBox="0 0 120 120" role="progressbar" aria-label="Focus session elapsed" aria-valuemin="0" aria-valuemax="100"><circle class="focus-track" cx="60" cy="60" r="51"/><circle class="focus-progress" cx="60" cy="60" r="51" pathLength="100"/><g class="focus-drift-ticks"></g></svg><div class="focus-clock"><span class="focus-time">0:00</span><span class="focus-state" role="status">Waiting</span></div></div><div class="focus-expanded" id="focus-expanded"><div class="focus-metrics"><span class="focus-drift">0 drifts</span><span class="focus-credited">0:00 on target</span></div><p class="focus-guidance"></p><div class="focus-controls"><button type="button" data-focus-action="pause">Pause</button><button type="button" data-focus-action="retarget">Retarget</button><button type="button" data-focus-action="end">End</button><button type="button" data-focus-action="abort">Abort</button></div><p class="focus-save-status" role="status"></p></div>`;
    host.append(widget);
    widget.querySelector('.focus-toggle').addEventListener('click', () => setCollapsed(!collapsed));
    widget.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !collapsed) { event.stopPropagation(); setCollapsed(true); widget.querySelector('.focus-toggle').focus(); }
    });
    widget.querySelectorAll('[data-focus-action]').forEach(control => control.addEventListener('click', () => {
      const action = control.dataset.focusAction === 'pause' && latest?.paused ? 'resume' : control.dataset.focusAction;
      command({action});
    }));
    setCollapsed(collapsed, false);
  }
  function renderWidget(s, offline = false) {
    if (!widget) return;
    widget.hidden = !s.active && !s.completed && !s.aborted;
    const label = offline ? 'Disconnected' : s.lock_deferred ? 'Waiting to lock' : !s.known && s.active ? 'Activity unavailable' : s.paused ? 'Paused' : s.excused ? 'Excused' : s.home ? 'Home base' : s.drifting ? 'Return to task' : s.active ? 'On target' : s.aborted ? 'Aborted' : 'Complete';
    widget.dataset.state = offline ? 'offline' : s.lock_deferred ? 'armed' : !s.known && s.active ? 'unavailable' : s.paused ? 'paused' : s.drifting && !s.home ? 'drifting' : s.active ? 'active' : 'complete';
    widget.querySelector('.focus-time').textContent = time(s.remaining_s);
    widget.querySelector('.focus-state').textContent = label;
    const progress = s.planned_s > 0 ? Math.max(0, Math.min(FOCUS_ARC_LENGTH, s.elapsed_s / s.planned_s * FOCUS_ARC_LENGTH)) : 0;
    const dial = widget.querySelector('.focus-dial');
    dial.setAttribute('aria-valuenow', String(Math.round(progress)));
    dial.setAttribute('aria-valuetext', `${time(s.elapsed_s)} elapsed, ${time(s.remaining_s)} remaining. ${label}`);
    widget.querySelector('.focus-progress').style.strokeDashoffset = String(FOCUS_ARC_LENGTH - progress);
    const drifts = Math.max(0, Math.floor(Number(s.drifts) || 0));
    const marks = widget.querySelector('.focus-drift-ticks');
    if (marks.dataset.count !== String(drifts)) {
      marks.replaceChildren();
      for (let i = 0; i < Math.min(drifts, FOCUS_DRIFT_TICKS_MAX); i++) {
        const tick = document.createElementNS(FOCUS_SVG_NS, 'path');
        tick.setAttribute('d', 'M60 3v5');
        tick.setAttribute('transform', `rotate(${i / FOCUS_DRIFT_TICKS_MAX * 360} 60 60)`);
        marks.append(tick);
      }
      marks.dataset.count = String(drifts);
    }
    widget.querySelector('.focus-drift').textContent = `${drifts} ${drifts === 1 ? 'drift' : 'drifts'}`;
    widget.querySelector('.focus-credited').textContent = `${time(s.on_target_s)} on target`;
    widget.querySelector('.focus-guidance').textContent = offline ? 'Reconnecting to the session. The timer shows the last confirmed state.' : s.lock_deferred ? 'Switch to your task. Only a fresh, stable target starts the clock.' : s.paused ? 'Your timer is paused. Resume when you are ready.' : s.excused ? 'This detour is excused until you return to your target.' : s.active ? 'One task. Your elapsed time comes from the local session.' : `Streak ${s.streak || 0} · ${time(s.drift_s)} away`;
    widget.querySelector('.focus-save-status').textContent = s.ledger_ok === false ? 'Focus history or restart state could not be saved.' : '';
    widget.querySelectorAll('[data-focus-action]').forEach(control => {
      control.disabled = pending || offline || !s.active;
      if (control.dataset.focusAction === 'pause') control.textContent = s.paused ? 'Resume' : 'Pause';
    });
  }
  function render(s) {
    latest = s;
    if (s.snooze_s > 0) window.JarvisVoice?.quietFor?.(s.snooze_s * 1000);
    debug.textContent = JSON.stringify({active: Boolean(s.active), armed: Boolean(s.armed), paused: Boolean(s.paused), known: Boolean(s.known), home: Boolean(s.home), lock_deferred: Boolean(s.lock_deferred), app_only: Boolean(s.app_only), has_intent: Boolean(s.has_intent), drifts: s.drifts || 0, excused: Boolean(s.excused), intent_window_open: Boolean(window.JarvisVoice?.intentWindowOpen?.()), ...window.JarvisWatch?.debug?.()}, null, FOCUS_DEBUG_INDENT);
    if (!s.active) window.JarvisVoice?.cancelAnswer?.();
    window.JarvisVoice?.setExternalSpeaking?.(Boolean(s.speaking));
    const remaining = time(s.remaining_s);
    status.textContent = s.active ? s.lock_deferred ? 'Focus · waiting to lock on…' : !s.known ? 'Focus · activity unavailable' : s.armed ? 'Switch to your task…' : `${remaining} · ${s.paused ? 'Paused' : s.excused ? 'Excused' : s.home ? 'Home base' : s.drifting ? 'Return to task' : 'Focused'}` : s.completed || s.aborted ? `Streak ${s.streak} · ${s.drifts} drifts` : '';
    status.style.color = s.drifting && !s.home ? 'var(--warn,#e8b04a)' : 'var(--accent,#55dbc9)';
    button.textContent = s.active ? 'FOCUS ON' : 'FOCUS';
    button.disabled = pending || s.active;
    renderWidget(s);
    window.dispatchEvent?.(new CustomEvent('jarvis:focus-state', {detail: {...s}}));
  }
  async function command(body) {
    if (pending) return;
    pending = true; button.disabled = true;
    if (latest) renderWidget(latest);
    window.JarvisVoice?.setThinking(true);
    try {
      const response = await fetch('/focus', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...body, muted: new URLSearchParams(location.search).getAll('mute').includes('1')}), signal: AbortSignal.timeout(FOCUS_REQUEST_TIMEOUT_MS)});
      const data = await response.json();
      document.getElementById('answer').textContent = data.answer;
      window.JarvisVoice?.setThinking(false);
      if (response.ok && data.state?.active && (body.action === 'start' || (!body.action && /focusing on\?/.test(data.answer)))) {
        window.JarvisVoice?.answerOnce?.(answer => command({action: 'intent', intent: answer}));
      }
      if (!data.spoken) window.JarvisVoice?.speak(data.answer);
      if (data.state) render(data.state);
    } catch (_) { status.textContent = 'Focus request unconfirmed · checking server'; }
    finally { pending = false; window.JarvisVoice?.setThinking(false); await poll(); }
  }
  async function poll() {
    try {
      const response = await fetch('/focus', {signal: AbortSignal.timeout(FOCUS_REQUEST_TIMEOUT_MS)});
      if (!response.ok) throw new Error();
      render(await response.json());
    } catch (_) {
      window.JarvisVoice?.setExternalSpeaking?.(false); status.textContent = 'Focus server disconnected';
      if (latest) renderWidget(latest, true);
    }
  }
  window.JarvisFocus = {command, toggle: () => setCollapsed(!collapsed), expand: () => setCollapsed(false), collapse: () => setCollapsed(true), state: () => latest ? {...latest} : null, matches: text => {
    const clean = text.trim().replace(/[,.!?]/g, '').replace(FOCUS_PREFIX, '');
    if (/^(?:drill sergeant|normal) mode$/i.test(clean) || FOCUS_RETARGET.test(clean)) return true;
    if (!FOCUS_COMMAND.test(clean)) return false;
    if (/^(?:give me|snooze|call me out every|extend|add)\b/i.test(clean)) {
      return FOCUS_DURATION.test(clean.replace(/^(?:give me|snooze(?: for)?|call me out every|extend(?: focus| the session)?(?: by)?|add) /i, ''));
    }
    return !/ on this$/i.test(clean) || FOCUS_DURATION.test(clean);
  }};
  createWidget();
  window.addEventListener?.('storage', event => { if (event.key === FOCUS_COLLAPSED_KEY) setCollapsed(event.newValue === '1', false); });
  button.addEventListener('click', () => command({action: 'start', defer_lock: true}));
  async function loop() { await poll(); setTimeout(loop, FOCUS_POLL_MS); }
  loop();
})();
