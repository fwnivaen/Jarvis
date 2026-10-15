const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let now=0,pixels=new Uint8ClampedArray(96*54*4),quiet=false,frames=0,resolveReply;
const requests=[],speech=[],timers=new Map();let id=0;
const ctx={window:{},crypto:{randomUUID:()=> 'test-watch-session-token'},performance:{now:()=>now},AbortController,AbortSignal,
 setTimeout(fn,ms){timers.set(++id,{fn,ms});return id},clearTimeout(id){timers.delete(id)},
 fetch:async(path,opts)=>{requests.push({path,body:JSON.parse(opts.body)});if(path==='/watch')return {ok:true,json:async()=>({card:true})};return new Promise(resolve=>{resolveReply=()=>resolve({ok:true,json:async()=>({answer:'Try the first visible step.'})})})}
};
vm.runInNewContext(fs.readFileSync('viewer/watch.js','utf8'),ctx);
const watch=ctx.window.JarvisWatch.create({thumbnail:()=>pixels.slice(),frame:()=>{frames++;return {image:'synthetic',media_type:'image/jpeg'}},quiet:()=>quiet,say:t=>speech.push(t),status(){}});
async function tick(t){now=t;watch.tick();for(let i=0;i<8;i++)await Promise.resolve()}
async function reply(){resolveReply();for(let i=0;i<8;i++)await Promise.resolve()}
(async()=>{
 watch.start();await tick(5000);await tick(59999);assert.equal(frames,0);
 await tick(60000);assert.equal(frames,1);await tick(70000);assert.equal(frames,1);await reply();assert.equal(speech.length,1);
 await tick(239999);assert.equal(frames,1);await tick(240000);assert.equal(frames,2);
 quiet=true;await reply();assert.equal(speech.length,1);await tick(425000);assert.equal(frames,2);
 quiet=false;pixels.fill(200);await tick(430000);await tick(489999);assert.equal(frames,2);await tick(490000);assert.equal(frames,3);
 pixels.fill(50);await tick(495000);await reply();assert.equal(speech.length,1); // changed screen invalidates pending answer
 await tick(670000);assert.equal(frames,4);watch.stop();await reply();assert.equal(speech.length,1);
 await tick(900000);assert.equal(frames,4);
 for(const r of requests.filter(r=>r.path==='/watch'))assert.deepEqual(Object.keys(r.body).sort(),['active','token']);
 assert.equal(ctx.window.JarvisWatch.changed(new Uint8Array(400),new Uint8Array(400)),false);
 assert.equal(ctx.window.JarvisWatch.changed(new Uint8Array(400),new Uint8Array(400).fill(255)),true);
 console.log('WATCH PASS: local-only thumbnail checks, 60-second stillness, one frame, 180-second cooldown, relief/input suppression, stale replies and stop cleanup.');
})().catch(e=>{console.error(e);process.exitCode=1});
