# XML comparison checklist — baseline / main / sea / defaults

This documentation task has not deployed or controlled the game. The coordinator has now installed MAIN and started its fresh-game checks; use fresh disposable games and one final verified integrated DLL throughout. The completed-production deferral build030606 is compiled/deployed and pinned below. Its default completed-production test77/0 and separate six-stage saved continuation now pass. Do not silently reuse the older012022 or024049 artifact or switch binaries between XML phases.

Default production and persistence smoke evidence is archived in work/test-runs/production-turn-030606; older combat evidence remains tied to its recorded builds. Stop promptly if the known high-CPU/no-progress loading signature recurs. Use ordinary maps; do not load the edited dense save or hot-reload the full UI. Close Civ V before every staging/deployment block below. Preserve each phase's logs and screenshots before the next launch overwrites them.

## Shared shell setup

```powershell
$ErrorActionPreference='Stop'
$root='E:\Projects\Civ5StackMod'
$py='C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$build=Join-Path $root 'work\msvc-output\Release\20260927-030606'
$expected='CC8F233774E4608EA3891471FA10E551DED25CBBE566393EF9A76F976B5621CC'
$dll=Join-Path $build 'CvGameCore_Expansion2.dll'
$pdb=Join-Path $build 'CvGameCore_Expansion2.pdb'
$installed="C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\MODS\(1) Community Patch\CvGameCore_Expansion2.dll"
if ((Get-FileHash -LiteralPath $dll).Hash -ne $expected) { throw 'Wrong comparison DLL' }
function StageFixedXmlRun {
    & $py (Join-Path $root 'work\stage_vp.py') --dll $dll --pdb $pdb
    if ($LASTEXITCODE) { throw 'Staging failed' }
    & $py (Join-Path $root 'work\stage_vp.py') --verify
    if ($LASTEXITCODE) { throw 'Staging verification failed' }
    & (Join-Path $root 'work\deploy-vp.ps1') -ValidateOnly
    & (Join-Path $root 'work\deploy-vp.ps1')
    if ((Get-FileHash -LiteralPath $installed).Hash -ne $expected) { throw 'Installed DLL changed' }
}
& $py (Join-Path $root 'work\xml-variation.py') verify
if ($LASTEXITCODE) { throw 'XML payload verification failed' }
```

The XML tool changes only the two allowlisted canonical XML files, guards their hashes, backs up current bytes and refuses a running game. The existing stager refreshes modinfo MD5s. Full staging also restores normal separate helper imports instead of the supplemental test's concatenated installed file. No DLL rebuild occurs in this sequence. Verify the loaded module path/hash after each launch as well as the installed file.

## A. Default baseline on the frozen new build

```powershell
& $py (Join-Path $root 'work\xml-variation.py') restore
if ($LASTEXITCODE) { throw 'Default restoration failed' }
StageFixedXmlRun
```

Restart, activate mods, start a new game. In FireTuner InGame, load helpers:

```lua
include("StackingTests"); include("StackingExtraRuntimeTests"); include("StackingXMLVariationTests")
local v={}; for r in GameInfo.Stacking_Settings() do v[r.Name]=tonumber(r.Value) end
assert(v.BaseCapacity==2 and v.MaximumCapacity==9 and v.CollateralPercent==20 and v.CollateralHPFloorPercent==50 and v.CityProtectionMaximumPercent==90)
StackTests.passed=0; StackTests.failed=0; StackTests.Capacity()
```

Record actual base2 and tech3/5/7/9, separate civilian/full-stack behavior, configuration loader diagnostic and DLL hash. AirWave and city combat passed on012022; field melee/gift/actual purchase passed on024049. These are archived per-build results. Run focused default smoke/deferral checks on the final comparison DLL before changing XML. Close without saving after preserving results.

## B. Main variation — same DLL

```powershell
& $py (Join-Path $root 'work\xml-variation.py') apply --profile main
if ($LASTEXITCODE) { throw 'Main profile failed' }
StageFixedXmlRun
```

Restart into another new game; load the same helpers. Run separately, completing Fire/CheckShot after animations before the next setup:

```lua
StackTests.passed=0; StackTests.failed=0
StackXMLTests.Data("main")
StackXMLTests.CapacityDomains(true)
StackXMLTests.Cleanup()
StackTests.Capacity()
StackXMLTests.Roles()
StackXMLTests.SetupFloor()
StackTests.Fire()
-- after animation:
StackTests.CheckShot()
StackXMLTests.SetupCity()
StackTests.Fire()
-- after animation:
StackTests.CheckShot()
```

