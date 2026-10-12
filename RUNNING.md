# Run Jarvis

Requires Python 3.9+, an internet connection for the pinned viewer CDN libraries,
and a signed-in Codex CLI. There is no npm build or Python package installation.

```bash
cd /Users/fwnivaen/.codex/.chatgpt-projects/g-p-6ac83442ec1c8191b488a8adf6db36db/jarvis
python3 preflight.py
python3 server.py
```

Open <http://127.0.0.1:4700> in Chrome. Keep Terminal running; Ctrl+C stops it.
The server indexes notes on startup. After editing notes, restart the server and
refresh the page. `python3 build.py` can also rebuild the graph separately.
`preflight.py` uses Node only to check JavaScript syntax, without npm packages.

## Explore

Drag to orbit, scroll to zoom, and click a glowing node to fly to it and see its
excerpt and connected notes. Use the sidebar to search titles or highlight a
group. Recenter restores the overview. Auto orbit respects reduced-motion settings.

The 30 sample notes describe the fictional Juniper Kitchen café. Replace them
with your own Markdown in `notes/`; parent folders become groups. Node IDs are
array indexes in deterministic filename order, so rebuilds may change IDs when
files are added or renamed. The server and graph always rebuild from the same list.

Try:

- What does Menu Pricing say about the harvest and ginger tofu bowls?
- How will the Staffing Plan address the Customer Feedback about pickup waits?
- What are the Quarterly Goals, and how does the Weekly Scorecard compare?

## Brain

The default is `codex-cli`, using the model in the root configuration file.
The server first checks PATH, then the CLI bundled with ChatGPT or Codex on Mac.
It reuses the CLI's existing sign-in; it does not extract, copy, or log credentials.
If you need to sign in and `codex` is not on PATH, use:

```bash
/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex login
```

Each request runs `codex exec` in an empty temporary working directory outside
this repository. It uses read-only sandboxing, disabled command/browser/plugin/
connector features, disabled web search, no user config, and no project instructions.
The prompt travels on stdin; only the final-answer file is parsed. CLI diagnostics
are captured privately and discarded. Invalid JSON or out-of-context IDs are rejected.
The timeout is 90 seconds. The console reports timing without logging questions,
note contents, answers, or credentials. The CLI itself needs network access to the
model service; the model is not permitted to use network tools.

For the future API backend, edit the project-root configuration file locally,
set `brain` to `openai-api`, enter your own key there, and use a model available
to that API account. Settings reload per question. Never put this file in `viewer/`
or paste its contents into chat. The API route has no enabled tools and uses the
same note-only prompt, history, and output validation. API billing is separate.

History is in memory, limited to four successful turns per browser cookie, and
expires after one hour. Restarting clears it. One brain request runs at a time.
Follow-ups use previous questions to help retrieve the right notes. At most six
notes are sent; answers cite only valid IDs from that selection. Keyword retrieval
does not guarantee semantic understanding or factual accuracy.

## Local security and troubleshooting

The server binds only to 127.0.0.1 and serves an explicit allowlist of viewer files.
It refuses symlinks, other hostnames, cross-origin chat, oversized questions,
and arbitrary file paths. Root files, notes, Git metadata, and credentials are
never served. Selected note excerpts are intentionally available in graph-data.js.
Do not expose this local server to the internet.

`.gitignore` protects normal adds; it cannot block a deliberate `git add -f`.
The preflight check verifies both ignored files remain untracked.

If the environment says it cannot listen on port 4700, start the server in your
own Terminal. A blank galaxy with a library error means the CDN is unavailable.
Brain-unavailable messages mean the CLI could not run or reach its service; they
are not fabricated note answers. A successful preflight is an offline check,
not proof of a working model connection or a rendered browser.

To test one real question from a second Terminal:

```bash
curl --max-time 100 -sS http://127.0.0.1:4700/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does Menu Pricing say about the harvest and ginger tofu bowls?"}'
```

The result includes `answer`, `about_notes`, `nodes`, and `elapsed_s`. Failure responses also
include `error: true` and use HTTP 503. A failed call does not enter history.

## Browser voice

Voice uses the browser's Speech Synthesis and `webkitSpeechRecognition` APIs;
there is no speech subscription, API key, or backend change. Use Chrome on
localhost and allow microphone access. Recognition may use the browser vendor's
online recognition service, so this is not a promise of offline transcription.
British English playback is preferred when an installed voice is available;
otherwise an English or system default voice is used.

