# Adaptive routing implementation record

Approved scope: implement the reviewed routing policy using the existing ChatGPT/Codex transport, local-first decisions, scoped context, selective workers/review and measured evaluation. Preserve the interface, existing admission/cancellation/tool permissions, included-usage policy, and independent remote/learning gates.

## Checklist

- [x] Inspect current source, instructions and running server. Astra is active; Ultra/routing are disabled.
- [x] Baseline Python/browser regressions and full preflight. Evidence: `.local/upgrade-evidence/routing-baseline-{tests,preflight}.txt`.
- [x] Implement local policy, compact context and shared model-call/observed-token budgets.
- [x] Integrate ordinary chat, manual/vision paths, and durable Work workflows without adding an agent stack.
- [x] Add meaningful failure, quota, cancellation, context and routing coverage: 30 new tests; full suite 299 tests, zero skips; all 14 browser suites pass.
- [x] Run bounded live comparison with all attempts counted: six exposed synthetic case pairs pass across two development trials. Initial quota refusal retained. This is smoke evidence; general quality/allowance savings are not proven.
- [x] Verify settings/HTTP/UI behavior and full regression/preflight: final active service **14 pass, 0 fail, 2 warn**. Two API checks skipped for Codex sign-in. Separate live LangGraph/Codex/note-read check passed in one Luna call.
- [x] Required visible 1440×900 Focus probe: **16 pass, 0 fail** after the user unlocked the Mac, the actual tab was selected, and Chrome page zoom was reset from 90% to 100%. Full per-case title read; native screenshot confirmed selected visible page. Override reset.
- [x] Enable accepted local behavior: loopback service launched with `--adaptive-routing`; `/agents` confirms the flag and bounded limits, `/model` confirms included-only policy, and the viewer shows `ULTRA · LUNA / SOL`. Explicit teams work; implicit automatic team allocation is deferred after its larger/slower live result. Committed defaults remain off.
- [ ] Commit and push verified work.

## File plan and dependencies

| Files | Purpose | Gate |
| --- | --- | --- |
| `adaptive_routing.py` | stdlib task policy, context selection, aggregate budgets | deterministic coverage then live evaluation |
| `ultra.py`, `workflow_runtime.py` | preserve execution owners/tools; select profiles and avoid redundant calls | existing regressions, cancellation and quota tests |
| `tools/evaluate_routing.py`, `tests/test_adaptive_routing.py` | representative paired evidence, objective checks, full accounting | no savings claim from scripted fixtures |
| `ultra.json`, `tools/ultra_settings.py` | independent policy flag and reversible activation | full preflight and required acceptance gates |
| `docs/routing-*.md` | checklist, measured results, source attribution and rollback | update every phase |

## Migration and rollback

No private configuration/authentication or notes are migrated. New fields default off; no separately billed providers, hosted services, new packages or model cache downloads are needed. Runs pin settings; Work resumes reject changed settings. Disable the adaptive flag to restore existing execution; disable Ultra to restore the original manual brain. Preserve included-usage enforcement in every rollback.

## Evidence

Baseline revision: `62593f5cf9ec1a546d6adc4dc505708de1c3e018`. Baseline full preflight: **14 pass, 0 fail, 2 warn**. The original locked/wrong-size probe is retained as a failed attempt and is superseded by the visible passing run above. A transient candidate preflight foreground-reader failure (**13/1/2**) was retained; fresh running diagnostics were healthy and the unchanged code recheck passed (**14/0/2**). The final activated service also passed **14/0/2**.

Private evidence: `.local/upgrade-evidence/routing-{final-regressions,final-preflight,final-preflight-recheck,active-preflight}.txt`, `routing-live{,-complex}.json`, `routing-live-work.json`, `routing-cli-usage.json`, `routing-active-http.json`. Source hashes and summary accounting are documented in [results](routing-results.md); exact profiles, research attribution and operational rollback are in [policy](routing-policy.md). No model credentials, identity or credit balances enter these reports.

## Unfinished work and independent gates

- [ ] Fresh, larger paired evaluations for per-family quality, p95 latency and actual account allowance benefit. Six exposed cases do not establish general improvement.
- [ ] Calibrate any learned router or implicit team selection on this exact model pair. Keep deterministic current rules until evidence supports a change.
- [ ] Original upgrade acceptance: included-only raw-model compatibility for Deep Agents, complete legacy ownership migration, remote egress/input/viewing, separately owned live learning evaluation, canaries and promotion. See [the master checklist](upgrade-checklist.md).
- [ ] Remote deployment/verification: user still has no verified Oracle account; no Docker/OCI runtime is available here. Actual free allowances, Linux login/model compatibility, browser isolation/cleanup, backup restore, 24-hour soak and coordinated Mac-off test remain blocked. No paid resource created.

Routing and context/budget guards are **implemented and locally verified**. Synthetic model/tool behavior is **locally live verified**. Remote routing/browser execution is **not remotely verified**. General savings and learned improvement are **not tested/proven**. Deep Agents activation, remote deployment and learning promotion remain off.

## Final source and delivery audit

Tested input manifest: **132 indexed executable/configuration/dependency inputs**, SHA-256 `e35a8b4d1c5c0fae5c1811e6524fc230e78239c80a71b727dc5d8c951ca9c404`; private report `routing-tested-source-manifest.json`. All inputs still matched after activation. Reviewed staging: **18 files, zero forbidden paths, zero credential-pattern matches**. Repository check: **249 files, 190 local links, 0 failures**; whitespace and syntax checks passed.

Source-only archive: **112 files**, **15,396,841 bytes**, SHA-256 `df5c95c927bbd04766e9da0ea5140d399e78d7224b962b1af129a235af711253`. Includes adaptive/usage modules and routing guides; all embedded hashes match; zero private/symlink entries; no upload. Private artifact `.local/jarvis-remote-source-adaptive.tar.gz`, audit `routing-package-audit.json`. It predates only the final documentation records, which do not alter tested executable inputs. No deployment identifier exists.
