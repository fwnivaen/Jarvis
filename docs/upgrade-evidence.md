# Upgrade evidence ledger

Baseline: `77581c7b4c58aad67d5eca8fff465918cce019c8`, clean main. Candidate source manifest: `6a2d6dc838ba071d4b6ae341850623bda1d0cec9320c51307ec92bb45e9e942c`. This hash covers indexed executable/configuration/dependency/test inputs and is recorded privately in `.local/upgrade-evidence/reviewed-source-manifest-final.json`; documentation edits are excluded. Implementation commit: `f9dc6634b11fb036dd0d84aed3cef39240f394ae`, pushed to `origin/main`. The subsequent documentation-only record does not alter the tested executable tree. Evidence was collected on 2026-10-24 local time (some timestamps are 2026-10-25 UTC).

Raw logs, screenshots, downloaded upstream material, private stores and reports remain under ignored `.local/`; they are deliberately excluded from Git and the source archive. The sanitized summaries below are persistent evidence. A fixture pass does not pass a live remote/model/soak gate.

| Gate | Revision / environment | Procedure | Actual result | Evidence / limitations |
| --- | --- | --- | --- | --- |
| A inspection | baseline, macOS arm64 | Git/instructions/runtime/source and prior-pilot inspection | clean main; one admission, three workers, bounded deadline; earlier pilot preparatory only | Previous recommendation/pilot files inspected; no deployment inherited. |
| A system Python baseline | baseline, CPython 3.9 | `python3 -m unittest discover -s tests -p 'test*.py'` | 184 tests OK, **25 skipped** | `baseline-python.txt`; optional tests excluded. |
| A optional baseline | baseline, isolated CPython 3.12 | Existing optional test suite and all browser CJS suites | 184 tests OK, **one skipped**; 14 browser suites pass | `baseline-optional.txt`, `baseline-browser.txt`; embeddings later exercised explicitly. |
| A baseline preflight | baseline, original running loopback server | `python3 preflight.py` | **14 pass, 0 fail, 2 warn** | `baseline-preflight.txt`; warnings are API checks skipped for Codex sign-in. |
| A diagnostics | baseline and current, long-lived server | GET `/focus/diag`; read ledger structure/aggregate keys; native/browser inventory | Fresh tick and readable non-browser foreground at inspection; five session entries; legacy aggregate present. Chrome running; **window count unavailable** | No app/tab identities or ledger contents recorded. Assistant tab host originally `127.0.0.1:4700`; no agent-created tabs. |
| A/F visible probe | baseline and candidate, visible Chrome | Supported viewport request 1440×900; navigate to `?focusprobe=1`; inspect full title | **15 pass, 1 fail at 1600×1000; FAIL viewport** | `baseline-focus-probe.png`, `verified-focus-probe.{txt,png}`. Three observed attempts returned wrong dimensions. Override reset. This gate fails. |
| B/C/E/G/H optional regressions | candidate, isolated CPython 3.12/macOS arm64 | `python3 tools/check_ultra.py --embeddings` | **257 tests OK; zero skipped. All 14 JavaScript suites pass.** | `verified-check-ultra.txt`. Actual installed SDK/GEPA with scripted models, real SQLite/files/subprocesses and embeddings; remote provider and transport fixtures use doubles. |
| H standard-library compatibility | candidate, system CPython 3.9 | `python3 -m unittest discover -s tests -p 'test*.py'` | **257 tests OK; 28 skipped** | `verified-python.txt`. Optional dependencies are absent from core environment. |
| B native write boundaries | candidate, synthetic vault | Four new native gateway tests plus original 17 note-store/edit tests and optional document tests | Pass: duplicate/conflicting keys, uncertain-write refusal, original Unicode maximum/revision checks, feature switches, numeric-ID remap and later-source drift | `native-gateway-check.txt`, `native-note-check.txt`, `native-import-check.txt`; original assertions retained. MCP Context schema and distinct per-RPC identities also tested. |
| F native UI save | candidate, running server and visible browser | Create disposable synthetic preflight capture; edit through Notes → Review → Save; read file; restore original; invoke scoped test cleanup | UI displayed **Changes saved**; exact file read-back; original restored; fixture removed; 30-node/95-link graph restored | `native-ui-acceptance.json`, `verified-native-edit.png`. No existing note edited; this is local live UI evidence, not full accessibility acceptance. |
| H intermediate preflight failures | earlier candidate, running server | Repeated full live preflight after a long session gap | **13 pass, 1 fail, 2 warn** (foreground read); then **10 pass, 4 fail, 2 warn** (foreground read and transient Codex model/recall/vision calls) | `final-preflight.txt`, `final-preflight-recheck.txt`. These attempts are retained rather than replaced by the later success. No model/billing/auth-cache change made. |
| H latest full preflight | candidate after final native/MCP/spool edits, isolated test server on loopback 4703 | `python3 preflight.py --url http://127.0.0.1:4703` | **14 pass, 0 fail, 2 warn** | `verified-preflight.txt`. Includes real model swap/chat/recall/image, native capture-file-immediate-recall-cleanup, served-byte equality and configuration privacy. API checks skipped because Codex sign-in is active. |
| B local live Work | earlier candidate with final bridge cancellation semantics; real signed-in model | Submit, poll authoritative status/progress, validate sources/usage, replay same admission | Complete: acknowledgment 0.766 s; first progress **1.199 s (misses target)**; elapsed 13.910 s; one revisioned source, one tool call; 16,148 reported tokens; same replayed run | `live-work-confirmed.json`; run `44ff53fcb672059a70e294df`. Cost unknown. Sample precedes final native-route edits; not a success-rate or p95 estimate. |
| B local live Stop | same environment | Start separate read-only run; Stop; poll until underlying executor settled | acknowledgment 0.003 s; confirmed settlement 0.218 s; cancelled/cleanup complete; late result discarded | Same report; run `c172a5266e8928f307ee153a`. Ordinary local read-only work only. |
| B local graph load fixture | candidate graph implementation, scripted model | 20 serial graph runs plus competing admissions; bounded worker/cancel measurements | 20/20 complete; 20 competing admissions rejected; max three workers; median 84.897 ms/p95 491.244 ms; cancellation 11.262 ms; peak RSS 74,547,200 bytes; SQLite 1,118,208 bytes | `final-graph-fixture-benchmark.json`. Zero model calls; macOS process measurement, not remote/browser capacity. |
| C/G optional dependency installation | macOS arm64, CPython 3.12 helpers | Official pinned binary wheels/hash locks and `pip check`; actual-library fixture tests | Deep Agents 0.7.32/langchain-openai 1.7.2 and GEPA 0.1.4 isolated; compatibility checks pass | `deepagents-install.txt`, `gepa-install.txt`; source snapshot API differs from release, actual release interfaces used. No live separately billed model call. |
| C/D upstream provenance | official GitHub/PyPI/docs and Docker Hub metadata | Check reference commits, maintenance, licenses, selected APIs and multiarchitecture manifests | Four references verified; selected MIT SDKs and Apache-2.0 Selenium; image index/arm64/amd64 digests pinned | `dependencies/execution-manifest.json`, `execution-packages.json`, hash locks and license copies. Webtop not selected. Docker image not executed. |
| D binary Linux resolution | Linux platform constraints simulated by pip on macOS | CPython 3.12 arm64/amd64 binary-only dry-run with required hashes | Both lock resolutions pass | `linux-{arm64,amd64}-lock-resolve.txt`; **not a Linux installation/runtime/model check**. |
| D provider access | local instruments and explicit user reply | CLI/config existence checks; account availability question | No Docker/OCI CLI/config found; user: **No verified account yet** | Provisioning blocked. Current official terms reviewed; actual account allowances/capacity unknown. No paid resource or account created. |
| D controller spool | candidate, real private SQLite and temporary files | Valid request beside malformed JSON, insecure file and symlink | Two tests pass; bad entries quarantined without losing valid admission or reading symlink target | `tests/test_remote_controller.py`; local fixture, not systemd/Linux deployment. |
| D backup/restore | candidate, real local SQLite | Backup API, integrity check, restore into fresh directory, deliberate checksum corruption | Contents restored; corrupted backup rejected | Compatibility suite. **No remote application restore performed.** |
| D package/repository hygiene | candidate indexed source | Source-only allowlist archive, manifest hash audit, secret/state exclusions, link checks and whitespace checks | See finalized package audit below | No notes/config/auth/profile/native binaries/private stores/reference materials selected; archive is local and not uploaded. |
| G five-arm evaluation | candidate, scripted executors | Generate 24 topic-disjoint synthetic tasks (8/8/8); eight protected × three repetitions × five arms | 120 scripted protected executions exercised; expected answers stay with verifier; complete cost/critical/family/parent/signature gates tested | `tests/test_execution_evaluation.py`, `test_learning_gate.py`, [evaluation protocol](upgrade-evaluation.md). Exposed debug set is consumed; fresh protected topics and real costs required. No learning gain. |
| D/E/G/H remote acceptance | no deployment | Linux login/model, mTLS browser, network/profile/file isolation, resource cleanup, 19/20 browser runs, host load, restored application, 24-hour soak, Mac-off test | **Not tested / blocked** | No deployment identifier, remote artifacts or independent runtime. Never shut down implementation host to simulate acceptance. |

