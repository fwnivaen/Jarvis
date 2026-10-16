// Thumbnails exist only in memory. Only nudge() may encode and send a frame.
(() => {
 const SAMPLE_MS=5000, STILL_MS=60000, COOLDOWN_MS=180000;
 const WIDTH=96, HEIGHT=54, CHANNELS=4, RGB=3, PIXEL_DELTA=20, CHANGE_FRACTION=.008;
 const REQUEST_MS=130000, HEARTBEAT_MS=4000;
 const PROMPT='The screen has been mostly unchanged for one minute. From this single current screenshot, offer one concrete next step that could help with the visible task. Do not assume I am stuck or claim to know what I did earlier. Be direct, useful, and at most two short sentences; dry wit only if useful.';
 function difference(a,b) {
  if(!a || a.length!==b.length)return 1;
  let count=0;
  for(let i=0;i<b.length;i+=CHANNELS){let delta=0;for(let c=0;c<RGB;c++)delta+=Math.abs(a[i+c]-b[i+c]);if(delta/RGB>PIXEL_DELTA)count++;}
  return count/(b.length/CHANNELS);
 }
 function changed(a,b){return difference(a,b)>=CHANGE_FRACTION;}
 let debug={last_pixel_diff:null, pixel_gate:CHANGE_FRACTION, nudge_gate:false};
 function create(io) {
  let active=false,previous=null,stillAt=0,nextAt=0,generation=0,motion=0,inFlight=false,controller=null,timer,heartbeat;
  const token=crypto.randomUUID();
  async function lease(value) {
   try {const r=await fetch('/watch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,active:value}),signal:AbortSignal.timeout(HEARTBEAT_MS)});if(!r.ok)throw Error();const state=await r.json();if(value && !state.card)io.status('Watching · desktop face unavailable');}
   catch {if(value)io.status('Watching · desktop face disconnected');}
  }
  function beat(){if(!active)return;lease(true);heartbeat=setTimeout(beat,HEARTBEAT_MS);}
  function stop(){active=false;generation++;controller?.abort();controller=null;previous=null;clearTimeout(timer);clearTimeout(heartbeat);lease(false);io.status('Screen watch off');}
  function start(){if(active)return;active=true;generation++;previous=null;stillAt=performance.now();nextAt=0;io.status('Watching · local checks only');beat();tick();}
  async function nudge(now) {
   const version=generation,atMotion=motion;
   nextAt=now+COOLDOWN_MS;inFlight=true;controller=new AbortController();
   const timeout=setTimeout(()=>controller?.abort(),REQUEST_MS);
   try {
    const response=await fetch('/see',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:PROMPT,...io.frame()}),signal:controller.signal});
    const data=await response.json();
    if(active && version===generation && atMotion===motion && !io.quiet() && response.ok && typeof data.answer==='string')io.say(data.answer);
   }catch {if(active && version===generation)io.status('Watching · nudge unavailable; waiting before retry');}
   finally{clearTimeout(timeout);inFlight=false;controller=null;}
  }
  function tick(){
   if(!active)return;
   try {
    const pixels=io.thumbnail(WIDTH,HEIGHT),now=performance.now();
    debug.last_pixel_diff=difference(previous,pixels);
    if(changed(previous,pixels)){stillAt=now;motion++;}
    previous=pixels;
    debug.nudge_gate=!inFlight && now-stillAt>=STILL_MS && now>=nextAt && !io.quiet();
    if(debug.nudge_gate)nudge(now);
   }catch {previous=null;stillAt=performance.now();motion++;}
   timer=setTimeout(tick,SAMPLE_MS);
  }
  return {start,stop,tick,isActive:()=>active};
 }
 window.JarvisWatch={create,changed,difference,debug:()=>({...debug})};
})();
