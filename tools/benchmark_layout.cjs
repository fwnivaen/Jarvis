/* Run the unmodified browser worker in a Node worker thread with synthetic input. */
const {Worker}=require('node:worker_threads');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const BENCH=Object.freeze({sizes:[2000,10000,30000],timeoutMs:120000,
  groups:['Finance','Strategy','Marketing','Operations','Team','Sales','captures']});
const source=fs.readFileSync(path.join(__dirname,'../viewer/layout-worker.js'),'utf8');
const workerSource=`const {parentPort}=require('node:worker_threads');
global.self={onmessage:null,postMessage:null};
${source}
parentPort.on('message',data=>{const started=performance.now(),cpuClock=process.threadCpuUsage||process.cpuUsage,cpu=cpuClock(),heap=process.memoryUsage().heapUsed;
 self.postMessage=result=>{const used=cpuClock(cpu);parentPort.postMessage({result,wallMs:performance.now()-started,
 cpuMs:(used.user+used.system)/1000,cpuScope:process.threadCpuUsage?'worker-thread':'node-process',heapChangeBytes:process.memoryUsage().heapUsed-heap});};self.onmessage({data});});`;
const nodesFor=size=>Array.from({length:size},(_,id)=>({id,label:'Synthetic note '+String(id).padStart(6,'0'),group:BENCH.groups[id%BENCH.groups.length]}));
async function measure(worker,nodes,cached,revision){return new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('Worker timeout')),BENCH.timeoutMs);
  const result=value=>{clearTimeout(timeout);worker.off('error',failure);resolve(value);},failure=error=>{clearTimeout(timeout);worker.off('message',result);reject(error);};worker.once('message',result);worker.once('error',failure);worker.postMessage({nodes,cached,revision});});}
function validate(result,size){assert.equal(result.positions.length,size);for(let id=0;id<size;id++){const point=result.positions[id];assert.equal(point.id,id);for(const axis of ['x','y','z'])assert.ok(Number.isFinite(point[axis]));}}
(async()=>{
  const report={synthetic:true,environment:{node:process.version,platform:process.platform,arch:process.arch},runs:[]};
  for(const size of BENCH.sizes){
    const worker=new Worker(workerSource,{eval:true});
    try{
      const nodes=nodesFor(size),fresh=await measure(worker,nodes,{},1);validate(fresh.result,size);
      const repeat=await measure(worker,nodes,{},2);assert.deepEqual(repeat.result.positions,fresh.result.positions);
      const cached=Object.fromEntries(fresh.result.positions.map(({key,x,y,z})=>[key,{x,y,z}]));
      const next=nodesFor(size+1),incremental=await measure(worker,next,cached,3);validate(incremental.result,size+1);
      for(let id=0;id<size;id++)for(const axis of ['x','y','z'])assert.equal(incremental.result.positions[id][axis],fresh.result.positions[id][axis]);
      const row={nodes:size,cpuScope:fresh.cpuScope,freshWallMs:Number(fresh.wallMs.toFixed(2)),freshCpuMs:Number(fresh.cpuMs.toFixed(2)),freshHeapChangeMiB:Number((fresh.heapChangeBytes/1048576).toFixed(2)),
        repeatWallMs:Number(repeat.wallMs.toFixed(2)),cachedPlusOneWallMs:Number(incremental.wallMs.toFixed(2)),cachedPlusOneCpuMs:Number(incremental.cpuMs.toFixed(2)),
        deterministic:true,existingPositionsPreserved:true};report.runs.push(row);
    }finally{await worker.terminate();}
  }
  process.stdout.write(JSON.stringify(report,null,2)+'\n');
  process.stdout.write('LAYOUT BENCH PASS: synthetic 2k/10k/30k worker runs finite and deterministic; cached positions unchanged when adding a note. Timings are local CPU measurements, not renderer FPS.\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
