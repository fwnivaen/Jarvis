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

The default backend is `codex-cli`, using your existing Codex sign-in. To use the OpenAI API later, edit only the local root `config.json`: set `brain` to `openai-api`, set `model` to an API model available to your account, and enter your own key in `openai_api_key`. Existing settings reload on each question. Never paste or commit that file or a key. API usage is billed separately. Gemini and OpenRouter are not implemented; Prompt 08 is outside this audit.

## Notes and captures

Markdown lives in `notes/`; captures live in `notes/captures/`. Unrelated captures link to one Captures hub. The hub is derived from saved links and survives rebuilds without requiring an extra note file. If the notes folder is missing at startup, the server can show and speak a clear error; the daily launcher stops before starting it. Restore the folder and restart.

The browser handles voice and screen permissions. Internet access is needed for the graph libraries and cloud brain. The old copy in Documents and the old persona stash are retained untouched.

See RUNNING.md for detailed browser checks and historical verification notes.

## Microphone inside Codex

If browser speech recognition fails, Mic switches to the bundled Mac speech helper. Build it once with `./native/build_voice.sh` (Apple command-line tools required). macOS asks for microphone and speech-recognition permission for Jarvis Voice. Recognition requires an available on-device English recognizer; audio is not sent to an API. Mic off, an in-flight question, or a closed tab stops recording. A ten-second heartbeat limit stops an abandoned session. Temporary transcripts are deleted when the session closes.
