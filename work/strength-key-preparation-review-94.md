# Strength-key preparation review, DLL94

Read-only against3601cc10c. No core edit, compiler, native call or microbenchmark.
The matched T253 archive records27,025,346 ranged hits,15,697,048 defense hits,
6,993,094 attack hits and188,725 generic hits:49,904,213 total. It also records
1,641,468 misses,56,864 evictions,303 invalidations,445 capability scan attempts,
flags0 and no validation bypasses. These counts establish repeated preparation,
not its CPU share.

## Exact original key schema

|Words|Inputs|Reuse boundary|
|---|---|---|
|0|kind0/1/2/3|Exact cache-function kind|
|1–5|self owner/ID, ACTUAL live plot, damage, maxHP|Native identity and live health/position; hypothetical origin is separate|
|6–10|other owner/ID, actual plot, damage, maxHP; exact null sentinels|Owner-qualified identity, never raw ID alone|
|11–13|city owner/ID/native damage; exact null sentinels|City and unit namespaces remain distinct|
|14–15|provided/normalized source and target plot indexes|Hypothetical coordinates; preserve kind-specific null semantics|
|16|attack, adjacency, quick; defense ranged/embark predicates|Complete flag tuple, including physical embark/terrain eligibility|
|17|canonical own projected-wound modifier, or ignored/shortcut0|Actual GetDamageCombatModifier result, not raw damage or a bucket|
|18|attack opponent wounded and below-half predicates, or0|Melee floor-half versus ranged ceiling-half; defense ignores it|
|19–20|opponent and city times-attacked by SELF OWNER|Both counters coexist when both targets are supplied|
|21|live same-promotion previous-attack bonus|Setter has no direct scene invalidation|

Kind0 normalizes null source to self.plot and has both projected words0. Kind1
normalizes null source likewise; target fallback is explicit other plot, then
other unit plot, then city plot. Kind2 preserves NULL origins. Kind3 preserves
both null plot arguments and adds its original embarked shortcut predicates.
Do not substitute simulated SUnitStats position for the actual live plot words.

## Work that genuinely remains before a hit

MakeStackStrengthKey returns a fixed22-int/88-byte POD. It does not allocate,
copy a ledger/vector, query a database, or walk neighboring units. GetMaxHP
performs base*(100+modifier)/100+change. Unit::plot uses checked canonical
coordinates; damage/promotion/counters are fields or indexed fields. Several
owner/plot getters are repeated and can be loaded into locals, but these are
bounded reads. The old assertion-formatting frames were already addressed.
Source return-by-value alone does not prove extra88-byte copies; actual VC9
assembly must establish copying/stack-cookie cost.

The nontrivial repeated preparation is GetDamageCombatModifier: player wound
modifier, stronger/fight-well damaged unit/trait flags, ranged-health option,
nonpositive assumed-damage fallback, then exact integer arithmetic. Ranged
also derives effective base strength/support-fire. Defense also evaluates
CanEverEmbark and plot.needsEmbarkation. All are bounded; their projected inputs
change while many physical inputs may remain fixed. Original Lookup still
performs a second Context, full22-word hash and complete equality.

## A defensible bounded experiment

A caller-local same-pair/plot/flag preparation template could reuse original
getter outputs in a proved immutable native interval, then supply fresh exact
canonical projected fields and invoke the EXISTING Lookup. It must retain all
22 original words and both counters. A template that merely matches pointer,
epoch and projected damage is insufficient: maxHP/damage/position/history
setters can change without a new scene epoch, and actor/unit/city owner aliases
and pointer reconstruction must be excluded. Either live-validate those words,
or prove the narrower lexical callback-free caller interval rather than relying
on an unrestricted whole-search assumption. Tables indexed by arbitrary raw
unit IDs, another global pair map, or unbounded per-HP precomputation are poor
first choices; their lookup/storage overhead can erase the gain.

An independent representation possibility is a tiny OWNED key scratch loan
instead of a local array, while retaining every original getter/key write and
lookup. If actual assembly shows costly successful-wrapper frames, this could
remove them without any immutable-input assumption. Normal ownership, busy,
nested/private/foreign fallbacks and post-key Context remain; the outer key
must survive miss computation that can invoke other strength functions. Private
fallback should be cold, not embed an array in the normal scope. No /GS setting
change or new result cache is warranted. This is a proposal to inspect assembly,
not evidence that the current strength wrappers have that cost.

Both candidates need outer Scope lifetime as well as epoch: Scope Clear/reopen
can start a different search without a distinct scene signal. Existing lock,
modern-option and native AIR/loading capability proofs, rebuild suspension,
real-yield invalidation, thread/depth and post-compute admission must remain.
Prepared metadata must be bounded and released with that scope; no table
budget, FIFO policy or search limit changes. Unlike vector danger keys, strength
keys have no source-capacity preflight to preserve, but node/result residency
and ring replacement remain unchanged.

The next source fixture should compare every generated original22-word key and
the existing hit/miss/eviction sequence, not only equal final strength. Include
null normalization, city+unit counters, actual versus virtual plots, live HP/
maxHP/history changes without epoch, traits and support-fire, floor/ceiling
boundaries, negative wound fallback, ignored extreme arguments, outer reopen,
foreign/nested/busy, dirty suspension/yield, allocation fallback and full hash
collisions. A successful source fixture supplies correctness and operation
counts; only matched native timing can supply seconds saved.
