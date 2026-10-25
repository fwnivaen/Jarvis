# JARVIS execution upgrade — persistent checklist

Contract: user attachment “Implement JARVIS with Deep Agents, remote workspaces, and evaluated learning”, 2026-10-24. Baseline revision `77581c7b4c58aad67d5eca8fff465918cce019c8`; clean `main`. Files under project `sources/` are read-only. No configuration, credentials, auth caches or personal profiles may enter artifacts or Git.

Implementation is distinct from acceptance. An unchecked gate stays off. Existing executor and interface remain the default. One admitted run and at most three internal workers remain unchanged.

## Gates and outstanding work

- [x] Usage constraint (user continuation), implemented and locally verified: enforce the existing ChatGPT/Codex subscription route; block separately billed API providers even when keys or model aliases exist. Check authentication/allowances without logging identity or credentials. No credit purchases, automatic resets, paid fallback, or unverified free-provider claims. See [policy and limits](usage-policy.md).
- [x] Usage local verification: 12 new provider/auth/quota/cancellation boundary tests; 269 Python tests with zero optional-environment skips and 14 browser suites; real signed-in CLI/preflight and app-server gateway tool/schema/usage checks. Full preflight **14 pass, 0 fail, 2 warn**. A usage snapshot is not a provider-side hard spending cap. The required visual gate below remains open.
- [x] Included-usage code committed/pushed: `9acd7abe1b1918c2e477935cfd5eb70cb5ce556b`; remote main hash checked. Source-only archive includes policy module/docs; 108 files, zero private entries, no upload. Primary local server runs the tested code with original settings. No deployment or optional feature enabled.

- [x] A: Locate actual repository and read applicable instructions; inspect baseline and prior pilot.
- [x] A: Standard Python baseline: 184 tests, 25 skipped; full live preflight: **14 pass, 0 fail, 2 warn**. Raw evidence: `.local/upgrade-evidence/baseline-{python,preflight}.txt` (private, untracked).
- [x] A: Optional baseline: 184 tests OK, one skipped; all 14 browser suites pass. Galaxy/probe references saved privately.
- [ ] A: Required visible **1440×900** probe. Baseline and updated probes report **15 pass, 1 fail at 1600×1000** despite the supported viewport override. Do not count this as a timing pass.
- [ ] A: Representative model-backed Work/cancellation/import/preferences/local-capability and latency/usage baseline. Existing preflight does not establish all of these.
- [x] B implementation/fixtures: durable scoped identities, version pins, shared budgets, operation receipts/uncertainty, cancellation fencing and adapter capabilities.
- [x] B local compatibility: graph reads, Ultra, HTTP tool calls, native note/capture/preference/import writes and MCP use ToolSession/gateway. Work UI request keys deduplicate admission. A cancelled read retains admission until its callback settles. Interrupt acknowledgment requires terminal turn confirmation or process termination.
- [ ] B: Authenticated per-task ownership across all legacy HTTP/MCP and local capability boundaries, including MCP process restart; full compatibility acceptance.
- [x] C implementation/fixtures: actual pinned SDK graph/helper, isolated CPython 3.12, authenticated protocol, note tools, virtual scratch, compiled child, reviewed procedure declaration, schema/error/cancellation tests.
- [ ] C: Actual model endpoint compatibility and paired benefit comparison; activation OFF. The included-usage-only constraint now rejects live API calls even when a key exists. A supported included-usage raw-model integration requires implementation and validation; never wrap CodexBridge as a raw model.
- [x] D preparation/fixtures: durable scheduler, private operator spool, systemd supervision, source-only packaging, SQLite backup/restore and operator teardown instructions. Malformed/insecure spool requests quarantine without cancelling other work. No deployment or remote viewer integration.
- [x] D dependency metadata: official revisions/licenses and image digests verified; hash-lock binary resolution passes for Linux arm64/amd64. This is not a Linux installation.
- [ ] D live: **BLOCKED: user confirmed no verified Oracle account.** No Docker/OCI CLI/config exists locally. Next: private account verification, actual free allowances/capacity, selected Linux runtime and fresh login. No paid fallback authorized.
- [x] E implementation/fixtures: durable workspace leases, creation/readiness, exact-session screenshot Watch, internal deny-egress network, independent expiry/reaper, cleanup semantics, signed mTLS RPC and replay protection.
- [ ] E implementation: vetted external-navigation egress proxy/firewall, bounded element input, atomic approved artifact transfer and viewer authentication/stream integration. Remain unavailable; live image behavior must be checked first.
- [ ] E: Remote live network/profile/file isolation, 19/20 browser fixtures, confirmed container cleanup. Takeover OFF until race tests pass.
- [x] F local: existing styles retained; supported controls, cleanup-pending state, stable note identity/revision resolution and historical-source warning. Saved Work view inspected; no agent tabs opened.
- [ ] F acceptance: full accessibility/reconnect/remote unavailable-capability acceptance; Watch/input controls only after E passes.
- [x] G implementation/fixtures: minimized opt-in graph and scheduler outcomes for either adapter, real offline GEPA helper, bounded candidates, signed reports and separate review, atomic promotion/rollback, deletion.
- [x] G evaluation preparation/fixtures: private 24 topic-disjoint synthetic cases (8/8/8); five arms × eight protected cases × three repetitions = 120 scripted executions. Existing source/arithmetic checks, paired case-cluster intervals and complete accounting gates. These are not learning evidence.
- [ ] G live acceptance: separately owned protected evaluator/proposer/reviewer; paired model runs with all proposal/reflection/retry/baseline/final costs; fresh protected cases; canaries and next-run serving activation. No learning gain claimed; promotion stays off.
- [x] H deterministic boundary coverage: identity/escalation, duplicate/uncertain effects, cancellation/settlement, SDK, scheduler recovery, workspace cleanup, RPC replay, poisoned lessons, evaluation, backup/restore and stable citations. Existing assertions retained; MCP assertions strengthened for per-RPC replay keys and hidden Context; native Unicode/revision tests retained.
- [ ] H acceptance: full preflight/probe and zero critical regression. Latest summaries are in [the evidence ledger](upgrade-evidence.md); the required viewport remains unverified.
- [ ] H: Real 24-hour remote soak, restored backup and coordinated physical Mac-off test from a second client. BLOCKED by deployment and user coordination; never shut down this implementation host.
- [x] Commit verified changes and push `origin main` per repository instructions: implementation `f9dc6634b11fb036dd0d84aed3cef39240f394ae`. Subsequent record-only commit preserves the tested source manifest. All unchecked gates above remain open.

