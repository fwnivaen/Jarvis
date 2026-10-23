# Framework evaluation — October 23, 2026

## Decision

Adopt **LangGraph 1.2.16** and **langgraph-checkpoint-sqlite 3.1.2** for explicit Work-tab workflows. Preserve ordinary chat's fast route, the existing Codex account transport, typed note tools, local output/source/math validation and frontend without a build step. Use JARVIS's own activity view rather than an external Studio.

AutoGen and Flowise were excluded before runtime prototyping because both requested repositories are archived. Their relevant source and documentation were inspected; no performance numbers are claimed for them. No AutoGen/Flowise code or UI was copied. A hybrid offers no demonstrated benefit for this installation.

## Existing system inspected

The clean initial checkout was `fe32a0839e68489f53010fed44eaea928d736942`, with no unrelated working-tree changes. Inspection covered `server.py`, `codex_bridge.py`, `ultra.py`, `ultra_monitor.py`, `ultra_tools.py`, `ultra_workflows.py`, memory/document modules, the actual viewer/Work workspace, launch scripts, pinned optional dependencies, native helper integration, repository instructions and GitHub Actions.

JARVIS is a loopback Python `ThreadingHTTPServer`, plain JavaScript/Three.js viewer, local Markdown vault and native macOS helpers. Its optional virtual environment already contained document, embedding, Qdrant and MCP integrations. Model access uses the signed-in Codex app-server connection. There is no deployed container or public service in this checkout. CI runs Python/JavaScript regressions and builds native helpers.

Existing functionality included routing, a bounded boss/worker crew, typed tools, source/math validation, private checkpoints, write deduplication and metadata polling. The Work tab still said no agent runner was connected. Missing capabilities were explicit background run controls, persisted per-run visibility, reconnectable events, transport cancellation and graph-level recovery of successful parallel work. Ultra's committed master flag was off; baseline tests enabled it only in memory. The new launcher enables it through a separate private local settings file.

## Upstream source and Studio verification

| Candidate | Architecture, extension points and runtime | Studio / licensing / maintenance | Result |
| --- | --- | --- | --- |
| Microsoft AutoGen | Core event/actor runtime, AgentChat teams, custom agents/model clients, tools, termination and cancellation; Python packages require 3.10+. Inspected `BaseGroupChat` and Studio `TeamManager`. A Codex-specific client adaptation would be needed. | Studio is in the **same repo**, `python/packages/autogen-studio`: separate FastAPI service with Gatsby/React frontend and SQLModel persistence. Code is MIT; documentation is CC-BY-4.0. No hosted subscription is required for that local code. The root now says archived, unmaintained, and no security fixes; Studio is explicitly a prototype. | Excluded before installation/prototyping. Its conversational team semantics overlap JARVIS's existing crew; an unmaintained extra runtime/UI is not justified. |
| LangGraph | Typed state, node callbacks, parallel `Send`, reducers, streaming updates and checkpointers. Python 3.10+ upstream; JARVIS uses 3.11+. Inspected `graph/state.py`, SQLite saver and serialization code. Retains our model and tool adapters. | Runtime and SQLite saver are MIT, actively updated at inspected HEAD. Current **LangSmith Studio** is a hosted UI connecting to Agent Server; it is not the MIT runtime UI. Local Studio instructions install a separate CLI/server and require a LangSmith account/API key. Free-tier access exists; hosted deployment/self-hosted platform licensing is separate. | Adopt runtime and SQLite persistence only. No Studio service, API key, subscription, Docker, React bundle or cloud tracing required by this implementation. |
| Flowise | Node/TypeScript server, React visual builder, component-node extensions, prediction API, SSE, abort controllers and persisted execution data. Inspected `buildAgentflow.ts`, predictions service, `SSEStreamer.ts`, packages and manifests. Current source specifies Node 24 and pnpm 10.26. | Visual UI lives in the **same repo** under `packages/ui`, with additional `agentflow`/`observe` packages. Core is Apache-2.0; `packages/server/src/enterprise` and explicitly marked files including `IdentityManager.ts` have a commercial license. Enterprise production use requires a subscription. GitHub marks the repo archived August 13, 2026. | Excluded before installation/prototyping. Would add another server/build/dependency stack and a custom Codex adapter. Its visual components are coupled to Flowise execution contracts; no measured advantage warrants reusing them. |

