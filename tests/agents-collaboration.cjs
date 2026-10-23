// Exercise production metadata rendering; worker content never enters the DOM.
const {readFileSync}=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const SOURCE=readFileSync('viewer/agents.js','utf8'),SECRET='PRIVATE_WORKER_REPORT_AND_REASONING',RECENT_COUNT=3;
function element(){return {hidden:true,textContent:'',dataset:{},children:[],append(child){this.children.push(child);},replaceChildren(){this.children=[];}};}
async function setup(data){
 const elements=Object.fromEntries(['agent-monitor','agent-rows','agent-summary','agent-limits','agent-crew','crew-members','crew-summary'].map(id=>[id,element()]));
 let timer;const context={Math,setTimeout(fn){timer=fn;return 1;},clearTimeout(){},
  document:{hidden:false,getElementById:id=>elements[id],createElement:element},window:{addEventListener(){}},
  fetch:async()=>({ok:true,json:async()=>data})};
 vm.runInNewContext(SOURCE,context);await new Promise(resolve=>setImmediate(resolve));
 return {elements,update(next){data=next;return timer();}};
}
(async()=>{
 const worker={id:'worker-1',role:'worker',model:'gpt-6.1-sol',effort:'medium'};
 const job={role:'worker',slot:worker.id,model:worker.model,effort:worker.effort,status:'running',phase:'drafting',
  elapsed_s:2,total_tokens:42,retries:0,current_tool:null,answer:SECRET,reasoning:SECRET};
 const data={enabled:true,crew_enabled:true,crew:[worker],active:true,elapsed_s:2,escalations:0,
  limits:{max_workers:3,worker_timeout_s:45,max_escalations:1},agents:[job],
  events:[{kind:'drafts_ready',slot:null,elapsed_s:1,report:SECRET}]};
 const view=await setup(data),card=view.elements['crew-members'].children[0],info=card.children[1];
 assert.equal(info.children[3].textContent,'Drafting');
 assert.equal(view.elements['agent-rows'].children[0].children[3].textContent,'running · Drafting');
 const activity=view.elements['agent-crew'].children.find(child=>child.className==='crew-activity');
 assert.equal(activity.textContent,'Worker drafts ready');
 const timeline=view.elements['agent-monitor'].children.find(child=>child.className==='agent-events');
 assert.equal(timeline.children[0].textContent,'1.0s · Worker drafts ready');
 await view.update({...data,agents:[{...job,status:'complete'}]});
 assert.equal(info.children[3].textContent,'Draft ready');
 await view.update({...data,agents:[{...job,phase:'reviewing',elapsed_s:5,total_tokens:84}],events:[
  {kind:'planned',slot:'boss',elapsed_s:0},
  {kind:'drafts_ready',slot:null,elapsed_s:1},
  {kind:'peer_review_started',slot:null,elapsed_s:2},
  {kind:'checkpoint_saved',slot:'worker-1',elapsed_s:3},
  {kind:'reported',slot:'worker-1',elapsed_s:4},
  {kind:SECRET,slot:'worker-1',elapsed_s:4},
  {kind:'reported',slot:SECRET,elapsed_s:4},
  {kind:'reported',slot:'worker-17',elapsed_s:4},
  {kind:'reported',slot:'worker-01',elapsed_s:4}]});
 assert.equal(view.elements['crew-members'].children[0],card,'review reuses the worker avatar');
 assert.equal(info.children[3].textContent,'Peer review');
 assert.equal(view.elements['crew-summary'].textContent,'1/1 reviewing');
 assert.equal(card.dataset.phase,'reviewing');
 assert.equal(timeline.children.length,RECENT_COUNT);
 assert.equal(timeline.children[0].textContent,'2.0s · Workers reviewing shared reports');
 assert.equal(activity.textContent,'Reports handed to boss');
 assert.ok(!JSON.stringify(view.elements).includes(SECRET));
 await view.update({...data,agents:[{...job,phase:SECRET}],events:[{kind:'resumed',slot:null}]});
 assert.equal(card.dataset.phase,'');assert.equal(info.children[3].textContent,'Working');
 assert.equal(view.elements['agent-rows'].children[0].children[3].textContent,'running');
 assert.equal(activity.textContent,'Saved work resumed');
 await view.update({...data,events:undefined,agents:[{...job,phase:undefined}]});
 assert.equal(activity.hidden,true);assert.equal(timeline.hidden,true);
 assert.equal(view.elements['agent-rows'].children[0].children[3].textContent,'running');
 assert.ok(!JSON.stringify(view.elements).includes(SECRET));
 console.log('AGENTS COLLABORATION PASS: draft/review/handoff phases, bounded safe events, stable worker cards and legacy fallback.');
})().catch(error=>{console.error(error);process.exitCode=1;});
