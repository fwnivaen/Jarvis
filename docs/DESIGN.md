# JARVIS V2 design and behavior

This document describes the code in this repository. It records implementation decisions, preserves the existing local services, and identifies gaps against the V2 brief. It does not certify performance or live acceptance; record that evidence in [V2-HANDOFF.md](V2-HANDOFF.md).

## Upgrade boundary

JARVIS remains a Python standard-library server with a plain HTML/CSS/JavaScript viewer. The existing ForceGraph3D/Three.js scene, graph data model, inference backends, Focus engine, native desktop card, voice helper, Eyes controller, and screen-watch lifecycle remain in place. There is no frontend build step, framework migration, mandatory Git LFS dependency, or replacement inference API.

The visual layers are:

| Responsibility | Source |
| --- | --- |
| Shared visual and motion tokens; bundled font declarations | `viewer/tokens.css` |
| Saved appearance before first paint | `viewer/theme.js` |
| Shell, command bar, material cards, workspaces, responsive rules | `viewer/app.css`, `viewer/ui.js`, `viewer/index.html` |
| Batched star/edge rendering, labels, hit testing, idle rendering | `viewer/galaxy.js` |
| Deterministic placement and local collision settling | `viewer/layout-worker.js` |
| Real audio meters and seven-state orb | `viewer/orb.js`, `viewer/orb.css` |
| Server-owned Focus state and persistent browser instrument | `focus.py`, `viewer/focus.js`, `viewer/focus-v2.css` |
| Existing native desktop instrument | `native/FocusCard.swift` |
| Local note read/edit boundary | `note_store.py`, `server.py`, `build.py` |
| Missing upstream integration contracts | `viewer/services.d.ts` |

## Visual system

The galaxy is the canvas. Floating surfaces use one material family. Teal identifies interaction and current activity; category colors, amber warnings, and red failures carry data. Counts, labels, model names, and source chips come from the loaded graph or local service state. Screenshot examples are not application data.

### Color

`viewer/tokens.css` is the shared source for CSS values. Renderer-specific constants remain named at the top of their modules.

| Role | Dark value |
| --- | --- |
| Void / deep background | `#040506` / `#07090B` |
| Surface 1 / 2 / 3 | `#0B0E11` / `#0F1316` / `#141A1E` |
| Subtle / default / strong stroke | white at 6% / 9% / 14% |
| Inner highlight | white at 5% |
| Primary / secondary text | `#ECEEF0` / `#9AA2AB` |
| Tertiary / disabled text | `#89939D` / `#4A525B` |
| Accent / bright accent | `#55DBC9` / `#8FF0E2` |
| Accent dim / glow | teal at 18% / 35% |
| Warning / danger / success | `#E8B04A` / `#E5636B` / `#5FD49A` |

Tertiary text is deliberately brighter than the brief's `#6B747E` to improve small helper-text readability. Disabled text is reserved for disabled controls. Contrast still requires measured acceptance on final composited surfaces.

| Constellation | Color |
| --- | --- |
| Finance | `#A08BEA` |
| Marketing | `#6F93EE` |
| Operations | `#E9A75C` |
| Sales | `#E2738F` |
| Strategy | `#B8C46A` |
| Team / existing People category | `#4FC7A6` |
| Captures | `#B9BEC4` |

Unknown categories receive deterministic colors at matching OKLCH lightness and chroma. Their identities are taken from real graph categories.

Light mode uses warm `#F4F3F0`, ink `#172127`, secondary ink `#46525B`, and darker teal `#137B6D`. Saved dark/light/system preference is applied before paint. The rendering layer receives theme changes. System contrast preference brightens tertiary text and strokes.

### Type, spacing, and material

Geist and Geist Mono are bundled WOFF2 fonts. UI fallback is Inter Display, then platform sans-serif; metadata fallback is JetBrains Mono, then platform monospace. The scale is 10.5px eyebrows, 12px helper text, 13px body, 15px brand, 18px metrics, 24px titles, and 44px expanded Focus time. Timers and numeric counters use tabular numerals. Use brightness and weight before introducing a new size.

Spacing follows 4, 8, 12, 16, 20, 24, 32, 40, and 56px. Radii are 6px chips, 10px controls, 14px cards, 18px inspectors, and fully round pills. The shared glass is surface 2 at 78%, with 24px backdrop blur, 140% saturation, a 1px default stroke, an inset top highlight, and a restrained black shadow. Light mode substitutes a lighter shadow and stronger highlight. This is CSS backdrop compositing; there is no physical refraction shader.

### Layout

