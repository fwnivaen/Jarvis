> Historical development record. Current setup: [Ultra guide](../../ULTRA-JARVIS.md). Current results: [verification](../ultra-verification.md).

> Historical Stage 1 guide. For the complete upgrade, current tools, dependencies and run commands, see [ULTRA-JARVIS.md](../../ULTRA-JARVIS.md).

# Ultra Jarvis — Stage 1 review

This extends the existing Python server, orb, galaxy, notes, voice, Eyes, Focus and screen watch. Stage 2 (memory/imports/preferences/MCP tools and action approvals) is deliberately deferred for review.

## Start on this Mac

In Terminal:

```sh
cd /path/to/Jarvis
python3 -m venv --without-pip .local/ultra-venv
.local/ultra-venv/bin/python tools/ultra_settings.py enable
.local/ultra-venv/bin/python server.py
```

Stop the existing server with Control+C first if it already occupies port 4700. Open [Jarvis](http://localhost:4700). A galaxy-style crew appears in the open top-left corner: one gold boss above three holographic workers. Click its heading to collapse it. The detailed activity drawer remains beside the orb, collapsed initially. The same agent rows appear in Terminal. Counts marked Unavailable have not been reported by Codex. In a redirected terminal, state changes print as tables without cursor controls.

No new packages are needed or installed. The virtual environment uses the Mac's existing Python. Existing `./start.sh` still works and retains its native-helper/galaxy rebuild behavior. Codex must already be installed and signed in with ChatGPT. No API key is copied, requested, or embedded.

Ultra ships **OFF** in the complete `ultra.json` file. Enable/disable changes only that nonsecret file; never put keys there. Changes take effect on the next request. The ordinary model chooser explicitly overrides automatic routing; “go back to your normal brain” restores Ultra when enabled. Astra is never selected automatically by Ultra. Sol is now also an exact spoken model choice.

```sh
.local/ultra-venv/bin/python tools/ultra_settings.py status
.local/ultra-venv/bin/python tools/ultra_settings.py disable
```

Turning Ultra off, removing its settings file, or providing invalid settings restores the prior brain path. A failure during an Ultra request returns a readable error rather than silently calling Astra. Existing explicit model commands and non-Codex overrides keep working. The old webcam route still uses its original model when the cheap-vision flag is off.

## What changed

1. **Cheap first answer:** Luna classifies and answers a simple request in one call. It does not spawn workers for that path. General note retrieval and summaries use the notes supplied by the existing retriever.
2. **Bounded delegation:** the boss uses **GPT-6.1 Sol max** for planning and the final check. The first three worker slots use **GPT-6.1 Sol medium**, **GPT-6 Luna max**, and **GPT-6 Luna high**, respectively. These are real model/effort choices, not display labels. Up to three workers run in parallel by default; requests that need fewer leave the other slots idle. Simple chat, routing and vision retain Luna high. Disabling crew profiles restores the original high-effort routing by job kind.
3. **Live activity:** `/agents`, the crew, a collapsible drawer, and a Terminal table share model, effort, stable crew slot, lifecycle status, operation phase, tool, elapsed time, retries and actual reported input/output/total tokens. Avatars animate only while their matching job is running or retrying. Promotions show the effective model and effort. Stage 1 has no executable agent tools, so Tool shows “—”. No prompts, task descriptions, answers, arguments or reasoning appear in activity metadata. Reasoning events are discarded by the bridge.
4. **Objective checks:** strict output types, real supplied note IDs, exact quoted supporting text, and restricted arithmetic are checked locally. Rounded decimals are checked at their stated precision. Retries get a fixed failed-check code and formatting instructions. These checks establish source existence and arithmetic consistency; they do not prove every semantic claim or discover omitted calculations. Failed workers are recorded, and an answer using only the remaining workers is explicitly marked partial.
5. **Vision savings:** webcam/screen requests use Luna first. Automatic screen-watch checks skip exact duplicate JPEGs for the same watch lease and question after a successful check. Only digests stay in the duplicate cache. Explicit questions always receive a fresh check. Existing local thumbnail/noise/stillness checks remain in place.

All model calls use one warm `codex app-server` process with separate ephemeral read-only threads. The bridge verifies model/effort/image capabilities against `model/list`, verifies a ChatGPT account, disables inherited MCP servers individually, disables shell/browser/apps/plugins/delegation features, and refuses tool requests. It does not expose arbitrary RPC or execution endpoints to the browser. A catalog entry alone does not establish account entitlement; only completed inference does.

## Flags and limits

Edit the complete `ultra.json` to control each feature. `enabled` is the master switch. `routing_enabled`, `parallel_workers_enabled`, `live_monitor_enabled`, `terminal_monitor_enabled`, `crew_profiles_enabled`, `crew_visual_enabled`, `cheap_vision_enabled`, and `skip_unchanged_frames_enabled` are independent feature flags. Turning `crew_visual_enabled` off hides the new crew while retaining the detailed monitor. Turning `crew_profiles_enabled` off restores the prior models/high effort. Monitor flags do not affect execution; disabling parallel workers makes the complex route use a single Sol answer.

- `max_workers`: 3 by default; configurable from 1 to 16. Extra slots beyond the requested first three use Luna high.
- `worker_retries`: 2 by default; maximum 2 (three attempts including the original). A promotion uses a retry.
- `worker_timeout_s`: 45 by default and maximum; one total worker deadline covers all attempts and any promotion. Direct and vision calls retain this cap. The boss shares the remaining request deadline so max effort is not incorrectly treated as a worker. A small transport shutdown grace interrupts the remote turn; failure to interrupt closes the app-server process so work cannot continue unattended.
- `max_escalations`: 1 by default and maximum, shared atomically across the entire request. Only invalid structured outputs, missing/invalid supporting sources or failed arithmetic can promote Luna to Sol. Crew-worker promotions use Sol medium and keep their slot identity; direct/vision promotions retain Sol high. Transport failures, prose expressing uncertainty, and confidence scores cannot promote. Sol never promotes to Astra.
- `request_timeout_s`: 240 by default; bounds the entire pipeline. The browser obtains this budget from the local service. Per-stage/worker deadlines still apply.
- Model settings are intentionally restricted to the verified requested IDs. Invalid or misspelled IDs disable Ultra; there is no nearest-model substitution.

The existing server accepts one user request at a time. The configurable worker pool operates inside that request. No agent writes, sends, edits notes, controls Focus or changes a screen in Stage 1. Approval-backed standard tools are part of Stage 2; existing direct user controls keep their current behavior.

## Verification commands

With the server running, in another Terminal window:

```sh
cd /path/to/Jarvis
.local/ultra-venv/bin/python -m unittest discover -s tests -p 'test*.py'
for test in tests/*.cjs; do node "$test" || break; done
.local/ultra-venv/bin/python preflight.py
```

Preflight now includes the new Python tests. It makes real model calls and creates, recalls, then cleans a disposable capture, as before. In Chrome, open [the visible Focus probe](http://localhost:4700/?focusprobe=1&mute=1) at an **actual page viewport of 1440 × 900** and read its full title. A hidden or incorrectly sized probe is not a pass.

Quick manual checks:

- Ask “Hello”: the drawer should show one Luna dispatch row and zero workers.
- The top-left crew should show Boss: Sol max; Worker 01: Sol medium; Worker 02: Luna max; Worker 03: Luna high. Idle slots must remain idle. Selecting a note compacts the crew so the note remains accessible. Opening Focus prioritizes the Focus card; closing it restores the crew. Full view and other workspaces hide the crew.
- Ask “Use three parallel workers to analyze Menu Pricing, Opening Checklist, and Launch Campaign separately; give one finding per note”: watch dispatch, brain, up to three worker rows, and a final Sol row. Worker failures must remain visible; an incomplete result must say so.
- Ask a screen question or “look at me” using the existing permission controls: the Vision row should begin with Luna.
- Explicitly choose Astra: a single direct Astra call is allowed. Reset to normal to restore routing.
- Disable Ultra: the drawer disappears and the old request path resumes.

Recorded results and environmental limitations are in `docs/ultra-verification.md`.

## Official verification, October 20, 2026

- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna): exact ID `gpt-6-luna`, high/max effort, image input and structured output support confirmed.
- [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol): exact ID `gpt-6.1-sol`, medium/high/max effort and structured output support confirmed, including the requested boss and worker choices.
- [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra): exact ID `gpt-6-astra`, high effort confirmed; manual selection only.
- [Codex app-server](https://learn.chatgpt.com/docs/app-server): initialization, model discovery, thread/turn lifecycle, structured output, usage events, interruption and approval response flow confirmed. The local installed CLI (`0.162.0-alpha.17.2`) generated its own schema, which uses `read-only` for thread sandbox and `never` for approval policy; those exact installed values are used. Here `never` denies escalation requests and does not authorize writes; tools are disabled and the sandbox is read-only.
- [Official Python SDK](https://learn.chatgpt.com/docs/codex-sdk): confirmed, requires Python 3.10+. This Mac's default Python is 3.9.6, so the standard-library protocol client avoids a Python upgrade and dependency changes.
- [ChatGPT plan inference limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations): subscription access differs from API-key access. The bridge stays inside local Codex authentication and its documented RPC inputs.

**UNVERIFIED:** the prompt's exact benchmark comparisons, per-task price ratios, universal model entitlement, and overall cost/latency savings on your workload. No dollar-cost estimate is fabricated from subscription token counts. Both automatic model IDs completed real high-effort calls with token usage on this Mac during Stage 1 verification. Later package versions/APIs for Pydantic AI, Qdrant, Docling, Mem0, MCP, Rich, Playwright, Phoenix and RealtimeSTT have not been selected or used in this stage and must be verified before Stage 2 adoption.

## Complete files

The supplied archive includes complete replacement files for `server.py`, `preflight.py`, `viewer/index.html`, and `viewer/watch.js`, plus every new module, test, stylesheet, flag file and this guide. It excludes configuration secrets, notes, generated graph data, native binaries, virtual environments and repository metadata. Use the Git commit or review the complete files in this checkout before replacing anything in a different installation.
