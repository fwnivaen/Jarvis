// Camera pixels and landmarks stay in this browser. Only look() encodes a frame.
const SAMPLE_MS = 80, HOLD_MS = 700, ABSENCE_MS = 12000, COOLDOWN_MS = 30000;
const RELIEF_MS = 180000, REQUEST_MS = 4000, LOOK_MS = 120000;
const START_TIMEOUT_MS = 30000, FRAME_STALE_MS = 2000, VIDEO_READY = 2;
const VIDEO_WIDTH = 640, VIDEO_HEIGHT = 480, JPEG_QUALITY = .82;
const PREVIEW_WIDTH=320, PREVIEW_HEIGHT=240, LANDMARK_RADIUS=3, FULL_PERCENT=100;
const tracker=window.JarvisPosture.create();
let tracking={};
const EAR_NOTICE = 'My ears are off, sir — tap the ear button and just talk.';
const LINES = {head_down: ['Sir, the phone has had its audience.', 'Your task is up here, sir.'], slouched: ['Sir, the chair is winning.', 'A little spine, sir. Literally.'], absent: ['Your desk has reported you missing, sir.']};
const clean = text => text.toLowerCase().replace(/[,.!?]/g, '').trim();
const isRelief = text => /^(?:no jarvis i need to do something important|give me a minute)$/.test(clean(text));
const matches = text => /^(?:(?:hey )?jarvis )?(?:look at me|what do you think of my shirt)$/.test(clean(text));
const START_COMMAND = /^(?:(?:hey )?jarvis )?(?:(?:turn|switch) on (?:your |the )?eyes|(?:enable|open) (?:your |the )?eyes|eyes on)$/;
const STOP_COMMAND = /^(?:(?:hey )?jarvis )?(?:(?:turn|switch) off (?:your |the )?eyes|(?:disable|close) (?:your |the )?eyes|eyes off)$/;
const STATUS_COMMAND = /^(?:(?:hey )?jarvis )?(?:can you see me|are (?:your |the )?eyes (?:on|working|real)|(?:are|is) (?:your |the )?eyes (?:just |merely )?(?:a )?prop|what can (?:your |the )?eyes do|eyes status)$/;
const isCommand = text => [START_COMMAND,STOP_COMMAND,STATUS_COMMAND].some(pattern=>pattern.test(clean(text)));
const el = id => document.getElementById(id);
let starting=false, startupTimer, startupCleanup=null, stream, video, face, pose, timer, generation = 0, quietUntil = 0, nextNudge = 0;
let publishing = false, sessionState = {}, baseline = null, since = {}, positions = {}, lastVideoTime = -1, lastFrameAt = 0, looking = false;
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
function classify(f,p,m,now) {
 tracking=tracker.update(f,p,m,now,video?.videoHeight/video?.videoWidth || VIDEO_HEIGHT/VIDEO_WIDTH);
 baseline=tracking.head_ready;
 return tracking;
}
function drawPreview(f,p) {
 const canvas=el('eyes-preview'),ctx=canvas?.getContext?.('2d');
 if(!ctx)return;
 canvas.width=PREVIEW_WIDTH;canvas.height=PREVIEW_HEIGHT;
 ctx.save();ctx.translate(canvas.width,0);ctx.scale(-1,1);ctx.drawImage(video,0,0,canvas.width,canvas.height);
 ctx.fillStyle='#69e0ff';
 for(const point of [f?.[1],f?.[33],f?.[263],f?.[152],tracking.shoulders?p?.[11]:null,tracking.shoulders?p?.[12]:null].filter(Boolean)){
  ctx.beginPath();ctx.arc(point.x*canvas.width,point.y*canvas.height,LANDMARK_RADIUS,0,Math.PI*2);ctx.fill();
 }
 ctx.restore();
}
function recalibrate(){tracker.reset();baseline=null;since={};el('eyes-status').textContent='Look straight ahead and hold still · resetting upright posture';}
async function sample(token) {
 if (token !== generation || !stream) return;
 try {
  if (video.readyState < VIDEO_READY || video.currentTime === lastVideoTime || stream.getVideoTracks?.()[0]?.muted) {
   if(performance.now()-lastFrameAt >= FRAME_STALE_MS){since={};el('eyes-status').textContent='Camera paused · no posture signal';}
   timer=setTimeout(()=>sample(token),SAMPLE_MS);return;
  }
  lastVideoTime=video.currentTime;
  const now=performance.now();lastFrameAt=now;
  const faceResult=face.detectForVideo(video,now),poseResult=pose.detectForVideo(video,now);
  const f=faceResult.faceLandmarks[0],p=poseResult.landmarks[0];
  const raw=classify(f,p,faceResult.facialTransformationMatrixes?.[0],now);
  drawPreview(f,p);
  signals={eyes_active:true, present:raw.present, head_down:sustained('head_down',raw.head_down,now,HOLD_MS), slouched:sustained('slouched',raw.slouched,now,HOLD_MS)};
  const absent=sustained('absent',!raw.present,now,ABSENCE_MS);
  if (!publishing) {
   publishing=true;
   post('/eyes',signals).then(state=>{if(token===generation)sessionState=state;}).catch(()=>{if(token===generation){stop();el('eyes-status').textContent='Eyes session disconnected';}}).finally(()=>{publishing=false;});
  }
  const state=sessionState;
  if (token !== generation) return;
  if (state.snooze_s) { quietUntil=Math.max(quietUntil,performance.now()+state.snooze_s*1000); sessionState={...state,snooze_s:0}; }
  el('eyes-status').textContent=!raw.present?'Away':!raw.face?'Face not tracked · look toward camera':!baseline?`Hold still, looking ahead · calibrating ${Math.round((tracking.calibration||0)*FULL_PERCENT)}%`:signals.head_down?'Head down':signals.slouched?'Slouched':!raw.shoulders?'Head tracked · shoulders out of view':!raw.body_ready?'Head tracked · calibrating upright shoulders':'Eyes · local only';
  el('eyes-tracking').textContent=`Face: ${raw.face?'tracked':'not found'} · Shoulders: ${raw.shoulders?'tracked':'out of view'}${tracking.pitch!==null&&tracking.pitch!==undefined?` · Head tilt: ${Math.round(tracking.pitch)}°`:''}`;
  el('eyes-nudge-status').textContent=now<quietUntil?`Relief · ${Math.ceil((quietUntil-now)/1000)} seconds quiet`:now<nextNudge?`Nudge cooldown · ${Math.ceil((nextNudge-now)/1000)} seconds`:'Nudges ready';
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
 generation++; starting=false; clearTimeout(startupTimer);clearTimeout(timer);
 startupCleanup?.();startupCleanup=null;
 stream?.getTracks().forEach(t=>t.stop()); stream=null;
 if(video)video.srcObject=null;
 face?.close(); pose?.close(); face=pose=null;
 signals={eyes_active:false,present:false,head_down:false,slouched:false};
 post('/eyes',signals).catch(()=>{});
 el('eyes-panel').hidden=true;const preview=el('eyes-preview');preview?.getContext?.('2d')?.clearRect(0,0,preview.width,preview.height);
 el('eyes').disabled=false;el('eyes').textContent='Eyes';el('eyes').setAttribute('aria-pressed','false');el('eyes-status').textContent='Eyes off';
}
async function start() {
 if(starting || stream)return;
 starting=true;
 const token=++generation;
 el('eyes').textContent='Cancel eyes';el('eyes-status').textContent='Loading local face and pose models…';
 startupTimer=setTimeout(()=>{if(token===generation){stop();el('eyes-status').textContent='Camera permission timed out · allow camera, then try Eyes again';}},START_TIMEOUT_MS);
 let localFace,localPose,localStream;
 const release=()=>{localFace?.close();localPose?.close();localStream?.getTracks().forEach(t=>t.stop());localFace=localPose=localStream=null;};
 startupCleanup=release;
 try {
  const vision=await import('/vision.mjs');
  const files=await vision.FilesetResolver.forVisionTasks(location.origin);
  if(token!==generation)return;
  localFace=await vision.FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/face_landmarker.task'},runningMode:'VIDEO',numFaces:1,outputFacialTransformationMatrixes:true});
  if(token!==generation)return;
  localPose=await vision.PoseLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/pose_landmarker.task'},runningMode:'VIDEO',numPoses:1});
  if(token!==generation)return;
  el('eyes-status').textContent='Allow camera in the browser prompt · microphone stays off unless you enable it';
  localStream=await navigator.mediaDevices.getUserMedia({video:{width:VIDEO_WIDTH,height:VIDEO_HEIGHT},audio:false});
  if(token!==generation)return;
  const localVideo=document.createElement('video');localVideo.muted=true;localVideo.playsInline=true;localVideo.srcObject=localStream;await localVideo.play();
  if(token!==generation){localVideo.srcObject=null;return;}
  face=localFace;pose=localPose;stream=localStream;video=localVideo;
  localFace=localPose=localStream=null;
  stream.getVideoTracks()[0].addEventListener('ended',()=>{if(token===generation)stop();},{once:true});
  recalibrate();el('eyes-panel').hidden=false;el('eyes-panel').open=true;lastVideoTime=-1;lastFrameAt=performance.now();
  clearTimeout(startupTimer);starting=false;startupCleanup=null;
  el('eyes').textContent='Eyes on';el('eyes').setAttribute('aria-pressed','true');
  if(!window.JarvisVoice?.isEnabled())announce(EAR_NOTICE);
  sample(token);
 } catch (error) {if(token===generation){stop();el('eyes-status').textContent=`Eyes unavailable (${error.name || 'landmarks'}) · ${error.message || 'allow camera and retry'}`;}}
 finally {release();if(token===generation)startupCleanup=null;}
}
async function command(text) {
 const q=clean(text);
 if(START_COMMAND.test(q)) {if(stream)announce('My eyes are already on, sir. Posture stays local.');else await start();return;}
 if(STOP_COMMAND.test(q)){stop();announce('Eyes off, sir.');return;}
 const active=stream?.active && performance.now()-lastFrameAt<FRAME_STALE_MS;
 announce(starting?'My local landmark models are starting. Please allow camera access in the browser prompt.':active?
  `My eyes are working locally, sir${!baseline?'—sit upright while I calibrate':signals.present?'—you are present':'—nobody detected'}. I receive posture signals, not a continuous photo feed; say “look at me” for one photo sent to Astra.`:
  'My eyes are real, sir, but the camera is off or unavailable. Tap Eyes or say “turn on your eyes”, allow camera access, and sit upright to calibrate. The microphone stays under your control.');
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
 if(!stream?.active || video.readyState<VIDEO_READY || !video.videoWidth || !video.videoHeight || stream.getVideoTracks()[0]?.muted || stream.getVideoTracks()[0]?.readyState!=='live'){announce('Turn on my eyes first, sir.');return;}
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
window.JarvisEyes={matches,isRelief,relief,look,isCommand,command};
el('eyes').onclick=()=>stream||starting?stop():start();
el('eyes-recalibrate').onclick=recalibrate;
el('eyes-sensitivity').onchange=event=>{tracker.setThreshold(event.target.value);since={};};
window.addEventListener('pagehide',stop);
