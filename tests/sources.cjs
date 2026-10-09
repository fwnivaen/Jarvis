// Execute the actual viewer response/camera code with browser and graph doubles.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const WAIT_MS=8000,FLIGHT_MS=1300;
const html=fs.readFileSync('viewer/index.html','utf8');
const moduleSource=html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
const elements=new Map(),frames=new Map(),flights=[],spoken=[];
let next=0,now=0,resolveReply,requests=0;
function el(id){if(!elements.has(id))elements.set(id,{value:'',hidden:true,style:{setProperty(){}},classList:{toggle(){},add(){},remove(){}},setAttribute(){},replaceChildren(){},append(){},focus(){},addEventListener(){}});return elements.get(id);}
const vector=(x,y,z)=>({x,y,z,clone(){return vector(this.x,this.y,this.z);}});
const camera={position:vector(0,80,620)},controls={target:vector(0,0,0),autoRotate:true};
const graph={camera:()=>camera,controls:()=>controls,cameraPosition(p,t){flights.push(p);Object.assign(camera.position,p);Object.assign(controls.target,t);},linkColor(){return this;},linkWidth(){return this;}};
const context={console,AbortController,performance:{now:()=>now},matchMedia:()=>({matches:false}),
 GRAPH:{nodes:Array.from({length:6},(_,id)=>({id,label:`Note ${id}`,group:'Finance',excerpt:'NOTE TEXT MUST NOT BE SPOKEN',x:id,y:0,z:0})),links:[{source:0,target:1},{source:1,target:2},{source:2,target:3}]},
 document:{getElementById:el,createElement:()=>el(`element-${++next}`)},
 requestAnimationFrame(fn){frames.set(++next,fn);return next;},cancelAnimationFrame(id){frames.delete(id);},setTimeout(){return ++next;},clearTimeout(){},
 fetch(){requests++;return new Promise(resolve=>resolveReply=resolve);},window:{JarvisVoice:{interrupt:()=>false,setThinking(){},speak(text){spoken.push({text,panel:el('detail').hidden,frames:frames.size});}}}};
vm.createContext(context);
vm.runInContext(moduleSource.slice(moduleSource.indexOf('const SETTINGS'),moduleSource.indexOf("$('search').addEventListener"))+moduleSource.slice(moduleSource.indexOf('// Intent is decided')),context);
context.graphDouble=graph;vm.runInContext('graph=graphDouble',context);
function state(){return JSON.parse(vm.runInContext('JSON.stringify({selected,lit:[...highlighted],activeGroup})',context));}
async function answer(question,data){const before=flights.length;const pending=context.ask(question);now+=WAIT_MS;assert.equal(flights.length,before);assert.equal(frames.size,0);assert.equal(controls.autoRotate,false);resolveReply({ok:true,json:async()=>data});await pending;}
(async()=>{
 await answer('What does Menu Pricing say about the bowls?',{answer:'A short summary.',about_notes:true,nodes:[0]});
 assert.equal(state().selected,0);assert.deepEqual(state().lit,[0,1]);assert.equal(el('detail').hidden,false);assert.equal(spoken.at(-1).frames,1);assert.equal(spoken.at(-1).text,'A short summary.');
 now+=FLIGHT_MS;for(const [id,fn] of [...frames]){frames.delete(id);fn(now);}
 const before=flights.length;
 await answer('Compare four notes.',{answer:'A combined summary.',about_notes:true,nodes:[0,1,2,3]});
 assert.equal(flights.length,before);assert.equal(frames.size,0);assert.deepEqual(state().lit,[0,1,2,3]);assert.equal(state().selected,null);assert.equal(el('detail').hidden,true);
 const cluster=state();await answer('Good morning! Tell me a joke.',{answer:'Good morning!',about_notes:false,nodes:[4]});
 assert.deepEqual(state(),cluster);assert.equal(flights.length,before);
 await answer('Unsupported note question',{answer:'Not covered.',about_notes:true,nodes:[]});assert.deepEqual(state(),cluster);
 await answer('Three notes',{answer:'Summary.',about_notes:true,nodes:[2,3,4]});assert.equal(state().selected,2);assert.ok(state().lit.includes(4));assert.equal(frames.size,1);
 await answer('Thanks!',{answer:'You’re welcome.',about_notes:false,nodes:[]});assert.equal(frames.size,0);
 assert.equal(requests,6);assert.ok(spoken.every(s=>!s.text.includes('NOTE TEXT')));
 console.log('SOURCES PASS: delayed response holds camera; single source flies and opens panel before speech; four sources light cluster without flight; small talk preserves view; empty sources hold; three sources retain all citations; new requests cancel flights; one request per turn.');
})().catch(e=>{console.error(e);process.exitCode=1;});
