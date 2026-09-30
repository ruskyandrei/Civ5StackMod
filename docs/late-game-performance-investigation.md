# Late-game performance investigation — 30 September 2026

Run: `Stacking-20260930T163501-573-p39396-r1`, campaign folder
`work/test-runs/campaign47-20260930-1735`. Production source reviewed at
`6c863259f`; installed/tested gameplay is DLL47. No production edits, builds,
tests or game calls were made for this review. The stopped campaign's native
segments, checkpoints and existing performance reports are the evidence.

## What the final recorded turn says

Follow-up status: exact allocation/lookup and duplicate destination-membership
optimizations passed offline comparisons and are committed at `2cc4911ba`.
Sampled original VP phase timing is included. No native speedup is claimed yet:
the first DLL47 control attempt crashed during post250 save loading at
19:56:52 BST in `CivilizationV_DX11.exe+0x0037bada`, before replay preparation.
Its dump/load logs are preserved under
`work/test-runs/perf-d47-c47-t251-control2/load-crash-evidence`. None of the new
source changes was deployed for that attempt. Closed-executable location alone
does not establish the underlying cause or exclude a mod interaction.

The nine canonical `native-segments/*-segment-*.log` files contain 17,003 paired
PLAN/PLAN_PERF records. Do not also count the original rolling `-00.log` etc:
those duplicate archived content, and `-00.log` has since been reused. Turn251
contains a partial final pass and is excluded from full-turn comparisons below.
Earlier `performance-check223.json` also contains only the start of turn225;
use the completed canonical native logs for later turns.

Intervals are from the first native tick for a turn to the first native tick for
the following turn. They include scheduling/foreground effects, not just CPU
time. PLAN timers overlap player unit-pass timers and must not be added to them.
PLAN_PERF's setup/finalize are coarse ticks; PLAN measures search time and is the
consistent quantity subtracted below. No diagnostics-off or upstream control is
available for this campaign.

| Turn | Full native interval | PLAN total | Searches | Stored search states | Near 6000-state searches | World units / counted combat | Stack tiles / largest |
|---|---:|---:|---:|---:|---:|---:|---:|
|150|18.047s|1.633s|87|26,988|1|568 / 406|69 / 5|
|181|22.813s|3.323s|86|44,384|0|667 / 461|80 / 5|
|200|33.281s|10.124s|83|58,210|3|734 / 520|115 / 5|
|220|28.797s|5.807s|120|40,926|1|805 / 589|121 / 7|
|224|73.672s|47.560s|100|121,105|8|821 / 595|124 / 7|
|240|62.812s|31.087s|127|138,506|10|837 / 605|115 / 7|
|246|41.469s|10.625s|115|67,632|4|851 / 602|125 / 7|
|250|68.000s|38.471s|125|92,997|5|851 / 607|130 / 7|

World unit/stack counts sum the first SUMMARY per player/turn. They are global
composition measures, not the number of threats at the costly target. The logs
do not expose every queried plot's attacker/candidate roster or membership-build
count, so exact local density and per-helper CPU shares cannot be inferred from
them.

Turn250's cost is concentrated:

| Actor and target | Calls at target | PLAN time | Relevant search details |
|---|---:|---:|---|
|Arabia3, 25:25|3|20.921s|10.529s: 21 supplied, 13 kept, 5,349 states, 503 completed; 8.776s: 24 supplied, 13 kept, 5,999 states, 361 completed; third 1.484s|
|Netherlands1, 25:26|1|8.078s|13 supplied/kept, 5,999 states, 314 completed|
|Mongolia0, 73:27|2|2.224s|11 supplied, 9 kept, about 4,300 states each|

The first two targets consume 28.999s, **75.38% of PLAN time**. These are real
completed searches, not a retry loop that never produces a plan. Across turn250,
searches with zero completed states consume 0.920s, only 2.39% of PLAN time.
An unconditional ban on failed searches would not solve the main spike and
would alter AI behavior.

Turn250 cache/phase totals:

- Danger: 6,898,527 hits / 345,827 misses, **95.23% hits**; 99,920 FIFO evictions.
- Combat strength: 19,767,845 hits / 674,851 misses, **96.70% hits**;
  36,132 evictions. All strength evictions occur in the 8.776s Arabia search.
- Explicit yields: 0.513s total; setup 1.646s total. Strength invalidations152
  mostly accompany the mandatory UI yield points. Zero reported logger ticks
  is coarse-clock evidence, not proof that diagnostics cost zero CPU.
- Non-PLAN interval: **29.529s**. Removing all search time could only approach
  that floor. Hypothetical 20/40/60% PLAN savings give 60.3/52.6/44.9s full turns
  if the rest is unchanged. These are arithmetic scenarios, not forecasts of an
  implementation's benefit. Sub30 for dense turns needs non-PLAN work too.

The worst 10.529s search does not even reach the 6000-state limit. Its 5,349
states request 8,719,621 cached strength hits and 122,634 misses: about 1,630
strength-hit calls per stored state. This is the best bounded replay to profile,
alongside the payload-limited Netherlands search and earlier saved275 control.

