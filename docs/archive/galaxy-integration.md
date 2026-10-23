> Historical development record. Current setup: [Ultra guide](../../ULTRA-JARVIS.md). Current results: [verification](../ultra-verification.md).

# Concept G integration — approved scope

The existing app is Python stdlib + vanilla JavaScript / Three.js. This is an integration into its current viewer, with the normal `./start.sh` launcher and existing APIs. No React or runtime build step is added.

## Visual and interaction plan

- Port the active handoff's Concept G chrome and Concept C GalaxyStage spiral, point shaders, 9,000 decorative stars, link glow and animation timing into the existing Three.js scene.
- Render foreground notes and links only from the existing graph. Keep current category names; map them to the reference colors with a stable fallback for new project categories. Counts update from the loaded graph.
- Preserve `viewer/orb.js` and `viewer/orb.css` exactly. Dock the existing orb on the right on desktop, in a clear area above the composer on small screens. Its current real microphone, model, TTS, approval and connection state controllers remain in charge.
- Keep one visible microphone button in the composer. “+” selects an existing note using the current note mention picker. The composer says “Ask Jarvis”.
- Keep Galaxy / Notes / Work tabs. Use the left rail for Focus, Eyes, screen watch, history and settings, without duplicating the tabs.
- Keep Briefing collapsed until opened or a conversation needs attention. Show Selected only after selecting a real note; expand the note reader on demand. Label only important, hovered and selected notes.
- Remove the old large decorative orbit guides and corner frames. Preserve all rings belonging to the existing orb.
- Use local Inter and JetBrains Mono fonts, local bloom dependencies, DPR capped at 2, batched points/lines, and pause galaxy rendering in hidden tabs. Respect reduced motion.
- Full view (F) hides chrome; Shift+F fits the galaxy. Desktop reference viewport is 1440×900. Narrow layouts have dedicated lanes so panels, orb, legend and composer do not overlap.

## File map

- `viewer/galaxy.js`, `viewer/layout-worker.js`: replace flat constellation rendering/layout with the reference spiral and live graph interaction.
- `viewer/index.html`, `viewer/ui.js`: adapt existing controls and note/chat state into the Open Deck layout.
- `viewer/open-deck.css`: reference glass, type, spacing and responsive rules; existing tokens remain available to the other workspaces.
- Local font files and `viewer/postprocessing.module.js`: browser-ready assets; version/license provenance in `docs/licenses/`.
- `server.py`: add only the new static assets to its existing allowlist; routes and data contracts stay unchanged.
- Existing voice, orb, Focus, Eyes, screen watch and note storage controllers retain their responsibilities.

## Verification and delivery

Check real note selection/search/edit approval, chat and voice state integration, viewport sizes, hidden-tab rendering, console/network failures and the existing regression suite. Run the visible 1440×900 Focus probe and full preflight. Commit on `feature/galaxy-ui` (the user's branch instruction takes precedence over the repository's generic push-to-main instruction).


# Delivery report

## Run

From this repository, run `./start.sh` and open http://127.0.0.1:4700. The normal launcher builds the real note index and starts the existing Python server. No npm command or React build is needed.

## Real wiring

| Element | Existing system connection |
| --- | --- |
| Foreground stars, links, labels and counts | The generated real note graph; verified with 30 notes and 95 links. No handoff note fixtures are imported. |
| Category colors | Finance → purple, Marketing → blue, Operations → orange, People → pink, Strategy → yellow. The reference's other category aliases and a stable fallback support future project groups. |
| Selected pill and note reader | Real graph selection and `/note?id=…`; click a star, then expand Selected to read it. Double click, search and keyboard selection also open the reader. |
| Search / ⌘K | The existing real note index and command palette. |
| Ask Jarvis / send | The existing `/chat` and capture/model command flow. |
| “+” | The existing `@` picker for attaching a real note mention. It does not introduce a file-upload service. |
| Microphone / orb click / held Space | Existing browser/native speech recognition, barge-in, transcription and voice endpoints. |
| Orb states | Existing controller: active mic → listening; pending model → thinking; actual TTS → speaking; note approval → confirm; unavailable backend → offline; otherwise idle. |
| Briefing | Existing answers, citations and voice status, initially collapsed. |
| Rail and Work tab | Existing Focus, Eyes, screen watch, notification history and settings. |
| Clock ring | Local time and actual Focus elapsed/planned time when a session is active. |

The 9,000 background dust points are decorative, as in the reference. They are never counted or searchable as notes. No replacement mock graph, chat endpoint or voice pipeline is included.