Pinned source snapshots, fetched and read locally:

- [AutoGen `004749e`](https://github.com/microsoft/autogen/tree/004749e6b7102c8fd317b9b1499ce5807223c278), commit October 16; [Studio source](https://github.com/microsoft/autogen/tree/004749e6b7102c8fd317b9b1499ce5807223c278/python/packages/autogen-studio), [Studio documentation](https://microsoft.github.io/autogen/stable/user-guide/autogenstudio-user-guide/index.html).
- [LangGraph `9d68e5b`](https://github.com/langchain-ai/langgraph/tree/9d68e5b3eb1a63027b05e9f0152149ea0284dcdb), commit October 22; [current Studio](https://docs.langchain.com/langsmith/studio), [local setup](https://docs.langchain.com/langsmith/local-dev-testing), [Studio quickstart](https://docs.langchain.com/langsmith/quick-start-studio), [pricing](https://www.langchain.com/pricing), [self-hosting terms overview](https://docs.langchain.com/langsmith/self-hosted). The legacy `langchain-ai/langgraph-studio` URL returned 404 during verification; it is not assumed to be an available embeddable UI.
- [Flowise `9291856`](https://github.com/FlowiseAI/Flowise/tree/9291856d1ea4a4ceea9f8fef8ce14f4f6c81e8eb), commit August 13; [root license and exceptions](https://github.com/FlowiseAI/Flowise/blob/9291856d1ea4a4ceea9f8fef8ce14f4f6c81e8eb/LICENSE.md), [commercial portion](https://github.com/FlowiseAI/Flowise/blob/9291856d1ea4a4ceea9f8fef8ce14f4f6c81e8eb/packages/server/src/enterprise/LICENSE.md). Two Flowise documentation URLs could not be fetched; its source and README supplied the inspected API/runtime evidence.

Top-level LangGraph releases were verified against PyPI before installation. `pip check` passes. The installed graph stack also resolved langchain-core 1.7.0, checkpoint 4.3.0, prebuilt 1.1.1, SDK 0.4.8 and langsmith 0.14.12; it is larger than the standard-library baseline. Licenses remain in installed distributions, with copied runtime/saver MIT notices under `docs/licenses`.

## Prototype and baseline

Before edits, repository hygiene passed, 163 Python tests ran (162 passed and one optional embedding check skipped), all 14 JavaScript suites passed, and full live preflight recorded **14 pass, 0 fail, 2 warn**.

A bounded prototype ran the same deterministic three-branch calculation 20 times through LangGraph/SQLite and a plain thread pool. Every result was correct. Graph median was **15.96 ms**, maximum **22.91 ms**; thread-pool mean was **12.95 ms**. These are different summary statistics over small synthetic samples, not a production speed claim. Reopening the checkpoint and resuming a deliberately failed branch executed only that branch; successful siblings were retained. Prototype peak process RSS was **72.35 MB** on this Mac. No model was called.

The concrete gap justified adapting JARVIS's model/tool boundary and adding a local background-run service, event projection and controls. LangGraph supplies graph scheduling and recovery. Custom adapter code supplies JARVIS-specific attempt reservations, original deadlines, existing validators, secret filtering, HTTP access rules and model interruption. A paid planner and repeated peer-review round were not necessary for these fixed analysis recipes.

## Actual model trials

Both approaches used the same installed account, fictional note vault and task wording. Trials were sequential, one observation per row. The graph uses fixed roles and high-effort profiles, while the legacy crew uses max-effort planning and its original mixed profiles. Causal attribution to the framework alone would be invalid.

| Workflow | Existing route | Integrated workflow |
| --- | --- | --- |
| “Who updates the Cash Flow Forecast, and when?” | Complete, **3.958 s**, one citation, **7,861 reported tokens**, one model job | Complete, **9.649 s** including cold initialization, one citation, **15,219 reported tokens**, analyst plus reviewer |
| Compare Menu Pricing, Opening Checklist and Launch Campaign; three cited priorities | **Failed after 240.026 s** during boss planning; no workers started; usage unavailable | Complete, **16.722 s**, three citations, **32,880 reported tokens**, three parallel analysts plus reviewer; one real retrieval tool call |

Simple questions remain best suited to ordinary quick chat. The workflow route adds persistence and review at additional latency/model usage. The legacy timeout was not masked or converted into a zero-cost success. Its exact upstream cause was not established. Final source quotations and arithmetic were checked locally; the displayed research answer was also inspected against the named café notes. This is not a broad semantic-accuracy benchmark.

Integrated state-poll p95 was **34.50 ms** for the cold focused run and **4.43 ms** for the research run. Baseline benchmark-process peak RSS was **29.44 MB**, with 0.011/0.300 seconds Python CPU for the direct/crew trials. These exclude the model subprocess and remote inference. The separate integrated stress-process peak RSS was **73.65 MB**; comparing these process peaks is only an indication of framework overhead. No total-host energy or cloud GPU measurement was available.

A further real run requested `note_read`, was cancelled, then resumed within its original budget: **complete**, three citations, **13 real tool calls**, one recovery, **36.563 s** total wall time and **529 ms** cancellation response. All three analysts retained their attempt counters and completed on attempt two; the reviewer used one attempt. **86,957 tokens were reported**, with accounting explicitly marked incomplete for cancelled attempts. A separate browser-launched cancellation stopped in about one second. Its retry window expired during a user pause, and the UI correctly required a fresh request.

The recovered run initially described `note_read` verification as unavailable despite successful tool events. The inherited final-review prompt prohibited reporting tool execution and lacked execution provenance. The adapter now supplies a confirmed tool-call list from completed worker reports and an explicit review boundary. A subsequent browser-launched live run completed in **31.523 s**, used two tool calls and **23,788 reported tokens**, and correctly stated that `note_read` succeeded; its prices and guidance matched the opened source note. This resolves the observed handoff defect, not all possible semantic errors.

Subscription token usage cannot be converted to a dollar bill from available data. No paid API credentials, new subscriptions or external hosting were used. Testing remained within existing per-request worker/time/retry limits.

## Stress, failures and iteration

The final runtime benchmark uses isolated temporary data and a deterministic model boundary. Twenty research runs completed; median **58.12 ms**, p95 **416.91 ms** including the cold first import. Peak worker concurrency was **3**. All **20 concurrent excess launches** were rejected with busy status. Cancellation was **14.53 ms** with the synthetic model; CPU was **0.883 s**, and SQLite data for the benchmark was **1.11 MB**. These numbers measure local orchestration, not remote-model throughput.

Automated tests exercise real graph scheduling and persistence, parallel execution, original deadlines, exhausted attempts, transport retry, failed tools, bounded cancellation of slow read tools, interrupted-run reopening, successful-sibling preservation, changed-source refusal, durable token accounting, redaction, permissions, unknown IDs, host/origin validation and private-path refusal. Real HTTP tests disconnect an event stream and reconnect with an out-of-range event ID; the client still receives the complete current snapshot without re-executing work. The transport test verifies `turn/interrupt` and cleanup.

Evaluation led to several corrections: bounded waits around read tools; attempt counters saved before model calls; preserving unknown usage across retries; checking sources discovered by workers before recovery; using actual theme tokens; retaining expanded findings when completed-state polls change only the unused remaining-time counter; routing recovery source checks through the same bounded, observable read-tool adapter; and rejecting non-string workflow names. One new transport test initially lacked its scratch-directory fixture; the fixture was corrected before final validation. The Focus probe initially ran at the wrong CSS dimensions because of browser zoom; those runs were failures, then a visible **1440×900** run passed all 16 cases and the temporary viewport override was reset.

## Operational limits

This is a working single-user integration, not a general public agent-hosting service. Runs are bounded by the existing 240-second request deadline; recovery hours later intentionally requires a new request. A crash can leave unreported model usage or repeat an uncommitted read-only node. There is no exactly-once remote inference guarantee. Source/math validation does not prove every natural-language conclusion. Studio-style arbitrary graph editing, hosted deployment, write-enabled workflow automation and multi-process scheduling are outside this implementation.

Reproduction, data handling, launch steps and available controls are in [WORKFLOWS.md](WORKFLOWS.md). Machine-readable measurements are in [framework-results.json](framework-results.json). Final regression and preflight results are recorded in [the current verification log](ultra-verification.md).