- The persistent top bar is 56px high. Galaxy, Notes, and Work tabs, breadcrumbs, real build version, local-service status, and command search remain above the stage.
- The category legend has no enclosing panel. Its counts come from graph data. The content safe width is 2048px.
- The command bar is 540 × 52px with a 36px bottom gap on wide layouts; focus expands its width by 8%. At 1280px it becomes 480px. On small screens it uses the viewport minus 32px.
- The orb is 176px on wide screens and 152px below 1920px; mobile uses a 40px status orb beside the command area.
- The default inspector is 380px wide, preview 304px, answer card 440px, and note reading measure 680px. Responsive tokens and media rules reduce these widths.
- At 1280px and below the legend becomes a named dot rail; below 1000px the inspector becomes a bottom sheet. Narrow inspectors and approval sheets stop above the command bar. Below 700px categories become a horizontal strip, command controls use larger touch targets, and cards support downward dismissal.
- The note reader is a list, reading column, and backlinks column on wide screens, reducing to one column on small screens. Workspaces reuse the same persistent shell.

Preview placement scores positions around the projected star and viewport edge against the command bar, orb, legend, inspector, Focus widget, and answer card, then clamps to the viewport. It reduces overlap with those surfaces; it does not solve avoidance against every projected star. Preview and inspector have a leader line to the selected star.

## Motion and rendering

| Token | Duration | Typical use |
| --- | --- | --- |
| `--instant` | 90ms | Press / optional sound |
| `--fast` | 160ms | Hover |
| `--base` | 240ms | Card entrance |
| `--slow` | 420ms | Panel / layout change |
| `--cinema` | 1200ms | Shared cinematic token |

Default easing is `cubic-bezier(.22,1,.36,1)`; camera easing is `cubic-bezier(.65,0,.35,1)`. The current fly-to is an interruptible 1100ms arced camera path. Card exit timing is 168ms. Focus preserves the same material, dial, and clock elements and retargets their transforms when collapsed or expanded. The app uses browser animation APIs and CSS, with no new motion framework. The brief's spring models are not implemented as a physics solver.

The layout worker deterministically seeds category anchors, uses shallow depth layers, performs local collision settling, and preserves saved placements. New notes can be placed without moving the cached vault. This is a custom local solver, not a d3-force or ForceAtlas2 simulation. Positions are browser-local under `jarvis.galaxy.layout.v2`, keyed by category and title; renaming either creates a new layout identity.

Stars use batched shader billboards with a bright core, colored halo, additive blending, real link-degree/pin size tiers, recent-edit warmth, and a selected cross. Twinkle changes brightness rather than position. Curved connections use instanced segmented geometry in resting and active states. Selection reveals arcs, runs directional photons, and dims unrelated stars. There is no selective postprocessing bloom pass or real strongest-link weight in the current graph model.

DOM constellation labels use zoom culling and greedy collision avoidance. A projected spatial grid performs hover hit testing. Rendering settles to idle and pauses while the document is hidden; selection photons or interaction keep it active. Settings reports actual node/link counts, draw calls, frame and hover times, and idle state. The isolated renderer lab additionally records first draw, worker/cache state, projection/render CPU time, and browser-exposed heap. These readings are not evidence of the requested 10k-node, ProMotion, or 30-minute memory targets until those runs are recorded.

Reduced motion follows either the system preference or saved setting. Camera travel cuts to the target; CSS removes or shortens motion, disables ripple, and simplifies boot and Focus transitions. No full screen-reader or motion acceptance claim should be made before the verification checklist is completed.

Boot uses a teal ignition point, the actual orb, a radial shader reveal, and a chrome fade, keyed to the server launch in session storage and skippable by a key. Normal duration is 1400ms, reduced duration 300ms. The existing orb grows at the optical center, glides to its dock, shader stars reveal radially, and chrome fades in last. Any key cancels the sequence. It runs after the real graph is ready. Optional quiet UI sounds are off by default.

## Interaction and real state

`⌘K` / `Ctrl K` searches real notes, categories, workspaces, and existing actions. `/` from an empty command field opens commands; `@` opens the real-note picker and inserts a textual mention. Mentions do not add a new backend retrieval contract. Galaxy controls support bounded orbit, pan, pointer-directed zoom, fit, note fly-to, linked-note arrows, and constellation keyboard navigation. The accessible tree exposes categories, notes, and linked notes. When keyboard focus enters it, it opens as a visible panel; background galaxy controls become inert inside another workspace.

