// Pure local landmark interpretation. No camera, network, storage, or speech.
(() => {
 const CALIBRATION_SAMPLES=20, CALIBRATION_MS=1400, STABLE_DEG=5, MAX_YAW_DEG=55;
 const HEAD_DOWN_DEG=12, HEAD_RELEASE_DEG=8, SLOUCH_DROP=.12, SLOUCH_RELEASE=.08;
 const MIN_VISIBILITY=.6, MIN_SHOULDER_WIDTH=.12, RAD_TO_DEG=180/Math.PI;
 const MIN_FACE_POINTS=264;
 const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
 const unit=v=>{const length=Math.hypot(...v);return length>Number.EPSILON?v.map(n=>n/length):null;};
 const median=values=>{const a=[...values].sort((x,y)=>x-y);return a[Math.floor(a.length/2)];};
 function axes(matrix){
  const d=matrix?.data;
  // MediaPipe face geometry matrices use column-major packing and +Y up.
  if(!d || d.length!==16 || !Array.from(d).every(Number.isFinite))return null;
  const x=unit([d[0],d[1],d[2]]),y=unit([d[4],d[5],d[6]]),z=unit([d[8],d[9],d[10]]);
  return x&&y&&z?{x,y,z}:null;
 }
 function angles(base,current){return {pitch:Math.atan2(-dot(base.y,current.z),dot(base.z,current.z))*RAD_TO_DEG,
  yaw:Math.atan2(dot(base.x,current.z),dot(base.z,current.z))*RAD_TO_DEG};}
 function visible(p){return !!p&&Number.isFinite(p.x)&&Number.isFinite(p.y)&&p.x>=0&&p.x<=1&&p.y>=0&&p.y<=1&&(p.visibility??1)>=MIN_VISIBILITY;}
 function create(){
  let baseline=null,bodyBaseline=null,headSamples=[],bodySamples=[],headDown=false,slouched=false,threshold=HEAD_DOWN_DEG;
  function reset(){baseline=bodyBaseline=null;headSamples=[];bodySamples=[];headDown=slouched=false;}
  function update(f,p,m,now,aspect=1){
   const face=!!(f&&f.length>=MIN_FACE_POINTS),shoulders=visible(p?.[11])&&visible(p?.[12]);
   const current=face?axes(m):null;
   const present=face||shoulders;
   let pitch=null,neck=null;
   if(current){
    if(!baseline){
     if(headSamples.length){const a=angles(headSamples[0].axes,current);if(Math.abs(a.pitch)>STABLE_DEG||Math.abs(a.yaw)>STABLE_DEG)headSamples=[];}
     headSamples.push({axes:current,time:now});
     if(headSamples.length>=CALIBRATION_SAMPLES&&now-headSamples[0].time>=CALIBRATION_MS){
      // Pick a real orientation near the median to preserve its orthonormal axes.
      const origin=headSamples[0].axes;
      const center=median(headSamples.map(v=>angles(origin,v.axes).pitch));
      baseline=headSamples.reduce((best,v)=>Math.abs(angles(origin,v.axes).pitch-center)<Math.abs(angles(origin,best.axes).pitch-center)?v:best).axes;
     }
    }
    if(baseline){
     const a=angles(baseline,current);
     if(Math.abs(a.yaw)<=MAX_YAW_DEG){pitch=a.pitch;headDown=pitch>=(headDown?Math.min(HEAD_RELEASE_DEG,threshold):threshold);}
     else headDown=false;
    }
   }else{headDown=false;headSamples=[];}
   // Slouch requires shoulders. Head rotation never does.
   if(face&&shoulders){
    const width=Math.hypot(p[11].x-p[12].x,(p[11].y-p[12].y)*aspect);
    if(width>=MIN_SHOULDER_WIDTH){
     neck=(((p[11].y+p[12].y)-(f[33].y+f[263].y))/2)*aspect/width;
     if(baseline&&pitch!==null&&Math.abs(pitch)<HEAD_RELEASE_DEG&&bodyBaseline===null){
      if(bodySamples.length&&Math.abs(neck-bodySamples[0].neck)>SLOUCH_RELEASE)bodySamples=[];
      bodySamples.push({neck,time:now});
      if(bodySamples.length>=CALIBRATION_SAMPLES&&now-bodySamples[0].time>=CALIBRATION_MS)bodyBaseline=median(bodySamples.map(v=>v.neck));
     }
    }
   }
   slouched=neck!==null&&bodyBaseline!==null&&bodyBaseline-neck>=(slouched?SLOUCH_RELEASE:SLOUCH_DROP);
   if(neck===null)bodySamples=[];
   return {present,head_down:headDown,slouched,face,shoulders,head_ready:!!baseline,body_ready:bodyBaseline!==null,
    pitch,drop:neck!==null&&bodyBaseline!==null?bodyBaseline-neck:null,
    calibration:Math.min(1,headSamples.length/CALIBRATION_SAMPLES,headSamples.length?(now-headSamples[0].time)/CALIBRATION_MS:0)};
  }
  return {update,reset,setThreshold(value){threshold=Number(value)||HEAD_DOWN_DEG;}};
 }
 window.JarvisPosture={create};
})();
