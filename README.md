# Jarvis — daily use

On this Mac, open Terminal and run this one command:

```sh
/Users/fwnivaen/.codex/.chatgpt-projects/g-p-6ac83442ec1c8191b488a8adf6db36db/jarvis/start.sh
```

Open http://localhost:4700 in Chrome and click once to enable speech. Keep Terminal open; Control+C stops Jarvis. The launcher rebuilds the galaxy before starting the server. Restart and reload after editing notes. Jarvis listens only on this Mac at 127.0.0.1.

## Checks

From the Jarvis folder, with the server running, run `python3 preflight.py` for the full live checks. `python3 preflight.py --quick` also runs the offline suite but skips model calls; skipped checks are warnings, not passes. Both modes briefly create and clean up a test capture. A tuned numeric FINISH_MS other than 900 produces a warning.

Offline regression tests: `python3 -m unittest discover -s tests -p test_offline.py` (standard library, temporary notes, no network or real brain).

## Brain settings

The default backend is `codex-cli`, using your existing Codex sign-in. To use the OpenAI API later, edit only the local root `config.json`: set `brain` to `openai-api`, set `model` to an API model available to your account, and enter your own key in `openai_api_key`. Existing settings reload on each question. Never paste or commit that file or a key. API usage is billed separately. OpenRouter is also supported; see runtime brain switching below.

## Notes and captures

Markdown lives in `notes/`; captures live in `notes/captures/`. Unrelated captures link to one Captures hub. The hub is derived from saved links and survives rebuilds without requiring an extra note file. If the notes folder is missing at startup, the server can show and speak a clear error; the daily launcher stops before starting it. Restore the folder and restart.

The browser handles voice and screen permissions. Internet access is needed for the graph libraries and cloud brain. The old copy in Documents and the old persona stash are retained untouched.

See RUNNING.md for detailed browser checks and historical verification notes.

## Microphone inside Codex

If browser speech recognition fails, Mic switches to the bundled Mac speech helper. Build it once with `./native/build_voice.sh` (Apple command-line tools required). macOS asks for microphone and speech-recognition permission for Jarvis Voice. Recognition requires an available on-device English recognizer; audio is not sent to an API. Mic off, an in-flight question, or a closed tab stops recording. A ten-second heartbeat limit stops an abandoned session. Temporary transcripts are deleted when the session closes.

Mac speech troubleshooting: `kLSRErrorDomain 201` means Dictation is disabled. Enable it under System Settings → Keyboard → Dictation. Jarvis still explicitly requires on-device recognition. Rebuilding the locally signed helper can cause macOS to request permission again; ordinary Jarvis restarts do not rebuild it.

## Runtime brain switching (Prompt 08)

Click the small brain chip above the answer to open the model chooser. Click any listed model to switch; unavailable choices explain why they cannot be used. The chooser also has a return-to-normal button. Speak through the usual mic buffer, or type the same command. Exact standalone names such as “Luna” also switch, while questions such as “What does Luna mean?” remain normal questions. Switching calls no model and never writes your selection to configuration. Unknown names and versions are refused exactly; there is no nearest-match fallback.

| Spoken name after “switch to” or “try on” | Backend | Exact model |
| --- | --- | --- |
| Astra / GPT 6 Astra | Codex CLI | `gpt-6-astra` |
| Luna / GPT 6 Luna | Codex CLI | `gpt-6-luna` |
| OpenRouter Astra | OpenRouter | `openai/gpt-6-astra` |
| Fable 5.1 / Claude Fable 5.1 | OpenRouter | `anthropic/claude-fable-5.1` |

Both Codex choices passed real minimal calls on this Mac on October 12, 2026. They use the existing Codex login and its usage allowance. The installed CLI's `exec --help` documents `--model`; its top-level help has no standalone model-list command. Candidates came from its local model catalog, then were verified individually. Only those verified IDs are enabled. The exact alias dictionary and explicit known sets live near the top of `server.py`.

Say **“go back to your normal brain”** to restore the backend and model in local configuration. Every server restart does the same. `/see` uses the active choice, with an explicit limitation if image input is unavailable. The viewer refreshes the chip after swaps and periodically so other open tabs catch up.

### Add an OpenRouter key later

1. Create an API key in your OpenRouter account, then open the local `config.json` in your editor. Never paste a key into chat or commit this file.
2. Replace only the `openrouter_api_key` placeholder with your key. Keep `brain` and `model` as they are if you want Codex as the normal startup brain. To make OpenRouter the default instead, set `brain` to `openrouter` and `model` to an exact OpenRouter ID from the table.
3. Restart Jarvis with `./start.sh`, reload Chrome, and say “try on Claude Fable 5.1” or “switch to OpenRouter Astra”. OpenRouter usage is billed by OpenRouter.

At startup with a real key, Jarvis intersects its explicit OpenRouter known set with the live catalog and reads image capabilities. Missing IDs are dropped. If the catalog cannot be checked, OpenRouter choices stay disabled for that run. After changing a key, restart to refresh this check. With a missing or placeholder key, an OpenRouter-only choice is refused out loud and lists the Codex choices. No backend or model substitution occurs.

`GET /model` returns only public backend/model/label status. `POST /model` accepts a JSON `question` containing the spoken command or exact alias and returns the confirmation/refusal plus current status. Neither endpoint exposes keys.

## Focus sessions

Build the floating desktop card once with `native/build_focus.sh`, then restart
`python3 server.py`. Click **FOCUS** for thirty minutes, or say/type
**thirty minutes on this**. Starting while Jarvis is frontmost arms the session:
the first non-home app/site becomes the target. The card appears at the top-right
of the main display across Spaces and tints brown during drift. It never takes
keyboard focus. The viewer also shows the countdown.

