// Camera pixels and landmarks stay in this browser. Only look() encodes a frame.
const SAMPLE_MS = 80, HOLD_MS = 700, ABSENCE_MS = 12000, COOLDOWN_MS = 30000;
const RELIEF_MS = 180000, REQUEST_MS = 4000, LOOK_MS = 120000;
const VIDEO_WIDTH = 640, VIDEO_HEIGHT = 480, JPEG_QUALITY = .82;
const MIN_VISIBILITY = .5, HEAD_DROP = .18, SLOUCH_DROP = .16, CALIBRATION_SAMPLES = 15;
const EAR_NOTICE = 'My ears are off, sir — tap the ear button and just talk.';
const LINES = {head_down: ['Sir, the phone has had its audience.', 'Your task is up here, sir.'], slouched: ['Sir, the chair is winning.', 'A little spine, sir. Literally.'], absent: ['Your desk has reported you missing, sir.']};
const clean = text => text.toLowerCase().replace(/[,.!?]/g, '').trim();
const isRelief = text => /^(?:no jarvis i need to do something important|give me a minute)$/.test(clean(text));
const matches = text => /^(?:(?:hey )?jarvis )?(?:look at me|what do you think of my shirt)$/.test(clean(text));
const el = id => document.getElementById(id);
let stream, video, face, pose, timer, generation = 0, quietUntil = 0, nextNudge = 0;
let publishing = false, sessionState = {}, baseline = null, calibration = [], since = {}, positions = {}, lastVideoTime = -1, looking = false;
let signals = {eyes_active:false, present:false, head_down:false, slouched:false};
async function post(path, body) {
 const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), signal:AbortSignal.timeout(REQUEST_MS)});
 if (!r.ok) throw new Error('Eyes session unavailable');
 return r.json();
}
function announce(text) { el('answer').textContent = text; window.JarvisVoice?.speak(text); }
function sustained(key, value, now, delay) {
 if (!value) { delete since[key]; return false; }
 if (since[key] === undefined) since[key] = now;
 return now - since[key] >= delay;
}
function classify(f, p) {
 const present = !!(f || p);
 if (!f || !p || p[11].visibility < MIN_VISIBILITY || p[12].visibility < MIN_VISIBILITY) return {present, head_down:false, slouched:false};
 const width = Math.hypot(p[11].x-p[12].x, p[11].y-p[12].y);
 if (!width) return {present, head_down:false, slouched:false};
 const shoulder = (p[11].y+p[12].y)/2;
 const head = (f[1].y-(f[33].y+f[263].y)/2)/Math.max(Math.abs(f[152].y-f[10].y), Number.EPSILON);
 const neck = (shoulder-f[152].y)/width;
 if (!baseline) {
  calibration.push({head, neck});
  if (calibration.length >= CALIBRATION_SAMPLES) baseline = {head:calibration.reduce((a,b)=>a+b.head,0)/calibration.length, neck:calibration.reduce((a,b)=>a+b.neck,0)/calibration.length};
  return {present, head_down:false, slouched:false};
 }
 return {present, head_down:head > baseline.head+HEAD_DROP, slouched:neck < baseline.neck-SLOUCH_DROP};
}
async function sample(token) {
 if (token !== generation || !stream) return;
 try {
  if (video.readyState < 2 || video.currentTime === lastVideoTime) { timer=setTimeout(()=>sample(token),SAMPLE_MS); return; }
  lastVideoTime=video.currentTime;
  const now=performance.now();
  const raw=classify(face.detectForVideo(video,now).faceLandmarks[0], pose.detectForVideo(video,now).landmarks[0]);
  signals={eyes_active:true, present:raw.present, head_down:sustained('head_down',raw.head_down,now,HOLD_MS), slouched:sustained('slouched',raw.slouched,now,HOLD_MS)};
  const absent=sustained('absent',!raw.present,now,ABSENCE_MS);
  if (!publishing) {
   publishing=true;
   post('/eyes',signals).then(state=>{if(token===generation)sessionState=state;}).catch(()=>{if(token===generation){stop();el('eyes-status').textContent='Eyes session disconnected';}}).finally(()=>{publishing=false;});
  }
  const state=sessionState;
  if (token !== generation) return;
  if (state.snooze_s) { quietUntil=Math.max(quietUntil,performance.now()+state.snooze_s*1000); sessionState={...state,snooze_s:0}; }
  el('eyes-status').textContent=!baseline?'Sit upright · calibrating…':signals.head_down?'Head down':signals.slouched?'Slouched':signals.present?'Eyes · local only':'Away';
  const kind=signals.head_down?'head_down':signals.slouched?'slouched':absent?'absent':null;
  if (kind && now>=quietUntil && now>=nextNudge && !looking && !state.paused) {
   nextNudge=now+COOLDOWN_MS;
   const pool=LINES[kind], index=positions[kind]||0; positions[kind]=index+1;
   announce(pool[index%pool.length]);
  }
  timer=setTimeout(()=>sample(token),SAMPLE_MS);
 } catch (_) { stop(); el('eyes-status').textContent='Eyes unavailable · try again'; }
}
function stop() {
 generation++; clearTimeout(timer);
 stream?.getTracks().forEach(t=>t.stop()); stream=null;
 if(video)video.srcObject=null;
 face?.close(); pose?.close(); face=pose=null;
 signals={eyes_active:false,present:false,head_down:false,slouched:false};
 post('/eyes',signals).catch(()=>{});
 el('eyes').textContent='Eyes';el('eyes').setAttribute('aria-pressed','false');el('eyes-status').textContent='Eyes off';
}
async function start() {
 el('eyes').disabled=true;
 const token=++generation;
 try {
  const vision=await import('/vision.mjs');
  const files=await vision.FilesetResolver.forVisionTasks(location.origin);
  face=await vision.FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/face_landmarker.task'},runningMode:'VIDEO',numFaces:1});
  pose=await vision.PoseLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/pose_landmarker.task'},runningMode:'VIDEO',numPoses:1});
  stream=await navigator.mediaDevices.getUserMedia({video:{width:VIDEO_WIDTH,height:VIDEO_HEIGHT},audio:false});
  if(token!==generation){stop();return;}
  video=document.createElement('video');video.muted=true;video.playsInline=true;video.srcObject=stream;await video.play();
  stream.getVideoTracks()[0].addEventListener('ended',stop,{once:true});
  baseline=null;calibration=[];since={};lastVideoTime=-1;
  el('eyes').textContent='Eyes on';el('eyes').setAttribute('aria-pressed','true');
  if(!window.JarvisVoice?.isEnabled())announce(EAR_NOTICE);
  sample(token);
 } catch (error) {stop();el('eyes-status').textContent=`Eyes unavailable (${error.name || 'landmarks'}) · ${error.message || 'allow camera and retry'}`;}
 finally {el('eyes').disabled=false;}
}
async function relief(text) {
 if(!isRelief(text))return false;
 quietUntil=performance.now()+RELIEF_MS;
 window.JarvisVoice?.stopSpeech();
 try {await post('/relief',{});el('answer').textContent='Three minutes of peace, sir.';}
 catch(_){el('answer').textContent='Eyes are quiet; focus silence could not be confirmed. Retry the relief command.';}
 return true;
}
async function look(question) {
 if(looking)return;
 if(!stream?.active || video.readyState<2){announce('Turn on my eyes first, sir.');return;}
 looking=true;const token=generation;
 window.JarvisVoice?.setThinking(true);
 try {
  const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;
  canvas.getContext('2d').drawImage(video,0,0);
  const image=canvas.toDataURL('image/jpeg',JPEG_QUALITY).split(',')[1];
  const r=await fetch('/look',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,image,media_type:'image/jpeg'}),signal:AbortSignal.timeout(LOOK_MS)});
  const data=await r.json();
  if(token===generation)announce(data.answer || 'That look failed, sir.');
 }catch(_){announce('I could not complete that look, sir.');}
 finally{looking=false;window.JarvisVoice?.setThinking(false);}
}
window.JarvisEyes={matches,isRelief,relief,look};
el('eyes').onclick=()=>stream?stop():start();
window.addEventListener('pagehide',stop);
