# Local vision assets

MediaPipe Tasks Vision 0.10.21 (`vision.mjs`, the two JS/WASM pairs) is
Copyright Google LLC, Apache-2.0; see MEDIAPIPE-LICENSE. The distribution retains
its bundled copyright notices. Retrieved from the pinned npm package via jsDelivr.

Face Landmarker float16 version 1 and Pose Landmarker Lite float16 version 1
are distributed by Google at storage.googleapis.com/mediapipe-models. They are
bundled unchanged for local inference, following the MediaPipe model guides:
https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker

All of these files are served by the local server's exact allowlist; the eyes
organ fetches no third-party code or model at runtime.
