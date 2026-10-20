// Metadata-only activity drawer. Never render prompts, output, or reasoning events.
(() => {
  'use strict';
  const SETTINGS = Object.freeze({pollMs:750, disabledPollMs:5000, hiddenPollMs:3000,
    timeoutGraceMs:10000, secondsToMs:1000, elapsedDigits:1});
  const root=document.getElementById('agent-monitor');
  if(!root)return;
  const rows=document.getElementById('agent-rows'),status=document.getElementById('agent-summary'),
    meta=document.getElementById('agent-limits');
  const labels={dispatch:'Quick route',brain:'Brain',worker:'Worker',answer:'Final answer',vision:'Vision'};
  let timer=null,destroyed=false,last=null;
  function cell(row,text){const element=document.createElement('td');element.textContent=String(text);row.append(element);}
  function render(data){
    last=data;root.hidden=!data.enabled;
    if(!data.enabled)return;
    status.textContent=data.active?'Working · '+data.elapsed_s.toFixed(SETTINGS.elapsedDigits)+'s':data.agents.length?'Last request · '+data.elapsed_s.toFixed(SETTINGS.elapsedDigits)+'s':'Ready';
    meta.textContent=`Up to ${data.limits.max_workers} workers · ${data.limits.worker_timeout_s}s per worker · ${data.escalations}/${data.limits.max_escalations} escalations`;
    rows.replaceChildren();
    for(const agent of data.agents){
      const row=document.createElement('tr');row.dataset.status=agent.status;
      cell(row,labels[agent.role]||'Agent');cell(row,agent.model);cell(row,agent.status);
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
