// Exercise the actual posture geometry, not a stubbed classifier.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const c={window:{}};vm.createContext(c);vm.runInContext(fs.readFileSync('viewer/posture.js','utf8'),c);
const create=c.window.JarvisPosture.create;
const face=()=>Array.from({length:478},()=>({x:.5,y:.3,z:0}));
const body=()=>Array.from({length:33},(_,i)=>({x:i===11?.3:.7,y:.6,z:0,visibility:.99}));
const mul=(a,b)=>Array.from({length:16},(_,i)=>{const row=i%4,col=Math.floor(i/4);let n=0;for(let k=0;k<4;k++)n+=a[k*4+row]*b[col*4+k];return n});
function matrix(pitch=0,yaw=0,roll=0){
 const [p,y,r]=[pitch,yaw,roll].map(n=>n*Math.PI/180);
 const rx=[1,0,0,0,0,Math.cos(p),Math.sin(p),0,0,-Math.sin(p),Math.cos(p),0,0,0,0,1];
 const ry=[Math.cos(y),0,-Math.sin(y),0,0,1,0,0,Math.sin(y),0,Math.cos(y),0,0,0,0,1];
 const rz=[Math.cos(r),Math.sin(r),0,0,-Math.sin(r),Math.cos(r),0,0,0,0,1,0,0,0,0,1];
 return {data:mul(mul(rz,ry),rx)};
}
function calibrate(t,p=undefined,base=matrix()){let v;for(let n=0;n<45;n++)v=t.update(face(),p,base,n*80,.75);assert.equal(v.head_ready,true);return v;}
const t=create();calibrate(t); // Shoulders intentionally absent, as in a tight webcam crop.
let v=t.update(face(),undefined,matrix(20),3700,.75);
assert.equal(v.head_down,true);assert.equal(v.shoulders,false);assert.ok(Math.abs(v.pitch-20)<.001);
v=t.update(face(),undefined,matrix(10),3800,.75);assert.equal(v.head_down,true);
v=t.update(face(),undefined,matrix(5),3900,.75);assert.equal(v.head_down,false);
v=t.update(face(),undefined,matrix(0,40),4000,.75);assert.equal(v.head_down,false);
v=t.update(face(),undefined,matrix(-20),4100,.75);assert.equal(v.head_down,false);
const offset=create(),base=matrix(-15,20,12);calibrate(offset,undefined,base);
v=offset.update(face(),undefined,{data:mul(base.data,matrix(18).data)},3700,.75);assert.equal(v.head_down,true);assert.ok(Math.abs(v.pitch-18)<.001);
const slouch=create();assert.equal(calibrate(slouch,body()).body_ready,true);
const lower=face();lower.forEach(p=>p.y+=.1);
v=slouch.update(lower,body(),matrix(),3700,.75);assert.equal(v.slouched,true);assert.equal(v.head_down,false);
const lostShoulders=body();lostShoulders[11].visibility=.1;
v=slouch.update(face(),lostShoulders,matrix(20),3800,.75);assert.equal(v.slouched,false);assert.equal(v.head_down,true);
v=slouch.update(undefined,undefined,undefined,3900,.75);assert.equal(v.present,false);assert.equal(v.head_down,false);
t.reset();v=t.update(face(),undefined,matrix(20),5000,.75);assert.equal(v.head_ready,false);assert.equal(v.head_down,false);
console.log('POSTURE PASS: head-only crop, calibrated camera angle, downward vs upward/yaw, hysteresis, independent shoulder confidence, slouch, tracking loss, recalibration.');
