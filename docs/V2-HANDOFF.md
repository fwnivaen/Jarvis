# JARVIS V2 handoff

V2 upgrades the existing Python/HTML app in place. The inference services, dense integer note IDs, Markdown vault, Focus engine/native card, voice routing, Eyes and screen-watch lifecycle remain the owners of their existing state. There is no npm build or framework migration. See [DESIGN.md](DESIGN.md) for the audit, preservation matrix and design decisions.

## Delivered implementation

| Area | Delivered behavior |
| --- | --- |
| Shared design | Bundled Geist/Geist Mono, dark and saved warm-paper themes, shared tokens and glass surfaces, improved small-text contrast, reduced motion and higher contrast preferences. |
| Shell | Persistent 56px header, real version/local availability, Galaxy/Notes/Work, named category legend, actual zoom, universal keyboard palette with notes, categories, workspaces and existing actions. |
| Galaxy | Instanced shader cores/halos, selected diffraction cross, shallow depth, curved instanced links, draw-on/photon selection, degree/recency/pin tiers, collision-culled DOM labels, spatial picking and idle/background pause. |
| Layout/input | Deterministic persisted worker layout; new notes preserve existing placements; bounded orbit, shift/right pan, cursor zoom, arced fly-to, Fit, linked-note arrows, constellation Tab traversal and Escape exit. |
| Orb/voice | Seven states with real triggers, real browser/native FFT and local Daniel output analysis, real model choice, device selection, barge-in/stop, 900ms buffer, hold Space and optional explicit-Mic wake gating. |
| Cards/answers | Full question and answer, actual returned source chips, Show on galaxy, full-answer dialog, tooltip/preview/inspector family, pinning, obstacle-aware preview placement and leader lines, transient insight/history. |
| Notes | Full Markdown reader, 680px reading measure, backlinks and neighborhood graph; local editing and checkbox changes require approval, conflict checking and verified durable readback. |
| Focus | Persistent expanded/compact browser instrument, real elapsed/drift marks, shared-element morph, saved collapse preference, private numeric restart snapshot with offline freeze and fresh target re-arm. Existing native card retained. |
| Launch/preferences | Real orb ignition/glide, radial shader reveal and chrome fade, 1400ms normal or 300ms reduced boot, any-key skip, once per server launch/browser session; quiet sounds off by default. |
| Responsive/accessibility | 2048 safe area, 152px laptop orb, dot legend at ≤1280, tablet bottom inspector, 390px chip strip and docked mic, 44px mobile controls, sheets, labeled controls, navigable category/note/link tree, live announcements and inactive-workspace isolation. |
| Other workspaces | Notes/Library/Project Brain/local Vault browsing share the actual Markdown reader. Work/Mission Control read real local services; Settings, integrations and voice reuse existing controls. Missing services clearly require a connection. |

## Needs wiring

The original brief permits typed TODO adapters where upstream modules are absent. [services.d.ts](../viewer/services.d.ts) supplies declaration-only boundaries marked `TODO(sir)` for Agency, Studio, agents, trading, automations, shared workspace, encrypted Vault and computer control. These require each real module's state, authority, cancellation and verified-result contract. There are no invented endpoints, orders, jobs, schedules, metrics or completion responses.

Existing `/chat` returns final JSON. Token/line streaming and retrieval prelighting need real upstream events. Weighted strongest-link narration needs relationship weights absent from the current graph. The optional wake phrase gates recognized transcripts after explicit Mic enablement; it is not an independent always-on hotword engine.

## Verification — 17 October 2026

| Check | Result |
| --- | --- |
| Python offline suite | **82 tests passed**, including private Focus restart state, durable note saves, stable filename/content revision conflicts and audio leases. |
| JavaScript regression suites | **GALAXY LIFECYCLE, VOICE, WAKE, CHAT, CAPTURE, SOURCES, SCREEN, FOCUS, FOCUS WIDGET, EYES, EYES LIFECYCLE, POSTURE and WATCH passed.** CHAT is included in `voice.cjs`; CAPTURE in `sources.cjs`. |
| Full live preflight | **14 pass, 0 fail, 2 warn.** Both warnings skip inactive OpenAI-backend checks while Codex is active. Real model switching/reset, chat, capture/immediate recall/cleanup, JPEG understanding, live Focus instruments, static serving and configuration privacy passed. [Exact output](preflight-final.txt). |
| Visible Focus probe | **16 pass, 0 fail**, DOM-asserted **1440×900**, visibility `visible`; exact per-case title below. |
| Real UI answer | “Who updates the Cash Flow Forecast, and when?” returned the actual Monday/Maya answer and one real source; question, source chip, inspector and orb state verified. No user Markdown was edited for screenshots. |
| UI review | Dark/light 2048×1152, selection/approval/answer at 1440×900, compact 1024px rail, 768px tablet sheet and 390×844 mobile exercised. Narrow sheet/command separation and no horizontal page overflow were measured. Saved reduced motion and restoration to system motion exercised. |
| Privacy/lifecycle | No startup camera, screen or microphone permission requested. Configuration/generated graph stay ignored; browser access blocked. Private restart state contains numeric/boolean counters, never activity identity. |
| Native/audio | Native voice helper rebuilt; real PCM FFT, silence behavior, Daniel WAV output, input enumeration and cleanup tested. Physical microphone/acoustics, permission dialogs and cross-Space native-card acceptance were not exercised. |
| Hygiene | JavaScript syntax and `git diff --check` passed. No original notes, local credentials or generated graph are included in the commit. |