## Required summary lines

Latest full preflight:

```text
14 pass, 0 fail, 2 warn
```

Full visible Focus probe title:

```text
FOCUS PROBE: 15 pass, 1 fail | 1600x1000 | FAIL viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

The probe was visible but wrong-sized, so acceptance is **failed**, not a timing pass. Historical 16/16 results from earlier work do not pass this upgrade's required probe.

## Remaining limits

No full five-arm model comparison, comparable live p95, 90% supported-task success estimate, exact provider cost accounting, below-80% sustained Linux RAM measurement, real browser trial, live read-only viewer, takeover race, 24-hour remote soak, restored remote application or physical Mac-off independence is verified. No private configuration, credentials, authentication cache or browser profile was copied. The original 4700 server was unavailable when work resumed; only agent-owned 4703 test servers were restarted. The browser was returned to its original address and viewport override reset. See [capability status](upgrade-results.md) and [unfinished checklist](upgrade-checklist.md).

## Finalized package and repository audit

- Source manifest: **158 indexed inputs**, SHA-256 `6a2d6dc838ba071d4b6ae341850623bda1d0cec9320c51307ec92bb45e9e942c`.
- Source archive: **101 files**, **15,361,183 bytes**, SHA-256 `b91deb3e2762467ebfeb7cb5344e420a6537e2e1a22460e66009118c7ab372dd`. All embedded manifest hashes match; zero forbidden entries; no upload.
- Private archive: `.local/jarvis-remote-source-verified.tar.gz`; private audit: `.local/upgrade-evidence/package-audit-final.json`.
- `python3 tools/check_repo.py`: **Repository check: 240 files, 165 local links, 0 failures**.
- Both working/indexed whitespace checks pass. Only reviewed source, tests, templates, locks, licenses and sanitized documentation are staged; private artifacts remain ignored.
- Final review strengthened the 90% per-family promotion minimum and retained the explicit rejection test; it did not lower acceptance floors. The final full suite and preflight passed afterward.

## Commit and cleanup record

Implementation commit `f9dc6634b11fb036dd0d84aed3cef39240f394ae` was pushed successfully to `origin/main`. The 67 reviewed staged files had zero forbidden paths and zero credential-pattern matches. Private evidence/archive/configuration stayed untracked. The agent-owned loopback test server was stopped after verification; no listener remains on its test port. No cloud deployment exists. Checklist and ledger completion metadata are recorded in a following documentation-only commit.

## Included-usage continuation — 2026-10-24

User constraint: continue using free resources/the existing ChatGPT CLI account. Base revision `7e5ee804b8a97861316128d757421d3ccd4eb357`. The tested source is identified in the follow-up commit record. Source-only policy changes do not activate Deep Agents, cloud workspaces, collection or learned behavior. Original private configuration and Codex credential stores remain in place.

| Gate | Environment / procedure | Actual result | Private evidence and limits |
| --- | --- | --- | --- |
| Usage authentication/routing | Installed Codex CLI 0.162.0-alpha.17.2, existing private sign-in; account/read, effective config/read and fresh account/rateLimits/read | ChatGPT authentication; OpenAI provider; standard tier; explicit ordinary included usage allowed | Only fixed route/permission fields inspected/reported, no identity/credentials or credit balance logged. No API key authentication probe, credit purchase, reset redemption or billing change. |
| Usage regression | Optional CPython 3.12, actual SDK/GEPA fixtures and local embeddings; `python3 tools/check_ultra.py --embeddings` | **269 Python tests OK, zero skips; 14 browser suites pass** | `included-usage-final-checks.txt`. 12 new usage tests cover keys/config/aliases, unknown/exhausted and multibucket quotas, provider/tier, revoked auth/queued tools, terminal failures and cancellation/expiry during admission. Original timeout/cancellation assertions retained; their fixtures now include account/usage RPCs. Legacy API transport assertions retained under explicit test-only policy override. |
| Intermediate failures | Earlier fixture/preflight attempts | First suite: 3 failures/1 error from old RPC fixtures lacking account/allowance responses. First preflight: **11 pass, 3 fail, 2 warn** (old fixtures, foreground reader, old key-refusal wording) | `included-usage-regressions.txt`, `included-usage-preflight.txt`; retained. RPC fixtures and refusal assertions updated for the actual new contract; original behavioral assertions retained. Subsequent complete regression/preflight runs passed. |
| Actual app-server gateway call | Live signed-in Luna/high, synthetic note only, ToolSession gateway and structured output schema | One `note_read`; correct answer/source; valid token accounting; 5.219 s, 11,903 cumulative reported tokens | `included-usage-live-tool.json`. No API key/provider substitution; cost unknown. This sample precedes the final cancellation-during-admission guard; that guard is covered in the final full tests/preflight. Not a benchmark or Linux evidence. |
| Live paid-provider refusal and UI | Running loopback server GET /model, full preflight swap/refusal; existing browser model chooser | Only Codex models available; both OpenRouter buttons disabled with included-usage explanation. Galaxy restored, 30 notes/95 links, devices off | `included-usage-live-model-policy.json`, `included-usage-model-chooser.jpg`. No model/provider change, new tab or optional feature activation. |
| Full preflight, final serving source | Primary server in optional environment on loopback 4700; `python3 preflight.py` | **14 pass, 0 fail, 2 warn** | `included-usage-serving-preflight.txt`. Warnings are the two API checks skipped for the Codex route. Actual ChatGPT model swap/chat/recall/image and synthetic capture/save/recall/cleanup passed. |
| Required Focus probe | Existing Chrome tab, supported 1440×900 viewport override | **15 pass, 1 fail at 1600×1000 — FAIL viewport** | Full title below. Browser reports visible; native inventory reports the Mac locked, so physical visibility/window count could not be established. Required gate stays failed. Override reset; original tab returned to primary JARVIS. |

Latest required summaries:

```text
14 pass, 0 fail, 2 warn
FOCUS PROBE: 15 pass, 1 fail | 1600x1000 | FAIL viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

