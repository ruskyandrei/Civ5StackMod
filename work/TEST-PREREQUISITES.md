# Local regression prerequisites

These checks are development scripts, not automatically loaded game tests. Build/runtime evidence remains separate. The native build/stage/deploy/restore scripts are already tracked; large toolchains, generated C++ probes, executables, DLL/PDB outputs, downloaded packages, saves and bulk runtime logs remain local under ignored work folders.

## Ordinary Lua and native checks

The Lua regression scripts were validated with **Lupa2.8**, importing `lupa.lua51` from `work/lua-validation` under the bundled Python. A clean checkout must supply that Python dependency (including its Lua5.1 backend); the installed binary package directory is deliberately not vendored. Native extracted-source checks require the local VC9/Windows SDK setup described in BUILD-LOCAL.md and generate their own separate work output.

The anti-cavalry, dispersion, production-turn binding and melee helper tests now read canonical `Core Files/Stacking` helpers from `(1) Community Patch`. They do not need duplicate work-folder Lua copies. The reader-only change was checked once against current source:40 anti-cav checks,54 dispersion checks,59+61 production binding fixture checks and5 melee helper checks passed. Counts describe separate stub suites, not live scenarios.

`test-production-resume.py` additionally needs the six Lua command files in `work/production-resume-030606`. It validates that exact historical saved-ID continuation method with stubs. Those command IDs are specific to the recorded fixture; they must not be pasted into an unrelated save. Its README explains the live procedure. `xml-ui10-sequence` contains the small manual UI command blocks and manifest; those preserve the actual button/hover/movement test method, not a synthetic UI pass.

## Historical air-calibration probe

`test-air-calibration.py` is **not currently a self-contained clean-checkout regression**. It requires these pre-existing local preparation artifacts:

- `work/air-calibration-regression/damage-bound-test.cpp`, containing the exact current `CvUnitCombat::DoDamageMath` body; the script verifies that source match.
- The matching native executable `work/air-calibration-regression/damage-bound-test.exe`, already built with the local VC9 environment. The script runs it to obtain the damage-bound rows; it does not compile or regenerate it.
- `work/AirWaveCalibrationAddon.lua`, the exact calibration-addon source used by that historical harness, plus the Lupa prerequisite above.

Do not commit the executable or pretend a missing dependency means a passing test. On the original PC the artifacts remain available. Elsewhere, reconstruct/build the matching native probe and provide the historical addon before invoking this script, or explicitly mark that one-off calibration check unavailable. No new builder/refactor was introduced during this packaging pass. The separately tracked interception and air-leaf extracted-source regressions remain independent checks of the corresponding DLL logic.

## Deliberate exclusions

Do not force-add all of work. Exclude toolchain/download/package folders, staging/deployment/backups, generated regression outputs, .Civ5Save files, bulk Lua/CSV logs, absolute-path pointer files, and old one-off patch-application scripts. Canonical numeric XML and the tracked xml-variation.py reproduce prepared profiles; generated profile folders and archived current-session manifests are not required source inputs.