Answers still arrive as the existing final `/chat` JSON response. Returned source IDs drive source chips, graph highlights, camera framing, and “Show on galaxy.” The viewer does not fabricate retrieval progress, token streaming, pre-answer citations, or strongest-link rankings. “Read full answer” opens the complete returned text.

The orb has seven states: IDLE, LISTENING, THINKING, SPEAKING, EXECUTING, AWAITING APPROVAL, and ERROR. Voice state drives listening/thinking/speaking; the real note-edit confirmation and save drive approval/executing/error. No autonomous agent runner is connected. Execution progress is indeterminate when the operation supplies no numeric progress.

The spectrum reads the actual browser microphone analyser, native microphone band/RMS metadata, or locally rendered Daniel audio output. Missing or stale signal is shown as unavailable and uses zero measured energy. Browser synthesis fallback and autonomous native Focus speech have no available output analyser and are labeled accordingly. Decorative idle motion must not be described as measured audio.

Mic remains explicit. Hold Space is push-to-talk outside editable fields. The optional “Jarvis” wake phrase is off by default and gates recognized transcripts only after Mic is enabled. It opens a short command window; stop/wait, relief, Focus answer windows, and hold-to-talk preserve immediate handling. This is not an independent always-on keyword detector. The existing browser recognition path may depend on browser speech services; the bundled native path requires available on-device recognition.

## Feature preservation matrix

“Implemented” identifies a real code path, not a completed live acceptance test.

| Capability | Existing owner and V2 surface | Preservation rule / current limit |
| --- | --- | --- |
| Markdown knowledge and graph | `build.py`, `server.py`; galaxy, Notes, Library, Project Brain | Keep existing note IDs, categories, links, capture semantics, and retrieval. Library/Project Brain reuse the local reader; they have no separate business backend. |
| Grounded questions | Existing `/chat` and source response | Preserve source IDs, grounded/casual distinction, exact model selection, and refusal behavior. Final JSON response only. |
| Capture and instant recall | Existing `/remember` and graph replacement | Persist before publishing the new graph. Derived Captures hub has no editable file. |
| Voice and personality | Existing `JarvisVoice`, `voice_bridge.py`, native helper | Preserve Daniel, British-English input, existing silence buffer, barge-in, stop, relief, and native fallback. Add real meters and opt-in transcript wake gate. |
| Runtime models | Existing `/model`, backend adapters, chooser | Preserve validated exact aliases and unavailable reasons. Never substitute a model or expose credentials. |
| Focus | Existing `focus.py`, `focus_reader.py`, native card; new browser instrument | Preserve sampling, grace, home-base accounting, excuses/refunds, pause, retarget, extend, nag, mute, relief, streak/report/ledger behavior. Add private active restart snapshot. |
| Eyes and posture | Existing `eyes.js`, `posture.js`, bundled landmark models | Permission remains explicit; keep calibration, sensitivity, stale-frame handling, startup cancellation, relief, and page-close cleanup. |
| Explicit camera look | Existing `/look` | Only the explicit look command encodes one camera frame for the configured image-capable brain. Background posture sends flags, not frames or landmarks. |
| Screen questions and watch | Existing screen share, `watch.js`, `/see`, `/watch` | Reuse one Entire Screen share; preserve stale-result suppression, quiet/relief gates, watch lease, ended-track cleanup, and cooldown. An enabled watch may send one current screenshot after its local stillness gate. |
| Desktop Focus face | `native/FocusCard.swift` | Keep nonactivating, cross-Space behavior and existing server-owned updates. Browser styling does not replace it. |
| Approvals and permissions | Existing browser/macOS permission flows; new `/note` edit confirmation | No sensor permission at boot. Note edit requires explicit confirmation, same-origin request, current revision, durable save, and verified readback. No general remote-action approval engine exists. |
| Mission Control | Work workspace reads `/focus`, `/watch`, voice status | Actual local activity and controls only. No invented jobs, completions, or agent counts. |
| Settings | Theme/motion/sound browser preferences; actual voice/model controls | Preferences stay in the browser. Selecting a device uses the native voice path; no credentials enter browser preferences. |
| Vault | Existing local Markdown collection | Browse/edit existing notes. Dedicated encrypted Vault and key-management service absent. |
| Agency / Studio / agents / trading / automations | Reserved workspace surfaces and `services.d.ts` | Connection required. No upstream data, action execution, schedules, portfolios, or demo counters. |
| Shared workspace / sync | Local navigation shell; `/system` reports `sync: false` | No tenant, shared workspace, synchronization, or workspace authorization service is present. |
| Computer control | Reserved workspace surface | No executor or permission bridge is connected. Do not equate screen observation with computer control. |