The first trusted page click speaks the welcome line. No speech is queued before
that click. Click **Mic** to enable listening (click again to turn it off). Mic
stays enabled across turns, but recognition is aborted and its results ignored
while `/chat` is in flight. After the answer arrives, listening resumes; during
playback it accepts only **stop** and **wait**, avoiding ordinary answer echo
being sent back as a question. Headphones make spoken interruptions more reliable.
The **Stop** button also cancels playback immediately without needing recognition.

Final phrases wait for `FINISH_MS = 900` milliseconds of quiet. New interim
speech cancels that deadline; new final phrases append and restart it. A pause
longer than that window sends the question. Stop/wait bypass the window and
cancel locally; they do not call the brain. Thinking remains visible for the
entire request, including the usual eight-second CLI delay. Speech status resets
on playback completion or error. Unsupported/denied microphones leave typing
available.

### Manual acceptance test

1. Open `http://127.0.0.1:4700` in a fresh Chrome tab. Before any click, hear
   nothing. Click the page: hear the welcome line once. Expect **Speaking…**
   during playback, then **Ready**. Click again: no repeated greeting.
2. Type “What are our Quarterly Goals?” and send. Expect **Thinking…** for the
   full response wait and a disabled Mic button. Clicking Mic during that wait
   must not record or start a second request. Expect the answer text and sources,
   then spoken output with **Speaking…**, followed by **Ready**.
3. Click **Mic**, grant permission, and wait for **Listening…**. Say “What does
   Menu Pricing” — deliberately pause about half a second — then say “say about
   the bowls?” Stop talking for at least 900 ms. Expect one combined question in
   the input, one `/chat` request (inspect DevTools Network), **Thinking…** for
   the entire wait, and one answer. No request should start at the mid-sentence
   pause. Repeat with a pause over 900 ms to confirm the configured boundary.
4. With Mic enabled, ask for a detailed answer. While it is being spoken, say
   “stop”. Playback should cancel as soon as recognition reports the word,
   without the 900 ms buffer or another brain request. Repeat with “wait”. Test
   the **Stop** button mid-answer too; it cancels synchronously. Expect
   **Listening…** after cancellation. Spoken recognition latency depends on the
   browser; the application adds no finish delay for these commands.
5. Open `http://127.0.0.1:4700/?mute=1` in a separate tab. Click, type a question,
   and try Mic. Hear **nothing**, including no greeting or answers. See the
   normal text answer and thinking/listening status; never **Speaking…**.
   Keep the original tab idle so its audio cannot be mistaken for this tab.
6. Deny microphone permission in a fresh permission session: see the permission
   message and verify typed chat still works. Turn Mic off with a buffered
   phrase: it must not send later. Try a failed server request: thinking clears
   and the visible error is spoken unless muted.

Automated checks: `python3 preflight.py` and `node tests/voice.cjs`. The voice
suite uses browser API doubles and a virtual clock; it verifies timing and state
without recording or playing audio. It does not replace the live checks above.


## Source camera proof

Intent and citations arrive together from the existing single Codex CLI call.
While thinking, automatic orbit and any unfinished camera flight stop. On a
note answer with one to three distinct sources, the camera flies to the first
(strongest) citation, lights its direct neighbours plus the other cited notes,
and opens its excerpt panel before answer speech starts. Four or more sources
light the cited cluster and its connecting links without moving the camera;
the previous single-note panel closes. Source highlighting clears category
filters so cited notes cannot be hidden by a prior filter.

Greetings, jokes and thanks return `about_notes: false` with no citations and
preserve selection, highlights, and camera position. Unsupported note questions
also hold the view. The only spoken content is the short answer, never the
on-screen excerpt. Clicking a source remains an explicit manual navigation.

Try these in order after restarting the server and refreshing the viewer:

| Question | Expected proof |
| --- | --- |
| What does Menu Pricing say about the harvest and ginger tofu bowls? | Fly to Menu Pricing, light neighbours, show its panel during the answer. |
| Summarize Menu Pricing, Cash Flow Forecast, Staffing Plan, and Quarterly Goals, giving one key point from each note. | With all four cited, light all four and hold the camera; close the single-note panel. |
| Good morning! Tell me a joke. | No camera flight or highlight/selection change, even after the note questions. |

`node tests/sources.cjs` executes actual viewer functions with graph/browser
doubles and delayed responses. It checks the four-source threshold, panel and
speech ordering, small talk after notes, empty sources, three-source answers,
cancelling an unfinished flight, and one HTTP request per turn. Run it with
`node tests/voice.cjs` and `python3 preflight.py`.

