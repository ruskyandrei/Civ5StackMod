# After each XML profile run

Keep DLL030606 SHA256`CC8F233774E4608EA3891471FA10E551DED25CBBE566393EF9A76F976B5621CC` fixed. MAIN is currently installed; canonical, staged and installed CP/VP hashes independently match the prepared MAIN payload. This preparation did not apply profiles or control the game.

1. Finish actual attack/check frames and UI movement. Record final Lua summaries, retained setup errors, unrun checks and screenshots. For ten combat units, capture rendered Outside order, stationary5/4+1outside without another mouse-hex event, new-order7/3+0outside, final toast and exact positions/HP/Squads. API assertions alone are not rendered-UI proof.
2. Before closing the exact test process, run:

```powershell
& 'E:\Projects\Civ5StackMod\work\Archive-XMLRun.ps1' -Profile main -GameProcessId 18876
```

Replace PID for later games. This read-only evidence tool checks canonical/staged/installed XML, unchanged DLL and exact loaded CP module; it copies full/filtered logs, exact installed helper/UI files, XML bytes and staging manifest to a new work archive. It never deploys, applies XML, launches/stops the game or declares mechanics passed. Add screenshots and scenario results to the returned directory. Preserve any extra post-close log/CSV flush separately, without replacing the first snapshot.

3. Close normally. Apply the next chosen profile and use `StageFixedXmlRun` from `XML-RUN-CHECKLIST-20260927.md`, still pointing to the same030606 DLL/PDB. For the required sea control:

```powershell
& $py (Join-Path $root 'work\xml-variation.py') apply --profile sea-enabled
if ($LASTEXITCODE) { throw 'Sea profile failed' }
StageFixedXmlRun
```

Fresh game, loaded-module proof, then `StackXMLTests.Data("sea-enabled")`, `SetupSeaCollateral()`, and Fire/CheckShot in separate frames. Require a legal native shot and exactly two secondary ships with30%/60% policy. Archive using `-Profile sea-enabled -GameProcessId <exact PID>`. Optional disabled-feature runs use their own profile name; Data readback alone does not demonstrate disabled mechanics. Do not run main floor/city expectations under a disabled feature.

4. After the last variation, archive and close. Restore exact defaults and deploy the same DLL:

```powershell
& $py (Join-Path $root 'work\xml-variation.py') restore
if ($LASTEXITCODE) { throw 'Default restoration failed' }
& $py (Join-Path $root 'work\xml-variation.py') verify
if ($LASTEXITCODE) { throw 'Payload verification failed' }
StageFixedXmlRun
& (Join-Path $root 'work\Archive-XMLRun.ps1') -Profile defaults-restored -ValidateOnly
```

All three locations must now equal CP`EA3B52F4569D9C7DAE212466A71CCD3F897AACF18C1E108FAFFE8FB1FB89D850` and VP`2D1ACCB36FDF5A620E115513786D5D59DB92E97F027AF6333D23423AEECEA05A`, with unchanged DLL. ValidateOnly creates no archive and makes no game/config changes.

5. Fresh default game: verify live database base2/max9/collateral20%/floor50%/protection90%/sea-disabled; run capacity progression and actual naval sea negative control (primary damage, no secondaries). Record summaries and remaining gaps. Archive using `-Profile defaults-restored -GameProcessId <exact PID>`. Exact file restoration plus fresh live DB and representative damage readback establish that the restored data was loaded. Preserve graphics/preferences and original saves.
