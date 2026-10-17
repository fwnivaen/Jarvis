/* Batched light rendering on the existing ForceGraph3D scene and controls. */
const GALAXY = Object.freeze({cache: 'jarvis.galaxy.layout.hud.v3', workerTimeout: 1600,
  layoutMs: 300, captureSettleMs: 2000, idleSettleMs: 240, hoverMs: 180,
  edgeSegments: 22, denseEdgeSegments: 6, denseEdgeThreshold: 10000, curvature: .08, edgeAlpha: .085, crossAlpha: 1,
  revealMs: 300, staggerMs: 60, photonSeconds: 3, photonWidth: .026,
  depth: 18, radius: 190, spreadX: 75, spreadY: 48, opticalY: 0,
  starBase: 22, starTier: 3.5, selectedScale: 1.65, hoverScale: 1.15,
  dim: .25, groupPreview: .4, editedWindow: 172800, dustCount: 1100,
  dustRadius: 1500, dustOpacity: .25, dustSize: 1.25, hitRadius: 14,
  hitCell: 32, clickDistance: 5, labelGap: 38, labelMinZoom: .45,
  labelMaxZoom: 2.8, tooltipWidth: 260, tooltipGap: 18, margin: 16,
  zoomStep: 1.2, zoomMs: 600, minDistance: 145, maxDistance: 1500,
  categoryLightness: .73, categoryChroma: .10, fullSizeNodes: 800, minimumDustScale: .28, detachFrames:4,denseNodes:5000,densePixelRatio:1.25,projectionIntervalMs:33,
  orbitLimit: Math.PI / 10, performanceSamples: 180, reportMs: 1000,
  bootDelay:1000, clusterStagger:.06, clusterReveal:.6, maxClusterDelay:.6, nebulaWidth:250, nebulaHeight:150, nebulaCap:32, nebulaOpacity:.065, nebulaDimOpacity:.015, nebulaLightOpacity:.018, nebulaDepth:10, dustParallaxScale:.35,
  parallax:6, easeIterations:14, dustNearFraction:.4, dustNearScale:.6,
  anchors: {finance: [-225, 90], strategy: [25, 165], marketing: [245, 85],
    operations: [175, -125], people: [-195, -145], team: [-195, -145], sales: [260, -135], captures: [25, -190]},
  palette: {finance: '#A08BEA', marketing: '#6F93EE', operations: '#E9A75C',
    sales: '#E2738F', strategy: '#B8C46A', people: '#4FC7A6', team: '#4FC7A6', captures: '#B9BEC4'}});
