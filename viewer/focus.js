/* Focus state contains only booleans and counters. Speech for autonomous events is server-owned. */
const FOCUS_POLL_MS = 1000;
const FOCUS_SECONDS_PER_MINUTE = 60;
const FOCUS_REQUEST_TIMEOUT_MS = 4000;
const FOCUS_PREFIX = /^(?:(?:hey )?jarvis[, ]+)?(?:please )?/i;
const FOCUS_NUMBER = '(?:[0-9]+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|ninety)';
const FOCUS_DURATION = new RegExp(`^${FOCUS_NUMBER}(?:[ -]${FOCUS_NUMBER})? (?:seconds?|minutes?|hours?)(?: on this)?$`, 'i');
const FOCUS_COMMAND = /^(?:[\w\s-]+ (?:seconds?|minutes?|hours?) on this|(?:start )?focus(?: session)?|call me out every .+|(?:give me|snooze(?: for)?) .+|(?:extend(?: focus| the session)?(?: by)?|add) .+|(?:pause|resume|end|finish|abort|cancel)(?: focus| the session)?|(?:it's|its|it is) (?:okay|ok)(?: .*)?)[.!?]*$/i;
(() => {
  const button = document.getElementById('focus');
  const status = document.getElementById('focus-status');
  let pending = false;
  function render(s) {
    window.JarvisVoice?.setExternalSpeaking?.(Boolean(s.speaking));
    const remaining = `${Math.floor(s.remaining_s / FOCUS_SECONDS_PER_MINUTE)}:${String(s.remaining_s % FOCUS_SECONDS_PER_MINUTE).padStart(2, '0')}`;
    status.textContent = s.active ? !s.known ? 'Focus · activity unavailable' : s.armed ? 'Switch to your task…' : `${remaining} · ${s.paused ? 'Paused' : s.excused ? 'Excused' : s.home ? 'Home base' : s.drifting ? 'Return to task' : 'Focused'}` : s.completed || s.aborted ? `Streak ${s.streak} · ${s.drifts} drifts` : '';
    status.style.color = s.drifting && !s.home ? '#ffad84' : '#a5dacf';
    button.textContent = s.active ? 'FOCUS ON' : 'FOCUS';
    button.disabled = pending || s.active;
  }
  async function command(body) {
    if (pending) return;
    pending = true; button.disabled = true;
    window.JarvisVoice?.setThinking(true);
    try {
      const response = await fetch('/focus', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal: AbortSignal.timeout(FOCUS_REQUEST_TIMEOUT_MS)});
      const data = await response.json();
      document.getElementById('answer').textContent = data.answer;
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
    } catch (_) { window.JarvisVoice?.setExternalSpeaking?.(false); status.textContent = 'Focus server disconnected'; }
  }
  window.JarvisFocus = {command, matches: text => {
    const clean = text.trim().replace(/[,.!?]/g, '').replace(FOCUS_PREFIX, '');
    if (!FOCUS_COMMAND.test(clean)) return false;
    if (/^(?:give me|snooze|call me out every|extend|add)\b/i.test(clean)) {
      return FOCUS_DURATION.test(clean.replace(/^(?:give me|snooze(?: for)?|call me out every|extend(?: focus| the session)?(?: by)?|add) /i, ''));
    }
    return !/ on this$/i.test(clean) || FOCUS_DURATION.test(clean);
  }};
  button.addEventListener('click', () => command({action: 'start'}));
  async function loop() { await poll(); setTimeout(loop, FOCUS_POLL_MS); }
  loop();
})();
