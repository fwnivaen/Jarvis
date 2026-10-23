// Production visual controller with bounded, metadata-only local fixtures.
const assert=require('node:assert/strict'),{setup,run,BASE}=require('./support/agent-view');
const PRIVATE='DO_NOT_RENDER_REASONING';
(async()=>{
 const off=await setup({legacy:{...BASE,enabled:false,crew_enabled:false,routing_enabled:false}});
 assert.equal(off.elements['agent-monitor'].hidden,true);assert.equal(off.elements['agent-crew'].hidden,true);assert.equal(off.api.timeoutMs(100000),100000);off.api.destroy();
 const job={role:'worker',slot:'worker-2',model:'gpt-6-luna',effort:'max',status:'running',current_tool:null,elapsed_s:1.2,retries:1,total_tokens:null,reasoning:PRIVATE,task:PRIVATE};
 const active=await setup({legacy:{...BASE,active:true,elapsed_s:1.5,agents:[job],reasoning:PRIVATE}});
 const cards=active.elements['crew-members'].children;
 assert.equal(cards.length,3);assert.deepEqual(cards.map(c=>c.dataset.slot),['worker-1','worker-2','worker-3']);
 assert.deepEqual(cards.map(c=>c.children[1].textContent),['Scout','Weave','Prism']);
 assert.equal(cards[1].dataset.status,'running');assert.equal(cards[0].dataset.status,'idle');
 assert.equal(active.elements['crew-summary'].textContent,'1 working');
 assert.deepEqual(active.elements['agent-rows'].children[0].children.map(cell=>cell.textContent),['Weave','gpt-6-luna','max','running','—','1.2s','1','Unavailable']);
 assert.equal(active.api.timeoutMs(100000),250000,'preserve the existing request deadline');
 assert.ok(!JSON.stringify(active.elements['agent-crew']).includes('gpt-6'));
 assert.ok(!JSON.stringify(active.elements).includes(PRIVATE));
 await active.fail();assert.equal(active.elements['agent-crew'].dataset.connected,'false');assert.equal(active.elements['crew-summary'].textContent,'Offline');
 await active.update({data:{...BASE,active:true,agents:[{...job,status:'complete'}]}});
 assert.equal(active.elements['crew-members'].children[1],cards[1],'polling preserves the avatar and its animation');
 assert.equal(cards[1].dataset.status,'complete');
 await active.update({data:{...BASE,crew_enabled:false}});assert.equal(active.elements['agent-crew'].hidden,true);assert.equal(active.elements['agent-monitor'].hidden,false);
 const graph=run(1);active.event(graph);assert.equal(active.elements['agent-crew'].hidden,false,'workflow activity does not depend on the legacy crew flag');
 active.elements['crew-open-work'].onclick();assert.equal(active.elements.workspace,'work');
 active.listeners.pagehide();assert.equal(active.cleared(),true);assert.equal(active.listeners['jarvis:workflow-state'],undefined);
 const before=JSON.stringify(active.elements);active.event(run(3));assert.equal(JSON.stringify(active.elements),before);
 console.log('AGENTS PASS: three equal identities, live workflow/chat signals, stable avatars, offline state, metadata privacy, Work link and teardown.');
})().catch(error=>{console.error(error);process.exitCode=1;});
