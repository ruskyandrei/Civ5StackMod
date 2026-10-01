# AI follow-up implementation — 1 October 2026

Authorized scope: work through the six decisive-war priorities while keeping
complete dense-turn regression within10%. The earlier <30s optimization effort
is separate. Existing tactical13-unit/6,000-state and bounded path/work limits
remain; new numerical policy is editable in StackingConfig.xml.

## Baseline and acceptance

Fresh DLL96 replay: `work/test-runs/perf-ai-followup-baseline96-251-255`, native
`Stacking-20261001T123357-831-p39784-r1`, immutable manual251 source
SHA256 `2A31D7020FFA5348582DD46442D079308CEDC7880248C1B1623A39FF62BC659B`.
Standard view, five campaign mods, quick combat/movement, Summary diagnostics,
tactical/instruction sampling off. Complete252 takes31.547s; dense253 takes
57.517s (PLAN32.994s). The dense acceptance ceiling is63.2687s, 110% of this
fresh control, rather than rounding the limit up from an approximate60s.
Normal closure12:36:43UTC; game/service/session absent, both guards disarmed.

Final comparisons must use the same save/configuration and complete native
turn boundaries. AI decisions are expected to change; semantic differences
are reviewed, not treated as cache-equivalence failures or hidden as timing.
Record search/call counts, full-turn and phase timings, memory and failures.
Repeat borderline results before accepting; do not retain a large regression.
Behavior acceptance uses directed source fixtures and native saved scenarios,
then longer campaigns measuring actual attacks and10/20-turn conquest retention.
One replay does not establish conquest rates or general late-game performance.

## Work packages — implemented, native acceptance pending

1. **First wave and core admission.** Separate desired army/reserve size from
   essential roles and sustainable combat power. Evaluate coherent subsets of
   already-scanned healthy units; optional late arrivals must not veto a useful
   first wave. An essential delayed capturer or siege battery still matters.
   Align operation/formation readiness and voluntary opening with that decision;
   do not credit an unrelated army or release a distant army based on loose troops.

2. **Affordable role production.** Connect missing siege/capture/ranged demand
   to native production sanity checks. Only a bounded domain-recommendation
   exception with actual supply and affordable budget headroom is eligible.
   Retain maintenance, resources, training, purchase, home-front and deployment
   safeguards. Credit each queued unit/formation promise once and invalidate
   cached queue totals on every head change. Full budgets do not permit free
   extra units or arbitrary scrapping of useful troops.

3. **Reinforcement continuity and contribution.** Track verified movement
   toward a stable staging route using already-generated paths. Repeated no-op
   orders and changed stages must not refresh progress. Separate real combat
   contribution from arrival/training, preserve useful support through detours,
   release futile holdings and keep existing stalled-queue safeguards. Keep
   reserves/replacements tied to the same objective and protect essential roles.

4. **Healing forecast.** Share exact native healing arithmetic when the AI is
   entitled to the required information. For ordinary visible enemy cities,
   retain an explicitly incomplete visible-information estimate. Preserve full
   blockade, damage-history smoothing/quiet turns, building and defense-process
   order. Planned city damage is after ordinary garrison absorption. Do not
   modify actual city healing, HP or fortification balance based on one campaign.

5. **Preparation/target feasibility.** Validate voluntary declarations against
   staged roles, legal domain routes, sustainable damage and affordable support.
   Preserve bribe/pact/forced-war exceptions. Test coast/water/closed-border and
   missing-capturer cases using VP's existing embark/invasion mechanisms; avoid
   introducing unrestricted transport or extra per-turn path work.

6. **Diagnostics and evaluation.** Record compact predicate/wave, production
   rejection, progress and contribution explanations from already-computed data.
   Preserve logger-off behavior. Run directed regressions for existing city
   defense/capture/fire scheduling and multi-front safeguards. Test balance and
   broader naval/air/cooperative coordination with campaigns before making
   unsupported mechanical changes.

Shared source patches are composed sequentially. Each work-only stage is bound
to the current source and receives directed tests; the integrated candidate is
rebuilt/tested before installation. No experiment from the paused performance
branch is silently reintroduced.

## Offline progress

The fresh control also matches the earlier96 replay's699 retained events and
both nonempty censuses. Healing passes13,785 source-based VC9 checks. Initial
reinforcement/contribution coverage passes73 checks, including logging off/on,
actual transfer-before-route ordering, reciprocal reversal, changed stage,
no-op ETA changes, reset/wrap, missing victim identities and timeout boundaries.
Peer review corrected a pre-readiness safe-shot clock and separated route credit
from useful siege progress. The complete combined offensive module passes50
additional wave/core checks; production passes61; the integrated healing suite
passes13,785. These execute actual candidate functions with explicit modeled
engine services. They do not prove campaign effectiveness or turn times.

Retargeting and cancellation invalidate the previous objective's cached staffing,
as well as the new objective. Native births/losses, army membership changes,
city creation/acquisition/removal, production queue changes and completed economy
orders invalidate the relevant budget/staff caches. No new path queries or larger
tactical search limits are introduced. Candidate native acceptance remains pending.

## New XML settings

All settings are rows in `(1) Community Patch/Database Changes/StackingConfig.xml`.
DLL loading clamps values to the listed ranges.

| Setting | Default | Range | Purpose |
| --- | ---: | ---: | --- |
| AIAssaultEssentialSiegeUnits | 2 | 0–32 | Minimum land siege core, bounded by desired siege count |
| AIAssaultFirstWaveMaximumTurns | 1 | 0–4 | Latest arrival admitted to a first wave |
| AIAssaultWaveMaximumRecords | 64 | 4–256 | Bounded per-objective wave metadata |
| AIAssaultIncompleteDamagePercent | 125 | 100–300 | Required damage margin when healing inputs are incomplete |
| AIOffensiveProductionRoleRepairUnits | 2 | 0–8 | Bounded allowance for actual missing combat roles |
| AIOffensiveProductionRecommendationSlack | 2 | 0–8 | Domain recommendation slack, subject to supply/economy gates |
| AIOffensiveContributionRadius | 2 | 0–6 | Nearby combat eligible as objective contribution |
| AIAssaultAttackProgressStallTurns | 24 | 0–240 | Abandon a ready siege without net city progress; 0 disables |

`ASSAULT_PLAN`, `WAR_READINESS` and `OPERATION_READINESS` report the selected
wave and failed predicates: capture1, siege/ranged2, count4, strength8,
sustainable damage16, cohesion32, own-army core64, incomplete evidence128.
`OFFENSIVE_PRODUCTION` reports bounded rejection reasons from already-computed
intent. `OFFENSIVE_CONTRIBUTION` separates actual city/field damage and capture
from arrival. The offline summary reader recognizes these categories.

Target selection already filters approach/domain/third-party border routes.
A production budget should constrain proposed new builds; zero headroom alone
does not prove a fielded army cannot attack. Global army/navy recommendations
distribute the full soft supply cap; the old basic-army constant weights that
distribution rather than imposing a six-unit army ceiling. The implementation
therefore repairs bounded role production within affordable headroom and first
wave admission, rather than blindly increasing total military recommendations.
