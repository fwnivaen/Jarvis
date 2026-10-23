// Test genuine runtime-state projections, not generated animation activity.
const assert=require('node:assert/strict'),{setup,run,BASE}=require('./support/agent-view');
(async()=>{
 for(const count of [1,2,3]){
  const view=await setup({workflow:run(count)}),crew=view.elements['agent-crew'];
  assert.equal(crew.dataset.source,'workflow');assert.equal(crew.dataset.mode,['solo','pair','trio'][count-1]);
  assert.equal(view.elements['crew-summary'].textContent,count+' working');
  assert.equal(view.links.filter(link=>link.dataset.active==='true').length,[0,1,3][count-1]);
  assert.deepEqual(view.elements['crew-members'].children.map(c=>c.dataset.status),Array.from({length:3},(_,i)=>i<count?'running':'idle'));
 }
 const queued=run(2);queued.agents=queued.agents.map(a=>({...a,status:'queued'}));
 const waiting=await setup({workflow:queued});assert.equal(waiting.elements['crew-summary'].textContent,'Preparing');assert.ok(waiting.links.every(link=>link.dataset.active==='false'),'queued jobs do not imply collaboration');
 const current=run(3),view=await setup({workflow:current}),cards=view.elements['crew-members'].children;
 const review={...current,agents:[...current.agents.map(a=>({...a,status:'complete'})),{slot:'reviewer',status:'running',model:'test-model',effort:'high',elapsed_s:1,attempts:1,usage_reported:false,tokens:0}]};
 await view.update({workflow:review});
 assert.equal(view.elements['crew-members'].children.length,3,'the final reviewer does not create a hierarchy or fourth avatar');
 assert.equal(view.elements['crew-activity'].textContent,'Combining their findings');
 assert.ok(view.links.every(link=>link.dataset.active==='true'&&link.dataset.phase==='merge'));
 assert.equal(view.elements['crew-members'].children[0],cards[0]);
 await view.fail();assert.equal(view.elements['agent-crew'].dataset.mode,'offline');assert.ok(view.links.every(link=>link.dataset.active==='false'));
 await view.update({workflow:review});assert.equal(view.elements['agent-crew'].dataset.connected,'true');
 const finished={...review,status:'complete',created_at:1002,elapsed_s:10,agents:review.agents.map(a=>({...a,status:'complete'}))};
 await view.update({workflow:finished});assert.equal(view.elements['crew-summary'].textContent,'Complete');assert.ok(view.links.every(link=>link.dataset.active==='false'));
 view.advance(15000);await view.poll();assert.equal(view.elements['crew-summary'].textContent,'Ready');assert.ok(cards.every(c=>c.dataset.status==='idle'));
 const live=run(2);live.created_at=2000;view.event(live);view.event({...finished,id:'old',created_at:1000});assert.equal(view.elements['crew-summary'].textContent,'2 working','old saved selection cannot replace active work');
 const job={role:'worker',slot:'worker-1',model:'test-model',effort:'high',status:'running',phase:'reviewing',elapsed_s:2,total_tokens:42,retries:0};
 const peer=await setup({legacy:{...BASE,active:true,agents:[job,{...job,slot:'worker-2'}],events:[{kind:'peer_review_started',slot:null,elapsed_s:2},{kind:'UNKNOWN_PRIVATE_TEXT',slot:'worker-1'}]}});
 assert.equal(peer.elements['crew-activity'].textContent,'Reviewing shared findings');assert.equal(peer.elements['agent-crew'].dataset.mode,'pair');
 assert.ok(!JSON.stringify(peer.elements).includes('UNKNOWN_PRIVATE_TEXT'));
 console.log('AGENTS COLLABORATION PASS: 1/2/3 active agents, shared links, actual review/merge states, completion, reconnection and stale-run refusal.');
})().catch(error=>{console.error(error);process.exitCode=1;});
