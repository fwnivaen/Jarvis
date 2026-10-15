const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map(),requests=[],speech=[];
const el=id=>{if(!elements.has(id))elements.set(id,{textContent:'',setAttribute(){}});return elements.get(id)};
let now=0;
const ctx={console,AbortSignal,performance:{now:()=>now},document:{getElementById:el},window:{addEventListener(){},JarvisVoice:{speak:t=>speech.push(t),stopSpeech(){speech.length=0}}},setTimeout(){},clearTimeout(){},fetch:async(path,o)=>{requests.push({path,body:JSON.parse(o.body)});return {ok:true,json:async()=>({})}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('viewer/posture.js','utf8'),ctx);vm.runInContext(fs.readFileSync('viewer/eyes.js','utf8'),ctx);
const run=s=>vm.runInContext(s,ctx);
(async()=>{
 assert.equal(run("matches('what do you think of this screen')"),false);
 assert.equal(run("matches('what do you think of my shirt?')"),true);
 assert.equal(run("matches('look at me')"),true);
 assert.equal(run("isCommand('turn on your eyes')"),true);
 assert.equal(run("isCommand('can you see me?')"),true);
 assert.equal(run("isCommand('what do you think of this screen?')"),false);
 await ctx.window.JarvisEyes.command('can you see me');
 assert.match(el('answer').textContent,/camera is off or unavailable/);
 assert.equal(requests.length,0); // Capability status uses no brain and no image.
 speech.length=0;
 assert.equal(run("sustained('head_down',true,0,HOLD_MS)"),false);
 assert.equal(run("sustained('head_down',true,699,HOLD_MS)"),false);
 assert.equal(run("sustained('head_down',true,700,HOLD_MS)"),true);
 assert.equal(run("sustained('absent',true,0,ABSENCE_MS)"),false);
 assert.equal(run("sustained('absent',true,11999,ABSENCE_MS)"),false);
 assert.equal(run("sustained('absent',true,12000,ABSENCE_MS)"),true);
 await ctx.window.JarvisEyes.relief('no Jarvis, I need to do something important');
 assert.equal(run('quietUntil'),180000);assert.equal(requests.at(-1).path,'/relief');
 assert.equal(run('179999 >= quietUntil'),false);assert.equal(run('180000 >= quietUntil'),true);
 assert.equal(run('COOLDOWN_MS'),30000);
 assert.equal(speech.length,0);
 // Exercise the actual sampling and nudge path with a virtual clock.
 run(`quietUntil=0; nextNudge=0; since={}; sessionState={}; baseline={};
 stream={active:true}; video={readyState:2,currentTime:0};
 face={detectForVideo:()=>({faceLandmarks:[]})};
 pose={detectForVideo:()=>({landmarks:[]})};
 classify=()=>({present:true,head_down:true,slouched:false});`);
 async function tick(t) { now=t;run('video.currentTime++');await run('sample(generation)');await Promise.resolve(); }
 await tick(0); await tick(699); assert.equal(speech.length,0);
 await tick(700);assert.equal(speech.length,1);
 await tick(29999);assert.equal(speech.length,1);
 await tick(30700);assert.equal(speech.length,2);
 for(const phrase of ['gimme 3 minutes','give me three minutes','Jarvis, give me a minute','please give me 3 minutes']) assert.equal(run(`isRelief(${JSON.stringify(phrase)})`),true);
 await ctx.window.JarvisEyes.relief('gimme 3 minutes');
 for(let t=30800;t<210700;t+=100) await tick(t);
 assert.equal(speech.length,0); // Relief cancelled speech and no later nudge escaped.
 await tick(210700);assert.equal(speech.length,1);
 for(const r of requests.filter(r=>r.path==='/eyes')) {
  assert.deepEqual(Object.keys(r.body).sort(),['eyes_active','head_down','present','slouched']);
  assert.ok(Object.values(r.body).every(v=>typeof v==='boolean'));
 }
 console.log('EYES PASS: exact look routing, 700ms hold, 12s absence, 30s cooldown, three-minute silent relief.');
})().catch(e=>{console.error(e);process.exitCode=1});
