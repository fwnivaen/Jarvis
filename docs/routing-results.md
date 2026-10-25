# Adaptive routing verification

Local macOS arm64, isolated optional CPython environment; 2026-10-25. Baseline source revision: `62593f5cf9ec1a546d6adc4dc505708de1c3e018`. Verified implementation: `b892f033f4bef19af3747d593bfe40c02255aeab`, pushed to main. Candidate files are recorded by SHA-256 in the private reports; the final source manifest is recorded in the checklist. No remote deployment or learning promotion is implied.

## Deterministic verification

The final full suite runs **299 Python tests, zero skips**, plus all **14 browser-controller suites**. Thirty new routing tests cover exact local operations, profile selection, explicit worker refusal, scoped context/gap disclosure, unknown usage, shared concurrent budgets, interruption of other active turns, checkpoint accounting, objective escalation, terminal auth/quota failures, manual Astra and graph behavior. Existing checks and assertions remain intact.

Command: `python3 tools/check_ultra.py --embeddings`. Evidence: `.local/upgrade-evidence/routing-final-regressions.txt`. Baseline full preflight: **14 pass, 0 fail, 2 warn**. The first candidate preflight returned **13 pass, 1 fail, 2 warn** because the running foreground reader could not read the current browser tab. The fresh diagnostic was healthy; no Focus code was changed. Subsequent results are recorded in the checklist rather than erasing this attempt.

The required visible Chrome probe passed after selecting the actual probe tab and resetting the host's 90% page zoom. Full title:

```text
FOCUS PROBE: 16 pass, 0 fail | 1440x900 | PASS viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

The tab's host was `127.0.0.1:4700`, visibility was `visible`, dimensions were read from the real document, and a native Chrome screenshot confirmed the probe was selected. Temporary viewport overrides were reset and original 90% host zoom restored afterward. The native Window menu later established four browser windows. The viewer's galaxy/orb/chat design was inspected without frontend changes.

## Model-backed synthetic trials

Each arm uses the same source facts and existing checked app-server harness. The baseline is Astra High in that harness; it is not a legacy CLI latency benchmark. Quality checks require expected facts/source IDs, no partial/error answer, and the existing exact-quote and arithmetic validators. Every planner/worker/retry is included in accounting. No private notes or credentials were included.

| Case | Astra calls / seconds / tokens | Adaptive calls / seconds / tokens | Objective checks |
| --- | --- | --- | --- |
| Arithmetic with extra formatting instruction | 1 / 4.038 / 6,055 | Luna High: 1 / 4.148 / 6,445 | Both pass |
| Exact note command | 1 / 3.541 / 6,106 | Local: 0 / 0.000 / 0 | Both pass |
| Focused fact | 1 / 4.152 / 6,100 | Luna High: 1 / 3.486 / 6,406 | Both pass |
| Dependency planning | 1 / 13.652 / 6,433 | Sol Medium: 1 / 10.232 / 6,416 | Both pass |
| Conflicting revisions | 1 / 4.580 / 6,187 | Sol High: 1 / 8.257 / 6,439 | Both pass |
| Explicit two-agent team | 1 / 10.490 / 6,406 | Sol plan + two Luna workers + Sol synthesis: 4 / 36.090 / 27,024 | Both pass |

The exact local arithmetic path is independently covered by deterministic execution tests. The live arithmetic example intentionally includes additional wording and therefore follows the model path; it does not demonstrate zero-call arithmetic.

The initial trial completed six model turns and then received `quota_exhausted` before its Sol planning turn. The individual call's usage is null with `usage_complete: false`; its old aggregate `reported_tokens: 0` means no tokens were reported, not a verified zero-token turn. The runner now emits null when every call is unknown. It stopped immediately with no fallback. A later authoritative snapshot from JARVIS's exact Codex connection explicitly allowed included usage with valid quota windows. Only then were the three unfinished case pairs run in a separate report: nine calls, all six answers passed. The earlier refusal and later recovery both remain in evidence.

The first three pairs preceded budget-cancellation/context-disclosure hardening. The complex pairs precede a scheduling refinement that removes implicit automatic teams; their explicit request profiles are unchanged. These are development smoke trials, not one frozen statistical benchmark. The table combines the completed pairs transparently and does not hide the earlier failed admission or repeated planning baseline.

Evidence: `.local/upgrade-evidence/routing-live.json`, `routing-cli-usage.json`, `routing-live-complex.json` and their text logs. Reports include exact candidate hashes and supported efforts. Total pilot work: **16 admitted/reserved model attempts across the two trials**, including the refused attempt, with known usage on 15 completed turns. Provider cost and included-allowance savings remain unknown.

A separate real LangGraph/Codex/tool trial completed a focused Work request against synthetic notes in **5.649 seconds**, using one Luna High call and **12,796 reported tokens**. The model called registered `note_read`, returned the required fact and source, and cleanup completed. This is a live graph/tool integration check, not a scripted model or a remote run. Evidence: `routing-live-work.json`. It adds one completed model turn beyond the paired pilot accounting above.

## Conclusions and limits

Exact note retrieval avoids inference. Luna passed the focused examples. Sol Medium/High passed the demanding examples. Explicit teams worked, but consumed more time and tokens, so implicit automatic team creation was removed. Context compaction, selective review and bounded attempts are implemented; general success rate, per-family quality floors, p95 latency and account-allowance savings are **not established** by six exposed cases. Larger fresh paired cases are needed before making those claims or enabling a learned router. No result establishes the original remote/GEPA acceptance targets.

See [the persistent checklist](routing-checklist.md) for activation, final full preflight, live HTTP/Work evidence, source/package audits and outstanding work.
