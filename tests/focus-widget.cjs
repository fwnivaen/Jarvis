// Exercise the real widget with isolated numeric state; never contact the running server.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
class Element {
  constructor(name='div') { this.name=name; this.dataset={}; this.style={}; this.attributes={}; this.listeners={}; this.children=[]; this.hidden=false; this.textContent=''; this.parts=new Map(); }
  setAttribute(key,value) { this.attributes[key]=String(value); }
  addEventListener(event,handler) { this.listeners[event]=handler; }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children=children; }
  contains(node) { return node===this || this.children.includes(node); }
  focus() { doc.activeElement=this; }
  getBoundingClientRect() { return {left:0,top:0,width:100,height:100}; }
  querySelector(selector) { if(!this.parts.has(selector))this.parts.set(selector,new Element()); return this.parts.get(selector); }
  querySelectorAll(selector) {
    if(selector==='[data-focus-action]') {
      if(!this.controls)this.controls=['pause','retarget','end','abort'].map(action=>{const node=new Element('button');node.dataset.focusAction=action;return node;});
      return this.controls;
    }
    return [];
  }
}
const elements=new Map(), requests=[], timers=[], storage=new Map(), events={};
const el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
const doc={activeElement:null,getElementById:el,createElement:name=>new Element(name),createElementNS:(_ns,name)=>new Element(name)};
let state={active:true,known:true,planned_s:600,elapsed_s:150,remaining_s:450,on_target_s:120,drift_s:30,drifts:2,streak:1,ledger_ok:true}, disconnected=false;
const context={URLSearchParams,location:{search:'?mute=1'},document:doc,AbortSignal,
  localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
  setTimeout:fn=>timers.push(fn),
  window:{matchMedia:()=>({matches:true}),addEventListener:(name,fn)=>events[name]=fn,JarvisVoice:{setThinking(){},setExternalSpeaking(){},speak(){}}},
  fetch:async(path,options)=>{requests.push({path,options});if(disconnected)throw Error('offline');return {ok:true,json:async()=>options?.method==='POST'?{answer:'Confirmed',spoken:true,state}:state};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('viewer/focus.js','utf8'),context);
async function flush(){for(let i=0;i<20;i++)await Promise.resolve();}
async function poll(){assert.ok(timers.length);timers.shift()();await flush();}
(async()=>{
  await flush();
  const widget=el('stage').children[0];assert.ok(widget);assert.equal(widget.hidden,false);
  const dial=widget.querySelector('.focus-dial'), clock=widget.querySelector('.focus-clock');
  assert.equal(widget.querySelector('.focus-progress').style.strokeDashoffset,'75');
  assert.equal(dial.attributes['aria-valuenow'],'25');
  assert.equal(widget.querySelector('.focus-time').textContent,'7:30');
  assert.equal(widget.querySelector('.focus-drift-ticks').children.length,2);
  assert.equal(requests.filter(r=>r.options?.method==='POST').length,0);
  widget.querySelector('.focus-toggle').listeners.click();
  assert.equal(widget.dataset.collapsed,'true');
  assert.equal(widget.querySelector('.focus-toggle').attributes['aria-expanded'],'false');
  assert.equal(widget.querySelector('.focus-expanded').inert,true);
  assert.equal(storage.get('jarvis.focus.collapsed.v2'),'1');
  assert.equal(widget.querySelector('.focus-clock'),clock);assert.equal(widget.querySelector('.focus-dial'),dial);
  state={...state,paused:true,elapsed_s:180,remaining_s:420,drifts:32};await poll();
  assert.equal(widget.dataset.state,'paused');assert.equal(widget.querySelector('.focus-progress').style.strokeDashoffset,'70');
  assert.equal(widget.querySelector('.focus-drift-ticks').children.length,24);assert.equal(widget.querySelector('.focus-drift').textContent,'32 drifts');
  const pause=widget.querySelectorAll('[data-focus-action]')[0];assert.equal(pause.textContent,'Resume');
  pause.listeners.click();await flush();
  assert.equal(JSON.parse(requests.find(r=>r.options?.method==='POST').options.body).action,'resume');
  disconnected=true;await poll();
  assert.equal(widget.dataset.state,'offline');assert.equal(widget.querySelector('.focus-time').textContent,'7:00');assert.ok(pause.disabled);
  events.storage({key:'jarvis.focus.collapsed.v2',newValue:'0'});assert.equal(widget.dataset.collapsed,'false');
  widget.listeners.keydown({key:'Escape',stopPropagation(){}});assert.equal(widget.dataset.collapsed,'true');
  console.log('FOCUS WIDGET PASS: shared persistent clock/dial, real elapsed arc, real bounded drift ticks, saved/synced morph state, accessible collapse, existing controls, offline freeze.');
})().catch(error=>{console.error(error);process.exitCode=1});
