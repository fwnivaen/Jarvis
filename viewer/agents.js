// Metadata-only activity drawer. Never render prompts, output, or reasoning events.
(() => {
  'use strict';
  const SETTINGS = Object.freeze({pollMs:750, disabledPollMs:5000, hiddenPollMs:3000,
    timeoutGraceMs:10000, secondsToMs:1000, elapsedDigits:1, workerDigits:2, recentEvents:3, maxCrewSlots:16});
  const root=document.getElementById('agent-monitor');
  if(!root)return;
  const rows=document.getElementById('agent-rows'),status=document.getElementById('agent-summary'),
    meta=document.getElementById('agent-limits');
  const crew=document.getElementById('agent-crew'),members=document.getElementById('crew-members'),
    crewStatus=document.getElementById('crew-summary');
  const labels={dispatch:'Quick route',brain:'Brain',worker:'Worker',answer:'Final answer',vision:'Vision'};
  const states={running:'Working',retrying:'Retrying',complete:'Complete',failed:'Needs attention',skipped:'Skipped',queued:'Queued'};
  const phases={classifying:'Routing',planning:'Planning',answering:'Working',checking:'Checking',drafting:'Drafting',
    sharing:'Sharing reports',reviewing:'Peer review',reporting:'Reporting to boss',recovering:'Recovering'};
  const eventLabels=Object.freeze({planned:'Boss assigned the work',drafts_ready:'Worker drafts ready',
    peer_review_started:'Workers reviewing shared reports',peer_review_complete:'Peer review complete',
    reported:'Reports handed to boss',resumed:'Saved work resumed',checkpoint_saved:'Progress saved'});
  const crewActivity=crew?part(crew,'p','crew-activity'):null;
  const eventList=part(root,'ol','agent-events');eventList.ariaLabel='Recent agent activity';eventList.hidden=true;
  const cards=new Map();
  // Fixed local SVG artwork. Model data only enters textContent below.
  const workerGlyph='<svg viewBox="0 0 80 80" aria-hidden="true"><circle class="crew-orbit" cx="40" cy="39" r="35"/><circle class="crew-halo" cx="40" cy="39" r="29"/><path class="crew-body-line" d="M22 69v-6c0-9 8-15 18-15s18 6 18 15v6M35 47v5m10-5v5M29 57l4 12m18-12-4 12"/><rect class="crew-helmet" x="24" y="15" width="32" height="33" rx="13"/><rect class="crew-visor" x="29" y="25" width="22" height="12" rx="5"/><path class="crew-face" d="M34 31h3m6 0h3M34 42h12M40 15V9"/><circle class="crew-beacon" cx="40" cy="8" r="2"/><path class="crew-arm" d="M22 57l-4 8 9 5m30-13 5 6-6 5"/><rect class="crew-tablet" x="44" y="55" width="14" height="18" rx="3"/><path class="crew-face" d="M48 60h6m-6 4h4"/></svg>';
  const bossGlyph='<svg viewBox="0 0 80 80" aria-hidden="true"><circle class="crew-orbit" cx="40" cy="42" r="35"/><circle class="crew-halo" cx="40" cy="42" r="29"/><path class="crew-crown" d="m29 12-3-9 9 5 5-7 5 7 9-5-3 9Z"/><path class="crew-body-line" d="M20 75v-8c0-10 8-15 20-15s20 5 20 15v8M31 56l9 9 9-9M40 65v10"/><rect class="crew-helmet" x="23" y="18" width="34" height="33" rx="13"/><rect class="crew-visor" x="28" y="28" width="24" height="12" rx="5"/><path class="crew-face" d="M33 34h4m6 0h4M35 45h10"/><path class="crew-badge" d="m40 66 2 4 4 1-4 2-2 4-2-4-4-2 4-1Z"/></svg>';
  let timer=null,destroyed=false,last=null;
  function cell(row,text){const element=document.createElement('td');element.textContent=String(text);row.append(element);}
  function part(parent,tag,className,text){const element=document.createElement(tag);element.className=className;if(text!==undefined)element.textContent=text;parent.append(element);return element;}
  function eventText(event){
    if(!event||!Object.hasOwn(eventLabels,event.kind))return null;
    if(event.slot!==null&&event.slot!==undefined){
      const number=Number(String(event.slot).split('-')[1]);
      if(event.slot!=='boss'&&(!Number.isInteger(number)||number<1||number>SETTINGS.maxCrewSlots||event.slot!==`worker-${number}`))return null;
    }
    return eventLabels[event.kind];
  }
  function renderEvents(data){
    const events=(Array.isArray(data.events)?data.events:[]).filter(event=>eventText(event)).slice(-SETTINGS.recentEvents);
    eventList.replaceChildren();eventList.hidden=!events.length;
    for(const event of events){
      const elapsed=Number.isFinite(event.elapsed_s)?event.elapsed_s.toFixed(SETTINGS.elapsedDigits)+'s · ':'';
      part(eventList,'li','agent-event',elapsed+eventText(event));
    }
    if(crewActivity){crewActivity.hidden=!events.length;crewActivity.textContent=events.length?eventText(events[events.length-1]):'';}
  }
  function makeCard(profile){
    const card=part(members,'article','crew-card'+(profile.id==='boss'?' crew-card--boss':''));
    card.dataset.slot=profile.id;card.dataset.tone=profile.id==='boss'?'gold':profile.id==='worker-1'?'blue':profile.id==='worker-2'?'violet':'mint';
    const avatar=part(card,'div','crew-avatar');avatar.innerHTML=profile.id==='boss'?bossGlyph:workerGlyph;
    const info=part(card,'div','crew-info'),name=part(info,'h3','crew-name',profile.id==='boss'?'BOSS':'WORKER '+profile.id.split('-')[1].padStart(SETTINGS.workerDigits,'0')),
      model=part(info,'p','crew-model'),effort=part(info,'span','crew-effort'),state=part(info,'p','crew-state'),metrics=part(info,'p','crew-metrics');
    return {card,name,model,effort,state,metrics};
  }
  function renderCrew(data){
    if(!crew||!members||!crewStatus)return;
    const roster=Array.isArray(data.crew)?data.crew:[];
    crew.hidden=!(data.enabled&&data.crew_enabled&&roster.length);
    if(crew.hidden)return;
    crew.dataset.connected='true';
    const signature=roster.map(profile=>profile.id).join('|');
    if(members.dataset.roster!==signature){members.replaceChildren();cards.clear();for(const profile of roster)cards.set(profile.id,makeCard(profile));members.dataset.roster=signature;}
    let working=0,reviewing=0;
    for(const profile of roster){
      const view=cards.get(profile.id),jobs=data.agents.filter(job=>job.slot===profile.id),job=jobs[jobs.length-1],model=job?.model||profile.model,
        effort=job?.effort||profile.effort,state=job?.status||'idle';
      view.card.dataset.status=state;
      view.card.dataset.phase=Object.hasOwn(phases,job?.phase)?job.phase:'';
      view.model.textContent=model==='gpt-6.1-sol'?'6.1 SOL':model==='gpt-6-luna'?'LUNA':model==='gpt-6-astra'?'ASTRA':model;
      view.effort.textContent=String(effort).toUpperCase();
      view.state.textContent=state==='idle'?(data.agents.length&&!data.active?'Not needed':'Standby'):state==='running'?(phases[job.phase]||'Working'):state==='complete'&&['drafting','sharing'].includes(job?.phase)&&data.active?'Draft ready':states[state]||'Standby';
      if(profile.id==='boss'&&job?.role==='brain'&&state==='complete'&&data.active)view.state.textContent='Plan ready';
      view.metrics.textContent=job?`${job.elapsed_s.toFixed(SETTINGS.elapsedDigits)}s · ${job.total_tokens===null?'tokens pending':job.total_tokens.toLocaleString()+' tokens'}`:profile.id==='boss'?'Plans & checks':'Ready for a task';
      if(profile.role==='worker'&&['running','retrying','queued'].includes(state)){working++;if(job.phase==='reviewing')reviewing++;}
    }
    const workers=roster.filter(profile=>profile.role==='worker').length;
    const activeJob=data.agents.find(job=>['running','retrying'].includes(job.status));
    crew.dataset.active=String(data.active);
    crewStatus.textContent=data.active?(working?`${working}/${workers} ${reviewing===working?'reviewing':'working'}`:activeJob?.slot==='boss'?'Boss working':labels[activeJob?.role]||'Standing by'):data.agents.length?'Standing by · last '+data.elapsed_s.toFixed(SETTINGS.elapsedDigits)+'s':'Standing by';
  }
  function render(data){
    last=data;root.hidden=!data.enabled;
    renderEvents(data);
    renderCrew(data);
    if(!data.enabled)return;
    status.textContent=data.active?'Working · '+data.elapsed_s.toFixed(SETTINGS.elapsedDigits)+'s':data.agents.length?'Last request · '+data.elapsed_s.toFixed(SETTINGS.elapsedDigits)+'s':'Ready';
    meta.textContent=`Up to ${data.limits.max_workers} workers · ${data.limits.worker_timeout_s}s per worker · ${data.escalations}/${data.limits.max_escalations} escalations`;
    rows.replaceChildren();
    for(const agent of data.agents){
      const row=document.createElement('tr');row.dataset.status=agent.status;
      const phase=Object.hasOwn(phases,agent.phase)?phases[agent.phase]:null;
      cell(row,labels[agent.role]||'Agent');cell(row,agent.model);cell(row,agent.effort||'—');cell(row,phase?`${agent.status} · ${phase}`:agent.status);
      cell(row,agent.current_tool||'—');cell(row,agent.elapsed_s.toFixed(SETTINGS.elapsedDigits)+'s');
      cell(row,agent.retries);cell(row,agent.total_tokens===null?'Unavailable':agent.total_tokens.toLocaleString());
      rows.append(row);
    }
  }
  async function refresh(){
    try{
      const response=await fetch('/agents',{cache:'no-store'});
      if(!response.ok)throw Error();
      const data=await response.json();
      if(destroyed)return;
      if(typeof data.enabled!=='boolean'||!Array.isArray(data.agents)||!data.limits)throw Error();
      render(data);
    }catch{
      if(!root.hidden)status.textContent='Activity connection interrupted';
      if(crew&&!crew.hidden){crew.dataset.connected='false';crewStatus.textContent='Connection interrupted';}
    }finally{
      if(!destroyed)timer=setTimeout(refresh,document.hidden?SETTINGS.hiddenPollMs:last?.enabled?SETTINGS.pollMs:SETTINGS.disabledPollMs);
    }
  }
  function timeoutMs(fallback){return last?.routing_enabled?Math.max(fallback,last.limits.request_timeout_s*SETTINGS.secondsToMs+SETTINGS.timeoutGraceMs):fallback;}
  function destroy(){destroyed=true;clearTimeout(timer);}
  window.addEventListener('pagehide',destroy,{once:true});
  window.JarvisAgents={timeoutMs,destroy};
  refresh();
})();
