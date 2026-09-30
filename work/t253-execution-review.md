# T253 executor failures and prepared primary-identity fix

The original proposal was held during exact DLL56 cache validation. After that comparison passed, root authorized applying the primary-identity fix to production tactical source for the next build. The original proposal remains `work/primary-identity-production.patch`; source copies and integrity metadata are in `work/primary-identity-prepared`.

Patch file SHA256: `6e6d330eeeb9f455f028c634d81e84bc5b422d5d7e6464dbf833afda6e901ed3`. Pinned control: `0273c8e3e5104493af3be6ae62aec50bb576f7ae`.

## Observed cost and failures

Archived run `Stacking-20260930T211159-845-p16080-r1`, T253, has a 132.188s native event window and 99.943s summed PLAN time across 139 calls. Arabia (player3) attacking Utrecht (plot2225, 25:25) accounts for eight searches / 73.173s. The next largest target is Netherlands 25:26, two searches / 7.295s. `work/t253-execution-review.json` records the ordered evidence and source line numbers.

The first four Utrecht searches consume 47.947s. Three fail after ranged city shots labeled A_RANGEKILL (units8917,6976,6975, log lines4268/4274/4280). Scoring selects a simulated garrison and can predict its death; execution instead checks generic best defender, which can be another living stack member. The fourth failure, against a field defender at plot2315, is consistent with a legitimate damage-roll miss: successive native hits29+32+34 leave that defender alive. It must continue to trigger a new plan.

A later 18.365s search captures Utrecht: combat132, unit7223 advances from2224 to2225, city ownership changes Netherlands1→Arabia3. It nevertheless fails A_MELEEKILL's postcondition at line4321. The executor dereferences its saved generic defender after city entry, although `CvUnit::setXY` destroys hostile city defenders with `kill(false)` and `IsDead()` merely checks HP. A deleted object need not have HP set to its maximum. Three subsequent Utrecht searches consume another 6.861s; some restarts after a real capture remain necessary because visibility, city ownership and troop positions changed.

## Prepared fix

Add two ephemeral fields to STacticalAssignment: selected primary unit owner and ID. They are initialized by both constructors, cleared by init/wipe, copied naturally, and included in semantic assignment equality. ScoreAttackDamage records exactly its selected pEnemyUnit. A scored city with no garrison uses its city owner plus ID−1; unscored movement/healing has NO_PLAYER/−1. No save serialization changes.

Before combat, execution selects the native city garrison for city attacks or native stack defender for field attacks and matches its owner/ID to the forecast. This avoids confusing incidental collateral victims or a newly selected stack member with the planned primary. After the mission it resolves the same identity through its owning player's unit table. Missing, HP-dead or delayed-dead expected victims count as defeated; a surviving wrong victim never satisfies a kill.

City garrison kills require the city to survive as an enemy city; captures require attacker advance, ownership by the attacker and no remaining enemy combat occupants. No-advance melee kills require the expected victim's actual defeat even when a fresh preview revises damage downward. Existing city-attack policy guards also apply to range-kill and no-advance garrison attacks. Actors are resolved after combat before any dereference; missing/dead/delayed/plotless actors produce an owner/ID-based failure diagnostic.

The initial HP-consistency gate is excluded. Projected per-hit raw damage can be below current live HP while native randomness still produces a valid kill. Identity matching preserves that possibility and still detects actual damage-roll misses. Scores, damage math, recruitment caps, search breadth, state budgets and retries are unchanged.

## Offline evidence and memory

The initial poison-pointer prototype passed35 checks. The explicit-identity alternative passed108 checks using actual assignment/damage-container definitions and the actual final scorer classifier. The complete prepared source, including actor IsDead and safe diagnostics, then passed110 checks against pinned54. Source paths and mode are recorded in `work/stack-plan-primary-prepared-regression/result.json`; production remains untouched. The fixture default will test actual production after the patch is applied; `--prepared` explicitly selects these prepared source copies.

Cases cover garrison death with a different best defender still alive, ordinary stacked melee/ranged kills, no-advance behavior, deleted defenders after capture, known no-garrison/zero-damage-entry captures, owner/ID collisions, wrong-victim death, actual roll misses, favorable native kills, policy rejection, removed/HP-dead actors and diagnostics, plus lifecycle/copy/equality for all assignment types.

Genuine VC9/x86 reports STacticalAssignment112→120 bytes (+8), with the actual damage container36 bytes. The 2,000-entry assignment pool adds16,000 bytes. A pessimistic illustration of6,000 independently allocated position vectors each containing the largest observed89 assignments adds4,272,000 bytes (~4.07MiB); CoW sharing reduces actual usage, while vector capacity and longer promoted-unit sequences can raise it. This is an observed-workload estimate, not a universal hard ceiling.

No separate STacticalAssignment hash specialization was found. Existing forecast hashes describe combat state rather than the executor's primary metadata. Adding fields to equality narrows equivalence without violating an equal→same-hash contract; unequal records may still collide. Keep full equality checks. This proposal can intentionally distinguish branches that previously had identical damage maps but different primary victims.

## Remaining validation

Apply only after the exact canonical strength-cache replay, rerun `work/test-stack-plan-primary-applied.py` without `--prepared`, relevant actual-source regressions and the same preserved T251→254 native scenario. Expect corrected executor behavior to alter some valid planner/combat sequences; document those changes rather than treating a different result as automatically equivalent. Confirm Utrecht capture, legitimate roll/visibility restarts and actual turn timings. No game speedup is claimed from these fixtures.

## Applied-source validation after DLL56

The canonical replay matched all506 semantic records and all censuses, including capture. The reviewed fix is now in CvTacticalAI.cpp/h; scorer math is asserted byte-identical to pinned54 except the primary identity writes. Actual applied-source tests passed110 checks, city score-gate39, assault batches16, reserved capture20, and virtual-stack140,057, all with zero failures. Execution diagnostics passed89 checks before the final compact primary fields, then added three checks for their enabled/disabled mismatch behavior.

PLAN_EXEC_FAIL now includes expected primary owner/ID and the native primary selected before the mission, with reason `primary_changed` for an identity mismatch. Verbose PLAN_ASSIGN includes the forecast primary. Values come only from the assignment and already resolved locals; disabled diagnostics add no queries or snapshots. Actor removal retains safe owner/ID after-state collection. DLL build and native behavior/timing validation remain root's next step; no new native speed claim yet.
