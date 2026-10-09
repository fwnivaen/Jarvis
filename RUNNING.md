# Run Jarvis

Requires Python 3.9+, an internet connection for the pinned viewer CDN libraries,
and a signed-in Codex CLI. There is no npm build or Python package installation.

```bash
cd /Users/fwnivaen/Documents/Codex/2026-10-08/new-chat-5
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

The result includes `answer`, `nodes`, and `elapsed_s`. Failure responses also
include `error: true` and use HTTP 503. A failed call does not enter history.
