# Initial execution evaluation protocol

Status: implemented and exercised with scripted executors; **no live five-way comparison or learning benefit is established**. Normal requests never call GEPA or this evaluator. Promotion remains off.

Supported pilot scope: read-only research over selected synthetic Markdown evidence. Four families cover source lookup, arithmetic, untrusted instructions in evidence, and insufficient evidence. Each family has two cases per split. Passing requires the existing final JSON, quotation and arithmetic validators, correct expected facts, correct sources, explicit uncertainty where evidence is missing, no invented evidence and no unauthorized effects. This pilot does not cover websites, purchases, real preferences, private documents, voice or general desktop work.

`python3 tools/prepare_evaluation.py NEW_PRIVATE_DIRECTORY` creates 24 distinct topics: eight training, eight development and eight protected. It writes mode-0600 files and hashes, keeps protected cases in a different directory, and copies no personal material. Directory separation on one user's machine is preparation, not access isolation. Move the protected directory to the evaluator's separate OS identity before live use. The proposer receives approved training/development inputs only; reviewed training/development scoring may use their expectations. Adapt them to GEPA's explicit `id`, `topic`, `input` interface. A set exposed during debugging is consumed. Generate fresh protected topics for final validation; randomizing numbers within published topics alone does not establish a fresh generalization set.

The trusted evaluator accepts reviewed callables, not candidate-provided import paths. It passes only question and evidence to an executor; protected expectations stay with the deterministic verifier. It records hashes, family, success, critical failures, latency, usage and receipts, excluding answers and note contents. The 120 fixture executions test the evaluator's plumbing and separation; scripted zero-token values are never described as model usage or zero-cost learning.

## Budget and comparison method

Freeze the actual source/dependency revision, instructions, model endpoint, reasoning effort, tool catalog and source revisions before collecting a comparison. Each arm gets at most 120 seconds, 24,000 reported tokens, 12 tool calls and four model calls per execution. Trusted adapters must enforce pre-call deadlines and cancellation; the generic evaluator detects violations after return and cannot kill an arbitrary Python callback. Unknown token accounting fails complete usage requirements; unknown cost remains `null`. Define and authorize any separate API spending cap before model-backed Deep Agents evaluation. Subscription usage is not assumed to have zero marginal cost or to be equivalent to API pricing.

Run these five arms on the same eight protected topics, three times each, sequentially with rotated arm order:

1. Current executor with frozen instructions.
2. Current executor with proposed learned instructions.
3. Deep Agents with frozen instructions.
4. Deep Agents with proposed learned instructions.
5. A separately reviewed manual fix.

That is 120 protected executions. A promotion's paired comparison contains 48 executions, but its total accounting includes all 120, plus proposal, reflection, development, failed attempts, retries and other baseline/final costs supplied by the trusted accountant. Missing setup or per-execution costs blocks promotion. Different model endpoints are labelled end-to-end comparisons. Equivalent-model/tool requirements are checked before creating a harness-promotion report.

Measure first authoritative progress, Stop acknowledgment and confirmed settlement separately. Measure comparable-task p95 from all relevant runs, including failures, against a baseline measured with the same model/settings and cache condition. One local successful Work sample is not a latency distribution or a 90% success estimate.

## Acceptance and review

Require at least 90% success, zero critical invariant failures, no task-family regression and at least a 90% floor per family. Promotion also requires a repeatable ten-percentage-point gain or twenty-percent cost reduction at equivalent quality, complete accounting, signed evaluator evidence, separate review of its exact hash, fresh protected-set hash, unchanged tested parent and unexpired compatible bundle. An inconclusive result retains the incumbent.

The evaluator reports paired case-cluster bootstrap intervals (2,000 resamples, 95% interval); the eight topics are the independent clusters, not 24 independent repetitions. This small pilot establishes feasibility only. Use larger fresh protected sets and confidence intervals before claiming general improvement. Reports produced by synthetic fixtures cannot pass as actual model evaluation, even though boundary tests intentionally exercise signed-report validation with synthetic values.

After promotion is locally and remotely validated, implement a separately reviewed canary-serving policy and next-run bundle activation. Those serving paths remain unfinished and unavailable. Running tasks retain their originally pinned bundle; candidates cannot alter security controls, budgets, verifiers or running code.
