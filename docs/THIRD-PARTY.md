# Bundled assets

The existing rendering dependencies are pinned and served locally. Their upstream license files are in licenses/. No package installation or build step is required.

| Asset | Upstream | License |
| --- | --- | --- |
| Three.js0.179.1 | https://github.com/mrdoob/three/tree/r179 | MIT; licenses/three-LICENSE.txt |
|3d-force-graph1.79.0 | https://github.com/vasturiano/3d-force-graph | MIT; licenses/3d-force-graph-LICENSE.txt. The distributed bundle retains its embedded dependency notices. |
| Geist / Geist Mono variable Latin fonts | https://github.com/google/fonts/tree/main/ofl/geist and https://github.com/google/fonts/tree/main/ofl/geistmono | SIL Open Font License1.1; licenses/geist-OFL.txt and geistmono-OFL.txt |

Existing MediaPipe assets remain under their existing ownership and notices.

Whitespace-only cleanup: the font license trailing spaces and one mixed-indent line in three.core.js were normalized for repository diff checks; license text and runtime behavior are unchanged.