The target is the frontmost app's bundle ID; for Chrome-family browsers it also
includes a SHA-256 hash of the lowercase URL hostname (not path, query, fragment,
or port). Different paths on the same site remain focused. Browser internal pages
are compared by their host too. The local Jarvis root/index tab on port 4700 is
home base, including its query parameters. Home time counts as permitted time;
it never triggers a callout. Returning home preserves an excursion so you can
excuse it there. Returning to the actual target closes the excursion.

The server samples once per second using a **fresh `osascript` process** to query
System Events, then the active Chrome-family tab when relevant. No cached
NSWorkspace notification state is used. The reader compares identities internally;
only booleans leave it. `/focus` explicitly constructs a whitelist of booleans and
numeric counters. No app name, bundle ID, URL, host, or hash enters viewer/card
state, speech, or the ledger. Raw CLI diagnostics are discarded. Failed queries
freeze the countdown and show Activity unavailable; they do not invent focus.
A one-second sampler cannot observe excursions that happen entirely between
samples. An observed switch gets 800ms grace; at normal query latency its first
callout is on the following tick, approximately 1–2 seconds after switching.

Commands (speech and typed input use the same handler):

| Say | Effect |
| --- | --- |
| thirty minutes on this | Start; arm if on the Jarvis home tab |
| call me out every thirty seconds | Set the nag interval (minimum three seconds) |
| give me fifteen seconds | Suppress speech temporarily; continue accounting |
| it's okay, I'm doing research | Refund this excursion's time and drift count; stay quiet until back at the target |
| pause / resume | Freeze / resume countdown and observation |
| extend by five minutes | Add time to the plan |
| end the session | Finish and speak the report |
| abort | Stop, report, and reset the clean streak |

One persistent excursion counts once and escalates across three canned speech
pools with each nag. The macOS `say` process speaks autonomous callouts and the
report even if the viewer reloads or closes. Browser `?mute=1` does not mute this
server-owned accountability speech. The session lives in server memory; restarting
the server ends it. Reloading the viewer only fetches its current state.

The report gives minutes permitted/on-target out of planned minutes, drift count,
and streak. A non-aborted session earns a streak increment when credited time is
at least 85% of **planned** time; ending early is not a shortcut. The private,
ignored `ledger-focus.json` stores totals only (sessions, aborts, planned seconds,
on-target seconds, drifts, streak). It stores no session history or timestamps.
If that ledger is malformed or unwritable, the report says it could not be saved.

### macOS 27 permissions, before live testing

In **System Settings → Privacy & Security** grant the **launcher** of the server:

- **Automation → System Events**, and **Automation → Google Chrome** (or the
  Chrome-family browser used). For `start.sh` in Terminal, the launcher is Terminal;
  for a server launched from Codex, it is normally Codex. Follow the responsible
  application name macOS actually shows. The grant is to the launcher controlling
  those apps, not to Chrome controlling Jarvis.
- **Accessibility / Device Control and Data Access** for that same launcher if
  macOS requests it for the System Events frontmost-process query.
- For the existing native microphone, **Microphone** and **Speech Recognition**
  belong to **Jarvis Voice**. If browser recognition is selected, Chrome needs
  microphone access plus the localhost site's microphone permission instead.

Focus needs no Screen Recording, Input Monitoring, Full Disk Access, or remote
Apple Events permission. The native countdown card and `say` need no such grant.
An initial permission dialog may outlast the reader's short timeout; allow it and
let the next tick retry. Denial is shown as Activity unavailable.

### Verification

Run `python3 -m unittest discover -s tests -p 'test*.py'`, `node tests/focus.cjs`,
the existing voice/sources/screen suites, and `python3 preflight.py`.
The privacy test exhausts the named public schema across start/arm, drift, pause,
resume, snooze, excuse, extend and finish, asserting primitive boolean/numeric
values only; ledger tests assert the aggregate schema separately.

For the physical live loop, bring Chrome forward yourself (background automation
clicks do not necessarily activate it). Start on Jarvis, switch to a work site,
and wait for Target locked. Switch to another host and hear a callout within
three seconds. Switch back: drift tint clears. Reload Jarvis: countdown rejoins.
Say/type **end the session** and hear the report. Listen on the Mac itself;
a running `say` process alone does not prove audible output or speaker volume.

Implementation verification (2026-10-13): 31 Python checks and the focus, voice,
source-camera, and screen browser suites passed; the Swift card compiled. Full
live preflight reported `13 pass, 0 fail, 2 warn` (inactive API backend skipped).

The authorized automatic foreground test passed against the real running server:
Chrome switched between two disposable local-site tabs, the server recorded one
drift, and the callout speech process started **1.50 seconds** after initiating
the switch. Returning to the target cleared drift; Jarvis home remained exempt;
reloading rejoined the same countdown. The final report retained exactly one
drift, its speech process completed, and the test closed its temporary Chrome
window. No focus session was left running. This timing measures the native speech
process starting, not an acoustic recording of speaker output. The user separately
reported hearing the callout within three seconds and seeing the tint clear.

To repeat the physical automation deliberately, run
`python3 tools/verify_focus_live.py`. It activates Chrome, switches test tabs,
plays speech, and adds one real test session to aggregate totals. It refuses to
interrupt an existing session and closes only its own disposable window. The
local test URLs may show Not found: only their differing hosts matter to this
reader test. Do not run it while you need uninterrupted foreground control.
