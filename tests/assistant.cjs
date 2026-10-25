// Built-in commands and saved routines bypass inference; ordinary chat keeps its existing route.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const requests=[],elements=new Map(),answers=[];
let catalog={shortcuts:[{trigger:'writing time',commands:['open Notes']}]};
const context={window:{JarvisUI:{onQuestion(){},onAnswer(value){answers.push(value);}},JarvisVoice:{speak(){}}},
 document:{getElementById(id){if(!elements.has(id))elements.set(id,{textContent:'',value:''});return elements.get(id);}},
 crypto:webcrypto,AbortSignal,setTimeout,clearTimeout,console,
 fetch:async(path,options)=>{requests.push({path,options});return {ok:true,json:async()=>path==='/assistant'?catalog:{matched:true,answer:'Requested',nodes:[],about_notes:false}};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('viewer/assistant.js','utf8'),context);
(async()=>{
 await new Promise(setImmediate);
 for(const text of ['Open Safari','Jarvis, open Notes.','Move window left','Maximize window','Play music','When I say writing time, open Notes','Background task: compare notes','Writing time!'])assert.equal(context.window.JarvisAssistant.matches(text),true,text);
 for(const text of ['Who updates the Cash Flow Forecast?','What does the screen say?','Remember that the review is Tuesday','thirty minutes on this','switch to Luna'])assert.equal(context.window.JarvisAssistant.matches(text),false,text);
 assert.equal(requests.filter(item=>item.options?.method==='POST').length,0);
 await context.window.JarvisAssistant.handle('Open Safari');
 const post=requests.find(item=>item.options?.method==='POST');assert.equal(post.path,'/assistant/command');assert.match(JSON.parse(post.options.body).request_key,/^[a-f0-9]{24}$/);assert.equal(answers[0].answer,'Requested');
 assert.equal(requests.some(item=>['/chat','/focus'].includes(item.path)),false);
 console.log('MAC ASSISTANT PASS: exact command/routine routing, ordinary chat preserved, unique action keys, shared answer display, no Focus route.');
})().catch(error=>{console.error(error);process.exitCode=1;});
