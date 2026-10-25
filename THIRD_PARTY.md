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

## Workflow runtime

LangGraph 1.2.16 and langgraph-checkpoint-sqlite 3.1.2 are installed dependencies, not vendored framework source. Both are Copyright (c) 2024 LangChain, Inc., MIT licensed: [LangGraph notice](docs/licenses/langgraph-MIT.txt), [SQLite saver notice](docs/licenses/langgraph-checkpoint-sqlite-MIT.txt). Transitive distributions retain their own license files. The JARVIS adapter and Work-tab console are project code. No AutoGen, Flowise, or hosted Studio code was copied. See the [upstream review](docs/framework-evaluation.md) for separate Studio and Flowise commercial licensing boundaries.

## Gated execution helpers

Deep Agents 0.7.32 and GEPA 0.1.4 are optional, separately installed distributions: [Deep Agents MIT notice](docs/licenses/deepagents-MIT.txt), [GEPA MIT notice](docs/licenses/gepa-MIT.txt). Their independent hash locks and transitive package provenance are in [the execution manifest](dependencies/execution-manifest.json) and [package inventory](dependencies/execution-packages.json). Existing requirements are unchanged. No optimizer/framework source is vendored.

The prepared browser worker selects the official Selenium Chromium image by digest. The pinned docker-selenium source declares Apache 2.0: [license copy](docs/licenses/selenium-Apache-2.0.txt). Image components retain their respective notices. Webtop was reviewed but is not selected or installed. These references do not establish a deployed or validated browser service.

## Atticus Mac feature reference

[Atticus Mac](https://github.com/SaarthurR/atticus-mac), by SaarthurR, was reviewed at commit `c7ab0370c4832507d54a8f731d57dc023e34c8fa` as a feature reference for local fast commands, explicit routines, global push-to-talk and reviewed dictation. Jarvis implements these within its own Python/Swift architecture and retains its Codex / ChatGPT provider. Atticus's monolithic Claude-oriented runtime and installer are not dependencies. Its [MIT license](docs/licenses/atticus-mac-LICENSE.txt) is retained for attribution.
