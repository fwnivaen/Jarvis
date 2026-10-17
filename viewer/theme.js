/* Run before paint; no permission, camera, or network side effects. */
(() => {
  const KEY='jarvis.preferences.v2';
  let saved={};
  try{saved=JSON.parse(localStorage.getItem(KEY)||'{}');}catch{}
  const systemLight=matchMedia('(prefers-color-scheme: light)').matches;
  document.documentElement.dataset.theme=saved.theme==='light'||(saved.theme==='system'&&systemLight)?'light':'dark';
  document.documentElement.dataset.motion=saved.motion==='reduced'?'reduced':'system';
})();
