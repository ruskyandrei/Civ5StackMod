# RESUME: headless turn-time gap investigation (branch perf-turn-time-gap)

Work order (2026-10-27, from the civ5-vp-stats session): find why StackMod 0.3.4 (f5c5b86e0) takes ~2.5x the CPU
per AI turn of plain VP 5.4.8 (7307aefdf) in the civ5-headless host, and why the gap grows. Deliverables: a write-up
`docs/headless-turn-time-gap-20261027.md`, a README line 16 correction, optional prototype fixes on this branch (local
commits only; no push, no release, do not touch `E:\Projects\civ5-vp-stats`). At most 8 cores busy. Host runs in
efficiency mode (user, 2026-10-27).

## State: done (write-up, README fix and prototype committed)

- Branch `perf-turn-time-gap` off master f5c5b86e0, in the main checkout (the user asked for a new branch off main).
- Commits: `233fc7436` clang build scripts gain the 4 stacking sources; `92a6d310a` prototype P1 (no danger rebuild
  on visibility changes and moves); then the write-up + README commit.
- Scratch in `work/perf-gap/` (ignored): `tools/`, `dlls/<variant>/` (DLL+PDB), `runs/`, `logs/`, `civ5headless.toml`,
  `inputs/`. Reproduction commands: section 7 of the write-up.
- `work/wt/vp548` has an untracked `work/` (copied build-vp-msvc.py, toolchain junction, msvc outputs) and a
  `commit_id.inc`, `clang-build/`, `clang-output/` (ignored); its clang.cpp was restored after the shim experiment.

## Results (details in the write-up)

- Gap = compiler (upstream clang+LTO+SSE3 vs StackMod's VC9 /Ox no-LTCG: 1.57x at T250 on plain VP) x StackMod's own
  work (1.05x early to 1.6-1.7x late, same compiler).
- StackMod's own excess is mostly danger-map rebuilds triggered by DirtyStackDangerForVisibility/Observers
  (7.6 of 30 Gcycles/turn at T250 vs 0.8 in VP). P1 removes them: -24% per late turn, ~60% of the same-compiler excess.
- Logging: ~0.4 s/turn in both variants; not the cause.
- README benchmark: real game, VC9 vs VC9, Oct 1 build, one calmer game, frame pacing floor.
- Blocked: local clang 19 builds (even plain VP) fail at DLL load (FireWorksWin32.obj's FDebugHelper::LoadSymbols ->
  clang CvString::formatv ABI mismatch); StackMod's VC9 /LTCG link hangs at ~5 s linker CPU (plain VP links fine).

## Possible next steps (not started)

1. AI quality of P1: a two-game A/B (one seed, `work/perf-gap/runs/ab2-{base,p1}`) is in the write-up (speed
   -24 to -25% mid-game; games diverge at T10, so no verdict on play). For a verdict: more seeds, or the head-to-head
   gate on branch `perf-gap-p1-ab` (998bcde87, `--improved-mask`).
2. Working clang toolchain matching upstream's (older clang, VS2008/SDK7 flags), then time StackMod with clang.
3. Find the StackMod /LTCG link hang.
