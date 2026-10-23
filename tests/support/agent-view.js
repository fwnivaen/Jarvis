const {readFileSync}=require('node:fs'),vm=require('node:vm');
const SOURCE=readFileSync('viewer/agents.js','utf8');
const LIMITS={max_workers:3,worker_timeout_s:45,max_escalations:1,request_timeout_s:240};
const BASE={enabled:true,routing_enabled:true,crew_enabled:true,active:false,agents:[],events:[],limits:LIMITS,elapsed_s:0};
function element(){return {hidden:true,textContent:'',dataset:{},children:[],append(child){this.children.push(child);},replaceChildren(){this.children=[];},querySelectorAll(){return this.links||[];}};}
function run(count=3){return {id:'111111111111111111111111',created_at:990,status:'running',elapsed_s:10,tool_calls:1,
 agents:Array.from({length:count},(_,i)=>({slot:'worker-'+(i+1),status:'running',task:'Analyze supplied evidence',elapsed_s:2,attempts:1,model:'test-model',effort:'high',tokens:14,usage_reported:true}))};}
async function setup({legacy={...BASE},workflow=null}={}){
 const elements=Object.fromEntries(['agent-monitor','agent-rows','agent-summary','agent-limits','agent-crew','crew-members','crew-summary','crew-activity','crew-open-work'].map(id=>[id,element()]));
 const links=['0-1','1-2','0-2'].map(pair=>{const e=element();e.dataset.pair=pair;return e;});elements['agent-crew'].links=links;
 let timer=null,cleared=false,offline=false,now=1000000;const listeners={},requests=[];
 class Clock extends Date{static now(){return now;}}
 const context={Math,Date:Clock,AbortSignal:{timeout(){}},setTimeout(fn){timer=fn;return 1;},clearTimeout(){cleared=true;},
 document:{hidden:false,getElementById:id=>elements[id],createElement:element},
 window:{addEventListener(name,fn){listeners[name]=fn;},removeEventListener(name){delete listeners[name];},JarvisUI:{setWorkspace(name){elements.workspace=name;}}},
 fetch:async path=>{requests.push(path);if(offline)throw Error('offline');return {ok:true,json:async()=>path==='/agents'?legacy:path.startsWith('/workflows/run')?workflow:{enabled:true,available:true,active:workflow?.status==='running'?workflow.id:null,runs:workflow?[workflow]:[]}};}};
 vm.runInNewContext(SOURCE,context);await new Promise(resolve=>setImmediate(resolve));
 async function poll(){await timer();await new Promise(resolve=>setImmediate(resolve));}
 return {elements,links,requests,api:context.window.JarvisAgents,listeners,advance(ms){now+=ms;},cleared:()=>cleared,
 async update({data=legacy,workflow:next=workflow}={}){offline=false;legacy=data;workflow=next;now+=4001;await poll();},
 async fail(){offline=true;await poll();},
 event(value){listeners['jarvis:workflow-state']?.({detail:value});},poll};
}
module.exports={setup,run,BASE};
