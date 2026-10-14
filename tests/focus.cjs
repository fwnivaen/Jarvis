// Execute the real focus controller and shared voice/text submission entry point.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const elements = new Map(), requests = [], spoken = [];
const state = {active: true, known: true, armed: false, paused: false, remaining_s: 1734, drifting: false};
const el = id => {
  if (!elements.has(id)) elements.set(id, {textContent: '', style: {}, addEventListener(event, fn) {this[event] = fn;}});
  return elements.get(id);
};
const context = {document: {getElementById: el}, AbortSignal, setTimeout() {},
  window: {JarvisVoice: {interrupt: () => false, setThinking() {}, speak(text) {spoken.push(text);}}},
  fetch: async (path, options) => {requests.push({path, options}); return {ok: true, json: async () => options?.method === 'POST' ? {answer: 'Focus paused.', state} : state};}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('viewer/focus.js', 'utf8'), context);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(el('focus-status').textContent, '28:54 · Focused');
  assert.equal(requests[0].path, '/focus'); // Rejoins without starting another session.
  for (const text of ['thirty minutes on this', 'call me out every thirty seconds', 'give me fifteen seconds', "it's okay, I'm doing research", 'pause', 'resume', 'extend by five minutes', 'abort', 'lock on this tab', 'lock this tab', 'keep me in this tab', 'this is the tab', 'stay on this tab', "okay, I'm gonna need you to keep me in this tab."]) {
    assert.equal(context.window.JarvisFocus.matches(text), true, text);
  }
  for (const text of ['What are our Quarterly Goals?', 'give me a summary', 'add a note', 'lock my screen']) assert.equal(context.window.JarvisFocus.matches(text), false);
  const html = fs.readFileSync('viewer/index.html', 'utf8');
  vm.runInContext(html.match(/async function ask\(question\)\{[\s\S]*?(?=\n<\/script>)/)[0], context);
  await context.ask('pause');
  const posts = requests.filter(r => r.options?.method === 'POST');
  assert.equal(posts.length, 1);
  assert.equal(posts[0].path, '/focus');
  assert.equal(JSON.parse(posts[0].options.body).question, 'pause');
  assert.deepEqual(spoken, ['Focus paused.']);
  await context.ask('lock this tab');
  assert.equal(JSON.parse(requests.filter(r => r.options?.method === 'POST').at(-1).options.body).question, 'lock this tab');
  console.log('FOCUS PASS: reload joins numeric server state; voice/text commands bypass brain and screen routes; local confirmation.');
})().catch(error => {console.error(error); process.exitCode = 1;});
