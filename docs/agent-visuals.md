# Galaxy agent visuals

The left side of Galaxy now contains three equal agent signals, replacing the Sol/Luna boss-and-worker tree. These are presentation names for existing worker slots, not new agents or model profiles:

| Signal | Existing slot | Appearance |
| --- | --- | --- |
| Scout | `worker-1` | Cyan compass diamond |
| Weave | `worker-2` | Violet orbital petals |
| Prism | `worker-3` | Amber faceted hexagon |

Idle symbols are dim and still. Working agents glow, breathe and rotate an orbit. Status text also identifies working, queued, retrying, done, stopped and interrupted states, so color and motion are not the only indicators. A failed activity connection stops the animation and displays Offline.

Thin flowing curves connect agents contributing to the same active workflow. Two participants create one connection; all three create a complete constellation. A completed participant can remain connected while another finishes. These lines represent shared workflow findings, not an assertion that the agents exchange direct messages. During the existing final review, the flow reverses and the footer says “Combining their findings”; no fourth avatar or boss hierarchy is introduced. Connections stop when the workflow ends, and the completion cue returns to idle after 12 seconds.

The desktop panel measures approximately **244 × 178 CSS pixels**, with a **224 × 173** mobile layout. It collapses to its header, hides in full view and other workspaces, pauses animations while collapsed, and respects reduced motion. Light mode has its own colors. The arrow opens the existing Work controls and detailed activity.

### Refresh entrance

The panel fades in and glides from 12 px left and 6 px below its final position, over 680 ms after a 140 ms delay. The animation starts when the panel becomes visible after refresh and also plays when returning to Galaxy. Polling does not restart it. It changes opacity and transform only, preserving panel dimensions and layout. Both the operating-system reduced-motion preference and JARVIS's Reduced motion option disable the entrance, showing the panel immediately. This follow-up changes CSS only; agent logic is untouched.

On October 23, the loaded browser reported `crew-enter`, `0.68s` duration and `0.14s` delay after refresh. The visible transition was sampled at opacity `0.446856` and translation `(-6.63773px, 3.31886px)`, then settled at opacity 1 with zero translation. Reduced motion reported `animation: none`, opacity 1 and no transform; the original Follow system preference was restored. Both agent JavaScript regression suites passed. The required full preflight reported **13 pass, 1 fail, 2 warn**: the running-server foreground-read instrument failed, matching its pre-edit `front_readable: false` diagnostic. The two warnings skip API-key/model checks for Codex sign-in. The visible Focus probe again passed **16 pass, 0 fail | 1440x900**, with every per-case PASS in the title below. The viewport override was reset. Browser window count remained unavailable; ledger counts remained five session entries and six legacy aggregate keys, and the controlled host was `127.0.0.1:4700`.

One browser refresh temporarily lacked layout and graph assets (`GRAPH is not defined`); a subsequent complete reload restored the page. Served CSS and UI files matched disk. No asset-loading or Focus code was changed.

## Runtime boundary

`viewer/agents.js` reads the existing `/agents`, `/workflows` and `/workflows/run` public snapshots. The existing Work view dispatches its received run snapshot as a browser event for immediate visual updates. Active activity is polled every 750 ms; workflow discovery occurs every four seconds when idle. Requests have timeouts and slower polling in hidden tabs. Stable avatar elements avoid rebuilding the symbols on each poll.

No prompts, model choices, framework code, execution limits, tools, persistence, server routes or agent orchestration changed. Raw reasoning and output text are not added to the constellation. Its state and event labels use known values; the existing detailed activity views remain available. Native SVG and CSS add **no dependencies or build step**.

## Research and design choice