```text
FOCUS PROBE: 16 pass, 0 fail | 1440x900 | PASS viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

Repeated stress preflights hit the existing 600ms System Events deadline. Before changing it, the actual running diagnostics were checked (recovered readable activity, fresh live tick, no active session), the legacy ledger schema was read without identities, missing session ledgers/browser-window counts were recorded as missing, and the controlled-tab host was confirmed as local. The bounded query deadline was raised to 1200ms; timeout still fails closed and clears settling. A regression verifies a timed-out sample cannot arm or reuse a target. After restarting the actual server, 8/8 consecutive live diagnostic samples were readable/fresh; the subsequent full preflight result is in the linked output.

Artifacts: [dark desktop](screenshots/galaxy-dark-2048.jpg), [paper desktop](screenshots/galaxy-light-2048.jpg), [selection](screenshots/selection-1440.jpg), [approval](screenshots/note-approval-1440.jpg), [real answer](screenshots/answer-1440.jpg), [tablet](screenshots/note-tablet-768.jpg), [mobile](screenshots/galaxy-mobile-390.jpg), [visible probe](screenshots/focus-probe-1440.jpg). CSS dimensions were asserted independently; exported captures may reflect browser zoom/capture scaling.

## Performance evidence and limits

Measured on **MacBookPro17,1, Apple M1, 8 GiB RAM, macOS 27.0.1, Chrome 154**. This is not the brief's MacBook Air/ProMotion acceptance configuration.

The isolated [renderer lab](http://127.0.0.1:4700/galaxy-benchmark.html) uses the production renderer with fictional data and a separate layout cache. It never loads the user's notes or calls a model. [Saved measurement](screenshots/benchmark-10k.json):

| Synthetic load | Recorded value |
| --- | --- |
| Notes / links | 10,000 / 30,000 |
| Canvas CSS size / renderer ratio | 1290×940 / 0.9 (browser zoom) |
| Mode | Continuous draw, shallow auto-orbit, synthetic picking sweep |
| Steady render submissions | **60.00/second** |
| Frame interval mean / p95 | **16.67 / 17.40 ms** |
| Draw calls / triangles | **3 / 380,000** |
| Last projection / render submission CPU | 4.7 / 0.3 ms |
| First observed draw after fixture creation | 131.8 ms; excludes navigation/dependency load |
| Last / maximum observed picking | 0 / **53.6 ms**; strict under-2ms worst-case target **not passed** |
| Heap | Browser-exposed snapshots vary with allocation/GC; a short run cannot certify a memory plateau. |

Submission rate counts completed WebGL render calls, not displayed GPU frames. These values do not certify 60fps at native Retina resolution, 120fps on ProMotion, or a navigation-to-first-frame budget for a 1k vault. Idle pause was observed with selection, rotation, picking and continuous mode cleared; hidden-tab pause is also exercised by the renderer lifecycle.

The [worker benchmark](layout-benchmark.json) passed finite/deterministic 2k/10k/30k fixtures and preserved all cached positions when one note was added:

| Notes | Fresh worker wall time | Cached plus one |
| --- | --- | --- |
| 2,000 | 76.13 ms | 3.29 ms |
| 10,000 | 622.12 ms | 11.87 ms |
| 30,000 | 4213.65 ms | 30.34 ms |

These are CPU layout measurements. Recursive graph resume and duplicate RAF scheduling failures found during stress work were fixed and have regression coverage. Dense graphs use bounded pixel ratio, six-segment arcs, cached static attributes, recycled numeric picking cells and projection throttling.

## Acceptance still outstanding

Implementation is delivered; the original brief's complete acceptance is **not certified**. Remaining items are the absent upstream integrations above, native-resolution/presented 60–120fps, strict worst-case hover, navigation-to-first-frame measurement on a 1k vault, a completed 30-minute memory soak, physical assistive-technology and sensor/audio/cross-Space checks. Token contrast calculations pass, but they do not constitute a full WCAG 2.2 AA audit.

Deliberate implementation differences are documented in DESIGN: custom deterministic collision worker instead of adding a layout package; shader halos instead of a selective postprocessing bloom pass; CSS backdrop glass without physical refraction; interruptible browser easing rather than a spring physics solver. These should not be described as exact fulfillment of those effects.

## Run and repeat checks

```sh
./start.sh
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/galaxy-lifecycle.cjs
node tests/voice.cjs
node tests/sources.cjs
node tests/screen.cjs
node tests/focus.cjs
node tests/focus-widget.cjs
node tests/eyes.cjs
node tests/eyes-lifecycle.cjs
node tests/posture.cjs
node tests/watch.cjs
node tools/benchmark_layout.cjs
python3 preflight.py
git diff --check
```

Open [JARVIS](http://127.0.0.1:4700/). Full preflight calls the configured brain and creates then cleans up a test capture. Do not run state-changing live Focus tools against a user's active session casually. For a reported Focus failure, inspect the actual running diagnostics, private session/legacy ledgers, browser-window count and controlled-tab host before patching, as required by `AGENTS.md`.