## Changed files

- `viewer/galaxy.js`: spiral dust, batched real note points and lines, original GLSL, bloom, hover/selection, labels, orbit/zoom, hidden-tab/workspace suspension and performance diagnostics.
- `viewer/layout-worker.js`: stable seeded 3D positions, preserving cached note positions when data grows.
- `viewer/index.html`: Open Deck structure and adapters for the real graph, selection, camera, composer and connection status.
- `viewer/ui.js`: workspace adapters, live graph/count refresh, Selected, Briefing, full view, rail and clock; approval keeps the existing orb visible.
- `viewer/open-deck.css`: local typography, reference chrome/glass, right orb dock and responsive lanes for panels, approval, legend and composer.
- `viewer/Inter.woff2`, `viewer/JetBrainsMono.woff2`, `viewer/postprocessing.module.js`: local browser assets.
- `server.py`: static asset allowlist only. No API route, storage contract, authentication or model implementation changed.
- `tests/galaxy-layout.cjs`, `tests/galaxy-lifecycle.cjs`: stable real-data layout, picking and renderer lifecycle checks.
- This report, the three added dependency licenses under `docs/licenses/`, and desktop/mobile screenshots under `docs/screenshots/`.

`viewer/orb.js` and `viewer/orb.css` are byte-for-byte unchanged from the starting commit. Their shaders, particle design, rings, animation controller and audio analysis are preserved.

## Differences from the handoff

- The preserved Jarvis orb replaces the handoff orb; it is docked on the right on desktop and above the composer on mobile.
- One composer mic replaces the reference's duplicate voice buttons. Briefing starts closed; Selected appears after selection; details open on demand. The rail exposes existing tools instead of repeating the top tabs. Large old guide rings and corner frames are hidden.
- Real note categories, positions and link density replace the handoff's 248-note fixture. The category names remain those already in this repository.
- The vanilla port retains the app's vendored Three.js 0.179.1 and ForceGraph 1.79.0 for compatibility with existing camera and note behavior. Bloom uses a locally bundled postprocessing 6.39.5, matching the handoff version. No React dependencies are added.
- Mobile panel positions intentionally differ so the orb, status, legend, controls and approvals have clear space. At 390×843, the approval panel ends at y≈493 and the orb begins at y≈523.
- Existing service availability still applies: the Work view does not pretend an unconnected agent runner exists.

## Verification

- Python regression suite: **82 tests passed**.
- JavaScript regression suites: **12 suites passed**, covering galaxy, orb, voice, Focus, Eyes, watch, screen, sources and posture behavior.
- Actual UI checks: real note search, star selection, formatted reader, note attachment picker, approval (cancelled without writing), real chat, live TTS, mic listening and backend disconnect/recovery. All six orb states were observed from real events, not state previews. The mic was switched off after the check.
- Desktop reviewed at asserted 1440×900; narrow layouts checked at 390 and 320 CSS pixels. Approval panels also checked on mobile. Final clean preview recorded no console errors. The retained ForceGraph/Three arrangement still emits its existing multiple-Three-instances warning.
- Galaxy uses batched stars/lines, DPR capped at 2 and hidden-tab/workspace suspension. A settled Chrome run measured about 16.7 ms per frame (~60 fps); performance remains dependent on GPU, DPR and other active browser renderers.
- Required visible probe: **FOCUS PROBE: 16 pass, 0 fail | 1440x900**. All individual cases passed, including visible-at-finish, commands, disconnect and pixel-change checks. This is a hermetic controller probe and does not start a real Focus session.
- Full live preflight: **13 pass, 1 fail, 2 warn**. Chat, configured model, note capture → recall → cleanup, real JPEG vision, static-file consistency, security and configuration-ignore checks passed. The failure is the existing macOS foreground activity/tab reader in Focus: it intermittently returns unreadable/unavailable/foreground-changed. The running server's Focus tick remained fresh, with no active session. Browser window count was unavailable from the automation inventory; the controlled page host was verified as `127.0.0.1:4700`. The two warnings skip OpenAI-specific checks because the configured brain uses Codex CLI. No Focus backend code was changed.

![Desktop, 1440×900](https://github.com/fwnivaen/Jarvis/blob/a1819019322ca73996927c3a9731e5ec1c22be90/docs/screenshots/galaxy-desktop.jpg)

![Mobile, 390×844](https://github.com/fwnivaen/Jarvis/blob/a1819019322ca73996927c3a9731e5ec1c22be90/docs/screenshots/galaxy-mobile.jpg)
