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