Verification for this change: both Node suites and preflight passed. Live
verification was blocked in the task environment: binding port 4700 was denied,
and a direct Codex brain attempt reported that sign-in was required. The table
above describes acceptance expectations, not fabricated live-model results.


## Voice captures (Prompt 05)

Restart the server once after installing this update, then refresh the viewer.
Say or type **remember that**, **note to self**, **don't let me forget**, or
**log this**, followed by the complete note. Voice uses the same 900 ms finish
buffer, including interim speech and multiple final fragments.

`/remember` writes a unique Markdown file under `notes/captures/`, with a title,
local date, and the full text after the trigger. It publishes the updated retrieval
index before replying. No brain call is made. The most relevant keyword match
gets a durable related-note link using the existing build rules. With no match,
the first star is the birth position, without inventing a semantic link.
The star pulses at its parent's position, then the camera flies to it. Reduced
motion skips the pulse and camera animation. Existing IDs stay stable until a
server restart; reload the viewer after restarting. New pages receive the current
in-memory graph, including captures. Other already-open tabs should be refreshed.

Write errors are shown and spoken through the normal voice gate (unless muted
or browser audio is unavailable). If a network response is lost, Jarvis says the
save is unconfirmed: check the captures folder before retrying. A successful save
with a display failure is reported as saved and searchable, with a visual error.

Acceptance test:
1. Click Mic and say: **remember that the finish window should be 900 milliseconds**.
2. Expect one short spoken confirmation and a new star, without a page reload.
3. Immediately ask: **What should the finish window be?** Expect **900 milliseconds**
   with the new capture as a source.
4. Check the real Markdown in `notes/captures/`. Restart and refresh to verify persistence.

Automated capture tests run in temporary folders and never add test notes to your
brain: `python3 preflight.py`, `node tests/voice.cjs`, `node tests/sources.cjs`.


## Screen sight (Prompt 06)

Restart the Python server and refresh Chrome. Click **Screen**, then choose the
screen, window, or tab in the browser picker. **SCREEN SHARING LIVE** stays visible
until sharing stops. Audio is not captured. Click **Stop sharing** or the browser's
stop control to end the stream. **Use notes** ends sharing and restores normal chat.

While sharing, typed and spoken questions go to `/see`. Explicit recall triggers
such as **remember that** still save text through `/remember`. Each screen question
captures exactly one frame at submission time, scales its long side to at most
1600 pixels, and encodes JPEG at `SCREEN_JPEG_QUALITY = 0.82`. The JSON envelope
contains `question`, base64 `image`, and `media_type: image/jpeg`; the HTTP envelope
is `application/json`. No startup frame is cached. Unavailable, muted, or ended
streams refuse capture. Ending or changing the share during a request discards
that answer. Ended screen mode remains explicit until sharing again or Use notes.

The configured brain backend and model remain unchanged. Codex image support is
checked with `codex exec --help`; supported versions receive `--image` with a
private temporary JPEG outside the repository. Temporary files are removed on
success, failure, and timeout. Unsupported CLI versions return a spoken butler
error. The API backend uses an `input_image` base64 JPEG data URL. Vision has its
own `SEE_TIMEOUT_S = 120`; the browser allows 130 seconds including transport.
Thinking remains visible throughout. Results use the existing speech gate,
including mute and stop. Frames and screen answers never enter notes or chat
history. The model is instructed to admit unreadable details rather than guess.

Live acceptance:
1. Restart the server, refresh Chrome, click Screen, and select a harmless window.
2. Ask **what am I looking at**. Expect the actual contents described on screen
   and spoken, with Thinking visible until completion.
3. Change the shared content and ask again. Expect the new contents.
4. Stop sharing and ask again. Expect an explicit ended-share response, no `/see`
   request, and no remembered description. Use notes restores ordinary questions.
5. Stop sharing while Thinking. Expect the old answer to be discarded.

Verification in the coding session: `python3 preflight.py` passed 15 checks;
`node tests/voice.cjs`, `node tests/sources.cjs`, and `node tests/screen.cjs` passed.
Checks cover both backend payloads, JPEG rejection, temporary-file cleanup on
success/error/timeout, no vision history, fresh frames, downscaling, thinking,
and ended shares. Installed CLI help confirms `-i, --image <FILE>...`.
Live verification remains pending: this session cannot bind port 4700, and a real
CLI attachment probe returned a brain-connection error. No live screen answer
was obtained; the automated doubles are not an end-to-end demo.