## File-level plan / dependency matrix

| Files | Purpose | Depends on / activation gate |
| --- | --- | --- |
| `execution_control.py`, `execution_gateway.py` | stdlib durable identities, leases, lifecycle, journal, admission and scoped tools | B fixtures; no larger concurrency |
| `usage_policy.py`, `codex_bridge.py`, `server.py`, `preflight.py`, `tests/test_usage_policy.py` | enforce included ChatGPT usage, reject API selection/unknown quotas, preserve cancellation and terminal errors | live local sign-in/allowance/protocol evidence; Linux compatibility remains gated |
| `execution_adapters.py`, `workflow_runtime.py`, `ultra_tools.py`, `server.py`, `tools/ultra_mcp.py` | explicit existing-executor adapter and gateway migration | preserve validators, bounded deadlines, legacy behavior |
| `optional/deepagents/`, `tools/setup_execution.py` | pinned SDK helper with virtual scratch and declared tools | SDK fixture tests then actual model endpoint |
| `remote_workspaces.py`, `deploy/remote/` | browser ownership, worker protocol, network policy, supervision, backup and cleanup | Linux/Docker + isolation + authentication; no paid provisioning |
| `outcome_collection.py`, `learning_gate.py`, `execution_evaluation.py`, `optional/gepa/` | sanitized outcomes, offline proposals, paired evaluation and reviewed promotion | stable frozen baseline + fresh protected evidence |
| `viewer/workflows.js` | only controls backed by advertised runtime capabilities | prior gate verified; no design or build changes |
| `tests/test_execution_*.py`, `tests/test_remote_*.py`, `tests/test_learning_*.py` | deterministic failure and compatibility evidence | tests label fixture vs live |
| `docs/upgrade-*.md`, `dependencies/execution-manifest.json` | evidence ledger, contracts, provenance, operations, rollback | updated each stage |

## Migration and rollback

New optional features default off independently: Deep Agents, remote workspaces, outcome collection, promotion. Do not change model/provider/billing. New private stores use separate versioned paths; do not rewrite existing notes or graph IDs. Back up SQLite using its backup API, restore into a fresh private directory, validate before use. Rollback: stop controller/workers, fence leases, confirm workspace destruction (otherwise cleanup pending), disable the affected feature, restore prior executable revision and retain the private journal for uncertainty reconciliation. Preserve the included-usage restriction in any rollback; never restore paid API selection as a workaround. Never delete a pending write and replay it. Running tasks pin their initial engine/model/tools/approved bundle. Candidate instructions cannot change enforcement.

## Evidence rules

Each row in `upgrade-evidence.md` records revision, environment, procedure, result, evidence and limits. Fixture success never passes remote/model/soak gates. A callback timeout fences results but does not establish stopped underlying work. Production routes remain disabled when their acceptance gate is incomplete.