Running Focus `/focus/diag` was queried; diagnostic fields and live tick passed the final preflight. Session ledger has five records; legacy numeric aggregate exists. Native browser-window count is **unavailable**, because the Mac was locked. The assistant-controlled tab's host was verified as the primary loopback server. A browser visibility bit does not establish physical unlocked visibility, and the wrong viewport alone fails acceptance.

The installed protocol exposes no atomic included-only spending reservation or reliable free-versus-purchased credit classification. A fresh snapshot can race shared account usage or an in-flight turn. No provider-enforced zero-charge guarantee, free API credits, Linux readiness, remote operation or learned improvement is claimed. See [usage policy](usage-policy.md) for enforcement and recovery. Oracle verification, unfinished ownership/browser/learning implementation and every other open acceptance gate remain in [the checklist](upgrade-checklist.md).

### Follow-up revision and package audit

- Implementation `9acd7abe1b1918c2e477935cfd5eb70cb5ce556b` pushed successfully; `refs/heads/main` was read back with the same hash.
- Tested code manifest: **118 indexed Python/JavaScript/browser-test/shell inputs**, SHA-256 `9b5b4cb9a6063600e2fad9f3b0f85065f8b25f07aac69394ebec5054a5f35c1d`; private manifest `included-usage-tested-source-manifest.json`.
- Archive of that implementation revision: **108 files**, **15,383,632 bytes**, SHA-256 `1fc1ce734cd3c198e97bb72eb0f90f6faaa847a5e44a9498b28a22fe432fcf90`. Includes usage module and six policy/upgrade guides. All embedded file hashes match, zero forbidden/private/symlink entries, no upload. Private artifact `.local/jarvis-remote-source-included-usage.tar.gz`; audit `included-usage-package-audit.json`. This archive predates only this documentation record.
- Repository check: **243 files, 175 local links, 0 failures**; indexed whitespace check passed; no configuration, auth cache, API key, notes, private state or screenshot staged.
- Agent-owned test server on 4703 stopped. The primary server on loopback 4700 remains running with the tested code and original private settings; local PID/log stay ignored. Browser returned to Galaxy, temporary viewport override reset, microphone/camera/screen controls remained off. No cloud resources or billing settings changed.

