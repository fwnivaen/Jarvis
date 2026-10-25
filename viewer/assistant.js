/* Local Mac commands share the existing Jarvis server and signed-in brain. */
(() => {
  'use strict';
  const SETTINGS=Object.freeze({keyBytes:12,pollMs:180,recordLimitMs:60000,requestMs:120000,historyLimit:12});
  let savedTriggers=new Set();
  let handling=false;
  let recordVersion=0;
  let generation=0,token=null,pollTimer=null,limitTimer=null,recording=false,starting=false;
  const make=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
  const button=(text,handler)=>{const b=make('button',text);b.type='button';b.className='control';b.onclick=handler;return b;};
  function key(){return Array.from(crypto.getRandomValues(new Uint8Array(SETTINGS.keyBytes)),x=>x.toString(16).padStart(2,'0')).join('');}
  async function request(path,body){const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(SETTINGS.requestMs)});const data=await response.json();if(!response.ok)throw Error(data.answer||data.text||'The local assistant is unavailable.');return data;}
  function matches(question){const text=question.trim().replace(/^(?:(?:hey )?jarvis[, ]+)?(?:please )?/i,'').replace(/[.!?]+$/,'').toLowerCase();return savedTriggers.has(text)||/^(?:(?:open|launch) |search (?:the web for|for) |(?:move )?window (?:left|right)$|(?:maximize|cent(?:er|re)) window$|(?:play|pause|resume) music$|when i say |(?:work in (?:the )?background|background task)\s*:)/i.test(text);}
  function rememberCatalog(data){savedTriggers=new Set((data.shortcuts||[]).map(item=>item.trigger));return data;}
  request('/assistant').then(rememberCatalog).catch(()=>{});
  async function handle(question){
    if(handling)return true;handling=true;
    try{
      const data=await request('/assistant/command',{question,request_key:key()});
      if(!data.matched)return false;
      request('/assistant').then(rememberCatalog).catch(()=>{});
      const answer=document.getElementById('answer');if(answer)answer.textContent=data.answer;
      window.JarvisUI?.onQuestion(question);window.JarvisUI?.onAnswer(data);window.JarvisVoice?.speak(data.answer);
      if(data.workflow_run)window.JarvisUI?.setWorkspace('work');
      document.getElementById('question').value='';
      return true;
    }catch(error){
      const answer=document.getElementById('answer');if(answer)answer.textContent=error.message;
      window.JarvisUI?.onQuestion(question);window.JarvisUI?.onAnswer({answer:error.message,nodes:[]});
      return true;
    }finally{handling=false;}
  }
  function dispose(){
    generation++;recordVersion++;recording=false;starting=false;clearTimeout(pollTimer);clearTimeout(limitTimer);
    if(token){request('/voice/stop',{token}).catch(()=>{});token=null;}
  }
  function mountSummary(parent){const card=make('div');card.className='assistant-summary';card.append(make('strong','Mac assistant'),make('p','Instant commands, saved routines, and reviewed dictation. Hold ⌃⌥Space with Jarvis Desktop open.'));card.append(button('Open Mac assistant',()=>window.JarvisUI?.setWorkspace('computer')));parent.append(card);}
  function mount(parent){
    dispose();const current=generation;
    const root=make('section');root.className='assistant-panel';parent.append(root);
    const status=make('p','Connecting to your local assistant…');status.setAttribute('role','status');status.setAttribute('aria-live','polite');root.append(status);
    const grid=make('div');grid.className='assistant-grid';root.append(grid);
    function section(title,description){const box=make('section');box.className='assistant-card';box.append(make('h2',title),make('p',description));grid.append(box);return box;}
    const desktop=section('Jarvis, anywhere','Hold Control + Option + Space to talk. Hold Control + Option + D to dictate. Escape cancels. Your voice is transcribed on this Mac.');
    const launch=button('Open Jarvis Desktop',async()=>{try{status.textContent=(await request('/assistant/desktop',{})).answer;}catch(error){status.textContent=error.message;}});desktop.append(launch,make('p','The desktop window reviews dictation before insertion. Window commands target the app you were using when you pressed the shortcut.'));
    const commands=section('Quick commands','These actions run locally without a model call. Opening an app or website reports the request; it does not claim to inspect the result.');
    const form=make('form'),input=make('input');input.placeholder='Open Safari';input.setAttribute('aria-label','Mac command');input.required=true;input.maxLength=2000;const run=make('button','Run command');run.type='submit';form.append(input,run);commands.append(form);
    form.onsubmit=async event=>{event.preventDefault();run.disabled=true;try{const data=await request('/assistant/command',{question:input.value,request_key:key()});status.textContent=data.matched?data.answer:'That is a question for Jarvis. Use the main chat, or start a background task in Work.';if(data.workflow_run)window.JarvisUI?.setWorkspace('work');else await refresh();}catch(error){status.textContent=error.message;}finally{run.disabled=false;}};
    commands.append(make('p','Try “Move window left”, “Maximize window”, “Play music”, or “Search the web for …”. In this dashboard, window commands act on the frontmost app.'));
    const shortcuts=section('Your shortcuts','Save an exact phrase with up to six supported commands. Separate commands with “and then”. Saving a routine does not run it.');
    const teach=make('p','Example: When I say writing time, open Notes and then open Safari');shortcuts.append(teach);
    const routines=make('div');shortcuts.append(routines);
    const dictation=section('Dictation','Record into a review field. Verbatim stays local. Clean up sends the text to your existing Codex / ChatGPT brain to fix punctuation and speech slips.');
    const transcript=make('textarea');transcript.rows=5;transcript.maxLength=8000;transcript.setAttribute('aria-label','Dictation review');dictation.append(transcript);
    const controls=make('div');controls.className='assistant-controls';dictation.append(controls);
    async function finish(){
      if(starting){status.textContent='The microphone is still starting. Press Stop once it is ready.';return;}
      if(!token)return;recording=false;clearTimeout(pollTimer);clearTimeout(limitTimer);record.disabled=true;
      const ending=token,version=recordVersion;token=null;
      try{const data=await request('/voice/finish',{token:ending});if(current!==generation||version!==recordVersion)return;transcript.value=data.text||transcript.value;status.textContent=data.confirmed?'Transcript ready. Review before copying.':'Final transcript unavailable. Review the partial text before using it.';}
      catch(error){status.textContent=error.message+' Your partial transcript is preserved.';}
      finally{record.disabled=false;record.textContent='Record dictation';}
    }
    const record=button('Record dictation',async()=>{
      if(recording){await finish();return;}if(starting)return;const version=++recordVersion;starting=true;record.disabled=true;window.JarvisVoice?.stopSpeech?.();
      try{
        const data=await request('/voice/start',{device_id:window.JarvisVoice?.inputDevice?.()||''});
        if(data.status==='error')throw Error(data.text);
        if(current!==generation||version!==recordVersion){await request('/voice/stop',{token:data.token});return;}
        token=data.token;recording=true;record.textContent='Stop and review';status.textContent='Listening. Stop to review; nothing will be inserted automatically.';
        async function poll(){if(!recording||current!==generation||version!==recordVersion)return;try{const state=await request('/voice/poll',{token});if(!recording||current!==generation||version!==recordVersion)return;if(state.status==='error')throw Error(state.text);if(state.text)transcript.value=state.text;if(state.status==='permission')status.textContent=state.text;if(state.status==='final'){await finish();return;}pollTimer=setTimeout(poll,SETTINGS.pollMs);}catch(error){dispose();record.textContent='Record dictation';status.textContent=error.message;}}
        poll();limitTimer=setTimeout(finish,SETTINGS.recordLimitMs);
      }catch(error){status.textContent=error.message;}finally{starting=false;record.disabled=false;}
    });
    const cleanup=button('Clean up text',async()=>{cleanup.disabled=true;try{const data=await request('/assistant/dictation',{text:transcript.value,cleanup:true});if(current===generation){transcript.value=data.text;status.textContent='Cleaned text ready. Review it before copying.';}}catch(error){status.textContent=error.message;}finally{cleanup.disabled=false;}});
    const copy=button('Copy text',async()=>{try{await navigator.clipboard.writeText(transcript.value);status.textContent='Copied. Paste it where you want.';}catch{transcript.select();status.textContent='Select and copy the text with your keyboard.';}});
    controls.append(record,cleanup,copy,button('Cancel recording',()=>{recordVersion++;recording=false;starting=false;clearTimeout(pollTimer);clearTimeout(limitTimer);if(token){request('/voice/stop',{token}).catch(()=>{});token=null;}record.disabled=false;record.textContent='Record dictation';status.textContent='Microphone stopped. Your text is preserved.';}));
    const history=section('Recent actions','Requests and confirmed window changes from this Mac. Background agent progress lives in Work.');
    const log=make('div');history.append(log);
    async function refresh(){
      const data=rememberCatalog(await request('/assistant'));if(!root.isConnected)return;
      launch.disabled=!data.desktop_available;if(!data.desktop_available)launch.textContent='Desktop helper needs building';
      routines.replaceChildren();
      if(!data.shortcuts.length)routines.append(make('p','No saved shortcuts yet. Add one using the command field.'));
      for(const item of data.shortcuts){const row=make('div');row.className='assistant-routine';row.append(make('strong',item.trigger),make('p',item.commands.join(' → ')),button('Run '+item.trigger,async()=>{try{status.textContent=(await request('/assistant/command',{question:item.trigger,request_key:key()})).answer;await refresh();}catch(error){status.textContent=error.message;}}),button('Remove '+item.trigger,async()=>{try{await request('/assistant/shortcut',{trigger:item.trigger});status.textContent='Shortcut removed.';await refresh();}catch(error){status.textContent=error.message;}}));routines.append(row);}
      log.replaceChildren();for(const item of data.history.slice(0,SETTINGS.historyLimit)){const entry=make('div');entry.className='assistant-log';entry.append(make('strong',item.question),make('p',item.answer),make('small',new Date(item.at*1000).toLocaleString()));log.append(entry);}
      if(!data.history.length)log.append(make('p','No Mac commands run yet.'));
      if(data.notice)status.textContent=data.notice;
    }
    refresh().then(()=>{if(current===generation&&!status.textContent.startsWith('Saved commands'))status.textContent='Connected · Codex / ChatGPT · commands and shortcuts stay local';}).catch(error=>{status.textContent=error.message;});
  }
  window.JarvisAssistant={matches,handle,mount,mountSummary,dispose};
})();