## Scaling: expensive combinations under a fixed bound

The underlying move-assignment problem is combinatorial. It is not accurate to
claim that turn time is an unbounded exponential function of empire unit count.

`CvTacticalAI.cpp:46–47` caps movable actors at13 and switches from breadth-first
to depth-first after three generations. `FindBestUnitAssignments` clamps branch
and choice limits at13746–13748; the storage limit is checked at13974 and is
6000 for the running profile. `makeNextAssignments` at10845 enumerates each
available unit's reachable moves before choosing children. The unit cap does
not eliminate nearby enemy threats or fixed friendly occupants omitted from
the actor set. Each state can therefore become much more expensive in a dense
battle even when state/branch counts are unchanged.

Rough work per search is bounded stored states multiplied by available actors,
their reachable destination count, and the cost of scoring each destination.
Danger misses additionally traverse all known attackers and select/score every
surviving eligible stack defender after each hit. Injury containers use linear
ID scans; defender selection and repeated candidate-health reads add further
density-dependent work. Larger movement ranges, roads, overlapping attackers
and fixed occupants can increase this work independently of the13 actor cap.

Multi-batch assaults at `FindAndExecuteBestUnitAssignments`13650 deliberately
launch several separately bounded searches. The existing defaults are three
batches, four bounded retries, and a per-turn extra-batch budget. The Arabia
target's three substantial searches are compatible with that intended behavior.
Do not reduce these limits or skip batches to advertise an exact speedup.

## Ranked exact work to remove

### 1. Remove role-query strings and the repeated enable-map lookup

`CvStackingRules.cpp:385–410` constructs
`std::make_pair(id, std::string(role))` for each combat-class, class and explicit
unit-role lookup, then scans promotion-role rows. Calls originate in defender
flanking/interception selection (`CvUnitCombat.cpp:146–181`) and every collateral
limit lookup (`CvUnitCombat.cpp:272`, `CvStackingRules.cpp:476–478`). Even an
attacker with no collateral role takes this lookup path before returning zero.

`COLLATERAL_LIMIT` is16 bytes. The bundled VC9 `xstring` has a16-byte char buffer
including the terminator (`xstring:2063,2158`), so that temporary cannot fit its
15-character inline capacity. Each of the three role map lookups creates at
least one heap-backed string; exact copy/allocation counts require the native
source fixture. Short names such as FLANK and ANTI_CAVALRY still require string
construction/comparison, but should not be described as allocating solely due
to their length.

The loader at `CvStackingRules.cpp:283–315` accepts only four role names. A
private enum-keyed role map can convert those names once during loading. Keep
XML names and all public functions unchanged. Preserve precedence exactly:
combat-class default → class replacement → maximum with owned promotion grants
→ explicit unit replacement, including explicit0 disabling a granted role.
Owned promotions must still be read dynamically; do not permanently memoize a
unit's final role without proper promotion/reset invalidation. Promotion rows
can be indexed by role at load time, preserving their max-grant result.

`IsEnabled`428 currently does `GetInt("Enabled",0)` on every call. A boolean
inside RulesCache can mirror defaults, missing-schema0 and each clamped Enabled
row. `IsEnabled` must still call EnsureCache and ResetCache must reset the field;
no permanent static bool. Mirror during loading, not only at its end, so any
reentrant read sees the same state as the settings map. GetInt fallback, null
name and lazy/no-database behavior remain unchanged.

Tests: extend `test-stacking-setting-lookup.py` with actual loader/IsEnabled
comparisons during DB callbacks and reset/default/clamp/failure/missing-schema
cases. Add an actual Role/Lookup/LoadRoles fixture with real VC9 allocation
counting, all precedence cases, late promotion changes and0 replacements. Pin
the original source as a control. These are small, broadly used exact changes;
native call counts and seconds saved are currently unknown.

### 2. Build destination membership once within a scoring call

`ScorePlotForCombatUnitMove` calls `GetUnitDangerForPlot` at9635 and later
`ScoreStackPosition` at9711 with the **same unit, target plot, projected
selfDamage and const position**. Both call `GetVirtualFriendlyStack` independently
(wrapper8368 and scoring8427). That builder copies fixed members, resolves each
movable ID and searches `GetUnitStats`7481 through up to three unit-stat vectors.
The second call also asks the danger cache for solo and protected forecasts.

Reuse one caller-local lazy membership/damage buffer for these two calculations.
Preserve ordering, duplicates, arriving-unit deduplication and exact wounds.
Keep fixed-hazard early returns so safe singleton queries do not suddenly build
rosters. Invalidate/rebuild on existing scene/revision/depth/thread changes;
nested callbacks use private storage. Do not hold the shared buffer through
unrelated source-penalty or flank calls, causing accidental fallback allocations.
Raw cached danger and INT_MAX conversion must stay distinct; the stack score
uses raw/capped values, whereas GetUnitDangerForPlot converts the sentinel.

Tests: extend actual-source virtual-stack/scorer fixtures to compare every
score/result with DLL47, count membership/HP lookups and allocations, and exercise
fixed danger, source/destination wounds, missing stats, mixed domains, duplicates,
healing and sentinel cases. Require callback mutation/nested/foreign checks.
Measure the removed work rather than assuming the whole95% hit path disappears.