const STAR_VERTEX = `
attribute vec3 aCenter; attribute vec3 aTint; attribute float aSize;
uniform float uBoot;uniform float uReduced;attribute float aCluster;
attribute float aOpacity; attribute float aSelected; attribute float aWarm; attribute float aPhase;
varying vec2 vUv; varying vec3 vTint; varying float vOpacity; varying float vSelected;
varying float vWarm; varying float vPhase; varying float vRadius;varying float vReveal;
void main(){vUv=uv;vTint=aTint;vOpacity=aOpacity;vSelected=aSelected;vWarm=aWarm;vPhase=aPhase;vRadius=length(aCenter.xy)/350.;
float growth=uReduced>.5?1.:1.-pow(1.-clamp((uBoot-aCluster)/.6,0.,1.),3.);vReveal=growth;
vec3 point=aCenter;point.xy*=growth;vec4 center=modelViewMatrix*vec4(point,1.);center.xy+=position.xy*aSize;
gl_Position=projectionMatrix*center;}`;
const STAR_FRAGMENT = `
uniform float uTime;uniform float uLight;uniform float uReduced; varying vec2 vUv; varying vec3 vTint; varying float vOpacity;
varying float vSelected; varying float vWarm; varying float vPhase; varying float vRadius;varying float vReveal;
void main(){vec2 p=(vUv-.5)*2.;float r=length(p);if(r>1.)discard;
float halo=exp(-r*r*4.8)*mix(.28,.15,uLight);float core=exp(-r*r*65.);
float cross=pow(max(0.,1.-min(abs(p.x),abs(p.y))*36.),5.)*exp(-r*5.)*vSelected*.26;
float shimmer=1.+sin(uTime*(.34+vPhase*.055)+vPhase)*.08*(1.-uReduced);
vec3 hot=mix(vec3(.94,.98,1.),vec3(1.,.9,.74),vWarm*.25);
vec3 ink=mix(vTint*.34,vec3(.035,.05,.06),.55);
vec3 tint=mix(vTint,ink,uLight);hot=mix(hot,ink*.58,uLight);
float energy=halo+core+cross;
vec3 light=(tint*(halo+cross)+hot*core)/max(energy,.0001);
gl_FragColor=vec4(light*shimmer,clamp(energy*vOpacity,0.,1.)*vReveal);
#include <colorspace_fragment>
}`;
const EDGE_VERTEX = `
attribute vec3 aStart;attribute vec3 aEnd;attribute vec3 aBend;attribute vec3 aTint;
attribute float aActive;attribute float aDelay;attribute float aReverse;attribute float aAlpha;
uniform float uBoot;uniform vec2 uViewport;varying float vT;varying vec3 vTint;varying float vActive;
varying float vDelay;varying float vAlpha;
vec3 curve(float t){return (1.-t)*(1.-t)*aStart+2.*(1.-t)*t*aBend+t*t*aEnd;}
void main(){float t=position.x+.5;vec3 point=curve(t);point.xy*=smoothstep(0.,.8,uBoot);vec4 clip=projectionMatrix*modelViewMatrix*vec4(point,1.);
vec3 tangent=2.*(1.-t)*(aBend-aStart)+2.*t*(aEnd-aBend);
vec4 delta=projectionMatrix*modelViewMatrix*vec4(tangent,0.);
vec2 direction=normalize((delta.xy*clip.w-clip.xy*delta.w)*uViewport+vec2(.00001));
vec2 normal=vec2(-direction.y,direction.x);float width=mix(.85,1.35,aActive);
clip.xy+=normal*position.y*width/uViewport*2.*clip.w;
gl_Position=clip;vT=mix(t,1.-t,aReverse);vTint=aTint;vActive=aActive;vDelay=aDelay;vAlpha=aAlpha;}`;
const EDGE_FRAGMENT = `
uniform float uTime;uniform float uRevealStart;uniform float uReduced;uniform vec3 uAccent;
uniform float uBoot;uniform float uRevealSeconds;uniform float uPhotonSeconds;uniform float uPhotonWidth;
varying float vT;varying vec3 vTint;varying float vActive;varying float vDelay;varying float vAlpha;
void main(){float reveal=uReduced>.5?1.:clamp((uTime-uRevealStart-vDelay)/uRevealSeconds,0.,1.);
if(vActive>.5&&vT>reveal)discard;
float travel=fract((uTime-uRevealStart)/uPhotonSeconds-vDelay);
float photon=(1.-smoothstep(0.,uPhotonWidth,abs(vT-travel)))*vActive*step(1.,reveal)*(1.-uReduced);
float alpha=mix(vAlpha,.56,vActive)+photon*.35;
gl_FragColor=vec4(mix(mix(vTint,vec3(.55,.68,.8),.45),uAccent,vActive)+photon*.25,alpha*smoothstep(0.,.8,uBoot));
#include <colorspace_fragment>
}`;
const NEBULA_VERTEX = `
attribute vec3 aCenter;attribute vec3 aTint;attribute float aOpacity;attribute float aDelay;
uniform float uBoot;varying vec2 vUv;varying vec3 vTint;varying float vOpacity;
void main(){float reveal=smoothstep(aDelay,aDelay+.6,uBoot);vec3 p=aCenter;p.xy*=reveal;
vec4 center=modelViewMatrix*vec4(p,1.);center.xy+=position.xy*vec2(${GALAXY.nebulaWidth.toFixed(1)},${GALAXY.nebulaHeight.toFixed(1)});
gl_Position=projectionMatrix*center;vUv=uv;vTint=aTint;vOpacity=aOpacity*reveal;}`;
const NEBULA_FRAGMENT = `
varying vec2 vUv;varying vec3 vTint;varying float vOpacity;
void main(){float r=length((vUv-.5)*2.);if(r>1.)discard;gl_FragColor=vec4(vTint,exp(-r*r*5.)*(1.-smoothstep(.3,1.,r))*vOpacity);
#include <colorspace_fragment>
}
`;
// Numerically evaluate the same cubic-bezier(.22,1,.36,1) used by the chrome.
export function hudEase(value){if(value<=0)return 0;if(value>=1)return 1;let low=0,high=1,t=value;for(let i=0;i<GALAXY.easeIterations;i++){t=(low+high)/2;const x=3*(1-t)*(1-t)*t*.22+3*(1-t)*t*t*.36+t*t*t;if(x<value)low=t;else high=t;}return 1-Math.pow(1-t,3);}
function hash(text) { let value=2166136261; for(let i=0;i<text.length;i++)value=Math.imul(value^text.charCodeAt(i),16777619); return value>>>0; }
function identity(node) { return `${node.group}\u0000${node.label}`; }
function endId(value) { return typeof value==='object'?value.id:value; }
function key(link) { return `${Math.min(endId(link.source),endId(link.target))}:${Math.max(endId(link.source),endId(link.target))}`; }
export function categoryColor(group) {
  const known=GALAXY.palette[String(group).toLowerCase()];if(known)return known;
  // Convert a seeded OKLCH color to sRGB for Three.Color and DOM consumers alike.
  const hue=hash(String(group))%360*Math.PI/180,L=GALAXY.categoryLightness;
  const a=GALAXY.categoryChroma*Math.cos(hue),b=GALAXY.categoryChroma*Math.sin(hue);
  const l=Math.pow(L+.3963377774*a+.2158037573*b,3),m=Math.pow(L-.1055613458*a-.0638541728*b,3),s=Math.pow(L-.0894841775*a-1.291485548*b,3);
  const channels=[4.0767416621*l-3.3077115913*m+.2309699292*s,-1.2684380046*l+2.6097574011*m-.3413193965*s,-.0041960863*l-.7034186147*m+1.707614701*s];
  return '#'+channels.map(value=>Math.round(Math.max(0,Math.min(1,value<=.0031308?12.92*value:1.055*Math.pow(value,1/2.4)-.055))*255).toString(16).padStart(2,'0')).join('');
}
function cacheRead(storageKey=GALAXY.cache) { try{const value=JSON.parse(localStorage.getItem(storageKey)||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}catch{return {};} }
export function seedPositions(nodes,{storageKey=GALAXY.cache}={}) {
  const cached=cacheRead(storageKey),categories=[...new Set(nodes.map(node=>node.group))].sort();
  nodes.forEach((node,index)=>{
    const value=hash(identity(node)),phase=value/4294967296*Math.PI*2;
    const known=GALAXY.anchors[node.group.toLowerCase()],angle=categories.indexOf(node.group)*2.3999632297;
    const center=known||[Math.cos(angle)*GALAXY.radius,Math.sin(angle)*GALAXY.radius];
    const spread=Math.sqrt(((value>>>8)%997+1)/998),saved=cached[identity(node)];
    const point=saved&&['x','y','z'].every(axis=>Number.isFinite(saved[axis]))?saved:
      {x:center[0]+Math.cos(phase)*GALAXY.spreadX*spread,y:center[1]+Math.sin(phase)*GALAXY.spreadY*spread,
        z:((value%3)-1)*GALAXY.depth+Math.sin(index*2.3999632297)*4};
    for(const axis of ['x','y','z'])node[axis]=node['f'+axis]=point[axis];
  });
}
export function createGalaxy({graph,THREE,getData,stage,labels,onSelect,onClear,onGroup,flyCamera,reducedMotion,initialDistance,storageKey=GALAXY.cache}) {
  const camera=graph.camera(),renderer=graph.renderer(),controls=graph.controls(),scene=graph.scene();
  const host=stage.querySelector('#graph'),projected=new Map(),spatial=new Map(),labelElements=new Map();
  const stats={frames:0,drawCalls:0,triangles:0,hoverMs:0,maxHoverMs:0,frameMs:0,p95FrameMs:0,
    layoutWorker:false,layoutPersisted:false,idle:true,nodes:0,links:0,firstFrameMs:null,bufferMs:0,projectionMs:0,renderMs:0};
  const originalRender=renderer.render;renderer.render=function(...args){const started=performance.now();try{return originalRender.apply(this,args);}finally{stats.renderMs=performance.now()-started;}};
  const frameSamples=[],started=performance.now(),vector=new THREE.Vector3(),colors=new Map();
  const reserveIds=['chat-form','jarvis-orb-host','groups','detail','preview'];
  let nodes=[],links=[],nodeRef=null,linkRef=null,stars=null,edges=null,nebula=null,nebulaAttributes=null,nebulaGroups=[],attributes=null,edgeAttributes=null,detachRemaining=0,degrees=new Uint32Array(0),baseSizes=new Float32Array(0),edgeKeys=[];
  const originalPixelRatio=renderer.getPixelRatio();
  let hoverNeighbors=new Set(),hoverLinks=new Set(),parallaxX=0,parallaxY=0;
  let selected=null,highlighted=new Set(),activeLinks=new Set(),activeGroup=null,preview=null,hovered=null;
  let frame=null,awakeUntil=0,lastFrame=0,lastReport=0,revealStart=0,disposed=false,layoutRevision=0,resuming=false,ticking=false;
  let worker=null,workerTimer=null,layoutTimer=null,layoutMotion=null,pointerDown=null,pickPending=null;
  let projectionDirty=true,interactionSource='system',projectedWidth=0,projectedHeight=0,activeSignature='',continuous=false,bootStart=0,bootDuration=0,lastProjection=0,spatialColumns=0;
  const tooltip=document.createElement('div');tooltip.className='galaxy-tooltip';tooltip.setAttribute('role','tooltip');tooltip.hidden=true;
  const tooltipGroup=document.createElement('div'),tooltipTitle=document.createElement('strong');
  tooltipGroup.className='eyebrow';tooltip.append(tooltipGroup,tooltipTitle);stage.append(tooltip);
  const rootStyle=()=>getComputedStyle(document.documentElement);
  const accent=()=>new THREE.Color(rootStyle().getPropertyValue('--accent').trim()||'#55DBC9');
  const lightMode=()=>document.documentElement.dataset.theme==='light';
  const starMaterial=new THREE.ShaderMaterial({vertexShader:STAR_VERTEX,fragmentShader:STAR_FRAGMENT,
    uniforms:{uTime:{value:0},uLight:{value:lightMode()?1:0},uBoot:{value:1000},uReduced:{value:reducedMotion?1:0}},transparent:true,depthWrite:false,
    blending:lightMode()?THREE.NormalBlending:THREE.AdditiveBlending});
  const edgeMaterial=new THREE.ShaderMaterial({vertexShader:EDGE_VERTEX,fragmentShader:EDGE_FRAGMENT,
    uniforms:{uTime:{value:0},uRevealStart:{value:0},uReduced:{value:reducedMotion?1:0},
      uAccent:{value:accent()},uViewport:{value:new THREE.Vector2(1,1)},uRevealSeconds:{value:GALAXY.revealMs/1000},
      uBoot:starMaterial.uniforms.uBoot,uPhotonSeconds:{value:GALAXY.photonSeconds},uPhotonWidth:{value:GALAXY.photonWidth}},transparent:true,depthWrite:false});
  const nebulaMaterial=new THREE.ShaderMaterial({vertexShader:NEBULA_VERTEX,fragmentShader:NEBULA_FRAGMENT,
    uniforms:{uBoot:starMaterial.uniforms.uBoot},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending});
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent('jarvis:'+name,{detail}));
  function color(group){if(!colors.has(group))colors.set(group,new THREE.Color(categoryColor(group)));return colors.get(group);}
  function attribute(geometry,name,size,count){const attr=new THREE.InstancedBufferAttribute(new Float32Array(size*count),size);attr.setUsage(THREE.DynamicDrawUsage);geometry.setAttribute(name,attr);return attr;}
  function geometryFrom(plane,count){const geometry=new THREE.InstancedBufferGeometry();geometry.index=plane.index;geometry.attributes.position=plane.attributes.position;geometry.attributes.uv=plane.attributes.uv;geometry.instanceCount=count;return geometry;}
  function build(){
    const data=getData();nodes=data.nodes;links=data.links;nodeRef=nodes;linkRef=links;detachRemaining=GALAXY.detachFrames;
    renderer.setPixelRatio(nodes.length>=GALAXY.denseNodes?Math.min(originalPixelRatio,GALAXY.densePixelRatio):originalPixelRatio);
    if(stars){scene.remove(stars);stars.geometry.dispose();}
    if(edges){scene.remove(edges);edges.geometry.dispose();}
    if(nebula){scene.remove(nebula);nebula.geometry.dispose();}
    const starPlane=new THREE.PlaneGeometry(1,1),starGeometry=geometryFrom(starPlane,nodes.length);
    attributes={center:attribute(starGeometry,'aCenter',3,nodes.length),tint:attribute(starGeometry,'aTint',3,nodes.length),
      size:attribute(starGeometry,'aSize',1,nodes.length),opacity:attribute(starGeometry,'aOpacity',1,nodes.length),
      selected:attribute(starGeometry,'aSelected',1,nodes.length),warm:attribute(starGeometry,'aWarm',1,nodes.length),phase:attribute(starGeometry,'aPhase',1,nodes.length),cluster:attribute(starGeometry,'aCluster',1,nodes.length)};
    stars=new THREE.Mesh(starGeometry,starMaterial);stars.frustumCulled=false;stars.renderOrder=2;scene.add(stars);
    const edgePlane=new THREE.PlaneGeometry(1,1,links.length>=GALAXY.denseEdgeThreshold?GALAXY.denseEdgeSegments:GALAXY.edgeSegments,1),edgeGeometry=geometryFrom(edgePlane,links.length);
    edgeAttributes={start:attribute(edgeGeometry,'aStart',3,links.length),end:attribute(edgeGeometry,'aEnd',3,links.length),
      bend:attribute(edgeGeometry,'aBend',3,links.length),tint:attribute(edgeGeometry,'aTint',3,links.length),
      active:attribute(edgeGeometry,'aActive',1,links.length),delay:attribute(edgeGeometry,'aDelay',1,links.length),
      reverse:attribute(edgeGeometry,'aReverse',1,links.length),alpha:attribute(edgeGeometry,'aAlpha',1,links.length)};
    edges=new THREE.Mesh(edgeGeometry,edgeMaterial);edges.frustumCulled=false;edges.renderOrder=1;scene.add(edges);
    stats.nodes=nodes.length;stats.links=links.length;degrees=new Uint32Array(nodes.length);baseSizes=new Float32Array(nodes.length);edgeKeys=links.map(key);for(const link of links){degrees[endId(link.source)]++;degrees[endId(link.target)]++;}
    for(const element of labelElements.values())element.remove();labelElements.clear();
    for(const group of [...new Set(nodes.map(node=>node.group))]){
      if(!labels)break;const element=document.createElement('span');element.className='constellation-label';
      element.textContent=group.toUpperCase();element.style.setProperty('--category-color',categoryColor(group));
      labels.append(element);labelElements.set(group,element);
    }
    nebulaGroups=[...labelElements.keys()].slice(0,GALAXY.nebulaCap);
    const nebulaPlane=new THREE.PlaneGeometry(1,1),nebulaGeometry=geometryFrom(nebulaPlane,nebulaGroups.length);
    nebulaAttributes={center:attribute(nebulaGeometry,'aCenter',3,nebulaGroups.length),tint:attribute(nebulaGeometry,'aTint',3,nebulaGroups.length),opacity:attribute(nebulaGeometry,'aOpacity',1,nebulaGroups.length),delay:attribute(nebulaGeometry,'aDelay',1,nebulaGroups.length)};
    nebula=new THREE.Mesh(nebulaGeometry,nebulaMaterial);nebula.frustumCulled=false;nebula.renderOrder=0;scene.add(nebula);
    projected.clear();projectionDirty=true;updateBuffers(true);
  }
  function updateBuffers(positionsChanged=false){const bufferStarted=performance.now();
    const now=Date.now()/1000,centers=new Map(),categoryIndexes=new Map([...labelElements.keys()].map((group,index)=>[group,index]));
    nodes.forEach((node,index)=>{
      if(positionsChanged){attributes.center.setXYZ(index,node.x||0,node.y||0,node.z||0);const tint=color(node.group);attributes.tint.setXYZ(index,tint.r,tint.g,tint.b);}
      const tier=Math.min(3,Math.sqrt(degrees[node.id])*.55),pinned=Boolean(window.JarvisUI?.isPinned?.(node));
      const recent=Number.isFinite(node.edited_at)&&now-node.edited_at>=0&&now-node.edited_at<GALAXY.editedWindow;
      const scale=node.__threeObj?.scale?.x||1,selectedScale=node.id===selected?GALAXY.selectedScale:1;
      const densityScale=node.id===selected||hovered===node.id||pinned?1:Math.max(GALAXY.minimumDustScale,Math.min(1,Math.sqrt(GALAXY.fullSizeNodes/Math.max(1,nodes.length))));
      baseSizes[index]=(GALAXY.starBase+(tier+(pinned?1:0)+(recent ? .5 : 0))*GALAXY.starTier)*densityScale;attributes.size.setX(index,baseSizes[index]*Math.max(scale,selectedScale)*(hovered===node.id?GALAXY.hoverScale:1));
      let opacity=(!highlighted.size||highlighted.has(node.id))&&(!activeGroup||node.group===activeGroup)?1:GALAXY.dim;
      if(hovered!==null&&!hoverNeighbors.has(node.id))opacity*=GALAXY.dim;
      if(preview&&preview!==node.group)opacity*=1-GALAXY.groupPreview;
      attributes.opacity.setX(index,opacity);attributes.selected.setX(index,node.id===selected?1:0);
      if(positionsChanged){attributes.cluster.setX(index,Math.min(GALAXY.maxClusterDelay,(categoryIndexes.get(node.group)||0)*GALAXY.clusterStagger));attributes.warm.setX(index,recent?1:0);attributes.phase.setX(index,hash(identity(node))/4294967296*Math.PI*2);}
      if(!centers.has(node.group))centers.set(node.group,{x:0,y:0,z:0,count:0});const center=centers.get(node.group);center.x+=node.x||0;center.y+=node.y||0;center.z+=node.z||0;center.count++;
    });
    nebulaGroups.forEach((group,index)=>{const center=centers.get(group),tint=color(group);if(!center)return;nebulaAttributes.center.setXYZ(index,center.x/center.count,center.y/center.count,center.z/center.count-GALAXY.nebulaDepth);nebulaAttributes.tint.setXYZ(index,tint.r,tint.g,tint.b);const dimmed=(activeGroup&&activeGroup!==group)||(hovered!==null&&nodes[hovered]?.group!==group);nebulaAttributes.opacity.setX(index,lightMode()?GALAXY.nebulaLightOpacity:dimmed?GALAXY.nebulaDimOpacity:GALAXY.nebulaOpacity);nebulaAttributes.delay.setX(index,Math.min(GALAXY.maxClusterDelay,index*GALAXY.clusterStagger));});
    for(const attr of Object.values(nebulaAttributes))attr.needsUpdate=true;
    let activeIndex=0;
    links.forEach((link,index)=>{
      const start=nodes[endId(link.source)],end=nodes[endId(link.target)];if(!start||!end)return;
      if(positionsChanged){const dx=end.x-start.x,dy=end.y-start.y,length=Math.hypot(dx,dy)||1;
      edgeAttributes.start.setXYZ(index,start.x,start.y,start.z);edgeAttributes.end.setXYZ(index,end.x,end.y,end.z);
      edgeAttributes.bend.setXYZ(index,(start.x+end.x)/2-dy*GALAXY.curvature,(start.y+end.y)/2+dx*GALAXY.curvature,(start.z+end.z)/2+Math.min(length*.04,GALAXY.depth));
      const tint=color(start.group);edgeAttributes.tint.setXYZ(index,tint.r,tint.g,tint.b);}
      const active=hovered!==null?hoverLinks.has(edgeKeys[index]):activeLinks.has(edgeKeys[index]);
      edgeAttributes.active.setX(index,active?1:0);edgeAttributes.delay.setX(index,active?activeIndex++*GALAXY.staggerMs/1000:0);
      edgeAttributes.reverse.setX(index,end.id===selected?1:0);
      edgeAttributes.alpha.setX(index,GALAXY.edgeAlpha*(start.group===end.group?1:GALAXY.crossAlpha)*
        (highlighted.size&&(!highlighted.has(start.id)||!highlighted.has(end.id))?GALAXY.dim:1)*(hovered!==null&&!hoverLinks.has(edgeKeys[index])?GALAXY.dim:1));
    });
    for(const attr of Object.values(attributes))attr.needsUpdate=true;for(const attr of Object.values(edgeAttributes))attr.needsUpdate=true;stats.bufferMs=performance.now()-bufferStarted;
  }
  function project(node,output={},width=stage.clientWidth,height=stage.clientHeight){if(!node)return null;vector.set(node.x||0,node.y||0,node.z||0).project(camera);output.x=(vector.x+1)*width/2;output.y=(1-vector.y)*height/2;output.visible=vector.z>-1&&vector.z<1;return output;}
  function reserved(){const bounds=stage.getBoundingClientRect();return reserveIds.map(id=>document.getElementById(id)).filter(element=>element&&!element.hidden&&element.getClientRects().length).map(element=>{const r=element.getBoundingClientRect();return {left:r.left-bounds.left,top:r.top-bounds.top,right:r.right-bounds.left,bottom:r.bottom-bounds.top};});}
  function overlaps(a,b){return a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;}
  function placeLabels(){const projectionStarted=performance.now();
    projectedWidth=stage.clientWidth;projectedHeight=stage.clientHeight;
    const columns=Math.ceil(projectedWidth/GALAXY.hitCell)+2;if(columns!==spatialColumns){spatial.clear();spatialColumns=columns;}else for(const cell of spatial.values())cell.length=0;const centers=new Map(),occupied=reserved();
    for(const node of nodes){const point=project(node,projected.get(node.id)||{node},projectedWidth,projectedHeight);projected.set(node.id,point);if(!point.visible)continue;
      if(point.x>=-GALAXY.hitRadius&&point.x<=projectedWidth+GALAXY.hitRadius&&point.y>=-GALAXY.hitRadius&&point.y<=projectedHeight+GALAXY.hitRadius){
        const cell=Math.floor(point.x/GALAXY.hitCell)+1+(Math.floor(point.y/GALAXY.hitCell)+1)*spatialColumns;
        if(!spatial.has(cell))spatial.set(cell,[]);spatial.get(cell).push(point);
      }
      if(!centers.has(node.group))centers.set(node.group,{x:0,y:0,count:0});const c=centers.get(node.group);c.x+=point.x;c.y+=point.y;c.count++;
    }
    const zoom=initialDistance/camera.position.distanceTo(controls.target);
    for(const [group,element] of labelElements){const c=centers.get(group);let hidden=!c||zoom<GALAXY.labelMinZoom||zoom>GALAXY.labelMaxZoom;
      if(!hidden){const width=element.offsetWidth||group.length*8,x=c.x/c.count-width/2,y=c.y/c.count-GALAXY.labelGap;
        const box={left:x,top:y,right:x+width,bottom:y+18};hidden=box.left<0||box.right>stage.clientWidth||box.top<0||box.bottom>stage.clientHeight||occupied.some(other=>overlaps(box,other));
        element.style.transform=`translate3d(${Math.round(x)}px,${Math.round(y)}px,0)`;element.classList.toggle('active',activeGroup===group||preview===group||nodes[hovered]?.group===group);if(!hidden)occupied.push(box);
      }element.hidden=hidden;
    }
    const zoomElement=document.getElementById('zoom-value');if(zoomElement)zoomElement.textContent=Math.round(zoom*100)+'%';
    emit('camera',{zoom:Math.round(zoom*100),selected:projected.get(selected)||null});stats.projectionMs=performance.now()-projectionStarted;
  }
  function pick(x,y){const started=performance.now(),cx=Math.floor(x/GALAXY.hitCell),cy=Math.floor(y/GALAXY.hitCell);let best=null,distance=GALAXY.hitRadius*GALAXY.hitRadius;
    for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){const gx=cx+dx+1,gy=cy+dy+1;if(gx<0||gx>=spatialColumns||gy<0)continue;const cell=spatial.get(gx+gy*spatialColumns);if(!cell)continue;for(let i=0;i<cell.length;i++){const point=cell[i],d=(point.x-x)*(point.x-x)+(point.y-y)*(point.y-y);if(d<distance){best=point.node;distance=d;}}}
    stats.hoverMs=performance.now()-started;stats.maxHoverMs=Math.max(stats.maxHoverMs,stats.hoverMs);return best;
  }
  function showHover(node){if((node?.id??null)===hovered)return;hovered=node?.id??null;hoverNeighbors=new Set(node?[node.id]:[]);hoverLinks=new Set();
    if(node)for(const link of links)if(endId(link.source)===node.id||endId(link.target)===node.id){hoverNeighbors.add(endId(link.source));hoverNeighbors.add(endId(link.target));hoverLinks.add(key(link));}
    projectionDirty=true;tooltip.hidden=!node;host.style.cursor=node?'crosshair':'';
    if(node){tooltipGroup.textContent=node.group;tooltipGroup.style.color=categoryColor(node.group);tooltipTitle.textContent=node.label;const point=projected.get(node.id),reserves=reserved(),width=Math.min(GALAXY.tooltipWidth,stage.clientWidth-GALAXY.margin*2),height=70;
      const candidates=[{x:point.x+GALAXY.tooltipGap,y:point.y-height-GALAXY.tooltipGap},{x:point.x-width-GALAXY.tooltipGap,y:point.y-height-GALAXY.tooltipGap},{x:point.x+GALAXY.tooltipGap,y:point.y+GALAXY.tooltipGap},{x:point.x-width-GALAXY.tooltipGap,y:point.y+GALAXY.tooltipGap}];
      const candidate=candidates.find(p=>p.x>=GALAXY.margin&&p.y>=GALAXY.margin&&p.x+width<stage.clientWidth-GALAXY.margin&&p.y+height<stage.clientHeight-GALAXY.margin&&!reserves.some(r=>overlaps({left:p.x,top:p.y,right:p.x+width,bottom:p.y+height},r)));
      if(candidate){tooltip.style.left=candidate.x+'px';tooltip.style.top=candidate.y+'px';tooltip.style.maxWidth=width+'px';}else tooltip.hidden=true;
    }updateBuffers();wake(GALAXY.hoverMs);emit('hover',{node:node||null});
  }
  function frameTick(now){
    frame=null;if(disposed)return;ticking=true;if(lastFrame){frameSamples.push(now-lastFrame);if(frameSamples.length>GALAXY.performanceSamples)frameSamples.shift();}lastFrame=now;
    // The instanced layer owns glyphs; retain legacy object references for capture
    // scale/state, but remove thousands of empty groups from Three's scene walk.
    if(detachRemaining>0){detachRemaining--;for(const node of nodes){const object=node.__threeObj;if(object?.parent)object.parent.remove(object);}}
    if(getData().nodes!==nodeRef||getData().links!==linkRef){build();scheduleLayout(GALAXY.captureSettleMs);wake(GALAXY.captureSettleMs);}
    if(layoutMotion){const progress=reducedMotion?1:Math.min(1,(now-layoutMotion.start)/GALAXY.layoutMs),ease=hudEase(progress);
      for(const point of layoutMotion.positions){const node=nodes[point.id],from=layoutMotion.from.get(point.id);if(!node||!from)continue;for(const axis of ['x','y','z'])node[axis]=node['f'+axis]=from[axis]+(point[axis]-from[axis])*ease;}
      if(progress>=1)layoutMotion=null;projectionDirty=true;updateBuffers(true);
    }else if(selected!==null&&baseSizes[selected]){const node=nodes[selected];attributes.size.setX(selected,baseSizes[selected]*Math.max(node.__threeObj?.scale?.x||1,GALAXY.selectedScale));attributes.size.needsUpdate=true;}
    starMaterial.uniforms.uTime.value=now/1000;starMaterial.uniforms.uBoot.value=bootDuration?Math.max(0,(now-bootStart-GALAXY.bootDelay)/1000):1000;
    if(!reducedMotion){dustStars.position.x=parallaxX*GALAXY.parallax*GALAXY.dustParallaxScale;dustStars.position.y=parallaxY*GALAXY.parallax*GALAXY.dustParallaxScale;nearDust.position.x=parallaxX*GALAXY.parallax;nearDust.position.y=parallaxY*GALAXY.parallax;}edgeMaterial.uniforms.uTime.value=now/1000;
    edgeMaterial.uniforms.uViewport.value.set(Math.max(1,stage.clientWidth),Math.max(1,stage.clientHeight));
    if((projectionDirty&&now-lastProjection>=GALAXY.projectionIntervalMs)||projectedWidth!==stage.clientWidth||projectedHeight!==stage.clientHeight){placeLabels();projectionDirty=false;lastProjection=now;}
    stats.frames++;stats.drawCalls=renderer.info.render.calls;stats.triangles=renderer.info.render.triangles;
    if(stats.firstFrameMs===null)stats.firstFrameMs=now-started;
    if(now-lastReport>GALAXY.reportMs){lastReport=now;const sorted=[...frameSamples].sort((a,b)=>a-b);stats.frameMs=frameSamples.length?frameSamples.reduce((a,b)=>a+b,0)/frameSamples.length:0;stats.p95FrameMs=sorted[Math.floor(sorted.length*.95)]||0;
      const readout=document.getElementById('perf-readout');if(readout)readout.textContent=`${stats.nodes} notes · ${stats.links} links · ${stats.drawCalls} draw calls · frame ${stats.frameMs.toFixed(1)}ms · hover ${stats.hoverMs.toFixed(2)}ms · ${stats.idle?'idle':'active'}`;}
    if(pickPending&&!pointerDown){const p=pickPending;pickPending=null;showHover(pick(p.x,p.y));}
    const active=!document.hidden&&(!reducedMotion||continuous||now<awakeUntil||layoutMotion||controls.autoRotate||(selected!==null||activeLinks.size>0)&&!reducedMotion);
    ticking=false;if(active){if(frame===null)frame=requestAnimationFrame(frameTick);}else{stats.idle=true;lastFrame=0;renderer.render(scene,camera);graph.pauseAnimation();const readout=document.getElementById('perf-readout');if(readout)readout.textContent=`${stats.nodes} notes · ${stats.links} links · ${stats.drawCalls} draw calls · idle rendering paused · hover ${stats.hoverMs.toFixed(2)}ms`;}
  }
  function wake(duration=GALAXY.idleSettleMs){if(disposed)return;awakeUntil=Math.max(awakeUntil,performance.now()+duration);stats.idle=false;if(!resuming){resuming=true;try{graph.resumeAnimation();}finally{resuming=false;}}if(frame===null&&!ticking)frame=requestAnimationFrame(frameTick);}
  function persist(positions){const saved={};for(const point of positions)saved[point.key]={x:point.x,y:point.y,z:point.z};try{localStorage.setItem(storageKey,JSON.stringify(saved));stats.layoutPersisted=true;}catch{stats.layoutPersisted=false;}emit('layout',{persisted:stats.layoutPersisted,worker:stats.layoutWorker});}
  function requestLayout(){
    if(!worker)return;const revision=++layoutRevision;clearTimeout(workerTimer);workerTimer=setTimeout(()=>{stats.layoutWorker=false;},GALAXY.workerTimeout);
    worker.postMessage({revision,nodes:nodes.map(({id,label,group})=>({id,label,group})),cached:cacheRead(storageKey)});
  }
  function scheduleLayout(delay=0){clearTimeout(layoutTimer);layoutTimer=setTimeout(requestLayout,delay);}
  try{worker=new Worker(new URL('./layout-worker.js',import.meta.url));worker.onmessage=({data})=>{if(data.revision!==layoutRevision)return;clearTimeout(workerTimer);stats.layoutWorker=true;const from=new Map(nodes.map(node=>[node.id,{x:node.x,y:node.y,z:node.z}]));layoutMotion={start:performance.now(),from,positions:data.positions};persist(data.positions);wake(GALAXY.layoutMs);};worker.onerror=()=>{stats.layoutWorker=false;worker?.terminate();worker=null;};}catch{stats.layoutWorker=false;}
  function zoom(direction){const target=controls.target,delta=camera.position.clone().sub(target),length=Math.max(GALAXY.minDistance,Math.min(GALAXY.maxDistance,delta.length()*(direction>0?1/GALAXY.zoomStep:GALAXY.zoomStep)));delta.setLength(length).add(target);flyCamera({x:delta.x,y:delta.y,z:delta.z},{x:target.x,y:target.y,z:target.z},GALAXY.zoomMs);wake(GALAXY.zoomMs);}
  function fit(){onClear();const bounds=new THREE.Box3();for(const node of nodes)bounds.expandByPoint(new THREE.Vector3(node.x,node.y,node.z));const center=bounds.isEmpty()?new THREE.Vector3(0,GALAXY.opticalY,0):bounds.getCenter(new THREE.Vector3());const size=bounds.isEmpty()?new THREE.Vector3(300,250,0):bounds.getSize(new THREE.Vector3());const halfFov=camera.fov*Math.PI/360,aspect=Math.max(.2,stage.clientWidth/stage.clientHeight),distance=Math.max(size.y/2/Math.tan(halfFov),size.x/2/Math.tan(halfFov)/aspect)*1.35;
    flyCamera({x:center.x,y:center.y,z:center.z+Math.max(GALAXY.minDistance,distance)},{x:center.x,y:center.y+GALAXY.opticalY,z:center.z});wake();}
  function pointerMove(event){const r=stage.getBoundingClientRect();pickPending={x:event.clientX-r.left,y:event.clientY-r.top};parallaxX=pickPending.x/r.width-.5;parallaxY=.5-pickPending.y/r.height;if(!pointerDown)wake(GALAXY.hoverMs);}
  function pointerStart(event){pointerDown={x:event.clientX,y:event.clientY};controls.enableDamping=!reducedMotion;controls.mouseButtons.LEFT=event.shiftKey?THREE.MOUSE.PAN:THREE.MOUSE.ROTATE;showHover(null);wake();}
  function selectionDetail(source){return {node:selected===null?null:nodes[selected],related:links.filter(link=>endId(link.source)===selected||endId(link.target)===selected).map(link=>nodes[endId(link.source)===selected?endId(link.target):endId(link.source)]),source,open:source!=='pointer'};}
  function selectNode(node,source){interactionSource=source;onSelect(node);interactionSource='system';if(selected===node.id)emit('selection',selectionDetail(source));projectionDirty=true;wake();}
  function pointerEnd(event){if(!pointerDown)return;const moved=Math.hypot(event.clientX-pointerDown.x,event.clientY-pointerDown.y);pointerDown=null;if(moved<GALAXY.clickDistance&&event.button===0){const r=stage.getBoundingClientRect(),node=pick(event.clientX-r.left,event.clientY-r.top);if(node)selectNode(node,'pointer');else onClear();}wake();}
  function doubleClick(event){const r=stage.getBoundingClientRect(),node=pick(event.clientX-r.left,event.clientY-r.top);if(node){event.preventDefault();selectNode(node,'doubleclick');}}
  function keyDown(event){if(event.defaultPrevented||event.metaKey||event.ctrlKey||event.altKey||event.target.closest?.('input,textarea,select,[contenteditable="true"],dialog'))return;
    if(event.key==='Escape'){onClear();if(event.target===host||event.target===renderer.domElement)document.getElementById('question')?.focus();return;}
    if(event.key.toLowerCase()==='f'){event.preventDefault();fit();return;}
    if(event.key==='Tab'&&(event.target===host||event.target===renderer.domElement)){event.preventDefault();const categories=[...labelElements.keys()],index=categories.indexOf(activeGroup),direction=event.shiftKey?-1:1;onGroup(categories[(index+direction+categories.length)%categories.length]);return;}
    if(event.key.startsWith('Arrow')&&selected!==null){const connected=links.filter(link=>endId(link.source)===selected||endId(link.target)===selected).map(link=>nodes[endId(link.source)===selected?endId(link.target):endId(link.source)]);if(connected.length){event.preventDefault();connected.sort((a,b)=>{const pa=projected.get(a.id),pb=projected.get(b.id);return event.key==='ArrowLeft'?pa.x-pb.x:event.key==='ArrowRight'?pb.x-pa.x:event.key==='ArrowUp'?pa.y-pb.y:pb.y-pa.y;});selectNode(connected[0],'keyboard');}}
  }
  const controlStart=()=>{emit('interaction',{kind:'orbit'});wake();},controlChange=()=>{projectionDirty=true;wake();},visibility=()=>{if(document.hidden){awakeUntil=0;if(frame!==null)cancelAnimationFrame(frame);frame=null;graph.pauseAnimation();stats.idle=true;lastFrame=0;}else wake();};
  controls.enableDamping=!reducedMotion;controls.dampingFactor=.12;controls.minDistance=GALAXY.minDistance;controls.maxDistance=GALAXY.maxDistance;
  controls.minPolarAngle=Math.PI/2-GALAXY.orbitLimit;controls.maxPolarAngle=Math.PI/2+GALAXY.orbitLimit;controls.minAzimuthAngle=-GALAXY.orbitLimit;controls.maxAzimuthAngle=GALAXY.orbitLimit;controls.zoomToCursor=true;controls.mouseButtons.RIGHT=THREE.MOUSE.PAN;
  host.tabIndex=0;host.setAttribute('role','application');host.setAttribute('aria-description','Interactive galaxy. F fits all notes. Arrow keys follow selected connections. Tab cycles constellations. Escape clears selection and exits to the command bar.');
  const pointerLeave=()=>{pointerDown=null;showHover(null);},wheel=()=>{emit('interaction',{kind:'zoom'});wake();};
  host.addEventListener('pointermove',pointerMove);host.addEventListener('pointerdown',pointerStart);host.addEventListener('pointerup',pointerEnd);host.addEventListener('dblclick',doubleClick);host.addEventListener('pointerleave',pointerLeave);host.addEventListener('wheel',wheel,{passive:true});
  document.addEventListener('keydown',keyDown);document.addEventListener('visibilitychange',visibility);controls.addEventListener('start',controlStart);controls.addEventListener('change',controlChange);
  const zoomInElement=document.getElementById('zoom-in'),zoomOutElement=document.getElementById('zoom-out'),fitElement=document.getElementById('fit');
  const zoomIn=()=>zoom(1),zoomOut=()=>zoom(-1);zoomInElement?.addEventListener('click',zoomIn);zoomOutElement?.addEventListener('click',zoomOut);fitElement?.addEventListener('click',fit);
  const themeObserver=new MutationObserver(()=>{edgeMaterial.uniforms.uAccent.value.copy(accent());const light=lightMode();starMaterial.uniforms.uLight.value=light?1:0;starMaterial.blending=light?THREE.NormalBlending:THREE.AdditiveBlending;starMaterial.needsUpdate=true;dustMaterial.color.set(light?'#56616B':'#9AA2AB');graph.backgroundColor(rootStyle().getPropertyValue('--bg-void').trim()||'#040506');wake();});themeObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  const dustGeometry=new THREE.BufferGeometry(),dust=new Float32Array(GALAXY.dustCount*3);for(let i=0;i<GALAXY.dustCount;i++){const seed=hash('dust'+i);dust[i*3]=(seed/4294967296-.5)*GALAXY.dustRadius;dust[i*3+1]=((hash('y'+i)/4294967296)-.5)*GALAXY.dustRadius;dust[i*3+2]=-120-(hash('z'+i)/4294967296)*GALAXY.dustRadius/2;}dustGeometry.setAttribute('position',new THREE.BufferAttribute(dust,3));const dustMaterial=new THREE.PointsMaterial({color:lightMode()?'#56616B':'#9AA2AB',size:GALAXY.dustSize,opacity:GALAXY.dustOpacity,transparent:true,depthWrite:false});const dustStars=new THREE.Points(dustGeometry,dustMaterial);scene.add(dustStars);
  const nearGeometry=new THREE.BufferGeometry();nearGeometry.setAttribute('position',new THREE.BufferAttribute(dust.slice(0,Math.floor(GALAXY.dustCount*GALAXY.dustNearFraction)*3).map(value=>value*GALAXY.dustNearScale),3));
  const nearDust=new THREE.Points(nearGeometry,dustMaterial);scene.add(nearDust);
  build();scheduleLayout();wake(GALAXY.layoutMs);
  const api={wake,project,fit,zoom,categoryColor,ease:hudEase,boot(duration){bootStart=performance.now();bootDuration=reducedMotion?0:Math.max(0,duration);wake(duration);},setReducedMotion(value){reducedMotion=Boolean(value);edgeMaterial.uniforms.uReduced.value=reducedMotion?1:0;starMaterial.uniforms.uReduced.value=reducedMotion?1:0;if(reducedMotion){dustStars.position.set(0,0,0);nearDust.position.set(0,0,0);}controls.enableDamping=!reducedMotion;if(reducedMotion)controls.autoRotate=false;wake();},setContinuous(value){continuous=Boolean(value);wake();},refresh(){if(getData().nodes!==nodeRef||getData().links!==linkRef){build();scheduleLayout(GALAXY.captureSettleMs);wake(GALAXY.captureSettleMs);}else updateBuffers();wake();},
    highlight(state){const changed=state.selected!==selected,signature=[...state.activeLinks].sort().join(',');selected=state.selected;highlighted=state.highlighted;activeLinks=state.activeLinks;activeGroup=state.activeGroup;if(changed||signature!==activeSignature){revealStart=performance.now()/1000;edgeMaterial.uniforms.uRevealStart.value=revealStart;}activeSignature=signature;if(changed&&interactionSource==='system')emit('selection',selectionDetail('system'));projectionDirty=true;updateBuffers();wake(GALAXY.revealMs+activeLinks.size*GALAXY.staggerMs);},
    previewGroup(group){preview=group;projectionDirty=true;updateBuffers();wake();},get performance(){return {...stats};},
    destroy(){if(disposed)return;disposed=true;if(frame!==null)cancelAnimationFrame(frame);clearTimeout(workerTimer);clearTimeout(layoutTimer);worker?.terminate();themeObserver.disconnect();document.removeEventListener('keydown',keyDown);document.removeEventListener('visibilitychange',visibility);controls.removeEventListener('start',controlStart);controls.removeEventListener('change',controlChange);
      host.removeEventListener('pointermove',pointerMove);host.removeEventListener('pointerdown',pointerStart);host.removeEventListener('pointerup',pointerEnd);host.removeEventListener('dblclick',doubleClick);host.removeEventListener('pointerleave',pointerLeave);host.removeEventListener('wheel',wheel);zoomInElement?.removeEventListener('click',zoomIn);zoomOutElement?.removeEventListener('click',zoomOut);fitElement?.removeEventListener('click',fit);window.removeEventListener('pagehide',pageHide);window.removeEventListener('jarvis:pins',pinsChanged);
      renderer.render=originalRender;tooltip.remove();for(const element of labelElements.values())element.remove();for(const object of [stars,edges,nebula,dustStars,nearDust]){scene.remove(object);object.geometry.dispose();}starMaterial.dispose();edgeMaterial.dispose();nebulaMaterial.dispose();dustMaterial.dispose();}};
  const pageHide=()=>api.destroy(),pinsChanged=()=>api.refresh();window.addEventListener('pagehide',pageHide,{once:true});window.addEventListener('jarvis:pins',pinsChanged);return api;
}
