# Completed-unit production deferral

Committed as `5efb033` and compiled successfully in Release `20260927-030606` (`Release-5.4.6-4-g5efb033 Clean`). This change was absent from Release024049. Actual blocked-production/release runtime proof is still pending at this documentation checkpoint; source checks and build success do not establish it.

## Player behavior

With stacking enabled, a completed ordinary land or sea combat unit waits when neither its city nor a neighboring tile is a legal placement. Its existing queue entry and stored production remain. A normal notification explains that the unit is ready and asks the player to make room. Keep or select that unit in production to retry when a slot opens.

No new unit is created while blocked. Repeated completion checks do not add repeat orders, reduce the unit-class-making count, release an operation commitment, clear an investment, increment completed-item counts or grant completion yields. Explicit cancellation and reordering still work. Civilian, aircraft and special stacking/support production keep their prior behavior, as does disabled stacking.

Production continues to accumulate in the existing per-unit field, including hundredths of a hammer and previously applied feature/overflow production. Once placement succeeds, VP's original cost, overflow cap and excess-production-to-gold rules apply once. Gold/faith purchases retain their existing placement eligibility checks and charge only through their original successful purchase path. This patch does not modify purchase, generic CreateUnit, free-grant or upgrade/replacement semantics.

Routine dirty-production reconsideration at the start of a city's production update preserves an already completed combat head so it can retry placement. This is not a global AI-production freeze: explicit queue changes and other intentional AI choice calls remain available. Stored ordinary-combat production at or above its current cost is protected from ordinary decay if another head is selected. Siphoned unit production is also retained when blocked and does not announce a nonexistent completion; an unqueued type can be selected later, or retried by a later siphon of that type.

VP's earlier `doCheckProduction`/`CleanUpQueue` checks remain authoritative. Resource, supply, unit-class limits, obsolescence and other training rules may still invalidate an order or apply VP's existing production conversion. This is placement deferral, not an unconditional reservation that bypasses those rules.

## Scope and ordering

`CvCity::IsStackingProductionUnit` classifies the existing enabled combat/domain/support scope; `IsUnitProductionBlockedByStacking` reuses `CanPlaceUnitHere`. `popOrder` checks a finishing train order before repeat insertion or any queue/accounting/operation mutation. `produce(UnitTypes)` repeats the guard before item counting and creation, covering direct production callers. The trade-route siphon caller suppresses its success message while deferring. The common `CreateUnit` city fallback is unchanged for other spawn/replacement paths.

All in-repository `popOrder` callers were inspected:

- `clearOrderQueue`, network cancellation and `CleanUpQueue` remove orders with `bFinish=false`; their removal loops remain unaffected.
- `doProduction` makes one completion call per update and can safely retain its head.
- Great Engineer immediate completion is building-only.
- The Lua binding makes one requested call; callers must not assume that a finishing train call always removes its order when placement is unavailable.

Notification deduplication checks existing serialized messages, preventing repeats while an equivalent message is active or was already raised that turn. No new persistent city fields, save format changes or numeric settings were introduced. Two localized English rows were added to the already registered StackingConfig.xml.

## Validation

`work/test-completed-production-accounting.py` compiles actual extracted source helpers, notification code, production preflight and VP's unchanged production-accounting block using native VC9 with deterministic engine stubs. It passed44 checks. Coverage includes scope/disabled behavior, no creation or rewards while blocked, exact fractional production retention, investment timing, notice deduplication, one successful completion, normal overflow/gold settlement and direct siphon accounting. Trait/creation side effects are stubbed; this is not a live-game result.

Evidence is `work/completed-production-regression/accounting-result.json`. The separate `work/test-completed-production-queue.py` extracts the **complete actual** helper, popOrder, clearOrderQueue, swapOrder, doProduction and doDecay bodies, compiled with native VC9 and deterministic engine/queue services. Its97 checks passed at the frozen source hash, independently reviewed. It verifies stable blocked node identity; no repeat insertion/making decrement/operation uncommit; exact stored fractional production over repeated blocked updates; one successful release; ordinary clear/cancel termination; explicit reorder/replacement; routine AI-ready preservation; and completed versus unfinished/civilian/air/support/disabled decay. Three test-only mutations (removing pop deferral, ready-AI preservation and completed decay protection) each caused the tests to fail, demonstrating sensitivity to those safeguards. No production C++ was altered for mutation testing.

Queue evidence is `work/completed-production-regression/queue-result.json`, generated source and compile/mutation logs. The stable std::list stub models queue node lifetime across repeat insertion; push-order legality, DoCheckProduction/CleanUpQueue invalidation, traits and engine/Lua hooks remain integration boundaries. Production service accounting is covered separately by the44-check extraction and is deliberately stubbed in the97-check control-flow suite. Neither suite is a game test. The real runtime fixture must verify:

1. A valid trainable ordinary combat unit completes with the city and all legal neighboring slots full: no unit or completion reward, unchanged queue/repeat/making/commitment, increased stored production.
2. More than one blocked turn preserves fractional progress and does not duplicate orders or notices.
3. Free exactly one legal slot and end a normal turn: exactly one unit appears there, the queue advances/repeats once, normal overflow/gold settles once.
4. Explicit cancel/reorder while blocked remains usable; completed stored progress survives ordinary decay.
5. A save/reload while blocked retains the existing queue/progress and resumes when space opens.
6. Disabled, civilian, aircraft, support and already-invalid training cases retain their existing rules.

No VP DLL build, commit, deployment or game control was performed by the implementation agent for this patch.

## Frozen source checkpoint

Independent source review by `/root/ai_research` passed with no blocking issue. The reviewer checked guard ordering, repeat/making/operation preservation, direct siphon behavior, notification deduplication, completed-production decay scope and preservation of disabled/civilian/air/support behavior. Earlier VP training invalidation remains authoritative.

- `CvCity.cpp`: `2B63F7D2DC58601EE2D0848B8F243009BD5AFC3C739BEA401C09839B69118833`
- `CvCity.h`: `2D8CE27C08DBDE29FC37111E425D2FF4729C0A6508D8FE3203462F53B9054FE9`
- `StackingConfig.xml`: `EA3B52F4569D9C7DAE212466A71CCD3F897AACF18C1E108FAFFE8FB1FB89D850`

The 44-check accounting and 97-check queue/control-flow results refer to the exact frozen CvCity.cpp bytes above. Together they provide 141 source-extracted checks; engine hooks and the earlier queue eligibility checks remain integration boundaries.

## Build and pending runtime checkpoint

The coordinator's `work/msvc-output/Release/20260927-030606/build-result.json` records `status: success` and version `Release-5.4.6-4-g5efb033 Clean`.

- DLL SHA256: `CC8F233774E4608EA3891471FA10E551DED25CBBE566393EF9A76F976B5621CC`
- Matching PDB SHA256: `35900E547A07CB28C9F70BD41AF26548C51EC185502302294C4187D6B512F4A6`

`work/StackingProductionTurnTests.lua` provides the pending normal-UI sequence: fill natural city/ring slots, seed a real train order to its cost, end a normal turn, verify no unit/queue/accounting completion, move one tagged blocker outward normally, then end another turn and check exactly one completion. It never advances a turn automatically. The coordinator plans to load the normal-UI `StackProductionBase024049` baseline (SHA256 `1CD8AA14C7367A0BC964B99C3C070F68708C09747B660FE8600FEB26CF493BDB`; capital1087 at16,1; three eligible plots; turn1) under the new DLL. A baseline's successful load does not prove the later deferral behavior. Record actual runtime evidence separately when available.
