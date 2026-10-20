// Production activity drawer with a fake local response; no browser permissions.
const {readFileSync}=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const SOURCE=readFileSync('viewer/agents.js','utf8'),SECRET='DO_NOT_RENDER_REASONING',REQUEST_MS=250000;
function element(){return {hidden:true,textContent:'',dataset:{},children:[],append(child){this.children.push(child);},replaceChildren(){this.children=[];}};}
async function setup(data){
 const elements=Object.fromEntries(['agent-monitor','agent-rows','agent-summary','agent-limits'].map(id=>[id,element()]));
 let timer=null,cleared=false;const listeners={};
 const context={console,Math,setTimeout(fn){timer=fn;return 1;},clearTimeout(){cleared=true;},
  document:{hidden:false,getElementById:id=>elements[id],createElement:element},
  window:{addEventListener(name,fn){listeners[name]=fn;}},
  fetch:async()=>({ok:true,json:async()=>data})};
 vm.runInNewContext(SOURCE,context);await new Promise(resolve=>setImmediate(resolve));
 return {elements,api:context.window.JarvisAgents,listeners,poll:()=>timer(),cleared:()=>cleared};
}
(async()=>{
 const limits={max_workers:3,worker_timeout_s:45,max_escalations:1,request_timeout_s:240};
 const off=await setup({enabled:false,agents:[],limits});
 assert.equal(off.elements['agent-monitor'].hidden,true);assert.equal(off.api.timeoutMs(100000),100000);off.api.destroy();
 const active=await setup({enabled:true,routing_enabled:true,active:true,elapsed_s:1.5,escalations:0,limits,
  reasoning:SECRET,agents:[{role:'worker',model:'gpt-6-luna',status:'running',current_tool:null,
   elapsed_s:1.2,retries:1,total_tokens:null,reasoning:SECRET,task:SECRET}]});
 assert.equal(active.elements['agent-monitor'].hidden,false);
 const cells=active.elements['agent-rows'].children[0].children.map(cell=>cell.textContent);
 assert.deepEqual(cells,['Worker','gpt-6-luna','running','—','1.2s','1','Unavailable']);
 assert.ok(!JSON.stringify(active.elements).includes(SECRET));
 assert.equal(active.api.timeoutMs(100000),REQUEST_MS);
 active.listeners.pagehide();assert.equal(active.cleared(),true);
 console.log('AGENTS PASS: flag-off hiding, live metadata, unknown token counts, no task/reasoning rendering, request deadline and teardown.');
})().catch(error=>{console.error(error);process.exitCode=1;});
