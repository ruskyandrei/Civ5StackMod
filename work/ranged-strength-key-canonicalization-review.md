# Ranged strength projected-wound key review

Read-only against the frozen DLL56 source. No production changes, DLL/game calls or compiled fixture runs. This is a potential follow-up after the next behavior fix and measured waits, not a claimed native speedup.

## Exact projected-argument inventory

`CvUnit::GetMaxRangedCombatStrengthUncached` at CvUnit.cpp17265–17857 contains only these uses (besides parameter declarations):

| Argument | Use | Required observable key value |
|---|---|---|
| iAssumeExtraDamage |17850: GetDamageCombatModifier(!bAttacking, getDamage()+extra)|Exact integer result of the existing helper, with its original attack/defense mode|
| iAssumeExtraOtherDamage |17685: opponent getDamage()+extra >0|Wounded predicate bit, when attacking and opponent exists|
| iAssumeExtraOtherDamage |17691: opponent getDamage()+extra <(GetMaxHitPoints()+1)/2|Below-ceiling-half predicate bit, under the same condition|

There is no other projected wound argument use or propagation to religion, flank, aura, city, terrain or class/domain helpers. Those read unchanged live objects and are covered by the existing fixed-scene contract and retained metadata. The final -90 clamp and multiplication remain in the original body.

Thus kind1 word17 can store the exact wound modifier and word18 the two predicate bits. **Ranged uses ceiling half**: HP101 switches at51; full melee switches at50. Do not reuse the kind2 floor-half predicate. When defending, projected opponent damage is ignored even with a nonnull opponent; word18 can be zero. When the opponent is null it is likewise zero, including an ordinary city attack. When both city and opponent arguments exist, the opponent predicates still apply for attacks, and both independent attacked counters must remain.

Keep all other22word fields, live own/opponent damage and maxHP, city identity/damage, normalized source/target plots, attacking/quick/adjacency flags, independent unit/city counters and same-promotion history. Kinds0/2/3 retain their accepted contracts. This does not canonicalize danger ledgers, final strike damage, HP-based interception probability, collateral floors or city projected damage; those continue to use raw projected wounds.

## Exact shortcut and ignored arguments

The effective base at17292–17301 is GetBaseRangedCombatStrength(), overridden for ranged-support fire by GetBaseCombatStrength()/2. Only if that effective integer base is exactly zero does the original body return before either wound argument is observed. Combat strength1 support fire therefore also returns zero. In that case both projected words can be zero without calculating their sums or invoking the wound helper. Do not treat every base-ranged0 unit as returning0: a support-fire melee unit can have a positive effective base.

There is no embarked-defense shortcut in this ranged function. Do not import kind3's embark rule. No-capture, used attacks, naval fire forbidden from a city, cargo, delayed death and move eligibility are checks elsewhere, not additional strength-function shortcuts. Do not use those to erase its argument dependencies.

For nonzero effective base, own helper must receive the exact original total. It uses nonpositive assumed damage as a fallback to live damage, observes wounded player/unit modifiers and stronger-when-wounded, and applies ranged-defense health immunity only after the stronger-when-wounded branch. No clamping or HP buckets are equivalent to this contract. Guard unused opponent arithmetic when defending/null/zero-base so ignored INT_MIN/INT_MAX arguments do not become newly evaluated expressions. Preserve ordinary active-branch arithmetic and the existing ceil expression.

## Scripted callback boundary

At17782 the ranged body calls pCity->IsBlockadedWaterAndLand for attacking-city queries **even in quick mode**. The path is City.IsBlockaded→adjacent Plot.isBlockaded→native enemy canEndTurnAtPlot→canMoveInto→optional scripted CanMoveInto. The present kind1 cache wrapper17245 has no matching bypass. Broader equality can skip more of those scripted calls than the raw-key memo. A bounded future wrapper should bypass caching when MOD_EVENTS_CAN_MOVE_INTO && bAttacking && pCity, regardless quick. Preserve the body and its callback order; never add a fallback bypass that first computes an outcome and then repeats the original body.

Range flanking, terrain/fortification, aura and religion getters inspected here are read-only scans/info/stat getters; no additional projected argument is passed to them. No HeavyCharge fallback is present in this ranged body. Keep lookup's post-key generation check and scene/nested/foreign/admission behavior; effective-base/wound-key work must introduce no mutable world action.

## Fixture proposal

Compile the complete actual ranged body and current22word key/cache module against the pinned raw DLL56 wrapper, adding only a work-only canonical wrapper. Use actual GetDamageCombatModifier and base-support calculation. Numerical player/plot/religion/aura services may be deterministic substitutes, but do not substitute the entire ranged body with the existing small ranged stub: it deliberately depends on raw otherHP and would be an invalid oracle for this equivalence.

Test equal canonical key ⇒ equal original full strength across own negative/zero totals and live fallback; stronger/fight-well traits; defense-health setting; odd/even/HP1 ceiling boundary; attacking versus defending; city plus opponent/counter combinations; raw null arguments and their existing normalization; support fire with combat0/1/2/positive and zero effective base; ignored extreme arguments; fields unchanged outside17/18; key/compute invalidation, nested/foreign/disabled contexts and scripted city callbacks in quick and nonquick modes. Keep a bounded synthetic pressure comparison with unchanged cache capacity. It measures entry/miss/eviction opportunity, not game time.

The hypothesis is reduction of duplicate ranged entries and their pressure on the shared strength table, especially ranged-defense calls and city attacks whose raw opponent wounds are unused. Native kind-specific hit/miss/eviction and full semantic/census replay must decide whether the extra per-hit modifier/base reads are worthwhile. No new budget or gameplay limits are required.

## Work-only proof results

`work/test-ranged-strength-key-canonicalization.py` now compiles the **complete actual ranged and wound modifier bodies**, byte-matched to `c6067cda5`, with the actual22word key, cache/context module and raw kind1 wrapper. Player/plot/religion/aura services are deterministic fixtures. The candidate wrapper exists only in generated fixture C++ and adds the proposed observable wound keys plus scripted-city bypass.

**3,005,861 checks passed, zero failures.** Three hundred randomized profiles compare equal canonical keys to original full results and preserve all other key fields. Targeted cases cover ceilHP101 at51, own live-damage fallback, city plus opponent, defense-unused other wounds, zero ranged strength, support combat1→0 and combat2→nonzero, unused INT_MIN/INT_MAX and maxHPINT_MAX ceiling on defense, dirty-key/compute/nested/foreign/inactive/zero-budget transitions, and scripted-city callbacks even in quick mode.

Same64-entry synthetic trace (no native speed claim): attacking19,200→162 misses and19,136→98 evictions; defending19,200→1 misses and19,136→0 evictions. No capacity increase. The test's simple pressure profile intentionally holds every other argument fixed; the native campaign will have many identities/plots/flags and less reusable overlap.

Production CvUnit.cpp remains unchanged for kind1. Candidate58 requires separate root authorization/native comparison after the behavior fix; these proof counts do not establish a native improvement.
