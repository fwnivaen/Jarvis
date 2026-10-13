// Actual capture and request code; browser doubles, no recording or model calls.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/index.html','utf8');
const src=html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
const elements=new Map(),requests=[],spoken=[],draws=[];
let content='first',resolveReply,thinking=false,ended;
const el=id=>{if(!elements.has(id))elements.set(id,{textContent:'',value:'',classList:{add(){},remove(){}},setAttribute(){},replaceChildren(){},focus(){}});return elements.get(id)};
const track={readyState:'live',muted:false,stop(){this.readyState='ended'},addEventListener(type,fn){ended=fn}};
const stream={active:true,getTracks:()=>[track],getVideoTracks:()=>[track]};
const video={readyState:2,videoWidth:3200,videoHeight:1800,play:async()=>{}};
const ctx={console,AbortController,JSON,Math,Error,screenStream:undefined,
 document:{createElement(type){if(type==='video')return video;assert.equal(type,'canvas');return {width:0,height:0,getContext(){return {drawImage:(...args)=>draws.push(args)}} ,toDataURL(mime,q){assert.equal(mime,'image/jpeg');assert.equal(q,.82);assert.equal(this.width,1600);assert.equal(this.height,900);return 'data:image/jpeg;base64,'+content}}}},
 navigator:{mediaDevices:{getDisplayMedia:async options=>{assert.equal(options.audio,false);return stream}}},
 window:{JarvisVoice:{interrupt:()=>false,setThinking(v){thinking=v},speak(t){spoken.push(t)}}},
 setInterval(){},setTimeout:()=>1,clearTimeout(){},holdCamera(){},showAnswerSources(){},fetch(path,options){if(path==='/model')return Promise.resolve({ok:false});requests.push({path,body:JSON.parse(options.body)});return new Promise(resolve=>resolveReply=resolve)},el};
vm.createContext(ctx);
vm.runInContext(src.slice(0,src.indexOf('const $='))+'\nconst $=el;let busy=false;'+src.slice(src.indexOf('let screenStream='),src.indexOf('async function birthCapture'))+src.slice(src.indexOf('async function ask')),ctx);
(async()=>{
 await el('screen').onclick();assert.equal(draws.length,0);assert.match(el('screen-indicator').textContent,/LIVE/);
 content='at-question';const first=ctx.ask('what am I looking at');assert.equal(requests[0].path,'/see');assert.equal(requests[0].body.image,'at-question');assert.equal(requests[0].body.media_type,'image/jpeg');assert.equal(draws.length,1);assert.equal(thinking,true);
 resolveReply({ok:true,json:async()=>({answer:'Screen answer, sir.',nodes:[],about_notes:false})});await first;assert.equal(thinking,false);assert.equal(spoken.at(-1),'Screen answer, sir.');
 content='second-frame';const second=ctx.ask('and now?');assert.equal(requests[1].body.image,'second-frame');assert.equal(draws.length,2);
 ended();assert.match(el('screen-indicator').textContent,/ENDED/);resolveReply({ok:true,json:async()=>({answer:'STALE ANSWER',nodes:[]})});await second;assert.match(spoken.at(-1),/ended or changed/);assert.ok(!spoken.includes('STALE ANSWER'));
 await ctx.ask('what am I looking at');assert.equal(requests.length,2);assert.equal(draws.length,2);assert.match(spoken.at(-1),/share has ended/);
 el('screen-notes').onclick();const normal=ctx.ask('Hello');assert.equal(requests.at(-1).path,'/chat');resolveReply({ok:true,json:async()=>({answer:'Hello, sir.',nodes:[]})});await normal;
 track.readyState='live';await el('screen').onclick();track.muted=true;await ctx.ask('look');assert.equal(requests.length,3);assert.match(spoken.at(-1),/not available/);
 console.log('SCREEN PASS: no startup frame, fresh per-question JPEG, 1600px limit, voice/thinking path, ended-share refusal, stale reply discarded, notes restored, muted frame refused.');
})().catch(e=>{console.error(e);process.exitCode=1});
