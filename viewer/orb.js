/* The orb listens to runtime events. Every moving bar comes from measured audio. */
(() => {
  'use strict';
  const CONFIG = Object.freeze({bands:24,ticks:112,fft:1024,pixelRatio:2,minHz:80,maxHz:8000,
    floorDB:-70,ceilingDB:-12,smoothing:.65,staleMs:600,activeFrameMs:16,idleFrameMs:16,
    cometMs:1600,idleBreathMs:6000,ringTurnMs:48000,micGain:4,renderTimeoutMs:16000,
    ringRadius:.405,tickRadius:.35,waveRadius:.23,coreRadius:.27,progressWidth:2,
    waveformWidth:1.4,tickWidth:1,dotRadius:1,staticDots:96,modelCharacters:44});
  const VISUAL = Object.freeze({particles:1200,particleRatio:1.5,particleSize:2.1,cameraZ:3.4,
    cameraFov:45,sphereRadius:.88,innerRadius:.42,outerRadius:.96,goldenAngle:2.3999632297,
    breathDepth:.035,drift:.075,thinkSpin:1.4,thinkContract:.16,listenExpand:.12,
    activationMs:900,activationRadius:.32,ringRadii:[.465,.415,.365],ringSpeeds:[1,-1.45,.65],
    hintMs:2000,hintKey:'jarvis.hud.voice-hint',reducedFrameMs:160});
  const PARTICLE_VERTEX = `
    uniform float uTime;uniform float uLevel;uniform float uThinking;uniform float uReduced;
    uniform float uSize;uniform float uRatio;uniform float uBreath;
    attribute float aPhase;attribute float aSize;varying float vLight;
    void main(){vec3 p=position;float t=uTime*(1.-uReduced);
      float angle=t*(.075+uThinking*1.4)+p.y*.3+uThinking*length(p)*sin(t*.7);
      mat2 spin=mat2(cos(angle),-sin(angle),sin(angle),cos(angle));p.xz=spin*p.xz;
      p*=1.+uBreath*.035*(1.-uReduced)-uThinking*.16+uLevel*.12*(1.-uReduced);
      p+=normalize(p)*sin(aPhase+t*2.)*uLevel*.035*(1.-uReduced);
      vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;
      gl_PointSize=uSize*uRatio*aSize*(3.4/-mv.z);
      vLight=(.3+.7*smoothstep(-.9,.9,p.z))*(.78+.22*sin(aPhase+t*.7));
    }`;
  const PARTICLE_FRAGMENT = `
    uniform vec3 uColor;varying float vLight;
    void main(){float r=length(gl_PointCoord-.5)*2.;if(r>1.)discard;
      float glow=exp(-r*r*3.5);gl_FragColor=vec4(mix(uColor,vec3(.87,.98,1.),pow(vLight,3.)*.45),glow*vLight*.85);
      #include <colorspace_fragment>
    }`;
  const STATES = Object.freeze(['IDLE','LISTENING','THINKING','SPEAKING','EXECUTING','AWAITING APPROVAL','ERROR']);
  const host = document.getElementById('jarvis-orb-host');
  if (!host) return;
  const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = {get matches(){return motionQuery.matches||document.documentElement.dataset.motion==='reduced';}};
  host.classList.add('jarvis-orb');
  host.innerHTML = `<div class="orb-instrument" data-state="IDLE">
    <div class="orb-halo" aria-hidden="true"></div>
    <canvas class="orb-particles" aria-hidden="true"></canvas>
    <canvas class="orb-telemetry" aria-hidden="true"></canvas>
    <button type="button" class="orb-core" aria-label="Turn microphone on" aria-pressed="false">
      <span class="orb-caustic" aria-hidden="true"></span><span class="orb-name">J.A.R.V.I.S.</span>
      <span class="orb-dot" aria-hidden="true"></span>
    </button><svg class="orb-approval-line" aria-hidden="true"><path></path></svg>
  </div><div class="orb-status-chip"><span class="orb-state" role="status" aria-live="polite">IDLE</span><span class="orb-status-divider" aria-hidden="true">·</span>
  <button type="button" class="orb-model" aria-haspopup="dialog" aria-controls="brain-picker">Connecting brain</button></div>
  <div class="orb-voice-hint">Hold Space to talk</div>
  <details class="orb-input-settings"><summary aria-label="Microphone input settings" title="Microphone input settings"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2v12M8 2v12M13 2v12M1 5h4M6 11h4M11 6h4"/></svg></summary>
    <label>Input device<select class="orb-device" aria-label="Microphone input device"><option value="">System default</option></select></label>
    <p class="orb-device-note">Device selection uses the local Mac recognizer.</p>
    <p class="orb-signal-detail">Microphone off · no audio sampled</p>
    <div class="orb-detail">Hold Space to talk</div>
  </details>`;
  const $ = selector => host.querySelector(selector);
  const instrument = $('.orb-instrument'), canvas = $('.orb-telemetry'), ctx = canvas.getContext('2d');
  const core = $('.orb-core'), label = $('.orb-state'), model = $('.orb-model'), detail = $('.orb-detail');
  let voice = {enabled:false,thinking:false,speaking:false,externalSpeaking:false,pending:false,notice:'',backend:'browser'};
  let explicit = null, currentState = 'IDLE', native = null, browserMic = null, browserSource = null;
  let micRequest = 0, audioContext = null, playback = null, renderController = null, outputUnavailable = false;
  let heldSpace = false, enabledBeforeSpace = false, lastDraw = 0, spectrum = new Array(CONFIG.bands).fill(0);
  let connected = true, stopped = false, micPending = false, outputLoading = false, dirty = true;
  let particleView = null, listeningAt = -Infinity, rotationClock = 0, lastAnimation = 0, visualInk = null;
  try{if(!sessionStorage.getItem(VISUAL.hintKey)){host.classList.add('show-voice-hint');sessionStorage.setItem(VISUAL.hintKey,'1');setTimeout(()=>host.classList.remove('show-voice-hint'),VISUAL.hintMs);}}catch{}
  async function initParticles(){
    let renderer;
    try{
      const THREE=await import('/three.module.js');if(stopped)return;
      renderer=new THREE.WebGLRenderer({canvas:$('.orb-particles'),alpha:true,antialias:false,powerPreference:'low-power'});
      renderer.setPixelRatio(Math.min(devicePixelRatio||1,VISUAL.particleRatio));renderer.setClearColor(0,0);
      const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(VISUAL.cameraFov,1,.1,10);camera.position.z=VISUAL.cameraZ;
      const positions=new Float32Array(VISUAL.particles*3),phases=new Float32Array(VISUAL.particles),sizes=new Float32Array(VISUAL.particles);
      for(let i=0;i<VISUAL.particles;i++){
        const y=1-2*(i+.5)/VISUAL.particles,r=Math.sqrt(1-y*y),angle=i*VISUAL.goldenAngle;
        const seed=((Math.imul(i+1,16807)>>>0)%997)/997,radius=VISUAL.sphereRadius*(i%3?VISUAL.outerRadius:VISUAL.innerRadius+seed*.5);
        positions.set([Math.cos(angle)*r*radius,y*radius,Math.sin(angle)*r*radius],i*3);phases[i]=seed*Math.PI*2;sizes[i]=.55+seed*.7;
      }
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setAttribute('aPhase',new THREE.BufferAttribute(phases,1));geometry.setAttribute('aSize',new THREE.BufferAttribute(sizes,1));
      const material=new THREE.ShaderMaterial({vertexShader:PARTICLE_VERTEX,fragmentShader:PARTICLE_FRAGMENT,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
        uniforms:{uTime:{value:0},uLevel:{value:0},uThinking:{value:0},uReduced:{value:0},uBreath:{value:0},uSize:{value:VISUAL.particleSize},uRatio:{value:renderer.getPixelRatio()},uColor:{value:new THREE.Color(color('--accent'))}}});
      const points=new THREE.Points(geometry,material);scene.add(points);
      particleView={renderer,scene,camera,geometry,material};resize();dirty=true;
    }catch{renderer?.dispose();host.classList.add('orb-particle-fallback');}
  }

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
    if(next!==currentState){currentState=next;instrument.dataset.state=next;label.textContent=next;host.dataset.state=next;if(next==='LISTENING')listeningAt=performance.now();dirty=true;}
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
    if(text){model.textContent=text.replace(/^(?:CODEX|OPENROUTER)\s*[·/]\s*/i,'').slice(0,CONFIG.modelCharacters).toUpperCase();model.title='Switch brain · '+text;}
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
  function resize(){const size=instrument.clientWidth;const ratio=Math.min(devicePixelRatio||1,CONFIG.pixelRatio);canvas.width=size*ratio;canvas.height=size*ratio;canvas.style.width=size+'px';canvas.style.height=size+'px';ctx.setTransform(ratio,0,0,ratio,0,0);particleView?.renderer.setSize(size,size,false);dirty=true;}
  new ResizeObserver(resize).observe(instrument);
  function line(angle,radius,extension,width,ink,alpha,size){ctx.globalAlpha=alpha;ctx.strokeStyle=ink;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(size/2+Math.cos(angle)*radius,size/2+Math.sin(angle)*radius);ctx.lineTo(size/2+Math.cos(angle)*(radius+extension),size/2+Math.sin(angle)*(radius+extension));ctx.stroke();}
  function draw(now) {
    if(stopped)return;requestAnimationFrame(draw);
    const active=currentState!=='IDLE'&&currentState!=='ERROR';
    const frameMs=reduced.matches?VISUAL.reducedFrameMs:CONFIG.activeFrameMs;
    if(document.hidden||now-lastDraw<frameMs||reduced.matches&&!active&&!dirty)return;
    const delta=lastAnimation?Math.min(now-lastAnimation,100):0;lastAnimation=now;lastDraw=now;dirty=false;
    if(!reduced.matches)rotationClock+=delta*(currentState==='THINKING'?4:1);
    const size=instrument.clientWidth;if(!size)return;ctx.clearRect(0,0,size,size);
    const ink=color(currentState==='ERROR'?'--danger':currentState==='AWAITING APPROVAL'?'--warn':'--accent');
    const center=size/2,breath=reduced.matches?0:Math.sin(now/CONFIG.idleBreathMs*Math.PI*2);
    let measured=null;
    if(currentState==='SPEAKING'&&playback)measured=readSpectrum(playback.meter);
    else if(currentState==='LISTENING'&&voice.enabled){if(voice.backend==='native'&&native&&Date.now()-native.received<CONFIG.staleMs)measured=native;else if(browserMic)measured=readSpectrum(browserMic.meter);}
    spectrum=measured?.bands||new Array(CONFIG.bands).fill(0);
    const amplitude=measured?.rms||0;instrument.style.setProperty('--orb-level',String(amplitude));
    if(particleView){
      const u=particleView.material.uniforms;u.uTime.value=now/1000;u.uLevel.value=amplitude;u.uThinking.value=currentState==='THINKING'?1:0;u.uReduced.value=reduced.matches?1:0;u.uBreath.value=breath;
      if(ink!==visualInk){u.uColor.value.set(ink);visualInk=ink;}
      particleView.renderer.render(particleView.scene,particleView.camera);
    }
    VISUAL.ringRadii.forEach((ratio,ring)=>{
      const radius=size*ratio,turn=rotationClock/CONFIG.ringTurnMs*Math.PI*2*VISUAL.ringSpeeds[ring];
      ctx.strokeStyle=ink;ctx.lineWidth=CONFIG.tickWidth;ctx.globalAlpha=ring===0?.16:.28;
      ctx.beginPath();ctx.arc(center,center,radius,0,Math.PI*2);ctx.stroke();
      ctx.globalAlpha=.7;ctx.beginPath();ctx.arc(center,center,radius,turn,turn+Math.PI*(ring===1?.42:.2));ctx.stroke();
      if(ring<2)for(let i=0;i<CONFIG.ticks/2;i++){
        const angle=i/(CONFIG.ticks/2)*Math.PI*2+turn,major=i%7===0;
        line(angle,radius,major?size*.022:size*.008,CONFIG.tickWidth,ink,major?.55:.18,size);
      }
    });
    // A single activation wave; all subsequent audio motion is measured.
    const activation=(now-listeningAt)/VISUAL.activationMs;
    if(!reduced.matches&&activation>=0&&activation<1){ctx.globalAlpha=(1-activation)*.7;ctx.strokeStyle=ink;ctx.lineWidth=CONFIG.progressWidth;ctx.beginPath();ctx.arc(center,center,size*(VISUAL.activationRadius+activation*.23),0,Math.PI*2);ctx.stroke();}
    if(measured&&!reduced.matches)for(let i=0;i<CONFIG.ticks;i++){
      const energy=spectrum[Math.floor(i/CONFIG.ticks*CONFIG.bands)],angle=i/CONFIG.ticks*Math.PI*2-Math.PI/2;
      line(angle,size*.335,energy*size*.065,CONFIG.waveformWidth,ink,.35+energy*.65,size);
    }
    if(currentState==='THINKING'||currentState==='EXECUTING'||currentState==='AWAITING APPROVAL'){
      const start=-Math.PI/2+(reduced.matches?0:now/CONFIG.cometMs*Math.PI*2);
      const span=currentState==='EXECUTING'&&explicit?.progress!==null?Math.PI*2*(explicit?.progress||0):Math.PI*.48;
      ctx.globalAlpha=.8;ctx.strokeStyle=ink;ctx.lineWidth=CONFIG.progressWidth;ctx.beginPath();ctx.arc(center,center,size*.385,start,start+span);ctx.stroke();
    }
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
    destroy(){stopped=true;stopSpeech();stopMicMeter();audioContext?.close();particleView?.geometry.dispose();particleView?.material.dispose();particleView?.renderer.dispose();}};
  window.addEventListener('pagehide',()=>{stopSpeech();stopMicMeter();});
  resize();sync();initParticles();requestAnimationFrame(draw);
})();