A quick [Reddit mission-control discussion](https://www.reddit.com/r/SideProject/comments/1r8bmhl/built_a_visual_mission_control_for_ai_agents/) informed the emphasis on distinct agent identities and visible work. An [X announcement of A2UI](https://x.com/osanseviero/status/2002747011230269893) led to checking the [Google A2UI repository](https://github.com/google/A2UI). Its broader agent-generated UI approach was unnecessary for a small indicator over an existing runtime. No external code or artwork was copied. The chosen small constellation follows the galaxy's existing glass, line, color and typography styles.

## Verification — October 23, 2026

| Check | Observed result |
| --- | --- |
| One agent | One glowing symbol, two idle symbols, zero connections |
| Two collaborating | Two active symbols, one connection |
| Three collaborating | Three active symbols, three connections and shared-task caption |
| Queued work | Queued agents do not count as working or create false collaboration |
| Combining and completion | Existing reviewer produces the combining cue without a fourth avatar; completion stops the flow |
| Connection loss and recovery | Offline state stops motion; successful activity reads restore it |
| History selection | An older saved run cannot replace a newer active workflow |
| Desktop | Visual fixtures inspected at actual 1440 × 900 CSS viewport |
| Mobile | Actual 390 × 844 CSS viewport; no horizontal overflow |
| Accessibility | Light theme and reduced motion inspected; all six orbit/flow animations disabled in reduced motion |
| Space controls | Collapsed header measured about 35 px high; full view hides the panel and exiting restores it |
| Regressions | 184 Python tests passed with local embeddings; all 14 JavaScript suites passed |
| Final full live preflight | **14 pass, 0 fail, 2 warn**; API-key/model checks skipped for the signed-in Codex backend |
| Real workflow | Browser launch showed all three working; existing runtime completed in 24.8 s, with one tool call and 32,799 reported tokens |

The real task compared the fictional Menu Pricing, Opening Checklist and Launch Campaign notes. Its answer disclosed that Menu Pricing was absent from the retrieved evidence and cited the other two sources. This is an existing retrieval limitation; the UI work does not change or claim to correct it. The live screenshot below shows real execution. The other images use explicitly labelled, isolated visual fixtures and are not evidence of model execution.

- [Real three-agent execution](screenshots/agents-live.jpg)
- Labelled fixtures: [one](screenshots/agents-one.jpg), [two](screenshots/agents-two.jpg), [three](screenshots/agents-three.jpg), [mobile](screenshots/agents-mobile.jpg), [light and reduced motion](screenshots/agents-light.jpg)

The visible Focus probe passed at an asserted 1440 × 900 viewport. Its full title was read:

```text
FOCUS PROBE: 16 pass, 0 fail | 1440x900 | PASS viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

The initial wrong-size probe failed and was rerun only after asserting the required viewport. An initial full preflight reported `13 pass, 1 fail, 2 warn`: the running server could not read foreground activity. A subsequent running-server diagnostic reported `front_readable: true`; the final full preflight then passed with `14 pass, 0 fail, 2 warn`. Both warnings are API-key/model checks skipped for the signed-in Codex backend. No Focus code or operating-system permissions changed. The ledger instruments contained five session entries and six legacy aggregate keys; browser window count was unavailable from the browser inventory. The controlled tab host was `127.0.0.1:4700`. Temporary viewport overrides were reset and fixture tabs closed.

## View or reproduce

Start JARVIS with the existing workflow setup:

```sh
./start-workflows.sh
```

Open [JARVIS](http://127.0.0.1:4700), refresh, select **Work**, launch a task and return to **Galaxy**. For example: “Compare Menu Pricing, Opening Checklist and Launch Campaign. Give three priorities with citations.” Existing runtime limits and the signed-in model connection apply.

For repeatable visual states without model calls, keep JARVIS running and start:

```sh
python3 tests/support/preview_agents.py
```

Open [the labelled visual fixtures](http://127.0.0.1:4702/?state=one) and select one, two, three, review or complete. This loopback-only fixture server refuses POST requests and does not forward actions or inference. It is a test aid, not a replacement JARVIS service.

Run the targeted regressions with:

```sh
node tests/agents.cjs
node tests/agents-collaboration.cjs
```
