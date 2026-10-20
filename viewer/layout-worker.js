/* Stable spiral-cluster placement for the real note graph. Cached notes stay put. */
const LAYOUT=Object.freeze({version:4,radius:5.2,radiusSpread:1.6,angleOffset:.4,spread:1.1,spreadXZ:1.3,spreadY:.6,height:1.2,
  colors:['#f2a65a','#7c9cff','#a78bfa','#5eead4','#f472b6','#d9e06a','#9aa8ad'],
  palette:{projects:0,operations:0,research:1,marketing:1,finance:2,health:3,people:4,team:4,sales:4,ideas:5,strategy:5,captures:6}});
function hash(text){let value=2166136261;for(let i=0;i<text.length;i++)value=Math.imul(value^text.charCodeAt(i),16777619);return value>>>0;}
function rng(seed){return ()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};}
function gauss(R){return Math.sqrt(-2*Math.log(R()+1e-9))*Math.cos(2*Math.PI*R());}
const order=group=>LAYOUT.palette[String(group).toLowerCase()]??hash(String(group))%LAYOUT.colors.length;
self.onmessage=({data})=>{
  const {nodes,cached={},revision}=data,categories=[...new Set(nodes.map(n=>n.group))].sort((a,b)=>order(a)-order(b)||a.localeCompare(b));
  const centers=new Map(categories.map((group,i)=>{const R=rng(hash(group)),a=i/categories.length*Math.PI*2+LAYOUT.angleOffset,r=i===0?0:LAYOUT.radius+R()*LAYOUT.radiusSpread;return [group,{x:Math.cos(a)*r,y:(R()-.5)*LAYOUT.height,z:Math.sin(a)*r}];}));
  const positions=nodes.map(node=>{const key=`${node.group}\u0000${node.label}`,saved=cached[key];if(saved&&['x','y','z'].every(k=>Number.isFinite(saved[k])))return {id:node.id,key,x:saved.x,y:saved.y,z:saved.z};
    const R=rng(hash(key)),c=centers.get(node.group);return {id:node.id,key,x:c.x+gauss(R)*LAYOUT.spread*LAYOUT.spreadXZ,y:c.y+gauss(R)*LAYOUT.spread*LAYOUT.spreadY,z:c.z+gauss(R)*LAYOUT.spread*LAYOUT.spreadXZ};});
  self.postMessage({revision,version:LAYOUT.version,positions});
};