### 3. Prototype one exact outcome ledger for all queried stack members

`CvDangerPlotContents::GetStackDanger`1150 simulates the full stack from the same
friendly and enemy wounds for each queried member. For the non-city branch,
the queried unit mainly supplies defending owner/team and its final damage
projection. Selected defender, collateral, interception-use ledger and sequential
casualty selection depend on the shared stack state. The city helper1085 also
updates a shared occupant ledger before the queried member's delta is returned.

A bounded cache of the **final damage ledger** could reuse one expensive attack
sequence across different members, followed by each unit's own fog/terrain
damage and sentinel handling. This has greater potential to eliminate leaf
work than simply optimizing another string comparison, but needs a complete
dependency proof and opportunity count before implementation.

Key constraints: queried owner/team; exact friendly-city branch semantics
(`CvPlot::isFriendlyCity`4881 uses combat owner/open borders, not just owner ID);
ordered candidate membership, full relevant friendly wounds, exact enemy/city
wounds, plot/scene/city state; unit-specific hazard calculation stays outside.
`StackAirStrikeChance`1000 reads friendly wounds for interceptors **outside the
candidate stack** too. Do not drop those values from a proposed shared key
without proving they cannot vary in that caller. Preserve interceptor iteration
ties/uses, damaged AA, cavalry filters, field/city garrison replacement, city
capture sentinel, damage rounding and actual unit/city ID alias conventions.

Store value payload under a strict existing memory budget and retain private
fallbacks for inactive/nested/foreign callbacks. No cached raw CvCity pointer
may outlive scene changes. A ledger copied on every hit could cancel the gain;
borrow an immutable result only for a validated scene and caller lifetime.

Tests: actual full GetStackDanger and its helpers, original per-member calls vs
shared outcomes, field/city/air waves, hidden nationality/open borders, outside
AA wounds, sequential defender deaths, HP floor/collateral rounding and all
sentinel paths. Count distinct member queries per shared exact state first.
This is a higher-risk second phase; existing counters do not quantify overlap.

### 4. Reduce strength-hit/key overhead and scene-invariant miss work

Every hit still runs `MakeStackStrengthKey` (`CvUnit.cpp:16354`):20 integers,
live identity/HP/position getters and times-attacked lookup. The wrapper then
calls Context again through `CvStackingStrengthCache::Lookup` (cpp77–100), hashes
and compares the complete key. Turn250 has19.77 million such hits. A profiler
should separate key construction, hashing, epoch checks, table probing and leaf
misses before choosing a new cache design. Exact cached hash/safe key fragments
may help; hashes must remain bucket selectors, never substitutes for equality.

Uncached ranged-strength code (`CvUnit.cpp:17191` onward) still computes nearby
unit/improvement/city and adjacency modifiers for different projected HP keys.
Some modifier fragments are scene-invariant for the same unit and plot and
could be reused under the existing locked-scene lifetime. Do not factor injury
math speculatively: health, attack flags, target class, promotion conditions,
rounding and times-attacked are genuine inputs. Keep all Context/yield/foreign
mutation guarantees from `test-strength-cache.py`.

The selected-defender exchange cannot simply replace the final threat hit:
`GetStackExchange` uses non-quick leaf rules, while the danger caller's tactical
damage helper includes different adjacency/quick flags, legality, ranged support
and tile damage. Treat apparently duplicate damage calculations as distinct
until proven identical for a narrowly defined case.

## Measurement and implementation sequence

1. Keep DLL47, save251, XML and current diagnostic profile as the frozen control.
   Use a copy of the save and reproduce the original observer/human-unit setup
   before each replay. Turn251 is a continuation workload; it is not identical
   to completed turn250. Preserve an immediately pre250 save if available.
2. Add low-cost integer counters, or use a native CPU sampling profiler with
   matching DLL/PDB, to identify Role calls/allocations, membership builds,
   danger-key integer/hash work, strength-hit overhead and uncached leaf time.
   Add phase timers around non-PLAN military/allocation/path/world processing;
   the29.5s outside cannot be attributed from current PLAN logs. Avoid per-query
   string output or millions of timer calls that distort the workload.
3. Implement/test the settings/role representation first, then membership reuse.
   Each stays in a separate reviewable change with an original-source control.
4. Compare native decisions, real combat/city-action records, full unit/city
   census, ownership/HP/positions, occupancy and casualty sets. Preserve branch,
   actor, state, completed-position and batch/retry settings. Only source-level
   work counts/cache hit counts should drop for exact reuse.
5. If gains are too small, use the sampled profile and shared-ledger opportunity
   counts to justify the next change. Report actual seconds; do not extrapolate
   a helper microbenchmark into a universal late-game turn guarantee.

Expected outcome of the first two changes is a measured incremental reduction,
potentially seconds on dense searches if those repeated operations dominate.
No percentage is established yet. The68s turn needs both substantial tactical
work reuse and a separate non-PLAN investigation to approach30s consistently.
