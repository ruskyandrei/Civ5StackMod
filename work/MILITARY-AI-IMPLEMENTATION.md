# Military allocation implementation — 2026-09-27

User authorized implementation with mostly offline work and one final smoke launch. Baseline VP5.4.6 stacking source ef54698 ran through turn330 without reported crashes; notification default3 is user-confirmed. Save/log baseline and hashes are preserved under `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/ai-baseline-330`. No save-format fields changed.

Changes and known limits are described in `docs/military-ai-plan.md` and `docs/stacking-configuration.md`. Main new source is `CvStackingAI.cpp`, with small integration hooks in the existing AI. Tactical search remains13units/6000states; no increased search-memory limits.

Offline verification: native VC9 actual-source allocation135/135; native diagnostic observer/policy/IO44/44; Python log summarizer16/16; prior no-op39/39, endpoint16/16, siege41/41, production-placement74/74, combat-cache30100/30100, observer notifications41/41. The large cache count is repeated eviction/state coverage, not independent scenarios or a performance benchmark. Engine pathfinding/world services in the allocation harness are stubs. Logging on/off gives identical allocation outcomes in the controlled fixture; live deterministic equivalence is not claimed.

Build/deployment and one bounded smoke session completed as recorded below. The new DLL is installed and the game is closed. User's next fresh campaign supplies the meaningful longer-term evaluation: rear-city surplus, actual arrivals, siege composition, assembly ages/restarts, defended/lost cities, turn time and memory.


## Build and installed package

- Source commit: `9c33e2601af7e43ef10d8a884997d0c8a3761e0b`; embedded identifier `Release-5.4.6-11-g9c33e26 Clean`.
- Native VC9 Release: `work/msvc-output/Release/20260927-134456`, 177 translation units, two workers, 67.625 seconds. Input hashes and commands are in that directory. One pre-existing signed/unsigned tactical warning remains; compilation/linking succeeded.
- DLL SHA256: `E674B0853BD4C29DC1BE23B0CAF79AFDA60E0D3BCB70D6302D2E6CB3065E072D`.
- Matching PDB SHA256: `F46D70C241FBDE0B5299557E43589927B458CA43EE1C3B57FEDBB54024223731`.
- All 2367 staged/installed files hash-verified. Previous installation archived at `work/backups/deployment-replaced-20260927-134729-a0695589`. Graphics preferences unchanged.

## Live evidence and limits

Exactly one DX11 launch, PID15732. Loaded unmodified `autoplay_330.Civ5Save` with Community Patch, VP, EUI compatibility and Squads enabled. Reached Continue Your Journey and disarmed the load guard. Enabled native Verbose diagnostics and requested three autoplay turns. No Lua observer/scenario was injected.

The game advanced from330 into331 and332, with continuing native AI records through player63 of332. The independent memory watcher stopped the exact test process at its180-second duration bound, followed by the CPU guard's duration message. This is a time-boxed stop, not evidence of a crash/hang or memory-limit breach. Turn333 and return-to-human control were not confirmed. No new crash report/minidump appeared. Same-process save/reload was therefore not exercised; cache/reset fixtures passed offline. Do not describe this as three fully completed turns or an unrestricted stability test.

`work/test-runs/military-ai-134456` contains process/build provenance, watchdog outputs,90 memory samples, saved file hashes,587 copied session logs, `native-summary.json` and `result.json`. The native log has10291 records across330–332, no malformed rows, missing segments or row-budget truncation. All124 observed combat serials have one begin/end pair and matching participant identities; this does not by itself validate combat balance. There are295 city assessments,148 operation-budget records,13 assembly records,37 garrison orders with actual movement and zero observed unchanged-position garrison orders, plus five strategic reinforcement moves. No strategic arrival was observed in this short window. Blocked transfers primarily report no path within the configured native-domain horizon.

Peak private memory2327.609MiB; peak committed+reserved3091.313MiB; minimum free1004.563MiB; minimum largest free block968.563MiB. GPU spot samples were52–55°C. These observations are not a comparative speed/memory benchmark.

The original manual330 save SHA256 remains `3091B9C3F35C8DC56196BD4AB3BCB67B0F5561196DD060E3FC3DA53852DF4B9A`. All nine snapshotted manual/auto files match their original hashes; no test-written autosaves needed restoring. No subsequent game launch or game-running process remains.

## Next user autoplay

Start a fresh game with this package, enable Diagnostics → Summary for continuous observation (Verbose adds recruitment/endpoint reasons and periodic unit decisions), and save at notable incidents. The XML default remains Off. Prefer at least100 turns spanning wars, with observations of rear-city surplus, frontline losses, siege composition, arrival times and assembly restarts. Advanced naval/air coordination and richer multi-turn threat modeling remain follow-up work; see the plan's implementation checkpoint. This release establishes the initial policy and instrumentation, not calibrated long-campaign superiority.
