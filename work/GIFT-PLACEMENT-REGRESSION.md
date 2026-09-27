# Gifting placement regression — 2026-09-27

Source fix frozen in CvUnit.cpp SHA256 E49FFBB99EB629E8ABC2BB336AB65F04B7A0E9CC910677589DE4F56F3C14E0DD. No VP DLL build, deployment or game action was performed for this change. Independent source review by /root/ai_implementation/dense_review passed at this exact hash. The reviewer checked recipient capacity, owner exclusions, unchanged exception paths, post-hook ordering, creation coordinates and the80-check result. The actual024049 city-state transfer now passes12/0; see work/test-runs/gift-024049. Other capacity/domain variants remain source-level coverage.

## Behavior

Gifting still replaces a unit on its current tile. With stacking enabled, ordinary noncargo land/sea combat gifts now first test the recipient's final occupancy, excluding the donor being replaced. Every surviving ordinary same-domain combat occupant must belong to the recipient, and its count must be strictly below the recipient's live capacity. The donor's higher capacity cannot grant the recipient extra slots. Recipient-owned occupants can share when capacity permits.

No safe in-place stack means refusal before mutation. The player must separate a donor stack before gifting a member. No adjacent plot search, teleport, recipient-then-kill fallback or donor movement was added. Rechecking after the existing permission event hook prevents a hook's new occupant from making the earlier result stale before cargo removal or recipient creation.

Native domain and recipient territory rules are unchanged: the existing method requires owned territory belonging to the recipient, the donor's native domain unless a transport exception applies, peace, no visible enemy or forecast danger, eligible unit/class limits and the ordinary city-state/major rules. The new helper does not try to predict promotion losses on gifting or replace those existing tests. Disabled rules, civilian/air/support/cargo gifts retain their old path. The separate long-distance city-state gift mechanism is untouched.

## Source-level evidence

Run `work/test-gift-placement.py` with the bundled Python. It extracts the actual preflight, complete canGift and complete gift bodies from CvUnit.cpp, compiles those with VC9 against deterministic engine stubs and executes80 checks, all passing. Evidence: `work/gift-regression/result.json`, `compile.log` and generated `gift-source-test.cpp`.

Tests cover ordinary success, rejection with another donor, recipient vs donor capacity, caps2–10, city/domain slots, foreign owners including same-team owners, ignored delayed/dead/cargo/support/civilian occupants, disabled and excluded unit paths, native/transport/peace/danger/class/trait restrictions, and a permission hook adding an occupant. Rejected transaction tests check that recipient creation, donor/companion removal, cargo deletion, movement and gift rewards do not occur. Successful gift checks ensure the replacement remains at the original coordinates.

The stubs isolate control flow and occupancy; they do not validate the closed engine, real Lua UI, city-state quest processing or promotion conversion. These remain live concerns, not source test passes.

## Inert live fixture

`work/StackingGiftTests.lua` passes Lua5.1 syntax and loads with no game globals or side effects. It is now registered as an import-only CP source helper; it has not been deployed or run by this agent. Run only on a disposable game after manually calling include("StackingGiftTests"). It selects two adjacent empty natural city-state land plots at peace; no terrain, ownership, technology, diplomacy, city, turn or save edit is performed.

```lua
StackGiftTests.Plan("UNIT_WARRIOR")
StackGiftTests.Setup("UNIT_WARRIOR")
StackGiftTests.Separate()
-- Wait for normal one-tile movement:
StackGiftTests.GiftSeparated()
-- Wait a frame for delayed removal:
StackGiftTests.CheckGift()
StackGiftTests.Cleanup()
```

Setup first tests that a single donor can gift, ruling out danger or another unrelated refusal. It then adds a second donor on the same tile, requires CanGift=false and checks a rejected command leaves both units and recipient unit count unchanged. Separate sends an ordinary move to the adjacent tile. GiftSeparated requires the now-single donor to be giftable; CheckGift verifies exactly one recipient replacement at the original tile, unchanged HP, removal of the old donor and survival of the companion on its new tile. Cleanup removes only recorded fixture units; gifted influence/history persists, so discard the world without saving. The024049 live run passed all12 checks, including refusal without loss, ordinary separation movement, exact single recipient creation at the original tile and100HP preservation. Evidence is archived in work/test-runs/gift-024049.

## Separate completed-production policy

The gift test used DLL024049, whose inherited full-city `CreateUnit` fallback could place a completed unit above the combat cap. Purchase placement already required a legal slot. That historical exception does not describe the later030606 production policy.

Release030606 adds a narrow gate for ordinary combat-unit production: when the city and adjacent eligible plots are full, the completed order and stored production wait for space. Opening a slot allows normal completion on a later production turn, with existing rewards and overflow accounting. Normal purchases still require space immediately. The generic `CreateUnit` fallback remains for unrelated free grants and replacement paths; no global initUnit rejection or create-then-kill behavior was introduced.

The production change has141 source-level checks and an independent review. Its actual normal-turn test is tracked separately in `work/test-runs/production-turn-030606`; the complete live run now passes77 assertions plus a separate six-stage saved-state continuation, preserving the blocked queue/production then completing exactlyonce after a legal release. Those results belong to the separate production readouts, not the gift result. Existing supply, resource and obsolescence eligibility checks remain authoritative.