## Adaptive-routing continuation — 2026-10-25

Base revision `62593f5cf9ec1a546d6adc4dc505708de1c3e018`. [Detailed results](routing-results.md), [policy and research](routing-policy.md), [persistent activation/checklist](routing-checklist.md). Earlier visual/preflight failures above are historical and remain recorded.

| Gate | Procedure / actual result | Evidence / limits |
| --- | --- | --- |
| Baseline | Existing tests/preflight before edits; **14 pass, 0 fail, 2 warn** | `routing-baseline-{tests,preflight}.txt` |
| Final deterministic checks | **299 Python tests, zero skips; all 14 browser suites pass** | `routing-final-regressions.txt`; 30 new routing/budget/context/failure tests; actual optional graph/embedding environments |
| Local model comparison | Six exposed synthetic case pairs passed across two development trials; 16 reserved/admitted attempts including one quota refusal, 15 completed turns with reported usage | `routing-live.json`, `routing-live-complex.json`; candidate hashes included. Original refused attempt retained. Not a frozen statistical quality/cost benchmark |
| Quota behavior/recovery | Initial `quota_exhausted` was terminal; no retry/fallback. Later exact Codex connection returned fresh explicit ordinary usage permission and valid quota windows; only then unfinished trials resumed | `routing-cli-usage.json`; identity, credentials and credit balances excluded. Shared usage can change between reads |
| Live Work/tool integration | Real LangGraph/Codex Luna High, synthetic source, registered `note_read`, correct fact/source, one model call, cleanup complete; 5.649 s, 12,796 tokens | `routing-live-work.json`; one sample beyond paired pilot, not remote or statistical evidence |
| Full preflight | Candidate attempt **13 pass, 1 fail, 2 warn** (transient foreground reader); unchanged-source recheck **14 pass, 0 fail, 2 warn**; final activated service **14 pass, 0 fail, 2 warn** | `routing-final-preflight{,-recheck}.txt`, `routing-active-preflight.txt`. Two API checks skipped for Codex route. Full real swap/chat/recall/image/capture/cleanup/privacy checks |
| Required visible probe | **16 pass, 0 fail at 1440×900**; full per-case title read and selected visible native Chrome screenshot inspected | Actual probe tab selected; host 127.0.0.1:4700; page zoom reset 90% → 100%; temporary viewport reset. Native browser-window count remains unavailable from enabled inventory; it is not inferred from tab count |
| Local activation / UI | Running server confirms adaptive enabled, one admitted run/three workers, eight model-attempt/120,000 observed-token guards; included-only usage; four Work types. Viewer shows `ULTRA · LUNA / SOL`, idle Scout/Weave/Prism, working Work controls and restored 30-note/95-link galaxy | `routing-active-http.json`; private launcher flags only. Existing UI assets unchanged; old saved Work reports retain original profiles. No cloud or learning activation |
| Independent gates | Oracle account still unverified; raw-model Deep Agents compatibility, remote ownership/egress/input/viewing and live learning acceptance remain unfinished | Master checklist retains precise blockers. No remote deployment identifier, Mac-off independence, learned gain or general savings claim |

Latest required summaries:

```text
14 pass, 0 fail, 2 warn
FOCUS PROBE: 16 pass, 0 fail | 1440x900 | PASS viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

The running diagnostic was read, six session-ledger records and the legacy aggregate were inspected without recording identities, and the assistant tab host was verified. No Focus implementation was patched to obtain the pass. Explicit teams remain available, but implicit automatic team creation was removed after the live team used four calls/36.090 s/27,024 tokens versus one Astra call/10.490 s/6,406 tokens. These observations motivate a conservative policy; included allowance savings remain unknown.
