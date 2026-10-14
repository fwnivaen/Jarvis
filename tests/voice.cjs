// Browser speech doubles + virtual clock: no audio, network, or paid service.
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = readFileSync('viewer/index.html', 'utf8');
const source = html.match(/<script id="voice-controller">([\s\S]*?)<\/script>/)[1];
const FINISH = 900, MID_PAUSE = 600, BRAIN_WAIT = 8000;
function setup(search = '', supported = true) {
  let now = 0, next = 0, cancels = 0;
  const timers = new Map(), elements = new Map(), speech = [], recognizers = [], sent = [];
  const el = id => {
    if (!elements.has(id)) elements.set(id, {textContent: id === 'answer' ? 'Ready when you are.' : '', setAttribute() {}});
    return elements.get(id);
  };
  let click;
  class Recognition {
    constructor() { recognizers.push(this); }
    start() {}
    abort() { this.onend?.(); }
    result(parts) { this.onresult({resultIndex: 0, results: parts.map(([text, final]) => Object.assign([{transcript: text}], {isFinal: final}))}); }
  }
  const synth = {getVoices: () => [{name: 'Samantha', lang: 'en-US'}, {name: 'Serena', lang: 'en-GB'}, {name: 'Daniel (English (UK))', lang: 'en-GB', voiceURI: 'com.apple.voice.enhanced.en-GB.Daniel'}], cancel() {cancels++;}, speak(u) {speech.push(u);}};
  const context = {URLSearchParams, location: {search}, SpeechSynthesisUtterance: function(text) {this.text = text;},
    document: {getElementById: el, addEventListener(_, fn) {click = fn;}},
    setTimeout(fn, ms) {timers.set(++next, {fn, at: now + ms}); return next;},
    clearTimeout(id) {timers.delete(id);}, window: {speechSynthesis: synth, webkitSpeechRecognition: supported ? Recognition : undefined}};
  vm.runInNewContext(source, context);
  const voice = context.window.JarvisVoice;
  voice.setSubmit(q => {sent.push(q); voice.setThinking(true);});
  function tick(ms) {now += ms; for (const [id, t] of [...timers]) if (t.at <= now) {timers.delete(id); t.fn();}}
  return {context, voice, speech, sent, el, tick, click: () => click({isTrusted: true}), mic: () => el('mic').onclick(), current: () => recognizers.at(-1), cancels: () => cancels};
}
const a = setup();
assert.equal(a.speech.length, 0);
a.click(); assert.equal(a.speech.length, 1); assert.equal(a.speech[0].voice.lang, 'en-GB'); assert.equal(a.speech[0].voice.name, 'Daniel (English (UK))');
a.click(); assert.equal(a.speech.length, 1);
a.speech[0].onend(); a.mic();
assert.equal(a.el('voice-status').textContent, 'Listening…');
a.current().result([['Tell me about', true]]); a.tick(MID_PAUSE); assert.deepEqual(a.sent, []);
a.current().onspeechstart(); a.tick(FINISH); assert.deepEqual(a.sent, []);
a.current().result([['Tell me about', true], ['the quarterly', false]]); a.tick(FINISH); assert.deepEqual(a.sent, []);
a.current().result([['Tell me about', true], ['the quarterly goals', true]]);
a.tick(FINISH - 1); assert.deepEqual(a.sent, []); a.tick(1);
assert.deepEqual(a.sent, ['Tell me about the quarterly goals']);
assert.equal(a.el('voice-status').textContent, 'Thinking…');
const stale = a.current(); a.mic(); stale.result([['Unwanted question', true]]); a.tick(BRAIN_WAIT);
assert.equal(a.el('voice-status').textContent, 'Thinking…'); assert.equal(a.sent.length, 1);
a.voice.setThinking(false); a.voice.speak('A long answer');
assert.equal(a.el('voice-status').textContent, 'Speaking…');
const count = a.cancels(); a.current().result([['stop', false]]);
assert.ok(a.cancels() > count); assert.equal(a.el('voice-status').textContent, 'Listening…');
a.tick(FINISH); assert.equal(a.sent.length, 1);
a.voice.speak('Another answer'); a.current().result([['wait', true]]);
assert.equal(a.el('voice-status').textContent, 'Listening…');
a.current().result([['Across', true]]); a.tick(MID_PAUSE); a.current().onend();
a.current().result([['sessions', true]]); a.tick(FINISH);
assert.equal(a.sent.at(-1), 'Across sessions');
const capture = setup(); capture.mic();
capture.current().result([['remember that the finish window', true]]); capture.tick(MID_PAUSE);
capture.current().result([['remember that the finish window', true], ['should be 900 milliseconds', false]]); capture.tick(FINISH);
assert.equal(capture.sent.length, 0);
capture.current().result([['remember that the finish window', true], ['should be 900 milliseconds', true]]); capture.tick(FINISH);
assert.deepEqual(capture.sent, ['remember that the finish window should be 900 milliseconds']);
const oneAnswer = setup();
const answers = [];
oneAnswer.voice.answerOnce(text => answers.push(text));
oneAnswer.voice.setExternalSpeaking(true);
assert.equal(oneAnswer.current(), undefined);
oneAnswer.voice.setExternalSpeaking(false);
assert.equal(oneAnswer.current(), undefined); // An organ cannot open the microphone.
oneAnswer.mic();
const answerRecognition = oneAnswer.current();
answerRecognition.result([['Finish the quarterly budget', true]]); oneAnswer.tick(FINISH);
assert.deepEqual(answers, ['Finish the quarterly budget']);
assert.deepEqual(oneAnswer.sent, []);
assert.equal(oneAnswer.el('mic').textContent, 'Mic on');
answerRecognition.result([['Do not submit twice', true]]); oneAnswer.tick(FINISH);
assert.equal(answers.length, 1);
const muted = setup('?mute=1'); muted.click(); muted.mic(); muted.voice.speak('Never audible');
assert.equal(muted.speech.length, 0);
muted.current().result([['Still works', true]]); muted.tick(FINISH); assert.deepEqual(muted.sent, ['Still works']);
const missingVoice = setup();
missingVoice.context.window.speechSynthesis.getVoices = () => [{name: 'Samantha', lang: 'en-US'}];
missingVoice.click();
assert.equal(missingVoice.speech.length, 0);
assert.match(missingVoice.el('voice-status').textContent, /Daniel British voice unavailable/);
const denied = setup(); denied.mic(); denied.current().onerror({error: 'not-allowed'});
assert.match(denied.el('voice-status').textContent, /permission denied/);
const unsupported = setup('', false); assert.equal(unsupported.el('mic').disabled, false);
console.log('VOICE PASS: activation, British voice, 900ms buffering, interim speech, session restart, 8s thinking, busy mic, immediate interrupts, mute, permission and unsupported states.');

