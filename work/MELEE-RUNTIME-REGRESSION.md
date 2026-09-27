# Actual melee stack fixture — 2026-09-27

`StackingMeleeTests.lua` is registered as an import-only Community Patch helper. It defines functions until explicitly called. Lua5.1 syntax and an inert load without game globals pass. Actual024049 coverage is now archived at work/test-runs/melee-024049:246 passed,0 failed across five scenarios and six attacks. The runtime used explicit manual selection before attacks; the current helper automates that selection step. Independent source review verified Lua bindings, deterministic damage inputs and normal mission arguments with no blocking mismatch. Its suggested busy/WAIT guards were applied: pending evidence is retained until combat/mission resolution and an observed attack. No C++ or installed files were changed by this fixture task.

## What it verifies

Every scenario has two enemy combat occupants, so it fits the default starting capacity2 without any technology change.

| Setup name | Controlled composition | Required actual result |
|---|---|---|
| protect | Warrior50 + Archer10; Warrior attacker20 | Preview chooses healthy melee; only that unit loses the exact predicted HP. |
| wounded | Warrior50 at1HP + healthy Archer30; Warrior attacker20 | Healthy ranged unit is chosen and actually damaged;1HP melee remains unchanged. |
| flank | Warrior50 + Archer10; Horseman attacker20 | Configured cavalry bypass selects and damages the archer despite the stronger melee. |
| anticav | Spearman20 + Archer50; Horseman attacker20 | Configured anti-cavalry member intercepts; the stronger archer remains untouched. |
| advance | Two Warriors at1HP and strength1; Warrior attacker200 | First actual kill leaves the other defender alive and attacker at origin. Second actual kill clears the last defender and attacker enters the target. |

Numbers are fixture-only base combat strength and health controls. All spawned promotions are removed, preventing promotion-based withdrawal, support fire, capture and kill-healing from changing the mechanic under test. Unit-class/combat-type stacking roles remain and are checked through GetStackRoleInfo. Attackers receive300 maximum HP to survive retaliation. No existing unit stats are changed.

The victim is read from the shared stack preview and compared with an explicit expected role for the first four cases. The Lua helper does not reproduce defender scoring. Exact damage is calculated separately using the actual native attack/defense strength APIs and `GetMeleeCombatDamage(..., true, defender)`, including both returned hit and retaliation. The seed inputs match GenerateMeleeCombatInfo: same attacker ID, source plot and strengths. The ordinary preview's mean damage is logged but is not treated as the real roll. The helper refuses multiplayer to preserve the single-player real-roll convention.

## Manual commands

Use a disposable world already at war with another living major that retains a city. The helper never declares war; this prevents border expulsions or other changes to unrelated units. It finds empty, unowned, passable natural land with an empty radius-three buffer. It does not edit terrain, rivers, resources, roads, improvements, ownership, cities, technologies, turns or saves.

```lua
include("StackingMeleeTests")
StackMeleeTests.Plan()
StackMeleeTests.Setup("protect")
StackMeleeTests.Fire()
-- Wait for ordinary melee animation/resolution:
StackMeleeTests.Check()

StackMeleeTests.Setup("wounded")
StackMeleeTests.Fire()
-- Wait:
StackMeleeTests.Check()

StackMeleeTests.Setup("flank")
StackMeleeTests.Fire()
-- Wait:
StackMeleeTests.Check()

StackMeleeTests.Setup("anticav")
StackMeleeTests.Fire()
-- Wait:
StackMeleeTests.Check()

StackMeleeTests.Setup("advance")
StackMeleeTests.Fire()
-- Wait:
StackMeleeTests.Check()
StackMeleeTests.Fire()
-- Wait:
StackMeleeTests.Check()
StackMeleeTests.Summary()
StackMeleeTests.Cleanup()
```

`Try("Setup", "protect")`, `Try("Fire")` and `Try("Check")` provide logged errors via pcall if convenient. An explicit enemy player ID is accepted as the second Setup argument or first Plan argument. It must already be at war.

Setup, Fire and Check are separate calls. Fire revalidates adjacency, visibility, attack legality and the selected defender immediately before sending a normal MISSION_MOVE_TO into the hostile tile. It resets only the fixture attacker's moves/attack count between the two staged attacks. No turn is advanced.

Check requires combat animation to finish and verifies every defender's exact HP and location, one changed victim only, attacker retaliation HP, all surviving unit capacity, survivor-dependent advance, unrelated pre-existing units and natural plot state. All existing players' units are snapshotted before setup. Cleanup removes only units carrying this fixture's exact script tag; it refuses cleanup while an unchecked attack is pending. Combat rewards/history remain in the disposable world, so discard it without saving.

If a precondition fails, investigate the site or modified roles instead of recording a test pass. Do not weaken damage/victim assertions just to accommodate a mismatch. Current live-unverified areas include engine mission dispatch/animation behavior, civ-specific post-kill effects and exact post-combat HP under unusual external mods.

## Companion gift helper

`StackingGiftTests.lua` is now also registered as a manual import. See `work/GIFT-PLACEMENT-REGRESSION.md` for its explicit Setup/Separate/GiftSeparated/CheckGift sequence. It remains actual-live-unverified. ProductionTests, GiftTests and MeleeTests are imports only, with no automatically executing UI entry point.

## Native combat adviser

Fire explicitly calls UI.SelectUnit(attacker), verifies the selected owner/ID and looks at the target before queuing the normal mission. The ordinary combat-adviser confirmation uses Game.SelectionListMove and therefore acts on the current selection. If an adviser is open, confirm the intended attacker through the normal UI; do not alter adviser preferences. Check retains pending evidence with WAIT until the mission resolves. Never resubmit an unchecked pending mission unless original HP, coordinates, attack availability and moves are verified pristine. The024049 run recovered its initial selection/adviser issue this way and recorded no failed mechanic assertions.
