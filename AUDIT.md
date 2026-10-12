# Jarvis migration and audit — October 12, 2026

Scope: Prompts 01–07. Prompt 08 is not built and was explicitly excluded.

## Location and recovery

The working checkout is `/Users/fwnivaen/.codex/.chatgpt-projects/g-p-6ac83442ec1c8191b488a8adf6db36db/jarvis` on Nivaens-MacBook-Pro.local. The server binds to 127.0.0.1:4700. GitHub origin is `https://github.com/fwnivaen/Jarvis.git`, branch main.

The remote audit found no pull requests or unmerged remote branches to recover. The user reported no saved ChatGPT Work files. The other local copy, `/Users/fwnivaen/Documents/Codex/2026-10-08/new-chat-5`, ends at Prompt 02. Its feature code was already superseded. Its useful offline regression tests were adapted into `tests/test_offline.py`; neither that old folder nor any configuration or keys were copied or changed.

The old persona stash remains untouched. Recommendation: retain it until Prompt 08 is complete, then review and drop it with explicit approval if nothing unique remains.

## Changes

- One shared persona prefix for chat and sight; occasional sir, without mandatory insertion.
- Unrelated captures link to one derived Captures hub, retained through rebuilding from saved links. The hub is excluded from the spoken note count.
- SEE_MAX_PX naming and the requested OpenAI-only sight fallback.
- Numeric FINISH_MS validation; non-900 values warn. Offline tests run in quick and full preflight.
- Standard-library offline regressions use temporary notes, mocked brain calls, and no network. Coverage includes graph/retrieval, answer validation, request security, history, failure handling, hub persistence/cleanup, and the native speech bridge's origin/token/cleanup rules.
- Daily start.sh, README instructions, and clear missing-notes errors. Existing localhost binding and secret ignores remain intact. Configuration and keys were never printed, moved, or committed; config.json has no commits in fetched Git history.
- Mac-native on-device speech fallback for the embedded browser's recognition network failure. Microphone/Speech Recognition permission and enabled macOS Dictation are required. The user authorized enabling Dictation after reviewing its disclosure. Optional audio sharing for improving Siri/Dictation was declined.
- Native transcripts are temporary; recording stops while answering, on Mic off, or after an abandoned session's heartbeat expires. A speech-output transcript reset prevents buffered answer echo from becoming the next question.

## Verification

17 offline regression tests pass. Browser simulation suites for voice, source camera, captures and screen sight pass, including native fallback and speech echo regression coverage.

Full live preflight: `12 pass, 0 fail, 2 warn`. The two warnings skip inactive OpenAI API checks while Codex CLI is active. Live note answers, configured-model access, capture save/recall/cleanup, and JPEG vision passed. Earlier port binding and CLI sign-in blockers are resolved on this Mac. Some transient backend failures occurred during the audit; subsequent full runs passed, so future external-service availability is not guaranteed.

The user confirmed a spoken note question, camera movement, mid-sentence pause handling, small-talk camera stability, voice operation, and screen sight. Immediate capture recall was verified by live preflight. Prompt 08 model-switch tests were excluded.

The approved 900 ms test capture was deleted after the guided checks. Jarvis was rebuilt and restarted with 30 notes and 95 connections. No ordinary notes were deleted.

## Tomorrow and Prompt 08

Start with:

```sh
/Users/fwnivaen/.codex/.chatgpt-projects/g-p-6ac83442ec1c8191b488a8adf6db36db/jarvis/start.sh
```

Use **On your computer** for future chats and this same checkout. Read AGENTS.md and this report before continuing. Prompt 08 should build runtime-only brain switching, the backend/model chip, the exact-name dictionary and its preflight checks. Gemini and OpenRouter were not added during this audit.
