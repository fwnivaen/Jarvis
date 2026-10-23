# Third-party notices

Rendering libraries, fonts and posture assets are bundled for local use. Their upstream ownership and licenses remain in force. Dependency installation is not required for the viewer.

| Asset | Provenance | License / notice |
| --- | --- | --- |
| Three.js 0.179.1 | [mrdoob/three, r179](https://github.com/mrdoob/three/tree/r179) | [MIT](docs/licenses/three-LICENSE.txt) |
| 3d-force-graph 1.79.0 | [vasturiano/3d-force-graph](https://github.com/vasturiano/3d-force-graph) | [MIT](docs/licenses/3d-force-graph-LICENSE.txt); bundled dependency notices retained |
| postprocessing 6.39.5 | [pmndrs/postprocessing](https://github.com/pmndrs/postprocessing) | [zlib](docs/licenses/postprocessing-LICENSE.md) |
| Inter | [rsms/inter](https://github.com/rsms/inter) | [SIL OFL 1.1](docs/licenses/Inter-OFL.txt) |
| JetBrains Mono | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) | [SIL OFL 1.1](docs/licenses/JetBrainsMono-OFL.txt) |
| Geist / Geist Mono | [vercel/geist-font](https://github.com/vercel/geist-font) | [Geist OFL](docs/licenses/geist-OFL.txt), [Geist Mono OFL](docs/licenses/geistmono-OFL.txt) |
| MediaPipe Tasks Vision 0.10.21 | Google, pinned npm distribution; JS/WASM pairs retained unchanged | [Apache 2.0](docs/licenses/MediaPipe-APACHE-2.0.txt), embedded copyright notices |
| Face Landmarker float16 v1 / Pose Landmarker Lite float16 v1 | Google model distributions; [face guide](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker), [pose guide](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) | See the upstream model documentation and retained distribution notices |

Optional Python integrations are pinned in [requirements-ultra.txt](requirements-ultra.txt) and installed into a local virtual environment. They are not vendored here. The optional `BAAI/bge-small-en-v1.5` embedding is downloaded during setup and excluded from Git. See the [Ultra guide](ULTRA-JARVIS.md) for official dependency documentation and verification details.
