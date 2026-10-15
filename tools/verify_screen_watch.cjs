// Live acceptance with a synthetic display: two real vision calls, no personal screen capture.
// Requires Playwright available in NODE_PATH. Every test tab is muted.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
let browser;
(async()=>{
 browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const page=await browser.newPage();const calls=[],errors=[];let shares=0;
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(new URL(r.url()).pathname==='/see')calls.push(JSON.parse(r.postData()))});
 await page.addInitScript(()=>{
  window.testShareCount=0;window.testSurface='monitor';
  navigator.mediaDevices.getDisplayMedia=async options=>{
   window.testOptions=options;window.testShareCount++;
   const c=document.createElement('canvas');c.width=960;c.height=540;
   const g=c.getContext('2d');g.fillStyle='white';g.fillRect(0,0,960,540);g.fillStyle='black';g.font='30px sans-serif';g.fillText('TODO: Draft the project introduction',30,100);g.fillText('Next: write one sentence describing the goal.',30,170);
   const s=c.captureStream(1);const t=s.getVideoTracks()[0];t.getSettings=()=>({displaySurface:window.testSurface});
   window.testCanvas=c;window.testStream=s;return s;
  };
 });
 await page.goto('http://127.0.0.1:4700/?mute=1');
 await page.waitForFunction(()=>Boolean(window.JarvisScreen));
 let remaining=(await (await page.request.get('http://127.0.0.1:4700/focus')).json()).snooze_s;
 if(remaining)console.log('Browser: honoring existing relief before starting timed acceptance.');
 while(remaining>0){await new Promise(r=>setTimeout(r,1000));remaining=(await (await page.request.get('http://127.0.0.1:4700/focus')).json()).snooze_s;}
 const nudgeReply=page.waitForResponse(r=>r.url().endsWith('/see'),{timeout:210000});
 await page.click('#watch');await page.waitForFunction(()=>document.querySelector('#watch').textContent==='Stop watching');
 assert.equal(calls.length,0);assert.equal(await page.evaluate(()=>window.testOptions.video.displaySurface),'monitor');
 console.log('Browser: entire-screen request and local watch started, no frame sent.');
 const start=Date.now();
 while(calls.length===0 && Date.now()-start<75000)await new Promise(r=>setTimeout(r,1000));
 assert.equal(calls.length,1);console.log('Browser: one synthetic frame sent after actual 60-second threshold.');
 assert.ok((await nudgeReply).ok());
 await page.fill('#question','what do you think of this?');
 const reply=page.waitForResponse(r=>r.url().endsWith('/see'),{timeout:130000});await page.click('#send');assert.ok((await reply).ok());
 await page.waitForFunction(()=>!document.querySelector('#send').disabled);
 assert.equal(calls.length,2);assert.equal(await page.evaluate(()=>window.testShareCount),1);
 assert.match(await page.textContent('#answer'),/./);console.log('Browser: screen question answered using the same share.');
 await page.fill('#question','gimme 3 minutes');await page.click('#send');await page.waitForFunction(()=>document.querySelector('#answer').textContent.includes('Three minutes'));
 const state=await page.request.get('http://127.0.0.1:4700/focus');assert.ok((await state.json()).snooze_s>=179);
 assert.equal(await page.evaluate(()=>Boolean(window.JarvisVoice.isOccupied())),true);
 await page.click('#watch');
 await page.click('#screen');
 await page.evaluate(()=>{window.testSurface='browser'});await page.click('#watch');
 await page.waitForFunction(()=>document.querySelector('#watch-status').textContent.includes('single tab'));assert.match(await page.textContent('#watch-status'),/single tab/);assert.equal(await page.getAttribute('#watch','aria-pressed'),'false');
 assert.equal(calls.length,2);console.log('Browser: global relief active; tab-share monitoring refused; mute=1 throughout.');
 assert.deepEqual(errors,[]);await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{await browser?.close();});
