// Exercise real placement in the browser module and its worker with reordered,
// newly added, and cached notes. Real vault size/content is never assumed here.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const memory=new Map(),context={localStorage:{getItem:key=>memory.get(key)||null},console};
vm.createContext(context);
const source=fs.readFileSync('viewer/galaxy.js','utf8').replaceAll('export function','function');
vm.runInContext(source.slice(0,source.indexOf('function createGalaxy(')),context);
const seed=nodes=>{context.nodes=nodes;vm.runInContext('seedPositions(nodes)',context);return nodes;};
const notes=[{id:0,label:'Budget',group:'Finance'},{id:1,label:'Launch',group:'Projects'},{id:2,label:'People',group:'People'}];
const placed=seed(notes.map(n=>({...n}))),reordered=seed([...notes].reverse().map(n=>({...n})));
for(const n of placed){const same=reordered.find(p=>p.label===n.label);for(const axis of ['x','y','z'])assert.equal(n[axis],same[axis]);}
const saved=Object.fromEntries(placed.map(n=>[n.group+'\0'+n.label,{x:n.x,y:n.y,z:n.z}]));memory.set('jarvis.galaxy.layout.spiral.v1',JSON.stringify(saved));
const expanded=seed([...notes,{id:3,label:'A new project',group:'New category'}].map(n=>({...n})));
for(const n of placed)for(const axis of ['x','y','z'])assert.equal(n[axis],expanded.find(p=>p.label===n.label)[axis]);
assert.ok(expanded.every(n=>[n.x,n.y,n.z].every(Number.isFinite)));
const worker={self:{postMessage(result){worker.result=result;}}};vm.createContext(worker);vm.runInContext(fs.readFileSync('viewer/layout-worker.js','utf8'),worker);worker.self.onmessage({data:{nodes:[...notes,{id:3,label:'A new project',group:'New category'}],cached:saved,revision:4}});
assert.equal(worker.result.revision,4);for(const n of expanded){const w=worker.result.positions.find(p=>p.id===n.id);for(const axis of ['x','y','z'])assert.equal(n[axis],w[axis]);}
assert.equal(vm.runInContext("categoryColor('People')",context),'#f472b6');assert.equal(vm.runInContext("categoryColor('Research')",context),'#7c9cff');assert.equal(vm.runInContext("categoryColor('Projects')",context),'#f2a65a');
seed([]);worker.self.onmessage({data:{nodes:[],revision:5}});assert.equal(worker.result.positions.length,0);
console.log('GALAXY LAYOUT PASS: note-order independence, cached positions survive new categories, worker/browser agreement, reference category colors and empty vaults.');
