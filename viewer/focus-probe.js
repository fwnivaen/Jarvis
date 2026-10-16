/* No wall-clock assertions: a synthetic scheduler drives the real controller. */
const PROBE_WIDTH=1440, PROBE_HEIGHT=900, PROBE_FLUSH_TURNS=12;
const PROBE_PIXELS=400, PROBE_BRIGHT=255;
const probeTimers=[], probeRequests=[];
let probeState={}, probeIntent=false, probeFail=false;
window.setTimeout=fn=>{probeTimers.push(fn);return probeTimers.length;};
window.fetch=async (path,options)=>{
 probeRequests.push({path,options});
 if(probeFail)throw Error('simulated disconnect');
 return {ok:true,json:async()=>options?.method==='POST'?{answer:'Ready',spoken:true,state:probeState}:probeState};
};
window.JarvisVoice={setThinking(){},setExternalSpeaking(){},quietFor(){},speak(){throw Error('unexpected speech');},
 cancelAnswer(){probeIntent=false;},answerOnce(){probeIntent=true;},intentWindowOpen:()=>probeIntent};
async function flush(){for(let i=0;i<PROBE_FLUSH_TURNS;i++)await Promise.resolve();}
async function show(overrides){probeState={active:true,known:true,remaining_s:120,drifts:0,...overrides};const fn=probeTimers.shift();if(fn)fn();await flush();}
async function runProbe(){
 const results=[];
 const check=async(name,fn)=>{try{await fn();results.push(`PASS ${name}`);}catch{results.push(`FAIL ${name}`);}};
 const assert=value=>{if(!value)throw Error('assertion');};
 const status=()=>document.getElementById('focus-status').textContent;
 await flush();
 await check('viewport',()=>assert(innerWidth===PROBE_WIDTH && innerHeight===PROBE_HEIGHT));
 await check('visible',()=>assert(document.visibilityState==='visible'));
 await check('reload-read-only',()=>assert(probeRequests[0]?.path==='/focus' && !probeRequests[0].options.method));
 await check('focused',async()=>{await show({});assert(status()==='2:00 · Focused');});
 await check('deferred',async()=>{await show({lock_deferred:true});assert(status().includes('waiting to lock'));});
 await check('unavailable',async()=>{await show({known:false});assert(status().includes('unavailable'));});
 await check('paused',async()=>{await show({paused:true});assert(status().includes('Paused'));});
 await check('drift',async()=>{await show({drifting:true,drifts:2});assert(status().includes('Return to task'));});
 await check('excused',async()=>{await show({excused:true});assert(status().includes('Excused'));});
 await check('home',async()=>{await show({home:true,drifting:true});assert(status().includes('Home base'));});
 await check('intent-window',async()=>{await show({});await JarvisFocus.command({action:'start'});assert(probeIntent);await show({active:false});assert(!probeIntent);});
 await check('commands',()=>{for(const text of ['pause','resume','abort','thirty minutes on this','lock this tab'])assert(JarvisFocus.matches(text));assert(!JarvisFocus.matches('give me a summary'));});
 await check('pixel-identical',()=>assert(!JarvisWatch.changed(new Uint8Array(PROBE_PIXELS),new Uint8Array(PROBE_PIXELS))));
 await check('pixel-change',()=>assert(JarvisWatch.changed(new Uint8Array(PROBE_PIXELS),new Uint8Array(PROBE_PIXELS).fill(PROBE_BRIGHT))));
 await check('disconnect',async()=>{probeFail=true;await show({});assert(status()==='Focus server disconnected');probeFail=false;});
 await check('visible-at-finish',()=>assert(document.visibilityState==='visible'));
 const failures=results.filter(x=>x.startsWith('FAIL')).length;
 const summary=`FOCUS PROBE: ${results.length-failures} pass, ${failures} fail | ${innerWidth}x${innerHeight}`;
 document.getElementById('results').textContent=summary+'\n'+results.join('\n');
 document.title=summary+' | '+results.join(' | ');
}
window.addEventListener('load',runProbe);
document.getElementById('run').onclick=runProbe;
