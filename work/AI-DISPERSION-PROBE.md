# Bounded natural collateral-dispersion probe

`StackingDispersionTests.lua` is an inert manual CP import with functionally identical work copy (only its descriptive first comment differs). No installation, C++ or numeric XML change was made while preparing it. It defines StackDispersionTests; after coordinator staging, include("StackingDispersionTests") loads definitions only. The backed-up physical test-script method also works before staging. It does not start a scenario, request a turn, save a game or run autoplay. Use a disposable fresh game only after exact default XML is restored and its DLL/configuration recorded.

## Commands

After the coordinator has loaded the helper definitions in InGame:

```lua
StackDispersionTests.Try("Plan")
local ok,ready=StackDispersionTests.Try("Setup",true); print("DISP_SETUP",ok,ready)
```

The explicit true permits granting **only the selected AI team's Iron Working** if absent, with no bonus/announcement flags. Default capacity2 needs this one +1 unlock for a legal three-combat stack. Existing tech presence is recorded; cleanup removes the new units before restoring that presence. It does not change XML or source. Restoring a tech flag does not reverse every era, notification, resource-reveal or diplomatic consequence, so do not use this as an untouched save benchmark. If a suitable game already knows Iron Working, `Setup(false)` avoids the grant. Setup requires default BaseCapacity2/MaximumCapacity9 and enabled stacking/AI/collateral; it fails under the temporary MAIN profile.

Do not proceed unless output reports `ok=true`, `ready=true`, and a STACKDISP READY record. Setup false leaves its four tagged units for inspection; use Cleanup afterward. A failed positive precondition is a nondiagnostic fixture, not an AI failure.

```lua
StackDispersionTests.Try("Arm")
```

Start the existing bounded external `-Phase ai-turn` guard with a fresh writable signal, resolve normal human prompts, and use normal End Turn **once**. This helper emits real `STACKNAT|AI_START|...fixture=dispersion` and `STACKNAT|HUMAN_RETURN|...fixture=dispersion` markers solely so the existing external guard can auto-disarm on its actual one-turn return. Unit details use STACKDISP. No other natural observer may be armed.

After the human turn returns and missions finish:

```lua
StackDispersionTests.Try("Check")
StackDispersionTests.Try("Cleanup")
```

Archive logs/positions before cleanup. Do not save/reload this fixture: the small helper does not implement reattachment. Preserve/reload a normal pre-fixture save for full restoration. A different candidate can be inspected after Cleanup with `Setup(true, nextPlotIndex)` using the startNext value printed by Plan, but limit retries to a small explicit number. Do not repeatedly search until an AI outcome happens to match an expectation.

## What makes the case diagnostic

The bounded map scan finds natural, unowned, flat, feature-free source/threat/exit tiles, with no units, cities, ownership, improvements or roads within radius3. Other terrain inside that buffer is left untouched. Four units are newly tagged: fixed AI Pike, fixed AI Archer, spare AI Pike on the same legal cap3 tile, plus one human Catapult at distance2. At most six adjacent exits are considered. The helper never alters terrain, strength, HP, promotions, buildings, AI weights or existing units.

Preflight requires normal mutual visibility, genuine legal Catapult fire and Archer return-fire capability, at least two collateral victims, positive collateral on the spare, and all members above their collateral floor. The SAME fixed Pike must remain primary in packed and split previews, preventing a changed defender/tie from manufacturing the gain.

Each candidate must have a legal two-node path using exactly60 movement and ending at0, with no affordable melee counterattack on the Catapult. Before arming, temporary repositioning measures **next-turn GetDanger for all three members** in both arrangements. The split must strictly lower summed danger, not worsen either fixed member, keep all three individually below lethal danger, and preserve the Archer's firing position. Being outside current siege range is insufficient: a moving Catapult may still threaten the exit. Many sites may correctly be nondiagnostic for that reason. Measurements restore position/movement on both success and failure, and clear stale readiness.

The first AI update freezes only the new fixed Pike/Archer and gives only the spare60 moves once; a temporary dominance focus at the siege tile exposes the tactical choice. Exact one-AI-update/one-human-return gates prevent a later-turn result being mislabelled. A no-move outcome is recorded as NO_DISPERSION; it is not forcibly changed or hidden.

Check requires all four units alive at unchanged HP, original fixed-pair/threat positions, legal capacity, and **zero unrelated entrants within radius3**. An entrant makes the clean result inconclusive, even when neutral. If the spare moved, Check compares the actual split with a temporary packed counterfactual at the SAME post-turn state, so ordinary turn fortification of the fixed protector cannot explain the gain. The spare must have zero fortify turns before any such movement. A positive outcome is LOWER_COLLATERAL_EXPOSURE; a different movement without measured gain is separately reported.

## Limits and residual effects

Summed per-unit GetDanger is a conservative tactical metric, not a joint probability model of one Catapult's alternative targets. This case measures useful avoidance of collateral while retaining a protected ranged unit; it does not prove all dispersion choices or explain the exact contribution of the explicit concentration preference versus normal danger avoidance. The bounded search may find no qualifying site, especially because moving siege can cover the adjacent exit. Report that limitation and leave the live coverage gap open rather than changing combat stats/weights or editing a map.

Native SetXY clears fortification and updates LastMoveTurn. Requiring an unfortified spare prevents a false benefit from lost fortification, but its hidden movement metadata is not restored by setting plot/moves back. Record the actual AI displacement before this diagnostic counterfactual and discard the fixture afterward. Cleanup prechecks every tracked unit for identity/busy state before deleting any. It restores tracked tech/war presence only; era/fog/diplomatic history, revealed resources and the temporary AI focus (which expires normally) are residual disposable-world effects.

## Preparation evidence

Lua5.1 syntax and inert loading pass.54 deterministic tests exercise actual helper functions: benefit gates, natural Plan no side effects, explicit tech grant, four-unit setup, exact measurement restoration after errors, stale readiness clearing, fortification rejection, duplicate callback suppression, fixed/spare movement budgets, one-turn stop even if return-snapshot code errors, final counterfactual restoration, outsider/later-turn rejection, all-unit cleanup preflight, and nondiagnostic refusal to arm. These are engine stubs, not actual danger/pathfinding/AI proof. See work/test-dispersion-helper.py and dispersion-helper-validation.json. Independent source/API review guided the failure-path fixes; no live result is claimed.

Final independent source/API review passed at work SHA2565378F1E6C170A77711B1AA5271CE7B6EF12A1C2D2F3BB1048C96F5C9E3DA9DAD. The work checkpoint is unchanged. Source uses the same function bodies with only the first comment renamed Manual: source SHA256623EE4ECE95CF0A5483591C67149CD09E10B4AACB438BACC900A5D54F069F182, MD5EA4B14C609861F69271F6C04DD00F068. Source Lua5.1 inert loading passes;54 offline tests cover the unchanged implementation. Source helper/project/modinfo register a manual VFS import only; no actions or entrypoints changed. Evidence: dispersion-helper-registration.json.

## First bounded live attempts

Two030606 fresh-default sites (17,13 and19,13; Catapult18,11; one exit each) failed the normal mutual visibility gate before BASELINE/READY/Arm. No AI choice occurred, no further retries or behavior/terrain/stat changes were made, and final readback confirmed no tagged units/observer and AI IronWorking absent. This leaves actual dispersion inconclusive/unexercised; it is not an AI failure. See work/test-runs/dispersion-030606 for exact logs/module/config proof and cleanup qualification.
