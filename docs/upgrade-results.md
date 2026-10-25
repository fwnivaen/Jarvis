# Execution upgrade results — 2026-10-24

This is a staged implementation with acceptance gates still open. No remote deployment exists. The existing executor and design remain the default; Deep Agents, remote workspaces, outcome collection and promotion default off independently. Admission remains one run with at most three internal workers.

| Capability | Status | Evidence and next gate |
| --- | --- | --- |
| Durable lifecycle, scoped identities/budgets, operation receipts, scheduler and restart fencing | **Implemented; Locally verified** | SQLite, fixture and compatibility tests. Remaining: authenticated task ownership across every legacy transport and MCP restart. |
| Existing LangGraph/Codex execution, source validation and Stop | **Locally verified** | Real signed-in local Work completed with revisioned citation; interruption confirmed settlement. Linux runtime remains **Not tested**. |
| Native note/capture/preference/import gateway and replay | **Implemented; Locally verified** | Actual synthetic files, original Unicode/revision checks, duplicate/conflicting requests, uncertain-write refusal and visible Notes → Review → Save with file read-back and fixture cleanup. Physical private preference/import acceptance remains **Not tested**. |
| Official Deep Agents SDK integration | **Implemented; Locally verified** with scripted model | Actual installed SDK, virtual scratch, bounded child, tools, usage and subprocess cancellation. Live provider compatibility/benefit **Blocked** by separately authorized endpoint credentials and budget; Codex login is not an API key. |
| Linux controller, deployment services, source package, backup/restore | **Implemented preparation; Locally verified** fixtures | **Blocked**: user confirmed no verified Oracle account. Next: complete provider verification privately, inspect actual free allowances/capacity, then validate fresh Linux runtime/login. No paid fallback. |
| Independent remote browser and exact-session screenshot API | **Implemented; Locally verified** provider fixtures | Real image, mTLS network path, isolation, 19/20 trials and resource cleanup **Not tested**. Requires Linux/Docker first. No remote viewer connection exists. |
| External browser navigation, file transfer, authenticated Watch/stream and exclusive takeover | **Not tested; unfinished implementation** | Dependent on a verified browser and network boundary. Build/test egress redirect/rebinding protection and viewer authorization before activation. Current worker only accepts a synthetic page and read-only observations. |
| Minimized outcomes, official GEPA proposals, protected evaluator and reviewed promotion/rollback | **Implemented; Locally verified** fixtures | Actual GEPA library with scripted proposals; 120 scripted evaluation executions. Live learning **Not tested**; requires stable baseline, fresh protected topics, separate ownership and complete costs. |
| Canary monitoring and next-run serving of learned bundles | **Not tested; unfinished implementation** | Requires protected model-backed evaluation and reviewed promotion first. No learned behavior is serving. |
| Existing interface and local capabilities | **Locally verified in part** | Galaxy/Work visually inspected; 14 browser regression suites. Required 1440×900 Focus probe **Blocked** by viewport control returning 1600×1000. Accessibility, physical audio/camera and full reconnect acceptance remain open. |
| Remote independence | **Blocked; Not tested** | No deployment identifier. Requires live restoration, real 24-hour soak and coordinated physical Mac-off test from a second client. |

Nothing is **Remotely verified**. Prepared services and dependency resolution are not a deployed integration.

## Measurements and limits

The latest local regression run executes **257 Python tests with zero skips** in the optional CPython 3.12 environment, including the real installed SDK/GEPA fixtures and embeddings, plus **14 passing JavaScript suites**. System Python executes the same 257 tests with 28 optional skips. Full preflight and visible probe results, including failed attempts, are recorded in [the evidence ledger](upgrade-evidence.md).

One real local Work sample acknowledged in 0.766 seconds, produced first authoritative progress in **1.199 seconds** (misses the under-one-second target), and completed in 13.910 seconds with 16,148 reported tokens, one tool call and one revisioned source. Its replay returned the same run. Stop acknowledged in 0.003 seconds and confirmed cancelled settlement in 0.218 seconds, with cleanup complete. Cost is unknown. These observations precede the final native-route changes; the final preflight exercises those changed routes. One sample cannot establish 90% task success, a comparable p95 or improvement.

Twenty scripted graph runs completed, with 20 competing admissions rejected, at most three workers, median 84.897 ms and p95 491.244 ms. Scripted cancellation took 11.262 ms; peak process RSS was 74,547,200 bytes on macOS. These are fixture measurements with zero model calls, not Linux host-capacity evidence or a live latency comparison.

No five-way model evaluation, cost reduction, repeatable learning gain, production readiness or Mac-off behavior is claimed. The [persistent checklist](upgrade-checklist.md) retains all unfinished acceptance and implementation work; [operator instructions](../deploy/remote/README.md) cover deployment, private configuration, backup, restoration, teardown and rollback.
