# Target-distance field: measurement and future reuse boundary

This stage adds measurement only. It does not skip either flood or retain fields
across calls. Current control is DLL93 e38b19798; source bytes, full helper reversal and
existing emitter/reader behavior are recorded in source-proof.json and the
32-check light test-result.json. C++ compilation has not been performed here.

The single `target_distance_fields` TurnPhaseScope surrounds the complete
unchanged UpdatePlotDistanceToTarget body. It therefore includes the clear,
both GetPlotsInReach calls, their copies into gDistanceToTargetPlots, and the
gTargetPlot assignment. It is an inclusive combined wall/CPU interval, enabled
by existing Summary performance category/interval rules and bounded by the
existing per-turn diagnostic row budget. No new settings or formatter are
introduced. The staged reader adds only tactical-family recognition; parent
exclusive-remainder tables retain their existing child map, so this new row
must not be added to enclosing tactical/operation rows as another cost.

## Exact field inputs

UpdatePlotDistanceToTarget creates SPathFinderUserData with the player and
PT_LAND_UNIT_SIMPLE. It sets NO_EMBARK when CanEmbark is false, floods from the
target, then changes the same data object's path type to PT_NAVAL_UNIT_SIMPLE
and adds NO_OCEAN when the team cannot build an ocean-crossing unit. The land
flag remains in that same naval data object. A future replacement must preserve
the complete data/default flags, not normalize them to only flags used by the
two validity callbacks.

LandUnitSimpleValid reads revealed-to-team, water/deep water/mountain/ice,
CanCrossOcean/Mountain/Ice, ownership, friendly territory, war, and whether the
owner is a major civ. NavalUnitSimpleValid reads revealed state, water/coastal
city/passable improvement, deep water/NO_OCEAN, ice capability and the same
territory tests. Coastal passability includes MOD_GLOBAL_PASSABLE_FORTS,
improvement passability/pillaging, coast status and friendly permissions.
Friendly territory includes team open borders and minor-civ earned open borders.
CanCrossMountain also depends on generals-created when the relevant trait is
present; CanCrossOcean and CanEmbark combine team state and traits. Ordinary
unit HP and ordinary tile occupancy do not occur in these two callbacks.

These paths are StepFinder paths: CanEndTurnAtNode always returns true, costs
use the configured constant PATH_BASE_COST, and there are no initialization,
uninitialization or extra-child callbacks for these two path types. That narrows
the numerical field dependency; it does not make GetPlotsInReach itself pure.

## Hidden StepFinder state prevents a naive early return

GetPlotsInReach acquires the core lock if absent and calls Configure. Configure
replaces m_sData, callbacks and basic cost. FindPathWithCurrentConfiguration
increments the ushort generation (wrapping at0xFFFF), changes start/destination,
sanitizes flags and Reset clears previous touched-node/open/closed lists, best
node, counts and auxiliary checks. The complete search then populates nodes,
heap/order, closed-node traversal and statistics. The returned ReachablePlots
is built from the closed list and indexed afterward. The finder retains this
state at return, including the final naval configuration.

The usual subsequent GetPath/GetPlotsInReach APIs Configure and start a fresh
FindPath/Reset, which is encouraging. However public GetData, current generation,
start/destination and GetCurrentPath can observe prior state; VerifyPath and
ushort-generation behavior need separate proof. Skipping two floods shifts
generation wrap and removes touched-node clearing/population/statistics. Equal
gDistanceToTargetPlots values alone do not certify identical later path results
or tie order. A real reuse prototype must prove its complete caller seam and
subsequent service lifecycle, or preserve an equivalent service transition;
it must not borrow the live finder node arrays as cached field storage.

## Retry reuse is plausible, not established

The caller recomputes both fields before every tactical attempt, then clears
gDistanceToTargetPlots on return. HP-only combat between retries does not directly
change simple validity. Actual kills/moves can change revealed state; captures
change ownership/city/passability; pillaging changes fort passability. Mission
and Lua hooks can change technology, traits, permissions, topology or ownership.
The pure locked preview contract inside FindBestUnitAssignments does not span
the subsequent real execution and next retry. SceneEpoch alone does not cover
all relevant setters.

A later field service would need an exact player/target/full-data contract plus
complete invalidation for these actual inputs and the shared finder lifecycle.
Validation should compare the original two full floods, ordered ReachablePlots,
target distances, subsequent differently configured StepFinder queries/Verify,
generation wrap, reveal/capture/pillage/permission/capability changes and real
retry mission outcomes. First measure the combined envelope: source repetition
is a candidate, not evidence of multi-second savings.

## Files and usage

`measurement.patch` contains the one-line core timing delta and a work-reader
classification delta. Root may compose/apply it later. Candidate copies preserve
the current BOM and CRLF convention. `stage.py` only emits ignored artifacts;
`test.py` performs light source-binding/reversal/emitter-gate/parser checks.
Neither tool opens the game, connects to a controller or compiles the DLL.
`test.py --production` derives the entire expected timer candidate from pinned
DLL93, verifies both complete live files and seven unchanged dependencies,
then runs the32 checks against those actual live source/reader files. It saves
separate production-source-proof.json and production-test-result.json.