Expected: land progression3/5/6/9/10; sea+1 and city+1 until cap10; another team's technology remains independent; actual ten combat members fit per domain and eleventh is rejected. Role inheritance/class/promotion/unit overrides and VP siege modifier-20 apply. Floor test uses30%, minimum3,60% floor including63/101 ->61. City protection11/24/41/60/cap65, removal60 then49, restores65. Visually check ten combat members, not nine combat plus worker. The helper creates valid spaced cities but edits no terrain; do not use this modified world as the shared AI baseline save.

Do not run default-only `StackTests.Defenders()` or `SetupCityCollateral(true)` here: their expected roles/building amounts intentionally differ. Stop and investigate any FAIL or setup precondition; log it rather than counting an unexecuted attack as a pass.

## C. Sea collateral enabled — same DLL

Close the previous game, then:

```powershell
& $py (Join-Path $root 'work\xml-variation.py') apply --profile sea-enabled
if ($LASTEXITCODE) { throw 'Sea profile failed' }
StageFixedXmlRun
```

Restart/new game/load helpers:

```lua
StackTests.passed=0; StackTests.failed=0
StackXMLTests.Data("sea-enabled")
StackXMLTests.SetupSeaCollateral()
StackTests.Fire()
-- after animation:
StackTests.CheckShot()
```

Only the domain row differs from the main profile. Require a legal native sea shot, two actual secondary victims under Frigate limit2, exact30% damage and60% floor. The final comparison DLL must contain the naval/water early-return fix already present since012022; never change DLL between phases. Do not use the Extra helper's sea-negative-control setup with sea collateral enabled.

## D. Exact default restoration — same DLL

Close the game, then:

```powershell
& $py (Join-Path $root 'work\xml-variation.py') restore
if ($LASTEXITCODE) { throw 'Default restoration failed' }
& $py (Join-Path $root 'work\xml-variation.py') verify
if ($LASTEXITCODE) { throw 'Restoration verification failed' }
StageFixedXmlRun
```

Canonical SHA256 must return to CP `EA3B52F4569D9C7DAE212466A71CCD3F897AACF18C1E108FAFFE8FB1FB89D850` and VP `2D1ACCB36FDF5A620E115513786D5D59DB92E97F027AF6333D23423AEECEA05A`.

Restart/new game/load helpers. Repeat baseline readback and Capacity; then `StackExtraTests.SetupNaval("sea")`, FireNaval, CheckNaval in separate commands. Require normal primary damage with zero secondaries. Confirm default20%/50%, roles and cap90 in API/previews. Retain DLL hash unchanged across A/B/C/D and both canonical/staged/installed XML hashes for each phase.

Remaining optional controls: AIEnabled0/1, disabled flanking/collateral/selection, invalid-input diagnostics, later-era/category capacities, unique replacements and the bomber's enlarged six-secondary boundary. Record unrun cases explicitly. The four phases above prove representative XML-only mechanics, not every possible configuration or AI behavior.
## Profile refresh checkpoint

Reprepared from final canonical notification-text configuration without changing either canonical file. Current CP default SHA256 `EA3B52F4569D9C7DAE212466A71CCD3F897AACF18C1E108FAFFE8FB1FB89D850`; VP default `2D1ACCB36FDF5A620E115513786D5D59DB92E97F027AF6333D23423AEECEA05A`. All14 payloads parse/hash-verify. Every CP profile retains both new production-notification translations, and gameplay rows are semantically identical to the previous prepared profile. Old15-file snapshot preserved with verified hashes at `work/xml-variation-archives/20260927-030425-before-production-notice`. See `work/xml-variation/reprepare-proof.json`. The coordinator subsequently applied MAIN; canonical/staged/installed hashes match the prepared MAIN CP/VP payload. The manifest status describes the historical preparation checkpoint, not current deployment. Archive each phase and exact default restoration using work/XML-AFTER-RUN-CHECKLIST.md and work/Archive-XMLRun.ps1.

Current MAIN ten-combat roster/Outside order/stationary-hover/actual7move3stay sequence: `work/xml-ui10-sequence/README.md`; work-only commands reuse the imported Movement helper and require actual UI actions. Rendered behavior remains pending until recorded by the coordinator.
