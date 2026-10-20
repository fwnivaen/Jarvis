# Ultra Jarvis Stage 1 verification — October 20, 2026

Stage 1 is implemented for review. The committed master feature flag is OFF. Verification used a separate local server on port 4701 with Ultra enabled, leaving the existing port 4700 server running.

## Results

| Check | Result |
| --- | --- |
| Python regressions | **105 tests passed**: the existing 82 plus 23 new routing/protocol/privacy/limit tests |
| Browser controller regressions | **13 JavaScript suites passed**, including the new activity drawer suite |
| Real warm Codex connection | Luna high completed in 6.4s; Sol high completed in 4.7s; both reported usage |
| Simple request | One Luna dispatch call, zero workers, zero escalations; real request completed in 9.1s |
| Explicit parallel request | Sol planning, **3 concurrent Luna workers**, Sol final answer; all completed in **47.3s**, zero retries, zero escalations |
| Worker timings in that request | 8.0s, 4.1s, 7.7s; planner 24.5s; final check 14.8s |
| Sources in final answer | Three actual supplied note IDs; supporting quotes validated locally |
| Real image check | Full preflight's real red JPEG was correctly identified through the Luna vision route |
| Drawer | Actual model/status/time/retries/token values visible; native collapse/reopen verified; desktop and mobile screenshots saved |
| Duplicate frames | Automatic same-lease duplicates skipped; explicit fresh questions still call vision; regression tests passed |
| Failure handling | Retry and timeout tests passed; one shared promotion budget tested under racing workers; tool approvals refused; failed turns cannot return partial streamed output as success |
| Privacy | Reasoning/plan events discarded, unapproved tool requests refused, monitor has no free-text task/output fields, local-only endpoint and configuration allowlist tests passed |
| Full live preflight | **13 pass, 1 fail, 2 warn** |
| Visible Focus probe | **FOCUS PROBE: 16 pass, 0 fail \| 1440x900** |

The real three-worker request asked for independent findings from Menu Pricing, Opening Checklist and Launch Campaign. All five monitored model jobs finished successfully; the answer cited all three notes. No code, screen actions or file writes were executed by workers.

An earlier real failure run exercised the guardrails: one worker reached exactly 45.0 seconds, the request used exactly one promotion, and failed work was retained in activity state. That run exposed overly strict decimal rounding and inadequate retry-format feedback. Both were repaired, regression tested and followed by the successful three-worker run above. Explicit worker requests now bypass probabilistic cheap classification; an explicit request without workers also remains sequential.

## Remaining live limitation

Full preflight fails **Focus instruments (running server)** with “Running server cannot read foreground activity.” The pre-upgrade running server also reported foreground activity unavailable before implementation. No Focus implementation, ledger or permission behavior was changed for Stage 1. This remains a live host/access limitation; it is not counted as a pass. No physical Focus timing or audible speech result is claimed.

The two warnings are the existing OpenAI API-key/model checks, skipped because Codex subscription login is active. No API key was needed or requested.

The browser probe was visible and read from its full title at an actual page viewport of 1440 × 900. An initial wrong-size run was correctly treated as failed; the final title was:

```text
FOCUS PROBE: 16 pass, 0 fail | 1440x900 | PASS viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

Field instruments: the current numeric session ledger contained four existing entries; the legacy aggregate ledger had its expected six counter keys. No identities were logged. Controlled tab host was `127.0.0.1:4701`. Browser-window count was **missing** from the enabled UI inventory adapter, rather than inferred from tab count. Neither a fresh imported Focus object nor the simulated probe was used as evidence that the long-lived foreground reader works.

**UNVERIFIED:** actual webcam imagery and physical voice output in this session, general cost savings, benchmark/per-task price claims in the request, and future Stage 2 packages. Existing camera/voice controller regressions pass; no new permissions were granted during testing.

## Review artifacts

- [Desktop: three completed workers and final answer](screenshots/ultra-stage-1-desktop.jpg)
- [Mobile drawer](screenshots/ultra-stage-1-mobile.jpg)
- [Run, test, enable and roll back](../ULTRA-STAGE-1.md)

The complete-file archive excludes `config.json`, all keys, notes, generated graph data, virtual environments and private runtime state. Stage 2 has not been started.
