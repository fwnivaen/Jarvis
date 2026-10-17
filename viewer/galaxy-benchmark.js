import {seedPositions,createGalaxy} from '/galaxy.js';
const BENCHMARK=Object.freeze({storageKey:'jarvis.galaxy.synthetic.v2',defaultCount:2000,linksPerNode:3,
  distance:620,opticalY:24,pixelRatioLimit:2,sampleMs:1000,sweepPeriod:8000,sweepMargin:30,
  mebibyte:1048576,categories:['Finance','Strategy','Marketing','Operations','Team','Sales','captures']});
const $=id=>document.getElementById(id),stage=$('stage'),host=$('graph'),measurements=[];
let THREE,graph=null,api=null,data={nodes:[],links:[]},selected=null,count=BENCHMARK.defaultCount;
let loadStarted=0,firstDraw=null,baselineHeap=null,lastSample=0,lastRenderFrame=0,submissionRate=null;
let resizeObserver=null,meterFrame=null,loading=false,runStarted=0,latestMeasurement=null;
function memory(){return Number.isFinite(performance.memory?.usedJSHeapSize)?performance.memory.usedJSHeapSize:null;}
function fixture(size){
  const nodes=Array.from({length:size},(_,id)=>({id,label:`Synthetic note ${String(id).padStart(6,'0')}`,
    group:BENCHMARK.categories[id%BENCHMARK.categories.length],excerpt:'Synthetic performance fixture. No personal content.',
    edited_at:0}));
  const links=[];for(let id=0;id<size;id++)for(let edge=1;edge<=BENCHMARK.linksPerNode;edge++)links.push({source:id,target:(id+edge*BENCHMARK.categories.length+(id%23))%size});
  return {nodes,links};
}
function endId(value){return typeof value==='object'?value.id:value;}
function linkKey(link){return `${Math.min(endId(link.source),endId(link.target))}:${Math.max(endId(link.source),endId(link.target))}`;}
function highlight(node){
  selected=node?.id??null;const highlighted=new Set(),activeLinks=new Set();
  if(node){highlighted.add(node.id);for(const link of data.links)if(endId(link.source)===node.id||endId(link.target)===node.id){highlighted.add(endId(link.source));highlighted.add(endId(link.target));activeLinks.add(linkKey(link));}}
  api?.highlight({selected,highlighted,activeLinks,activeGroup:null});
  $('bench-status').textContent=node?`Synthetic note ${node.id} selected. Escape clears it.`:`${count.toLocaleString()} synthetic notes · ${(count*BENCHMARK.linksPerNode).toLocaleString()} synthetic links`;
}
function flyCamera(position,target){graph.cameraPosition(position,target);api?.wake();}
function dispose(){resizeObserver?.disconnect();api?.destroy();api=null;if(graph){const renderer=graph.renderer();graph.pauseAnimation();graph._destructor?.();renderer.dispose();renderer.forceContextLoss?.();graph=null;}host.replaceChildren();$('galaxy-labels').replaceChildren();}
function renderMode(){if(!graph||!api)return;const reduced=$('reduced').checked;graph.controls().autoRotate=$('rotate').checked&&!reduced;$('rotate').disabled=reduced;api.setContinuous($('continuous').checked);api.wake();}
async function load(size,resetCache=false){
  if(loading)return;loading=true;document.querySelectorAll('[data-count],#reset,#reduced,#sample').forEach(button=>button.disabled=true);
  $('bench-status').textContent=`Building ${size.toLocaleString()} synthetic notes…`;
  await new Promise(resolve=>requestAnimationFrame(resolve));
  try{
    dispose();count=size;if(resetCache)try{localStorage.removeItem(BENCHMARK.storageKey);}catch{}
    loadStarted=performance.now();runStarted=loadStarted;firstDraw=null;submissionRate=null;lastSample=0;baselineHeap=memory();
    data=fixture(size);seedPositions(data.nodes,{storageKey:BENCHMARK.storageKey});
    graph=ForceGraph3D({controlType:'orbit'})(host).backgroundColor('#040506').showNavInfo(false)
      .width(stage.clientWidth).height(stage.clientHeight).graphData(data).nodeThreeObject(()=>new THREE.Group())
      .nodeLabel('').linkVisibility(false).enableNodeDrag(false).enablePointerInteraction(false).warmupTicks(0).cooldownTicks(0);
    graph.d3Force('charge',null);graph.d3Force('link',null);graph.d3Force('center',null);
    graph.cameraPosition({x:0,y:0,z:BENCHMARK.distance},{x:0,y:BENCHMARK.opticalY,z:0});
    graph.renderer().setPixelRatio(Math.min(devicePixelRatio,BENCHMARK.pixelRatioLimit));
    api=createGalaxy({graph,THREE,getData:()=>data,stage,labels:$('galaxy-labels'),onSelect:highlight,onClear:()=>highlight(null),
      onGroup:group=>api.highlight({selected:null,highlighted:new Set(),activeLinks:new Set(),activeGroup:group}),
      flyCamera,reducedMotion:$('reduced').checked,initialDistance:BENCHMARK.distance,storageKey:BENCHMARK.storageKey});
    selected=null;lastRenderFrame=graph.renderer().info.render.frame;renderMode();
    resizeObserver=new ResizeObserver(()=>{if(graph){graph.width(stage.clientWidth).height(stage.clientHeight);api?.wake();}});resizeObserver.observe(stage);
    document.querySelectorAll('[data-count]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.count)===size)));
    $('bench-status').textContent=`${size.toLocaleString()} synthetic notes · ${(size*BENCHMARK.linksPerNode).toLocaleString()} synthetic links`;
  }catch(error){$('bench-status').textContent='Renderer failed: '+error.message;}
  finally{loading=false;document.querySelectorAll('[data-count],#reset,#reduced,#sample').forEach(button=>button.disabled=false);}
}
function sample(now){
  if(!graph||!api)return;const stats=api.performance,render=graph.renderer().info.render,heap=memory();
  if(firstDraw===null&&stats.frames>0&&render.frame>lastRenderFrame)firstDraw=now-loadStarted;
  if(!lastSample){lastSample=now;lastRenderFrame=render.frame;}
  if(now-lastSample>=BENCHMARK.sampleMs){submissionRate=(render.frame-lastRenderFrame)*1000/(now-lastSample);lastSample=now;lastRenderFrame=render.frame;}
  latestMeasurement={timestamp:new Date().toISOString(),elapsedSeconds:(now-runStarted)/1000,
    synthetic:true,nodes:count,links:data.links.length,viewport:{width:stage.clientWidth,height:stage.clientHeight,pixelRatio:graph.renderer().getPixelRatio()},
    mode:{continuous:$('continuous').checked,rotate:graph.controls().autoRotate,reducedMotion:$('reduced').checked,pickingSweep:$('sweep').checked},
    renderSubmissionsPerSecond:submissionRate,meanFrameIntervalMs:stats.frameMs,p95FrameIntervalMs:stats.p95FrameMs,
    drawCalls:render.calls,triangles:render.triangles,bufferCpuMs:stats.bufferMs,projectionCpuMs:stats.projectionMs,renderSubmitCpuMs:stats.renderMs,pickingMs:stats.hoverMs,maxPickingMs:stats.maxHoverMs,
    firstObservedDrawMs:firstDraw,jsHeapBytes:heap,heapChangeBytes:heap!==null&&baselineHeap!==null?heap-baselineHeap:null,
    layoutWorker:stats.layoutWorker,layoutPersisted:stats.layoutPersisted,idle:stats.idle};
  $('count').textContent=count.toLocaleString()+' / '+data.links.length.toLocaleString();
  $('fps').textContent=submissionRate===null?'Collecting…':submissionRate.toFixed(1);
  $('frame').textContent=stats.frameMs.toFixed(1)+' / '+stats.p95FrameMs.toFixed(1)+' ms';
  $('cpu').textContent=stats.bufferMs.toFixed(1)+' / '+stats.projectionMs.toFixed(1)+' / '+stats.renderMs.toFixed(1)+' ms';
  $('draw').textContent=render.calls.toLocaleString()+' / '+render.triangles.toLocaleString();
  $('picking').textContent=stats.hoverMs.toFixed(3)+' / '+stats.maxHoverMs.toFixed(3)+' ms';
  $('first').textContent=firstDraw===null?'Waiting for draw':firstDraw.toFixed(1)+' ms';
  $('heap').textContent=heap===null?'API unavailable':(heap/BENCHMARK.mebibyte).toFixed(1)+' MiB · '+((heap-baselineHeap)/BENCHMARK.mebibyte).toFixed(1)+' MiB';
  $('layout').textContent=(stats.layoutWorker?'Running result':'Pending / unavailable')+' · '+(stats.layoutPersisted?'saved':'unsaved');
  $('render-state').textContent=document.hidden?'Background paused':stats.idle?'Idle / paused':'Drawing';
}
function meter(now){
  if(!document.hidden){sample(now);if($('sweep').checked&&graph){const r=host.getBoundingClientRect(),phase=(now%BENCHMARK.sweepPeriod)/BENCHMARK.sweepPeriod*Math.PI*2;
    host.dispatchEvent(new PointerEvent('pointermove',{clientX:r.left+r.width/2+Math.cos(phase)*(r.width/2-BENCHMARK.sweepMargin),clientY:r.top+r.height/2+Math.sin(phase*3)*(r.height/2-BENCHMARK.sweepMargin),bubbles:true}));}}
  meterFrame=requestAnimationFrame(meter);
}
document.querySelectorAll('[data-count]').forEach(button=>button.addEventListener('click',()=>load(Number(button.dataset.count))));
$('reset').addEventListener('click',()=>{measurements.length=0;latestMeasurement=null;$('results').textContent='No measurements saved.';load(count,true);});$('continuous').addEventListener('change',renderMode);$('rotate').addEventListener('change',renderMode);
$('reduced').checked=matchMedia('(prefers-reduced-motion: reduce)').matches;$('reduced').addEventListener('change',()=>load(count));
$('sample').addEventListener('click',()=>{if(!latestMeasurement)return;measurements.push({...latestMeasurement,userAgent:navigator.userAgent});$('results').textContent=measurements.map(value=>JSON.stringify(value,null,2)).join('\n\n');});
document.addEventListener('visibilitychange',()=>{lastSample=0;submissionRate=null;});
window.addEventListener('pagehide',()=>{if(meterFrame!==null)cancelAnimationFrame(meterFrame);dispose();},{once:true});
try{THREE=await import('/three.module.js');if(typeof ForceGraph3D!=='function')throw Error('3D library unavailable');await load(count);meterFrame=requestAnimationFrame(meter);}catch(error){$('bench-status').textContent='Benchmark unavailable: '+error.message;}
