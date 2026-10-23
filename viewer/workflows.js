/* Real LangGraph execution snapshots; no fabricated agent activity. */
(() => {
  'use strict';
  const SETTINGS=Object.freeze({refreshMs:4000,requestMs:10000,maxQuestion:2000,recentEvents:30,secondsDigits:1});
  const TERMINAL=new Set(['complete','failed','cancelled','interrupted']);
  const STEPS=['retrieve','assign','workers','review','complete'];
  const LABELS={retrieve:'Retrieve sources',assign:'Assign work',workers:'Analyze',review:'Verify & answer',complete:'Complete'};
  const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  let root=null,timer=null,stream=null,selected=null,generation=0,last=null;
  async function request(path,body){
    const response=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(SETTINGS.requestMs),
      ...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
    const data=await response.json();if(!response.ok)throw Error(data.answer||'Workflow service unavailable.');return data;
  }
  function dispose(){generation++;clearTimeout(timer);stream?.close();stream=null;root=null;selected=null;last=null;}
  function mount(parent){
    dispose();const current=generation;let historySignature='';
    root=make('section','workflow-console');parent.append(root);
    const header=make('div','workflow-header'),heading=make('div');
    heading.append(make('p','workflow-eyebrow','AGENT WORKFLOWS'),make('h2',null,'Give your agents a task'));
    const engine=make('span','workflow-engine','LangGraph · local');header.append(heading,engine);
    const form=make('form','workflow-form'),question=make('textarea'),select=make('select'),start=make('button','control workflow-primary','Launch workflow');
    question.required=true;question.maxLength=SETTINGS.maxQuestion;question.rows=3;
    question.setAttribute('aria-label','Workflow task');question.placeholder='Compare Menu Pricing, Opening Checklist and Launch Campaign. Give three priorities with citations.';
    select.setAttribute('aria-label','Workflow type');start.type='submit';
    const controls=make('div','workflow-controls');controls.append(select,start);form.append(question,controls);
    const notice=make('p','workflow-notice');notice.setAttribute('role','status');
    const privacy=make('p','workflow-privacy','Read-only analysis of your notes. Activity and saved work stay local; model calls use your existing signed-in backend.');
    const layout=make('div','workflow-layout'),history=make('aside','workflow-history'),detail=make('div','workflow-detail');
    history.setAttribute('aria-label','Saved workflows');layout.append(history,detail);root.append(header,form,notice,privacy,layout);
    function message(text){if(current===generation)notice.textContent=text;}
    async function act(action){
      if(!selected)return;
      try{const run=await request('/workflows/'+action,{id:selected});if(current!==generation)return;render(run);connect(run.id);refresh();}
      catch(error){message(error.message);}
    }
    function render(run){
      if(current!==generation||run.id!==selected)return;
      const visibleState=value=>JSON.stringify(value,(key,item)=>key==='remaining_s'?undefined:item);
      if(TERMINAL.has(run.status)&&visibleState(run)===visibleState(last))return;
      last=run;
      detail.replaceChildren();
      const title=make('div','workflow-run-heading'),state=make('span','workflow-state',run.status);state.dataset.state=run.status;
      title.append(make('h3',null,run.question),state);detail.append(title);
      const meta=make('p','workflow-meta',`${run.elapsed_s.toFixed(SETTINGS.secondsDigits)}s · ${run.tool_calls} tool calls · ${run.total_tokens===null?'tokens unavailable':run.total_tokens.toLocaleString()+' reported tokens'}${run.usage_complete?'':' (usage may be incomplete)'}`);detail.append(meta);
      const progress=make('ol','workflow-progress');progress.setAttribute('aria-label','Workflow progress');
      for(const [index,step] of STEPS.entries()){
        const li=make('li',null,LABELS[step]);li.dataset.state=run.phase===step?'current':index<STEPS.indexOf(run.phase)?'done':'pending';progress.append(li);
      }detail.append(progress);
      const actions=make('div','workflow-controls');
      if(['running','cancelling'].includes(run.status)){const cancel=make('button','control','Cancel workflow');cancel.type='button';cancel.disabled=run.status==='cancelling';cancel.onclick=()=>act('cancel');actions.append(cancel);}
      if(run.can_retry){const retry=make('button','control','Retry saved work');retry.type='button';retry.onclick=()=>act('retry');actions.append(retry);}
      if(TERMINAL.has(run.status)){const again=make('button','control','Use task again');again.type='button';again.onclick=()=>{question.value=run.question;select.value=run.workflow;question.focus();};actions.append(again);}
      detail.append(actions);
      if(run.error)detail.append(make('p','workflow-error','Stopped: '+run.error.replaceAll('_',' ')+'.'+(run.can_retry?' Retry uses the remaining original budget.':' Start a new workflow for a fresh budget.')));
      const agents=make('div','workflow-agents');
      for(const agent of run.agents){
        const card=make('article','workflow-agent');card.dataset.state=agent.status;
        const head=make('div','workflow-agent-heading');head.append(make('h4',null,agent.slot==='reviewer'?'Lead reviewer':'Agent '+agent.slot.split('-')[1]),make('span','workflow-state',agent.status));
        card.append(head,make('p','workflow-task',agent.task),make('p','workflow-meta',`${agent.model} · ${agent.effort} · ${agent.elapsed_s.toFixed(SETTINGS.secondsDigits)}s · attempt ${agent.attempts}`));
        if(agent.error)card.append(make('p','workflow-error',agent.error.replaceAll('_',' ')));
        if(agent.output){const output=make('details','workflow-output'),summary=make('summary',null,'Verified findings');output.append(summary,make('p',null,agent.output));card.append(output);}
        agents.append(card);
      }
      if(!run.agents.length)agents.append(make('p','workflow-empty','Waiting for the first agent assignment…'));
      detail.append(agents);
      if(run.result){const output=make('section','workflow-answer');output.append(make('h3',null,'Completed answer'),make('p',null,run.result.answer));
        if(run.result.nodes.length){const sources=make('div','workflow-sources');sources.append(make('span',null,'Sources: '));for(const id of run.result.nodes){const link=make('a',null,window.JarvisUI?.sourceLabel(id)||'Note '+id);link.href='/note?id='+encodeURIComponent(id);link.onclick=event=>{if(window.JarvisUI?.openSource(id))event.preventDefault();};sources.append(link);}output.append(sources);}detail.append(output);}
      const activity=make('details','workflow-events');activity.open=true;activity.append(make('summary',null,'Execution activity'));
      const list=make('ol');for(const event of run.events.slice(-SETTINGS.recentEvents)){
        list.append(make('li',null,`${event.elapsed_s.toFixed(SETTINGS.secondsDigits)}s · ${event.slot||event.node||'Workflow'} · ${event.kind.replaceAll('_',' ')}${event.tool?' · '+event.tool:''}${event.error?' · '+event.error:''}`));
      }activity.append(list);detail.append(activity);
      if(TERMINAL.has(run.status)){stream?.close();stream=null;}
    }
    async function choose(id){
      selected=id;stream?.close();stream=null;
      history.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.runId===id)));
      try{const run=await request('/workflows/run?id='+encodeURIComponent(id));if(current!==generation||selected!==id)return;render(run);if(!TERMINAL.has(run.status))connect(id);}
      catch(error){message(error.message);}
    }
    function connect(id){
      stream?.close();selected=id;stream=new EventSource('/workflows/events?id='+encodeURIComponent(id));
      stream.addEventListener('state',event=>{if(current!==generation||selected!==id)return;try{render(JSON.parse(event.data));message('Connected to real workflow activity.');}catch{message('Activity update could not be read.');}});
      stream.onerror=()=>{if(current===generation&&stream)message('Activity connection interrupted. Reconnecting; the workflow continues on the server.');};
    }
    async function refresh(){
      clearTimeout(timer);
      try{
        const data=await request('/workflows');if(current!==generation||!root?.isConnected)return;
        start.disabled=!(data.enabled&&data.available)||Boolean(data.active);
        if(!select.options.length)for(const item of data.workflows){const option=make('option',null,item.label);option.value=item.id;select.append(option);}if(!select.dataset.ready){select.value='research';select.dataset.ready='1';}
        if(!data.enabled)message('Launch JARVIS with ./start-workflows.sh to enable agent workflows.');else if(!data.available)message(data.notice);else if(!selected)message('Ready. One workflow at a time, with up to '+data.limits.max_workers+' agents.');
        const nextHistory=JSON.stringify(data.runs.map(run=>[run.id,run.question,run.status,run.created_at]));
        if(nextHistory!==historySignature){
          historySignature=nextHistory;history.replaceChildren(make('h3',null,'Saved work'));
          for(const run of data.runs){const button=make('button','workflow-history-item');button.type='button';button.dataset.runId=run.id;button.setAttribute('aria-pressed',String(selected===run.id));button.append(make('strong',null,run.question),make('span',null,run.status+' · '+new Date(run.created_at*1000).toLocaleTimeString()));button.onclick=()=>choose(run.id);history.append(button);}
          if(!data.runs.length)history.append(make('p','workflow-empty','Your completed and interrupted runs will appear here.'));
        }
        history.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.runId===selected)));
        if(!selected&&data.runs.length)await choose(data.active||data.runs[0].id);
        else if(selected&&!stream){const run=data.runs.find(item=>item.id===selected);if(run)render(run);}
      }catch(error){message(error.message);}
      finally{if(current===generation&&root?.isConnected)timer=setTimeout(refresh,SETTINGS.refreshMs);}
    }
    form.onsubmit=async event=>{
      event.preventDefault();start.disabled=true;message('Starting workflow…');
      try{const run=await request('/workflows/start',{question:question.value,workflow:select.value});if(current!==generation)return;selected=run.id;render(run);connect(run.id);}
      catch(error){message(error.message);}finally{if(current===generation)refresh();}
    };
    refresh();
  }
  window.JarvisWorkflows={mount,dispose};window.addEventListener('pagehide',dispose);
})();
