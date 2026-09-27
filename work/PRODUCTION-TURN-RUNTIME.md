# Actual completed-production deferral fixture

`StackingProductionTurnTests.lua` is registered as a manual-only CP import. Lua5.1 syntax/inert-load checks pass; no event handler is installed until Setup is explicitly called. Release030606 actual repeat-order test passed77 checks with0 failures: two blocked normal UI turns retained the exact queue and accumulated production; a normal move opened one slot, then one later UI turn completed exactly one unit and advanced to the sentinel plus one repeated order. Evidence: `work/test-runs/production-turn-030606`. The initial old-helper Lua optional-flag error occurred before fixture mutation and is retained separately. It requires the DLL containing completed-unit deferral, not024049's earlier purchase-placement fix.

## Controlled sequence

Use a disposable single-player world, normal active human turn, no autoplay. Found a capital normally first if the natural postbattle save has no city. The helper never founds a city, edits terrain, declares war or advances a turn. Default capacity2 at a coastal city with fewer usable land neighbors minimizes supply pressure.

The selected city's center and every adjacent plot must contain no existing units. Move originals out normally before Setup. Choose a trainable ordinary land combat unit (default Warrior), no rally destination or production automation, no nearby foreign units, adequate treasury and spare supply headroom. Avoid training the same unit in another city during this controlled test. These preconditions separate queue/space behavior from existing supply/resource/obsolescence invalidation. The helper checks eligibility again after filling the ring; cleanup if that check fails.

```lua
include("StackingProductionTurnTests")
StackProductionTurnTests.Plan(nil,"UNIT_WARRIOR",false)
StackProductionTurnTests.Setup(nil,"UNIT_WARRIOR",false)
-- Finish unrelated human orders through normal UI; do not move fixture blockers.
-- Parent: normal UI EndTurn once, with bounded monitoring.
StackProductionTurnTests.CheckBlocked()
StackProductionTurnTests.OpenSlot()
-- Wait for the ordinary one-tile move:
StackProductionTurnTests.CheckOpenSlot()
-- Parent: normal UI EndTurn once more.
StackProductionTurnTests.CheckCompleted()
StackProductionTurnTests.Cleanup()
```

Each function can be called through `Try("FunctionName", ...)` for logged errors. Pass a real owned city ID instead of nil to choose a noncapital. After the basic case passes, a separate run with `repeatOrder=true` tests that a blocked repeat order is not duplicated and successful completion reinserts it exactly once after the sentinel building.

## Observations

Setup creates only tagged owned blockers, fills each legal city/ring land stack to its live capacity, sleeps those blockers, and replaces only the chosen city's queue with unit then an ordinary legal building. It seeds the unit's real stored production to its cost. It records queue contents, making count, completion count, existing units and production. An explicitly registered CityTrained observer records real completion events and starting XP; no direct PopOrder/produce call is used.

CheckBlocked requires a later human turn, unchanged exact queue/repeat flags, unchanged making and things-produced counts, zero CityTrained events/new unit, retained production and full legal occupancy. Production may increase while blocked; the patch deliberately preserves accumulating normal production rather than freezing or discarding it.

OpenSlot sends one tagged ring blocker outward with a normal MOVE_TO mission, beyond the immediate production radius. CheckOpenSlot waits for arrival, confirms one available slot and no immediate completion. After the next normal turn, CheckCompleted requires exactly one new unit/event, one things-produced increment, normal consumed unit bank, the correct making count, and queue advancement to the building. Repeat mode additionally requires one repeated unit tail. The completed unit must occupy the sole released slot; every survivor must remain within capacity. Starting XP is checked against the spawned unit's native free XP plus city production XP scaled by game speed. This checks a normal production reward, not a gold/faith purchase. Completion-event purchase flags must both be false.

Gold/overflow are logged but not asserted unchanged across turns: normal income/upkeep also runs. The source-level141-check regression separately covers retained fractional production, investments, overflow, excess-gold accounting and the queue/gate paths. This runtime helper does not prove non-head siphoning or automated-AI queue behavior.

Cleanup removes this helper's tagged blockers, any tagged units completed by the fixture, and its own CityTrained handler. It does not rewind the chosen queue, accumulated production, treasury, city growth, rewards or turns. Discard the disposable world without saving. Original-unit eligibility and movement remain under normal game rules.

## Related helper preconditions

- `StackProductionTests` tests **actual purchase placement**, not turn deferral. It requires an existing owned city/capital and an entirely empty ring, declares war if needed, and must stay within one human turn. Do not end a turn with its hostile ring in place. Its024049 live run passed9/0 and paid exactly140 gold.
- `StackGiftTests` does not require a capital, but needs peaceful city-state-owned natural land, a permitted undamaged unit and zero danger. It first verifies single-donor gifting before adding a companion. Its024049 normal-move/actual-transfer run passed12/0.
- `StackMeleeTests.Fire` now explicitly selects its attacker before queuing the attack. If the normal combat adviser appears, confirm the intended attack through the UI. Do not disable the user's adviser preferences or assume WAIT means a DLL pathfinding defect.

## Saved blocked-state continuation

The030606 blocked Turn2 save was loaded through the normal menu with the same DLL hash and independently verified process module. All six manual command stages passed: exact bank6400/repeat queue/making/production counts and all six unit IDs/positions/HP/caps restored; a normal blocked turn advanced bank6800, a normal move opened one slot, and the next normal turn created exactlyone1108HP100/XP0 with overflow1200 and the correct building/repeat queue. Saved0moves were preserved until the normal turn supplied movement; no Setup/reseed/queue rebuilding was used. Commands and evidence: `work/production-resume-030606` and `work/test-runs/production-turn-030606/blocked-reload-verified`. Six command stages are separate from the prior77 assertions, not an added assertion total.