## Focus persistence and privacy

The browser instrument reads the existing public Focus whitelist. Expanded and compact views share one DOM clock/dial/material. The teal arc represents elapsed planned time; amber tick marks represent actual drift count, with a numerical total when the compact visual mark limit is reached. Paused, drifting, offline, and activity-unavailable states remain distinct. Browser unavailability freezes its extrapolated display. The collapsed preference is saved separately under `jarvis.focus.collapsed.v2`.

The engine saves a private sibling active snapshot, normally `ledger-focus-active.json`. Its exact schema contains only `version`, `active`, `paused`, `drill`, `muted`, `planned_s`, `elapsed_s`, `on_target_s`, `drift_s`, `drifts`, `nag_s`, `snooze_s`, and `relief_s`. Flags are booleans; counters are bounded finite numbers. The file is mode 0600, flushed/fsynced, and atomically replaced. An inactive tombstone is saved on completion so the prior active session is not revived.

On restart an active snapshot restores the counters and remaining quiet durations, freezes server-offline time, clears the activity reader, and arms a fresh stable foreground target. It cannot restore the previous target: app/bundle identity, URL/host/hash, window/tab IDs, human labels, and spoken intent are absent. No old target is inferred from notes or browser storage. A corrupt/unwritable snapshot produces a persistence warning through `ledger_ok`; it does not claim a successful save. A crash can lose work since the last successful snapshot.

The legacy aggregate ledger and existing identity-free session history remain separate. Public state and diagnostics retain their existing exact whitelists. Foreground identity is transient inside the reader/engine. A distraction label may be spoken during the current tick but is never written to the snapshot, public state, diagnostics, reports, episode logs, session ledger, or notes.

## Local note editing

The reader fetches the indexed note by ID. The server resolves its stored private path; client-supplied paths do not select a file. Edits require a same-origin request with explicit approval, a matching filename-and-content revision, and a real editable Markdown file within the note root. Symlinks, traversal/outside paths, derived hubs, stale revisions, and oversized edits are rejected. The editor limit is 200,000 characters and 800,000 UTF-8 bytes.

The save prepares a temporary replacement, checks the revision again, anchors replacement to a safely opened parent directory, flushes/fsyncs, replaces atomically, reads back, verifies the identity-bound digest, and publishes the refreshed graph/index. UI success requires `verified: true`. Checkbox edits use the same confirmation path. Errors remain visible for review/retry. No brain call is required for a note edit.

## Needs wiring

`viewer/services.d.ts` declares integration boundaries only. It creates no runtime services, network endpoints, schedules, mock data, or permission grants. Each missing adapter must use the actual upstream state/action/result types when supplied: Agency, Studio, agents, trading, automations, shared workspace, encrypted Vault, and computer control. A connected adapter must distinguish unavailable, error, approval, execution, and verified completion; it must not make an unavailable service look like an empty successful dataset.

Other brief gaps remain explicit: token/line streaming, retrieval prelighting, weighted strongest-link insight, selective postprocessing bloom, physical glass refraction, uncertified presentation-rate, worst-case hover, memory-soak and physical accessibility acceptance. Update this document when those capabilities actually land.

## Final integration decisions

The pinned Three.js 0.179.1 and ForceGraph 1.79.0 files are bundled locally, with licenses, to remove CDN startup dependency. No framework or model service was replaced. The renderer disables the old raycaster and removes empty legacy glyph groups from the scene walk while retaining their state references for capture animation. Dense graphs use six-segment curved strips, a bounded pixel ratio, cached geometry attributes, and a 33ms ceiling on projection-grid/label rebuilding. Camera drawing remains independent of that projection rate. Resume is guarded against synchronous control callbacks and frame scheduling is coalesced to prevent duplicate animation loops; tests/galaxy-lifecycle.cjs covers both failures.

Light-mode semantic colors are darkened for small-text contrast; category names inside cards use ink while category dots/stars retain their data color. The light accent is #137B6D. Dark tertiary text is #89939D, raised from the brief’s #6B747E to pass small-text contrast. Mobile uses a single visible orb microphone over the retained Mic control’s layout slot, leaving Send available.

Stress verification exposed the existing 600ms foreground AppleScript deadline under renderer load. After the required running-server/ledger/host audit, this bounded deadline was raised to 1200ms. Unavailable reads still clear settling and grant no target credit; no diagnostic fields or identity storage were added. An isolated timeout/re-arm regression and eight consecutive live readable/fresh samples verify the change.
