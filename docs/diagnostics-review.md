# Diagnostics review and efficiency update — 2026-09-29

The existing logger already covers structural stacking, city retention, operation assembly/readiness, capture candidates, reinforcement progress, tactical recruitment/plans, memory and detailed combat. Its main cost problems were unbuffered per-record output, repeated recursive lock entry, repeated capacity/role lookup for every stack member, and post-AI snapshots that ignored the summary sampling interval. The existing VP AI/Message/Performance logs are a separate source of overhead and are not changed by this update.

Implemented improvements:

- Fixed-size, XML-configurable buffered output with row/time/boundary flushes, retained rotation/truncation safeguards and a selectable immediate crash-trace mode.
- Internal level/filter checks under one acquired logger lock; the public API remains synchronized.
- Cheaper representative stack sampling and consistent before/after snapshot intervals. The native fixture's ten stacks of ten units use 200 capacity getters instead of the previous 1,100; game pathfinding/turn-time is not measured by this fixture.
- Category masks and bounded Verbose turn windows; masked collection avoids unnecessary snapshot/combat/detail work.
- Compact Summary combat/city-capture outcomes, operation staffing/production snapshots, and first-pass logger cost counters. Civilization filters include incoming attacks.
- Ctrl+Shift+D map access in normal play with no visible button. XML and existing Lua activation remain available; a new explicit flush binding supports live inspection.

Read [configuration and recommended profiles](stacking-configuration.md#diagnostic-efficiency-filters-and-hidden-access) for exact defaults, limits, activation and interpretation.

## Offline validation

Native actual-source core/CRT tests cover buffering, thresholds, explicit/critical flushing, failure handling, masks, turn windows, rotation, player filters and synchronization. The complete diagnostic module fixture covers sampled collection, compact/detailed combat, ownership changes, disappearing identities, incoming attacks and filtered-out collection. Lua checks exercise manual normal-play access and both actual map input bridges, including modifier keys, mode gating and XML disabling. Parser fixtures recognize the new outcomes/cost rows.

Isolated actual-CRT file-output benchmark (1,000 rows, three repetitions per mode):

`bufferedMedianSeconds=0.001743 immediateMedianSeconds=0.392155 immediateOverBuffered=225.014 rows=1000 repeats=3`

This measures logger file-output overhead, not game speed. Whole-autoplay performance, actual input dispatch/rendering and campaign equivalence require the next live test. No game was launched for this review.

## Useful next evidence

The next autoplay can now distinguish low city health without capture, depleted/incomplete formations, production commitments, support arrivals and logger overhead without full Verbose participant traces. Still useful future additions are target-selection score/rejection explanations from already-computed values, reinforcement losses/arrival gaps tied to persistent objective IDs, and timing split across tactical, homeland and operational work. These are not implemented here; they should be driven by the compact results rather than adding every trace continuously.

## Prepared release

- Source: `ef5f17dc677af7b5083a88f7eac258a11bcdd2a5`; DLL version: `Release-5.4.6-18-gef5f17dc6 Clean`.
- Native VC9 x86 Release, 178 translation units, two workers, 100.047 seconds. Matching symbols preserved.
- DLL SHA256: `691F897329A4F04C5C7D999B1F38CAAD3B02D4FE73BD4F4165BC4FA08E479F86`.
- PDB SHA256: `C04E0C0029ACCE14EF196F10A11E82FC81D9E3FA72A9751371E489E81BCF7FDD`.
- 506 source inputs and all 2367 deployed files verified. All 50 save hashes and graphics settings are unchanged.
- Previous installation archive: `E:/Projects/Civ5StackMod/work/backups/deployment-replaced-20260929-222013-a11c78e2`.
- Eight targeted offline suites pass: 73 core/CRT checks, 22 complete-module event/sampling checks, 84 Lua diagnostics/input checks, 18 parser cases, the roster/geometry suite and existing no-op/endpoint/siege regressions.
- Evidence: `work/test-runs/diagnostics-efficiency-offline/checks.json`, `release.json` and individual logs.

No game was launched, and whole-autoplay improvement and live shortcut behavior remain pending. All changes are committed locally under the user's identity; nothing was pushed or published.

## Runtime smoke follow-up — 29–30 September 2026

See [runtime smoke validation](runtime-smoke-20260929.md) for live results, the corrected D-key constant, exact save/reload comparison, and the campaign replay cutoff. The current DLL remains `Release-5.4.6-18-gef5f17dc6 Clean`; UI source is `014d9cc76`. Broader offensive scenario acceptance and whole-game logging performance remain pending.
