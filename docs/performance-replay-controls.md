# Reproducible late-game performance controls

Use the persistent local Lua service described in `game-automation.md`. Each
game process gets one engine connection for its lifetime. Never print the
session file or reconnect to a live game after an ambiguous transport failure.
The replay harness owns game calls until it completes or fails.

## Saved input and boundaries

The verified late-game input is the unique manual turn251 save under
`work/test-runs/campaign47-20260930-1735`, SHA256
`2A31D7020FFA5348582DD46442D079308CEDC7880248C1B1623A39FF62BC659B`.
Use `work/run-behavior-replay.py --source-mode human --start-turn 251
--stop-turn 254 --return-player 0`, supplying its existing save, expected DLL,
process identity, fresh run directory and exact enabled-mod file arguments.
Human-source normalization deliberately performs VP's slot-change AI actions;
compare identically normalized runs, not an uninterrupted historical campaign.

Measure252-to253 while autoplay remains active at both boundaries. The final
253-to254 interval includes return-to-human processing. It remains useful as a
matched stress case, but label that boundary and compare its internal search
and player phases separately. Do not use the previously failed Post250 observer
save as a routine benchmark input.

Back up engine autosave slots before launch. The replay never requests an
overwrite of the manual input. Verify exact PID and UTC creation ticks, installed
DLL hash and both armed CPU/GPU/memory/progress guards before continuing.

## Presentation controls

`--view-mode preserve` is the default and never toggles the view. Available
view state is still recorded. Explicit `standard` and `strategic` modes require
the actual engine globals `InStrategicView()` and `ToggleStrategicView()`.

VP/EUI can process `GameplaySetActivePlayer` after the Lua call that changes
human/observer slots. An immediate strategic toggle can therefore be undone.
The harness applies explicit view in a separate late InGame command after the
before-world census, verifies the paused state in another call, and keeps the
LoadScreen continuation guard. Initial source preparation, original mode,
late application and final prepared mode remain separate evidence. It fails
if the requested observer view changes during polling. The eventual human
return can restore that player's own view.

The comparator's `--allow-cross-view` permits only an intentional difference
between two recorded prepared modes. Source/options/mods, complete world
censuses and selected native event sequences must still match. Historical
unrecorded modes are unknown and cannot qualify as a controlled cross-view pair.

## Legacy logging experiment

`work/engine-logging-profile.py apply-native-only --run-dir <fresh-directory>`
changes only `AILog`, `AIPerfLog` and `BuilderAILog` to zero, with the game closed.
It preserves `LoggingEnabled` and `MessageLog`; the native Summary logger has
its own runtime setting and remains enabled by the replay harness. Original
configuration bytes, hashes and narrow flag metadata are preserved.

Use a separate configuration-experiment directory: the game launcher itself
requires a fresh, nonexistent run directory. Copy narrow experiment metadata
into each relevant replay directory and verify the installed config hash before
launch/measurement. This helper is an experiment control, not a gameplay mod.

After normal game shutdown, run `restore --run-dir <same-directory>`. Restore
refuses an unexpected current hash rather than overwriting later user edits.
The helper tests use temporary files and do not access the real game config.
Full deployment may restore the project's normal logging flags; re-verify them
before another controlled run.

## Interpretation

`profile-turn-phases.py` measures first legacy event to first next-turn legacy
event and accounts for overlapping scopes using interval unions. New timing
rows must not shift those anchors. Adjacent-turn preparation can occur inside
that window; use `recorded_window_coverage` for the full covered interval.

`profile-phase-cpu.py` reads absolute same-thread CPU endpoints, reports
inclusive phase CPU and unambiguous gap deltas, and never treats work on other
threads as idle time. Clipped bounds cannot be linearly interpolated into CPU
time. Zero coarse CPU growth is evidence of little work on that thread, not
proof of a particular lock, renderer or scheduler cause.

Keep timing experiments separate from behavior fixes. Exact cache changes
should reproduce the retained plans, combat records and nonempty censuses.
Correcting an invalid plan or combat postcondition can intentionally change
actions; validate the corrected rule and remaining legitimate replans instead.
One fast turn, one seed, or one isolated cache microbenchmark is not a general
late-game performance result. Retain slow cases and unsuccessful experiments.

## Engine dispatch experiments

work/watch-gamecore-thread.ps1 observes only a native-recorded GameCore thread
with exact process creation, thread creation, native session and DLL SHA/path
binding. It never attaches, suspends, calls Lua or changes priority/affinity.
It stops on completion signal, identity loss or a bounded duration/sample/byte
limit. Its ThreadState/WaitReason snapshots can be joined to native tick32
intervals, but do not identify a particular engine synchronization object.
The first 100ms sample run consumed12.5 seconds of helper CPU over145 seconds,
so label such runs diagnostic and keep separate quiet timing controls.

work/gamecore-threading-profile.py supports plan/apply/restore/status against
an explicitly named config.ini and separate work/test-runs profile directory.
Apply requires its original SHA and game-closed checks. The only modification
is GameCoreThreadingUsesJobManager0→1; backups retain every other byte. Restore
requires the exact applied or original bytes and refuses unrelated changes.
Keep EnableGameCoreThreading1, view, save, DLL, mods and all other options fixed.

Job-manager workers may migrate thread IDs; missing same-thread gap records are
lost instrumentation coverage, not evidence of zero waits. Compare complete
native windows and retained behavior/censuses, and inspect thread distributions.
Always close the exact game normally and restore the config after the test.

## Optional automatic normal shutdown

`run-behavior-replay.py --quit-after-complete` closes the tested game after the
bounded replay finishes. The default still leaves it open. Before any commands,
the option pins Windows process handles and creation times for the game, its
existing Lua service and both guards. It also binds the session file's identity
and its whitelisted service PID; credentials are never included in evidence.

Shutdown requires the expected human return, unchanged source save, complete
nonempty after-censuses, archived native logs and successful offline analyses.
A fresh live read must confirm the stop. The harness requests normal quit once
through the existing service, waits for the exact game to exit, then stops that
same service once. It does not force-close, reconnect or retry an ambiguous
command. `normal-exit.json` and the replay manifest record confirmation or the
precise failure stage. Successful completion uses status
`completed_game_closed_service_stopped`. The offline mocked shutdown regression
passed25 checks; a real replay remains necessary to validate engine integration.
