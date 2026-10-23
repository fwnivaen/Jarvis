# Ultra Jarvis verification — October 22, 2026

Both stages extend the existing server and viewer. The checked-in master flag remains off, with an independently enabled review server at `http://127.0.0.1:4701/?mute=1`. Enable and run commands, feature flags and complete dependency details are in [ULTRA-JARVIS.md](../ULTRA-JARVIS.md). The earlier Stage 1 record is retained in [ultra-stage-1-verification.md](ultra-stage-1-verification.md).

## Automated and live checks

| Check | Observed result |
| --- | --- |
| Python suite in the local virtual environment | **163 tests passed**, including the real local embedding, persistent vector search, PDF/DOCX/XLSX imports and MCP stdio checks |
| JavaScript regressions | **14 suites passed**, covering the existing galaxy, orb, voice, Focus, camera, screen watch, capture/source behavior and both crew suites |
| Final full live preflight | **13 pass, 1 fail, 2 warn**; the failure is the running server's foreground-tab read |
| Visible Focus probe | **FOCUS PROBE: 16 pass, 0 fail \| 1440x900** |
| Real dynamic tool call | `preferences_get` completed through the warm Codex connection in **8.7 seconds** end to end; one registry call, zero workers and zero escalations |
| Real image request | Full preflight correctly identified the red JPEG through the cheap Luna vision route |
| Real three-worker collaboration | Boss planning and final review completed; Sol medium and Luna high each drafted and reviewed available peer findings; Luna max reached its **45-second** draft limit; a boss-reviewed **partial** answer was returned |
| Read back that saved partial answer | **2.08 seconds**, no model call, the same observed evaluation totals and `resumable: false` |
| MCP protocol | A real stdio client negotiated **2026-07-28**, discovered all **12 tools** and called the local registry |
| Source hygiene | No secrets, notes, generated graph data, models, virtual environments or private runtime journals are included in the upgrade archive |

The two preflight warnings are the existing API-key/model checks skipped because this installation uses Codex sign-in. The live preflight also passed note retrieval, capture followed by immediate recall and cleanup, model switching/reset, served-file integrity and browser access restrictions. An earlier full run passed **14 pass, 0 fail, 2 warn**, but full runs after the last server restart failed the foreground check, first on activity and then on the front tab. The final run is the current result; the earlier pass is not substituted for it.

Field diagnostics were fetched from the actual running review server. Its Focus tick was alive and fresh, with no active session or armed target. A subsequent diagnostic could read the foreground application but reported browser-tab access unavailable. The session ledger had five entries and the legacy ledger had six counter keys. Chrome's Window menu listed **five windows**. The controlled tab host was `127.0.0.1:4701`, while the physical foreground window differed and changed during inspection. UI control was then left alone. No identities were added to diagnostics, and no Focus implementation or permission changes were made. The simulated probe below does not establish reliable physical foreground tracking.

The final visible probe title was read in full at an asserted actual page viewport of 1440 × 900:

```text
FOCUS PROBE: 16 pass, 0 fail | 1440x900 | PASS viewport | PASS visible | PASS reload-read-only | PASS focused | PASS deferred | PASS unavailable | PASS paused | PASS drift | PASS excused | PASS home | PASS intent-window | PASS commands | PASS pixel-identical | PASS pixel-change | PASS disconnect | PASS visible-at-finish
```

## Collaboration and limits

The final live collaboration took **110.6 seconds** end to end. Its monitor measured **109.6 seconds**, five model jobs, four completed jobs, one failed worker, zero retries, zero escalations and **191,955 reported tokens**. Those are observations for this run, not a general speed or cost claim. The failed worker was Luna max. Its timeout did not hold the other workers behind a shared draft barrier: they exchanged and reviewed available findings before the boss synthesized the partial answer.

Earlier live trials exposed two issues that were corrected: final synthesis repeated retrieval instead of using all supplied tool sources, and a global draft barrier consumed the faster workers' review budget while one slow worker drafted. Final synthesis now receives all validated reports and retrieved passages with executable tools disabled. Drafts and reviews share one pool of at most three workers, and reviews start when peer findings become available. Regression tests cover the source handoff, shared worker deadlines, one peer-review round and parallelism bound.

The requested max-effort settings can still exceed the fixed 45-second worker budget. They were preserved. A worker timeout remains visible and the answer is marked partial. A boss timeout produces an explicit “not received a final boss review” notice with only locally checked findings. Neither timeout nor self-reported confidence triggers escalation.

Checkpoint tests cover context mismatches, original absolute deadlines, shared retry/escalation counters, source revisions, all observed token usage, completed and partial answer readback, and retained worker statuses in the monitor. New checkpoints preserve the full metadata roster so reopening an answer cannot mislabel previously used workers as “Not needed.” Tool journals deduplicate identical writes from peers and retries; interrupted uncertain writes are not automatically repeated. A deliberately slow local callback also confirmed that a worker's model wait remains bounded by its deadline.

## Memory, documents and tools

The isolated Python 3.12 environment contains the pinned official releases listed in `requirements-ultra.txt`. A real `BAAI/bge-small-en-v1.5` embedding produced **384 dimensions**. A synonym query found the matching note, and the embedded Qdrant index reopened successfully from local disk. Missing optional dependencies and embedding/index failures retain the original keyword retrieval behavior.

Real PDF, DOCX and XLSX fixtures were converted to Markdown. Tests cover paragraph/table order, formulas retained as text, provenance hashes, repeat-import reuse, refusal to overwrite edited imports, bounded input sizes, path/symlink restrictions and imported titles surviving server rebuilds. Text extraction does not perform OCR or reconstruct chart images.

The same typed tool registry serves crew calls, local HTTP and MCP. Tests cover all feature flags, explicit persistent preferences, local origin boundaries, current note revisions, screen request/confirmation distinctions and refusal of arbitrary built-in shell/file/browser tools. The installed Codex build requires the documented experimental dynamic-tool protocol and its `code_mode_host`; code-mode execution and unrelated tools remain disabled. Real tool execution was verified after applying that compatibility setting.

## Visual verification

The top-left glassy hierarchy retains the requested Sol max boss, Sol medium worker, Luna max worker and Luna high worker. Avatars are stable while their status changes. The nearby drawer shows only safe activity metadata; model output, prompts and private reasoning do not enter its table or terminal counterpart.

Desktop, compact mobile, collapse/reopen and Settings memory/import controls were inspected in a visible browser. At an actual **390 × 844** viewport, all four figures fit without horizontal overflow. Full view and other workspaces hide the crew, and reduced-motion preferences stop the decorative animation. Temporary viewport overrides were reset after checking.

- [Finished desktop](screenshots/ultra-complete-desktop.jpg)
- [Actual live collaboration](screenshots/ultra-collaboration-live.jpg)
- [Memory and import controls](screenshots/ultra-memory-settings.jpg)
- [Compact mobile crew](screenshots/ultra-complete-mobile.jpg)

**UNVERIFIED:** physical webcam imagery and audible native speech in this session, OCR/chart reconstruction, the prompt's benchmark and price ratios, general latency/cost savings, universal subscription model entitlement and future compatibility of experimental app-server APIs. Existing voice/camera controller regressions pass; those do not establish physical audio or camera results.
