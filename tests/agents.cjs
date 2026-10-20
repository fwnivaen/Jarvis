// Production activity drawer with a fake local response; no browser permissions.
const {readFileSync}=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const SOURCE=readFileSync('viewer/agents.js','utf8'),SECRET='DO_NOT_RENDER_REASONING',REQUEST_MS=250000;
function element(){return {hidden:true,textContent:'',dataset:{},children:[],append(child){this.children.push(child);},replaceChildren(){this.children=[];}};}
async function setup(data){
 const elements=Object.fromEntries(['agent-monitor','agent-rows','agent-summary','agent-limits','agent-crew','crew-members','crew-summary'].map(id=>[id,element()]));
 let timer=null,cleared=false,offline=false;const listeners={};
 const context={console,Math,setTimeout(fn){timer=fn;return 1;},clearTimeout(){cleared=true;},
  document:{hidden:false,getElementById:id=>elements[id],createElement:element},
  window:{addEventListener(name,fn){listeners[name]=fn;}},
  fetch:async()=>{if(offline)throw Error('offline');return {ok:true,json:async()=>data};}};
 vm.runInNewContext(SOURCE,context);await new Promise(resolve=>setImmediate(resolve));
 return {elements,api:context.window.JarvisAgents,listeners,poll:()=>timer(),update(next){offline=false;data=next;return timer();},fail(){offline=true;return timer();},cleared:()=>cleared};
}
(async()=>{
 const limits={max_workers:3,worker_timeout_s:45,max_escalations:1,request_timeout_s:240};
 const off=await setup({enabled:false,agents:[],limits});
 assert.equal(off.elements['agent-monitor'].hidden,true);assert.equal(off.elements['agent-crew'].hidden,true);assert.equal(off.api.timeoutMs(100000),100000);off.api.destroy();
 const crew=[{id:'boss',role:'boss',model:'gpt-6.1-sol',effort:'max'},
  {id:'worker-1',role:'worker',model:'gpt-6.1-sol',effort:'medium'},
  {id:'worker-2',role:'worker',model:'gpt-6-luna',effort:'max'},
  {id:'worker-3',role:'worker',model:'gpt-6-luna',effort:'high'}];
 const data={enabled:true,routing_enabled:true,crew_enabled:true,crew,active:true,elapsed_s:1.5,escalations:0,limits,
  reasoning:SECRET,agents:[{role:'worker',slot:'worker-2',effort:'max',model:'gpt-6-luna',status:'running',current_tool:null,
   elapsed_s:1.2,retries:1,total_tokens:null,reasoning:SECRET,task:SECRET}]};
 const active=await setup(data);
 assert.equal(active.elements['agent-monitor'].hidden,false);
 const cells=active.elements['agent-rows'].children[0].children.map(cell=>cell.textContent);
 assert.deepEqual(cells,['Worker','gpt-6-luna','max','running','—','1.2s','1','Unavailable']);
 assert.equal(active.elements['agent-crew'].hidden,false);
 const cards=active.elements['crew-members'].children;
 assert.equal(cards.length,4);assert.equal(cards[0].dataset.slot,'boss');
 assert.equal(cards[2].dataset.status,'running');assert.equal(cards[1].dataset.status,'idle');
 assert.equal(cards[0].children[1].children[2].textContent,'MAX');
 assert.equal(cards[1].children[1].children[2].textContent,'MEDIUM');
 assert.equal(active.elements['crew-summary'].textContent,'1/3 working');
 await active.fail();assert.equal(active.elements['agent-crew'].dataset.connected,'false');
 assert.equal(active.elements['crew-summary'].textContent,'Connection interrupted');
 const sameCard=cards[2];
 await active.update({...data,active:false,agents:[{...data.agents[0],model:'gpt-6.1-sol',effort:'medium',status:'complete',total_tokens:42}]});
 assert.equal(active.elements['agent-crew'].dataset.connected,'true');
 assert.equal(active.elements['crew-members'].children[2],sameCard,'polling preserves avatar elements and animations');
 assert.equal(sameCard.children[1].children[1].textContent,'6.1 SOL');
 assert.equal(sameCard.children[1].children[2].textContent,'MEDIUM','show the real promoted profile');
 assert.equal(cards[1].children[1].children[3].textContent,'Not needed');
 await active.update({...data,crew_enabled:false});assert.equal(active.elements['agent-crew'].hidden,true);
 assert.equal(active.elements['agent-monitor'].hidden,false,'crew flag preserves detailed monitor');
 assert.ok(!JSON.stringify(active.elements).includes(SECRET));
 assert.equal(active.api.timeoutMs(100000),REQUEST_MS);
 active.listeners.pagehide();assert.equal(active.cleared(),true);
 console.log('AGENTS PASS: crew hierarchy, exact profiles, honest idle/promoted state, stable avatar lifecycle, feature flags, metadata privacy, request deadline and teardown.');
})().catch(error=>{console.error(error);process.exitCode=1;});
