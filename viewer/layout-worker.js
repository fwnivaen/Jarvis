/* Stable, local layout. Existing placements never move when a note is added. */
const LAYOUT = Object.freeze({version: 3, radius: 190, spreadX: 75, spreadY: 48,
  depth: 18, minGap: 15, grid: 18, passes: 18, push: .48, golden: 2.3999632297,
  anchors: {finance: [-225, 90], strategy: [25, 165], marketing: [245, 85],
    operations: [175, -125], people: [-195, -145], team: [-195, -145], sales: [260, -135], captures: [25, -190]}});
function hash(text) {
  let value = 2166136261;
  for (let i = 0; i < text.length; i++) value = Math.imul(value ^ text.charCodeAt(i), 16777619);
  return value >>> 0;
}
function identity(node) { return `${node.group}\u0000${node.label}`; }
function seed(node, index, categories) {
  const category = node.group.toLowerCase(), known = LAYOUT.anchors[category];
  const angle = categories.indexOf(node.group) * LAYOUT.golden;
  const center = known || [Math.cos(angle) * LAYOUT.radius, Math.sin(angle) * LAYOUT.radius];
  const value = hash(identity(node)), phase = value / 4294967296 * Math.PI * 2;
  const spread = Math.sqrt(((value >>> 8) % 997 + 1) / 998);
  return {x: center[0] + Math.cos(phase) * LAYOUT.spreadX * spread,
    y: center[1] + Math.sin(phase) * LAYOUT.spreadY * spread,
    z: ((value % 3) - 1) * LAYOUT.depth + Math.sin(index * LAYOUT.golden) * 4};
}
self.onmessage = ({data}) => {
  const {nodes, cached = {}, revision} = data;
  const categories = [...new Set(nodes.map(node => node.group))].sort();
  const positions = nodes.map((node, i) => {
    const key = identity(node), saved = cached[key];
    const fixed = saved && ['x', 'y', 'z'].every(axis => Number.isFinite(saved[axis]));
    return {id: node.id, key, ...fixed ? saved : seed(node, i, categories), fixed: Boolean(fixed)};
  });
  // Cached nodes only populate buckets. Rechecking fixed/fixed collisions made
  // adding one note needlessly repeat the whole dense-vault collision workload.
  const fixedCells = new Map(), moving = positions.filter(point => !point.fixed);
  for (const point of positions) if (point.fixed) {
    const cell = `${Math.floor(point.x / LAYOUT.grid)}:${Math.floor(point.y / LAYOUT.grid)}`;
    if (!fixedCells.has(cell)) fixedCells.set(cell, []);
    fixedCells.get(cell).push(point);
  }
  // Spatial buckets keep collision work local, including on large vaults.
  for (let pass = 0; pass < LAYOUT.passes; pass++) {
    if (!moving.length) break;
    const cells = new Map([...fixedCells].map(([key, points]) => [key, [...points]]));
    for (const point of moving) {
      const x = Math.floor(point.x / LAYOUT.grid), y = Math.floor(point.y / LAYOUT.grid);
      for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
        for (const other of cells.get(`${x + dx}:${y + dy}`) || []) {
          const vx = point.x - other.x, vy = point.y - other.y, length = Math.hypot(vx, vy) || .01;
          if (length >= LAYOUT.minGap) continue;
          const force = (LAYOUT.minGap - length) * LAYOUT.push;
          const ux = vx / length || Math.cos(hash(point.key) * LAYOUT.golden);
          const uy = vy / length || Math.sin(hash(point.key) * LAYOUT.golden);
          if (!point.fixed) { point.x += ux * force; point.y += uy * force; }
          if (!other.fixed) { other.x -= ux * force; other.y -= uy * force; }
        }
      }
      const cell = `${x}:${y}`;
      if (!cells.has(cell)) cells.set(cell, []);
      cells.get(cell).push(point);
    }
  }
  self.postMessage({revision, version: LAYOUT.version,
    positions: positions.map(({id, key, x, y, z}) => ({id, key, x, y, z}))});
};
