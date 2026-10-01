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

## Work packages — implemented and deployed

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
tactical search limits are introduced. Native acceptance results follow below.

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

## Native acceptance — DLL102

Implemented in commits `b27db7970` and `19fa6e5ad`. Installed build:
`Release-5.4.6-102-g19fa6e5ad Clean`, DLL SHA256
`5CC28920C2625C3685F9E2484DE4D3C62E476201591794F4DB718F7E7FDC22E4`.
Release compilation and all2,368 deployment-file checks passed. Deployment
preserved saves and graphics settings, with the previous installation archived
at `work/backups/deployment-replaced-20261001-150650-2d5fcdbb`.

| Dense turn253 | Seconds | Difference from accepted control |
| --- | ---: | ---: |
| DLL96 control | 57.517 | — |
| DLL102 first run | 59.641 | +3.69% |
| DLL102 repeat | 59.375 | +3.23% |
| Acceptance ceiling | 63.2687 | +10% |

The archived legacy event boundary actually measures57.515s for the control;
the accepted57.517s and strict ceiling are retained explicitly, with the2ms
discrepancy reported by the gate. Both candidate runs used the same immutable
human251 save and five mods, stopped255, closed normally, stopped their Lua
services, removed session files and disarmed both guards. No guard trigger or
crash occurred. The repeat's retained semantic records and before/after censuses
match the first run exactly. Dense PLAN work:34.949s/136calls first,
34.786s/136calls repeat, versus32.994s/143calls control. Timing includes game
behavior changes, rather than isolating pure overhead from the new predicates.

All archived map/speed, quick-combat/movement, view, Summary/sampling and existing
raw XML controls match. The baseline did not archive engine INI logging/threading
controls, so strict engine-configuration equality is unknown; it is not inferred
from the unchanged intended setup. Results qualify this saved test under its
recorded controls, rather than guaranteeing all future late-game turn times.

Native mechanism evidence: the Mongols launched a10-unit naval wave at Hippo
Regius despite a22-unit desired target, reducing cityHP598→407 with six hits;
Arabia used a6-unit wave at The Hague, reducing494→343 with three hits. Cumae
also received nine hits/224damage. Those city attacks were absent in the control.
Utrecht's turn253 capture and17-hit sequence remain unchanged. All13 new combat
contribution rows match nearby native combat summaries. Support-production logs
contain10 queued/4 completed observations versus4/1 in the control; these are
retained observations, not unique-unit counts. Rejections remain bounded by
domain quotas. No truncated diagnostics or concrete gameplay defect was found
in this short window.

Native operation-core and voluntary-declaration gates were not exercised by
this replay; their directed source fixtures pass. Rome's fleet had movement,
but no city-assault objective in the retained evidence, so this test does not
prove a general naval target-selection fix. A fresh long campaign should measure
first effective attack, net siege progress, economy stability, reinforcement
contribution and10/20-turn conquest retention. More captures or faster durable
conquests have not yet been demonstrated; no city balance changes are justified
by these four turns alone.

Reproducible offline gate: `work/check-ai-followup-performance.py` (eight boundary
self-checks). Derived evidence is in the two `perf-ai-followup102*` run folders,
with `ai-followup102-performance-gate.json`,
`ai-followup102-repeat-performance-gate.json` and
`ai-followup102-repeat-comparison.json` under `work/test-runs`. Integration
fixtures use `--source-dir work/ai-followup-composed`; source adoption validation
uses `work/adopt-ai-followup.py --verify-applied`. To reconstruct that directory,
run the four component staging scripts, then `compose-ai-followup.py` (expected
explicit merge conflicts) followed by `finish-ai-followup-composition.py`.