(async () => {
  const loadingVoice = setup();
  const loadingSynth = loadingVoice.context.window.speechSynthesis;
  const installedVoices = loadingSynth.getVoices();
  let voicesReady;
  loadingSynth.getVoices = () => [];
  loadingSynth.addEventListener = (_, handler) => { voicesReady = handler; };
  loadingSynth.removeEventListener = () => {};
  loadingVoice.click();
  assert.equal(loadingVoice.speech.length, 0);
  loadingSynth.getVoices = () => installedVoices;
  voicesReady(); await Promise.resolve();
  assert.equal(loadingVoice.speech[0].voice.name, 'Daniel (English (UK))');

  const native = setup('?mute=1');
  const calls=[];
  native.context.fetch=async(path)=>{calls.push(path);return {ok:true,json:async()=>path.endsWith('/start')?{token:'test',status:'starting'}:path.endsWith('/stop')?{status:'stopped'}:{status:'listening',sequence:1,text:'A native sentence'}}};
  native.mic();native.current().onerror({error:'network'});
  for(let i=0;i<12;i++)await Promise.resolve();
  assert.ok(calls.includes('/voice/start'));
  assert.ok(calls.includes('/voice/poll'));
  native.tick(FINISH);
  assert.deepEqual(native.sent,['A native sentence']);
  assert.ok(calls.includes('/voice/stop'));
  const echo = setup();
  let heard='',seq=0;
  echo.context.fetch=async(path)=>({ok:true,json:async()=>path.endsWith('/start')?{token:'echo',status:'starting'}:path.endsWith('/stop')?{status:'stopped'}:{status:'listening',sequence:++seq,text:heard}});
  echo.click();echo.speech[0].onend();echo.mic();echo.current().onerror({error:'network'});
  for(let i=0;i<12;i++)await Promise.resolve();
  echo.voice.speak('The answer is ten pounds.');
  heard='The answer is ten pounds';echo.tick(150);
  for(let i=0;i<12;i++)await Promise.resolve();
  echo.tick(FINISH);assert.deepEqual(echo.sent,[]);
  heard='';echo.speech.at(-1).onend();
  for(let i=0;i<12;i++)await Promise.resolve();
  heard='My next question';echo.tick(150);
  for(let i=0;i<12;i++)await Promise.resolve();
  echo.tick(FINISH);assert.deepEqual(echo.sent,['My next question']);
  const external = setup('?mute=1');
  external.mic(); const oldRecognition = external.current();
  external.voice.setExternalSpeaking(true);
  oldRecognition.result([['Back to work sir', true]]); external.tick(FINISH);
  assert.deepEqual(external.sent, []);
  external.voice.setExternalSpeaking(false);
  external.current().result([['pause', true]]); external.tick(FINISH);
  assert.deepEqual(external.sent, ['pause']);
  const app = setup('?mute=1');
  let resolveReply, request;
  const response = new Promise(resolve => { resolveReply = resolve; });
  for (const id of ['send', 'question', 'suggestions', 'sources', 'answer-meta', 'answer-label', 'answer']) {
    Object.assign(app.el(id), {value: '', classList: {add() {}, remove() {}}, replaceChildren() {}, focus() {}});
  }
  Object.assign(app.context, {console, AbortController, fetch: (path, options) => {request = {path, options}; return response;}});
  vm.runInNewContext("const $ = id => document.getElementById(id); let screenMode = false, screenGeneration = 0; let busy = false, highlighted, activeLinks, selected; const GRAPH = {nodes: [], links: []}; const SETTINGS = {chatTimeoutMs: 100000, timePrecision: 2}; function isModelCommand() { return false; } function holdCamera() {} function showAnswerSources() {} function linkKey() {} function refreshHighlights() {}", app.context);
  vm.runInNewContext(html.match(/async function ask\(question\)\{[\s\S]*?(?=\n<\/script>)/)[0], app.context);
  vm.runInNewContext(html.match(/const CAPTURE_TRIGGER = .*;/)[0], app.context);
  const pendingReply = app.context.ask('A typed question');
  assert.equal(request.path, '/chat');
  assert.equal(JSON.parse(request.options.body).question, 'A typed question');
  app.tick(BRAIN_WAIT);
  assert.equal(app.el('voice-status').textContent, 'Thinking…');
  assert.equal(app.el('mic').disabled, true);
  resolveReply({ok: true, json: async () => ({answer: 'A real-shaped answer', nodes: [], elapsed_s: 8})});
  await pendingReply;
  assert.equal(app.el('answer').textContent, 'A real-shaped answer');
  assert.equal(app.el('voice-status').textContent, 'Ready');
  assert.equal(app.el('mic').disabled, false);
  assert.equal(app.speech.length, 0);
  console.log('CHAT PASS: shared /chat request, full delayed-response thinking, response display, mic recovery, mute.');
})().catch(error => { console.error(error); process.exitCode = 1; });
