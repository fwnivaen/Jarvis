# Adaptive model routing

`adaptive-v1` uses the existing signed-in Codex app-server. The core remains standard-library Python; no router service, additional agent framework, provider key, model download or paid fallback is introduced. The independent flag defaults off in `ultra.json`. The current acceptance and activation state is in [the checklist](routing-checklist.md).

## Profiles

| Request | Execution |
| --- | --- |
| Exact bounded arithmetic or `show note 7` / `read note 7` | Existing safe calculator or exact supplied note; no inference |
| Focused retrieval, summaries, extraction, ordinary conversation | Luna High answers and classifies in one call |
| Complex reasoning, design or debugging | One Sol 6.1 Medium call |
| Conflicting evidence, security reasoning, proofs, deadlocks | One Sol 6.1 High call |
| Explicit request for agents, or a selected workflow | Bounded team; chat uses Sol planning, Luna High workers and one Sol synthesis |
| Manual model selection or image input | Existing explicit model/image path, with the shared request budget |

Unfamiliar work can begin with Luna and request one Sol answer. This does not create a crew. Only failed deterministic output/source/arithmetic checks can promote a worker, at most once across the request. Auth, quota and budget failures are terminal. Model prose expressing uncertainty does not authorize escalation.

The live team example consumed four model calls and substantially more tokens/time than a single answer. Consequently, text such as “independently analyze A; separately analyze B” does not automatically allocate workers. Broader automatic team selection requires calibration and evidence of benefit. Work keeps its existing fixed role templates, avoiding an extra planning call. One checked general-work report with no unresolved issues is delivered without a second model restating it; multi-report or unresolved work retains Sol synthesis/review. Automatic peer-review rounds are omitted in adaptive mode. Astra remains a deliberate manual selection.

## Boundaries and accounting

The trusted current request controls the local scheduling policy. Notes, tool output, history and workers cannot grant authority or select more workers. Existing source/math validators, scoped tools, gateway permissions, write journal, admission, deadlines, identity checks and cancellation remain enforced. There is still one admitted user run and at most three workers.

Each request shares an eight-attempt guard and a 120,000 observed-token guard. Failed attempts, retries, planner, workers and reviewer share these limits. Reservations persist across checkpoint recovery. An attempt denied by account admission can have unknown usage; it is never reported as a known zero-token model turn. Unknown attempts reserve 12,000 tokens conservatively. Cumulative usage notifications are counted once per attempt. Crossing the observed-token guard interrupts other active model calls and prevents later tool work. Notifications can lag generation; these are application guards, not atomic provider billing caps.

Context selection keeps at most six query-ranked source excerpts, 12,000 source characters, two history turns and bounded preferences/reports. Stable identities and revisions remain attached to source excerpts. Every shortened category is labelled and the model must retrieve authorized missing evidence or disclose the gap. The total serialized payload has a 24,000-character ceiling; oversized constraints fail explicitly. These limits exclude system instructions, schemas, dynamic tool definitions, tool responses and provider-side image encoding. The observed-token guard still applies to actual reported model usage. There is no answer cache and no cross-revision reuse of mutable source content.

The included-only policy independently verifies ChatGPT authentication and a fresh authoritative allowance snapshot before every model turn. Standard service tier is retained. No API balance is assumed to be free; no credits, resets or fallback providers are purchased. See [usage policy and its limitations](usage-policy.md).

## Activation and rollback

After the recorded gates pass, launch the approved local mode:

```sh
./start-workflows.sh --adaptive-routing
```

The launcher derives private, nonsecret execution flags in `.local/workflow-settings.json`; it does not copy authentication or edit `config.json`. The committed master/adaptive flags stay off. Stop the existing loopback server before relaunching. Starting `./start-workflows.sh` without the option returns to the legacy workflow profiles. Starting `./start.sh` restores the original configured brain. In all cases the included-only policy remains enforced. Saved runs pin settings and reject recovery after a profile change; inspect them before starting a fresh request.

For deployments explicitly using `ultra.json`, `python3 tools/ultra_settings.py adaptive-enable` and `adaptive-disable` change only that policy flag; the separate master enable/disable controls remain available. Status prints both switches and shared budgets. These settings commands do not bypass acceptance gates or replenish an existing run.

`python3 tools/evaluate_routing.py` previews the policy without spending usage. `--live` runs a bounded synthetic comparison; `--case` and `--arm` select unfinished checks. Save each trial to a separate private `.local/` output. Do not repeatedly retry an admission refusal: obtain a fresh affirmative account snapshot first.

## Research incorporated

The [official model guidance](https://learn.chatgpt.com/docs/models) supports using Luna for focused work and Sol 6.1 for more demanding work. Exact model IDs/effort combinations are also verified against the installed app-server catalog. [Official usage guidance](https://learn.chatgpt.com/docs/pricing) does not establish a fixed number of included tasks from a token count; JARVIS reports observed tokens rather than invented allowance savings.

- [RouteLLM](https://github.com/lm-sys/RouteLLM): adopt paired calibration before claiming quality/cost improvements. Its pretrained router is not calibrated for this Luna/Sol pair, so no pretrained threshold is imported.
- [FrugalGPT](https://github.com/stanford-futuredata/FrugalGPT): adapt bounded cascades and complete cost accounting; published savings are not transferred to JARVIS.
- [Semantic Router](https://github.com/aurelio-labs/semantic-router): adapt local intent decisions without another inference call. Current deterministic rules remain inspectable; semantic similarity is not treated as proof of difficulty.
- [LangGraph](https://github.com/langchain-ai/langgraph) and [Codex](https://github.com/openai/codex): retain existing execution, persistence, tools and account transport. No second supervisor is introduced.

These are design adaptations, not vendored third-party code. LiteLLM transport replacement remains deferred because preserving the verified subscription/tool/cancellation boundary is more useful than adding another routing layer. Learning promotion, remote execution and Deep Agents activation retain their independent gates.
