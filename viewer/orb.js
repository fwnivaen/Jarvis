/* The orb listens to runtime events. Every moving bar comes from measured audio. */
(() => {
  'use strict';
  const CONFIG = Object.freeze({bands:24,ticks:112,fft:1024,pixelRatio:2,minHz:80,maxHz:8000,
    floorDB:-70,ceilingDB:-12,smoothing:.65,staleMs:600,activeFrameMs:32,idleFrameMs:160,
    cometMs:1600,idleBreathMs:5000,ringTurnMs:36000,micGain:4,renderTimeoutMs:16000,
    ringRadius:.405,tickRadius:.35,waveRadius:.23,coreRadius:.27,progressWidth:2,
    waveformWidth:1.4,tickWidth:1,dotRadius:1,staticDots:96,modelCharacters:44});
  const STATES = Object.freeze(['IDLE','LISTENING','THINKING','SPEAKING','EXECUTING','AWAITING APPROVAL','ERROR']);
  const host = document.getElementById('jarvis-orb-host');
  if (!host) return;
  const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = {get matches(){return motionQuery.matches||document.documentElement.dataset.motion==='reduced';}};
  host.classList.add('jarvis-orb');
  host.innerHTML = `<div class="orb-instrument" data-state="IDLE">
    <div class="orb-halo" aria-hidden="true"></div>
    <canvas class="orb-telemetry" aria-hidden="true"></canvas>
    <button type="button" class="orb-core" aria-label="Turn microphone on" aria-pressed="false">
      <span class="orb-caustic" aria-hidden="true"></span><span class="orb-name">J.A.R.V.I.S.</span>
      <span class="orb-dot" aria-hidden="true"></span>
    </button><svg class="orb-approval-line" aria-hidden="true"><path></path></svg>
  </div><div class="orb-state" role="status" aria-live="polite">IDLE</div>
  <button type="button" class="orb-model" aria-haspopup="dialog" aria-controls="brain-picker">Connecting brain</button>
  <div class="orb-detail">Hold Space to talk</div>
  <details class="orb-input-settings"><summary aria-label="Microphone input settings">Microphone input</summary>
    <label>Input device<select class="orb-device" aria-label="Microphone input device"><option value="">System default</option></select></label>
    <p class="orb-device-note">Device selection uses the local Mac recognizer.</p>
    <p class="orb-signal-detail">Microphone off · no audio sampled</p>
  </details>`;
  const $ = selector => host.querySelector(selector);
  const instrument = $('.orb-instrument'), canvas = $('.orb-telemetry'), ctx = canvas.getContext('2d');
  const core = $('.orb-core'), label = $('.orb-state'), model = $('.orb-model'), detail = $('.orb-detail');
  let voice = {enabled:false,thinking:false,speaking:false,externalSpeaking:false,pending:false,notice:'',backend:'browser'};
  let explicit = null, currentState = 'IDLE', native = null, browserMic = null, browserSource = null;
  let micRequest = 0, audioContext = null, playback = null, renderController = null, outputUnavailable = false;
  let heldSpace = false, enabledBeforeSpace = false, lastDraw = 0, spectrum = new Array(CONFIG.bands).fill(0);
  let connected = true, stopped = false, micPending = false, outputLoading = false, dirty = true;
  const clamp = value => Math.max(0, Math.min(1, Number(value) || 0));
  const editable = element => !!element?.closest?.('input,textarea,select,[contenteditable="true"],[role="textbox"]');
  const rootStyle = () => getComputedStyle(document.documentElement);
  const color = (name,fallback='--accent') => rootStyle().getPropertyValue(name).trim() || rootStyle().getPropertyValue(fallback).trim();
  const activeContext = async () => {
    if (!audioContext || audioContext.state === 'closed') {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) throw new Error('Web Audio is unavailable');
      audioContext = new Context();
    }
    if (audioContext.state === 'suspended') await audioContext.resume();
    return audioContext;
  };
  function analyser(context) {
    const node = context.createAnalyser(); node.fftSize=CONFIG.fft;
    node.minDecibels=CONFIG.floorDB;node.maxDecibels=CONFIG.ceilingDB;node.smoothingTimeConstant=CONFIG.smoothing;
    return {node,frequencies:new Uint8Array(node.frequencyBinCount),samples:new Float32Array(node.fftSize)};
  }
  function readSpectrum(meter) {
    meter.node.getByteFrequencyData(meter.frequencies);meter.node.getFloatTimeDomainData(meter.samples);
    const rate = meter.node.context.sampleRate;
    const maximum = Math.min(CONFIG.maxHz,rate/2);
    const bands = Array.from({length:CONFIG.bands},(_,index)=>{
      const low=CONFIG.minHz*Math.pow(maximum/CONFIG.minHz,index/CONFIG.bands);
      const high=CONFIG.minHz*Math.pow(maximum/CONFIG.minHz,(index+1)/CONFIG.bands);
      const start=Math.max(1,Math.floor(low/rate*CONFIG.fft)),end=Math.min(meter.frequencies.length,Math.max(start+1,Math.ceil(high/rate*CONFIG.fft)));
      let peak=0;for(let bin=start;bin<end;bin++)peak=Math.max(peak,meter.frequencies[bin]/255);return peak;
    });
    let squared=0;for(const sample of meter.samples)squared+=sample*sample;
    return {bands,rms:clamp(Math.sqrt(squared/meter.samples.length)*CONFIG.micGain)};
  }
  function stopMicMeter() {
    micRequest++;micPending=false;browserSource?.disconnect();browserSource=null;
    if(browserMic){browserMic.stream.getTracks().forEach(track=>track.stop());browserMic=null;}
  }
  async function startMicMeter() {
    if(browserMic||micPending||!voice.enabled||voice.backend==='native'||!navigator.mediaDevices?.getUserMedia)return;
    const revision=++micRequest;
    micPending=true;
    try {
      const stream=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
      if(revision!==micRequest||!voice.enabled||voice.backend==='native'){stream.getTracks().forEach(track=>track.stop());return;}
      const context=await activeContext();
      if(revision!==micRequest||!voice.enabled){stream.getTracks().forEach(track=>track.stop());return;}
      const meter=analyser(context);browserSource=context.createMediaStreamSource(stream);browserSource.connect(meter.node);
      browserMic={stream,meter};refreshDetail();
    }catch { if(voice.enabled){$('.orb-signal-detail').textContent='Recognition active · microphone spectrum unavailable';} }
    finally { if(revision===micRequest)micPending=false; }
  }
  function selectedState() {
    if(explicit)return explicit.state;
    if(!connected || /denied|unavailable|could not|failed|ended|retry/i.test(voice.notice||''))return 'ERROR';
    if(voice.thinking||outputLoading)return 'THINKING';if(voice.speaking)return 'SPEAKING';
    return voice.enabled?'LISTENING':'IDLE';
  }
  function refreshDetail() {
    const muted = new URLSearchParams(location.search).getAll('mute').includes('1');
    let message=explicit?.message||voice.notice||'';
    if(!message)message=currentState==='SPEAKING'?(voice.externalSpeaking?'Native focus voice · output spectrum unavailable':outputUnavailable?'Daniel · output spectrum unavailable':'Daniel · local audio'):
      currentState==='THINKING'?(outputLoading?'Preparing local Daniel audio':'Working on your request'):currentState==='LISTENING'?(voice.wakeListening?'Awaiting “Jarvis” · microphone enabled':'Listening · say stop to interrupt'):
      currentState==='ERROR'?'Reconnect or choose an input':muted?'Silent session · hold Space to talk':'Hold Space to talk';
    detail.textContent=message;
    const micLive=voice.enabled&&(browserMic||(native&&Date.now()-native.received<CONFIG.staleMs));
    $('.orb-signal-detail').textContent=micLive?(voice.backend==='native'?'Live local microphone FFT':'Live browser microphone FFT'):
      voice.enabled?'Recognition active · waiting for microphone samples':'Microphone off · no audio sampled';
  }
  function sync() {
    const next=selectedState();
    if(next!==currentState){currentState=next;instrument.dataset.state=next;label.textContent=next;dirty=true;}
    core.setAttribute('aria-pressed',String(voice.enabled));core.setAttribute('aria-label',voice.enabled?'Turn microphone off':'Turn microphone on');
    refreshDetail();
  }
  function updateVoice(value) {
    voice={...voice,...value};
    if(!voice.enabled||voice.backend==='native')stopMicMeter();else startMicMeter();
    if(!voice.speaking&&!playback)outputUnavailable=false;
    sync();
  }
  function nativeAudio(audio) {
    if(!audio||!Array.isArray(audio.bands)||audio.bands.length!==CONFIG.bands)return;
    native={bands:audio.bands.map(clamp),rms:clamp(audio.rms),received:Date.now()};
    refreshDetail();
  }
  async function release(token) {
    if(token)try{await fetch('/voice/release',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token}),keepalive:true});}catch{}
  }
  function stopSpeech() {
    renderController?.abort();renderController=null;outputLoading=false;
    const active=playback;playback=null;
    if(active){active.source.onended=null;try{active.source.stop();}catch{}active.source.disconnect();active.meter.node.disconnect();}
  }
  async function playSpeech(text,options={}) {
    stopSpeech();
    const controller=new AbortController();renderController=controller;
    outputLoading=true;sync();
    const timeout=setTimeout(()=>controller.abort(),CONFIG.renderTimeoutMs);
    let token=null;
    try {
      const context=await activeContext();
      const response=await fetch('/voice/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text}),signal:controller.signal});
      const data=await response.json();
      if(!response.ok||data.status!=='ready'||typeof data.token!=='string'||typeof data.url!=='string')throw new Error('Local audio unavailable');
      token=data.token;
      if(controller.signal.aborted||options.isCurrent?.()===false)return true;
      if(!data.url.startsWith('/voice/audio?token='))throw new Error('Invalid local audio response');
      const wave=await fetch(data.url,{signal:controller.signal});if(!wave.ok)throw new Error('Local audio expired');
      const bytes=await wave.arrayBuffer();await release(token);token=null;
      const buffer=await context.decodeAudioData(bytes);
      if(controller.signal.aborted||options.isCurrent?.()===false)return true;
      const meter=analyser(context),source=context.createBufferSource();source.buffer=buffer;
      source.connect(meter.node);meter.node.connect(context.destination);playback={source,meter};outputUnavailable=false;
      source.onended=()=>{if(playback?.source!==source)return;source.disconnect();meter.node.disconnect();playback=null;options.onEnd?.();sync();};
      outputLoading=false;source.start();sync();return true;
    }catch {
      if(controller.signal.aborted||options.isCurrent?.()===false)return true;
      outputUnavailable=true;outputLoading=false;sync();return false;
    }finally{clearTimeout(timeout);if(renderController===controller){renderController=null;outputLoading=false;sync();}await release(token);}
  }
  function setStatus(state,options={}) {
    if(!state){explicit=null;sync();return;}
    const normalized=String(state).toUpperCase().replace(/_/g,' ');
    if(!STATES.includes(normalized))return;
    explicit={state:normalized,progress:Number.isFinite(options.progress)?clamp(options.progress):null,message:options.message||'',target:options.target||null};sync();
  }
  function setModel(brain) {
    const text=typeof brain==='string'?brain:brain?.model||brain?.label;
    if(text){model.textContent=text.slice(0,CONFIG.modelCharacters);model.title='Switch brain · '+text;}
  }
  function toggleMicrophone() {document.getElementById('mic')?.click();}
  core.addEventListener('click',()=>{if(currentState==='ERROR'){explicit=null;voice.notice='';sync();}toggleMicrophone();});
  model.addEventListener('click',()=>document.getElementById('brain-chip')?.click());
  $('.orb-input-settings').addEventListener('toggle',async event=>{
    if(!event.target.open)return;
    try{
      const response=await fetch('/voice/devices');if(!response.ok)throw new Error();const data=await response.json();
      const select=$('.orb-device'),chosen=window.JarvisVoice?.inputDevice?.()??select.value;select.replaceChildren(new Option('System default',''));
      for(const device of data.devices||[])if(typeof device.id==='string'&&typeof device.name==='string')select.add(new Option(device.name,device.id));
      select.value=chosen;select.disabled=!data.available;
      $('.orb-device-note').textContent=data.available?'Selecting an input uses local Mac recognition.':data.reason||'Device selection unavailable';
    }catch{$('.orb-device-note').textContent='Input list unavailable · use macOS Sound settings';$('.orb-device').disabled=true;}
  });
  $('.orb-device').addEventListener('change',event=>{
    if(typeof window.JarvisVoice?.setInputDevice==='function')window.JarvisVoice.setInputDevice(event.target.value);
    else{$('.orb-device-note').textContent='Input selection needs the voice adapter';event.target.value='';}
  });
  window.addEventListener('keydown',event=>{
    if(event.code!=='Space'||event.repeat||editable(event.target)||event.altKey||event.ctrlKey||event.metaKey||document.querySelector('dialog[open]'))return;
    event.preventDefault();window.JarvisVoice?.activate?.();window.JarvisVoice?.beginHold?.();heldSpace=true;enabledBeforeSpace=Boolean(window.JarvisVoice?.isEnabled?.());
    if(!enabledBeforeSpace)toggleMicrophone();
  });
  function releaseSpace(){if(!heldSpace)return;heldSpace=false;if(!enabledBeforeSpace&&window.JarvisVoice?.isEnabled?.()){
    if(typeof window.JarvisVoice.finishHold==='function')window.JarvisVoice.finishHold();else toggleMicrophone();
  }else window.JarvisVoice?.endHold?.();}
  window.addEventListener('keyup',event=>{if(event.code==='Space'){if(heldSpace)event.preventDefault();releaseSpace();}});
  window.addEventListener('blur',releaseSpace);
  function resize(){const size=instrument.clientWidth;const ratio=Math.min(devicePixelRatio||1,CONFIG.pixelRatio);canvas.width=size*ratio;canvas.height=size*ratio;canvas.style.width=size+'px';canvas.style.height=size+'px';ctx.setTransform(ratio,0,0,ratio,0,0);dirty=true;}
  new ResizeObserver(resize).observe(instrument);
  function line(angle,radius,extension,width,ink,alpha,size){ctx.globalAlpha=alpha;ctx.strokeStyle=ink;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(size/2+Math.cos(angle)*radius,size/2+Math.sin(angle)*radius);ctx.lineTo(size/2+Math.cos(angle)*(radius+extension),size/2+Math.sin(angle)*(radius+extension));ctx.stroke();}
  function draw(now) {
    if(stopped)return;requestAnimationFrame(draw);
    const active=currentState!=='IDLE'&&currentState!=='ERROR';
    if(!active&&!dirty)return;
    if(now-lastDraw<(active&&!reduced.matches?CONFIG.activeFrameMs:CONFIG.idleFrameMs)||document.hidden)return;lastDraw=now;
    dirty=false;
    const size=instrument.clientWidth;if(!size)return;ctx.clearRect(0,0,size,size);
    const ink=color(currentState==='ERROR'?'--danger':currentState==='AWAITING APPROVAL'?'--warn':'--accent');
    const muted=color('--text-tertiary');const radius=size*CONFIG.ringRadius;
    let measured=null;
    if(currentState==='SPEAKING'&&playback)measured=readSpectrum(playback.meter);
    else if(currentState==='LISTENING'&&voice.enabled){if(voice.backend==='native'&&native&&Date.now()-native.received<CONFIG.staleMs)measured=native;else if(browserMic)measured=readSpectrum(browserMic.meter);}
    spectrum=measured?.bands||new Array(CONFIG.bands).fill(0);
    const amplitude=measured?.rms||0;instrument.style.setProperty('--orb-level',String(amplitude));
    for(let index=0;index<CONFIG.staticDots;index++){const angle=index/CONFIG.staticDots*Math.PI*2;ctx.globalAlpha=.14;ctx.fillStyle=muted;ctx.beginPath();ctx.arc(size/2+Math.cos(angle)*radius,size/2+Math.sin(angle)*radius,CONFIG.dotRadius,0,Math.PI*2);ctx.fill();}
    const rotation=active&&!reduced.matches?now/CONFIG.ringTurnMs*Math.PI*2:0;
    for(let index=0;index<CONFIG.ticks;index++){
      const energy=spectrum[Math.floor(index/CONFIG.ticks*CONFIG.bands)];
      const angle=index/CONFIG.ticks*Math.PI*2-Math.PI/2+rotation;
      line(angle,size*CONFIG.tickRadius,size*(.012+energy*.045),CONFIG.tickWidth,ink,active?.18+energy*.72:.10,size);
    }
    if(measured&&(!reduced.matches))for(let index=0;index<CONFIG.bands;index++){
      const x=size*.31+index/(CONFIG.bands-1)*size*.38,height=spectrum[index]*size*.18;
      ctx.globalAlpha=.3+spectrum[index]*.7;ctx.strokeStyle=ink;ctx.lineWidth=CONFIG.waveformWidth;ctx.beginPath();ctx.moveTo(x,size/2-height/2);ctx.lineTo(x,size/2+height/2);ctx.stroke();
    }
    let start=-Math.PI/2,end=start;
    if(currentState==='LISTENING')end=start+Math.PI*2*amplitude;
    if(currentState==='THINKING'||(currentState==='EXECUTING'&&explicit?.progress===null)){start+=reduced.matches?0:now/CONFIG.cometMs*Math.PI*2;end=start+Math.PI*.44;}
    if(currentState==='EXECUTING'&&explicit?.progress!==null)end=start+Math.PI*2*(explicit?.progress||0);
    if(currentState==='AWAITING APPROVAL')end=start+Math.PI*1.5;
    if(currentState==='ERROR')end=start+Math.PI*2;
    if(currentState==='SPEAKING')end=start+Math.PI*2*amplitude;
    if(end>start){ctx.globalAlpha=currentState==='ERROR'?.42:.9;ctx.strokeStyle=ink;ctx.lineWidth=CONFIG.progressWidth;ctx.lineCap='round';ctx.beginPath();ctx.arc(size/2,size/2,size*.38,start,end);ctx.stroke();}
    ctx.globalAlpha=1;
    if(explicit?.target&&currentState==='AWAITING APPROVAL'){
      const target=document.querySelector(explicit.target),path=$('.orb-approval-line path');
      if(target){const from=instrument.getBoundingClientRect(),to=target.getBoundingClientRect();path.setAttribute('d',`M ${size/2} 0 L ${to.left+to.width/2-from.left} ${to.bottom-from.top}`);}
    }
  }
  const brainChip=document.getElementById('brain-chip');
  new MutationObserver(()=>{dirty=true;}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme','data-motion','class']});
  if(brainChip){new MutationObserver(()=>setModel(brainChip.textContent.replace(/\s*▾\s*$/,''))).observe(brainChip,{childList:true,subtree:true});setModel(brainChip.textContent.replace(/\s*▾\s*$/,''));}
  window.JarvisOrb={updateVoice,nativeAudio,setStatus,setModel,playSpeech,stopSpeech,microphoneDevice:()=>window.JarvisVoice?.inputDevice?.()??$('.orb-device').value,
    setConnected(value){connected=Boolean(value);sync();},
    snapshot:()=>({state:currentState,micEnabled:voice.enabled,audioSource:playback?'local-daniel-output':voice.enabled&&voice.backend==='native'&&native?'native-microphone':browserMic?'browser-microphone':null,spectrum:!!playback||!!browserMic||!!(voice.enabled&&native&&Date.now()-native.received<CONFIG.staleMs)}),
    destroy(){stopped=true;stopSpeech();stopMicMeter();audioContext?.close();}};
  window.addEventListener('pagehide',()=>{stopSpeech();stopMicMeter();});
  resize();sync();requestAnimationFrame(draw);
})();
