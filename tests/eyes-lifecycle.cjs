// Real controller, with only the browser camera/model dependencies replaced.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('viewer/eyes.js','utf8').replace("import('/vision.mjs')",'loadVision()');
function setup(pending=false){
 const elements=new Map(),requests=[],spoken=[],timers=new Map();let next=0,resolveCamera,closed=0,stopped=0,draws=0;
 const el=id=>{if(!elements.has(id))elements.set(id,{textContent:'',setAttribute(){}});return elements.get(id)};
 const track={readyState:'live',muted:false,stop(){stopped++;this.readyState='ended'},addEventListener(){}};
 const stream={active:true,getTracks:()=>[track],getVideoTracks:()=>[track]};
 const video={readyState:2,currentTime:0,videoWidth:640,videoHeight:480,play:async()=>{}};
 const vision={FilesetResolver:{forVisionTasks:async()=>({})},FaceLandmarker:{createFromOptions:async()=>({detectForVideo:()=>({faceLandmarks:[]}),close(){closed++}})},PoseLandmarker:{createFromOptions:async()=>({detectForVideo:()=>({landmarks:[]}),close(){closed++}})}};
 const context={console,AbortSignal,performance:{now:()=>0},location:{origin:'http://localhost:4700'},loadVision:async()=>vision,
 document:{getElementById:el,createElement(type){if(type==='video')return video;assert.equal(type,'canvas');return {getContext:()=>({drawImage(){draws++}}),toDataURL:()=> 'data:image/jpeg;base64,test'}}},
 navigator:{mediaDevices:{getUserMedia:async opts=>{assert.equal(opts.audio,false);return pending?new Promise(r=>resolveCamera=r):stream}}},
 window:{addEventListener(){},JarvisVoice:{isEnabled:()=>false,speak:t=>spoken.push(t),setThinking(){}}},
 setTimeout(fn,ms){timers.set(++next,{fn,ms});return next;},clearTimeout(id){timers.delete(id)},
 fetch:async(path,o)=>{requests.push({path,body:JSON.parse(o.body)});return {ok:true,json:async()=>path==='/look'?{answer:'One frame, sir.'}:{}}}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('viewer/posture.js','utf8'),context);vm.runInContext(source,context);
 return {run:s=>vm.runInContext(s,context),el,requests,spoken,track,resolve:()=>resolveCamera(stream),hasRequest:()=>!!resolveCamera,closed:()=>closed,stopped:()=>stopped,draws:()=>draws,timers};
}
(async()=>{
 const live=setup();await live.run('start()');
 assert.equal(live.el('eyes').textContent,'Eyes on');assert.match(live.spoken[0],/My ears are off/);
 assert.equal(live.draws(),0);assert.ok(live.requests.every(r=>r.path==='/eyes'));
 await live.run("look('look at me')");assert.equal(live.draws(),1);assert.equal(live.requests.filter(r=>r.path==='/look').length,1);
 live.track.muted=true;await live.run("look('look at me')");assert.equal(live.draws(),1);
 live.run('stop()');assert.equal(live.stopped(),1);assert.equal(live.closed(),2);
 const cancelled=setup(true);const opening=cancelled.run('start()');
 for(let n=0;n<30&&!cancelled.hasRequest();n++)await Promise.resolve();
 assert.ok(cancelled.hasRequest());assert.match(cancelled.el('eyes-status').textContent,/Allow camera/);
 cancelled.run('stop()');cancelled.resolve();await opening;
 assert.equal(cancelled.stopped(),1);assert.equal(cancelled.closed(),2);assert.equal(cancelled.el('eyes').textContent,'Eyes');
 console.log('EYES LIFECYCLE PASS: audio:false, ears-off notice, no startup upload, one-frame look, muted-frame refusal, cancellation releases late camera and models.');
})().catch(e=>{console.error(e);process.exitCode=1});
