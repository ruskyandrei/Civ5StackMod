# Building the gamecore DLL with clang (27 October 2026)

Upstream Vox Populi ships a clang build of the gamecore DLL: `-msse3 /Ox -flto`, linked with lld. StackMod releases
have been VC9 builds (`/Ox`, x87, no whole-program optimisation), which are about 1.5 times slower per late turn
([docs/headless-turn-time-gap-20261027.md](headless-turn-time-gap-20261027.md)). Until now the local clang toolchain
produced DLLs that failed to load (error 1114). This note gives the cause, the working recipe, and what a clang
build of StackMod gains.

## The load failure

### Symptom

Every local clang build, of plain VP 5.4.8 as well as of StackMod, failed in `DllMain` with an access violation
inside MSVCR90's `vsnprintf`, reading address 0x1 or 0x2. Builds without `-flto` failed the same way.

### Where it crashed

- The host's crash line pointed at `CvString::formatv`, and the nearest Firaxis frame in its stack scan was
  `FDebugHelper::LoadSymbols`. That frame is a stale return address left in `LoadSymbols`' 2 KB stack frame
  (after its `SymGetModuleInfo64` call); `LoadSymbols` never calls `formatv`.
- A debugger attached from process start (`work/clang-fix/tools/hostdbg.py`, ignored folder) gave the real
  caller. The formatted buffer held `... - Startup (Version 1 ... - Build (null)`, which is the first
  `CUSTOMLOG` in `CvDllGameContext::InitializeSingleton` (`CvDllContext.cpp`): the DLL's own startup log line.

### Cause

- `CUSTOMLOG` calls `CvString::format(std::string&, const char*, ...)`, an inline variadic function in
  `CvString.h`.
- `build_vp_clang_sdk.py` passes the VC9 and Windows SDK include folders as `-external:I`. Clang searches those
  before its own resource headers, so `<stdarg.h>` and `<vadefs.h>` come from VC9. VC9 defines
  `va_start(ap, v)` as `ap = (char*)&v + 4`: the address of the last named parameter, plus 4.
- That macro is only right while the function keeps its own frame and `v` stays in its incoming stack slot.
  Clang 19 inlines variadic functions that do not call `__builtin_va_start`. After inlining, `&fmt + 4` points
  into the caller's frame and the variable arguments are dropped: the call site passes only the string, the
  format and a pointer to a local.
- Upstream's DLL calls `CvString::format` out of line with all its arguments.
  - Upstream's release script, `scripts/release.py`, runs `build_vp_clang.py` inside a VS2008 prompt. That script
    has no `-external:I`: the headers come from `INCLUDE`, after clang's own.
  - So upstream gets clang's `stdarg.h`, whose `va_start` is `__builtin_va_start`, and clang never inlines such a
    function.
  - The local wrapper loaded the `_sdk` variant of the script.
- The `CvString` definitions, the Firaxis objects and `/FORCE:MULTIPLE` played no part. The
  `-fms-compatibility-version=15.00` flag was not the cause either, but the matching value is VC9 SP1's
  `15.00.30729.1`, which clang reads from `cl.exe` in the VS2008 prompt.

## The recipe

`work/build-vp-clang.py` (usage in `work/BUILD-LOCAL.md`, "Clang build"):

- **Toolchain:** the portable clang/lld 19.1.7 in `work/toolchain/llvm`, VC9 SP1 headers and libraries, Windows
  SDK 7. No Visual Studio install is needed.
- **Inputs and flags:** the source list and flags come from `build_vp_clang_sdk.py`:
  `-m32 -msse3 /MD /GS /EHsc /fp:precise /Zc:wchar_t /Zi /Ox /Ob2 /Zo -flto`, and lld with
  `/LTCG /OPT:REF /OPT:ICF /FORCE:MULTIPLE`.
- **Headers:** VC9 and SDK through `INCLUDE`, after clang's own; no `-external:I`.
- **Compatibility:** `-fms-compatibility-version=15.00.30729.1 /std:c++14 /Zc:sizedDealloc- /Zc:threadSafeInit-`
  keep clang 19 on the VC9 runtime ABI. Clang 19 turns sized deallocation on by default.
  `-Wno-enum-constexpr-conversion` keeps VP's legacy `PlayerTypes` cast compiling, as `build_vp_clang.py` does.
- **Steps:**
  - `update_commit_id.bat` runs through `cmd /c`.
  - Compilation uses at most `--jobs` processes; the link uses at most `--jobs` threads.
  - A full build takes about 3.5 minutes: 30 s of compilation, then about 3 minutes of single-threaded link-time
    code generation.
- **Source list:** the clang scripts gain the four stacking AI sources (commit "Clang build scripts: compile the
  four stacking AI sources"). Without them a StackMod clang build would miss the stacking AI.

## Verification

All host runs used the stats project's pinned inputs through `work/perf-gap/tools/prun.py`, in Windows efficiency
mode. Run folders are under `work/perf-gap/runs/cf-*`, DLLs under `work/perf-gap/dlls/`.

### Plain VP 5.4.8 replays upstream's release game exactly

- **Build:** VP 5.4.8 (`7307aefdf`, the `work/wt/vp548` worktree), built with this recipe: DLL 9E7D9825.
- **Run:** a full game of continental-drift-p05 (seeds 900005/910005) to turn 300 in the host.
- **Result:** identical to the game of the pinned upstream release DLL (262AEE88):
  - the probe rows at all 30 shared checkpoints (every 10 turns);
  - all 684 replay messages;
  - the replay data;
  - the final state.
- **Timing:** per-turn times match upstream's DLL within a few percent (T1-50 0.54 s both, T101-150 1.34 against
  1.30 s). This run shared the machine with builds and other runs, so it is not a speed comparison.

The local toolchain therefore produces a DLL that plays like upstream's, even though it is clang 19 rather than
upstream's older clang.

### StackMod: 36% faster per late turn than the VC9 build

- **DLLs:** StackMod at master (0.3.4 source) built with this recipe (1D29FF86), against the 0.3.4 release DLL
  (VC9 `/Ox`, x87, no whole-program optimisation; 0F9F3B88).
- **Save:** the turn-250 save of StackMod's own continental-drift-p05 game
  (`work/perf-gap/runs/fg-sm-msvc/saves/Turn_0250 AD-1700.Civ5Save`).
- **Runs:** two runs of each DLL, all four side by side.

Seconds per turn:

| Turns | clang, run a | clang, run b | VC9, run a | VC9, run b | clang / VC9 |
|---|---:|---:|---:|---:|---:|
| T251-253 | 7.10 | 7.09 | 11.10 | 11.12 | 0.64 |
| T251-258 | 6.21 | 6.21 | 9.70 | 9.71 | 0.64 |

- **The gain is the compiler gap measured on plain VP.** It matches the write-up's plain-VP figure from VP's own
  turn-250 save (28.4 s against 44.5 s, also 0.64).
- **What this means against plain VP:** clang VP takes about 3.5 s per turn at turns 251 to 258, from its own
  save. Against that, StackMod's late turns would drop from about 2.7 times plain VP's to about 1.75 times.
  - This is rough: the two saves are different games.
  - The danger-rebuild fix (P1, about -24%, merged into master after this measurement) comes on top.

### Same game or not

- **Repeat runs are deterministic.** Repeat runs of the same DLL from the same save end in identical states, for
  clang and for VC9.
- **StackMod clang and VC9 play different games.** VC9 uses x87 and clang SSE, so floating-point results differ,
  as they did between plain VP's VC9 and clang builds.
  - By turn 258, four of the eight majors differ slightly in gold, science, culture or happiness: mostly under
    2%, at most 6% (one player's gold per turn).
  - No replay event (cities, wars, wonders) differs yet.
  - Expect the games to drift apart further, as plain VP's VC9 and clang games did from about turn 50.
  - This matters only for comparisons across compilers. A stats series that compares StackMod with plain VP should
    use clang for both.

### Real-game smoke test

- **Install:** the clang StackMod DLL replaced the installed `(1) Community Patch` DLL. That DLL is the
  `ai-improvements` VC9 build D4390E6C; its mod files differ from master only by extra `StackingConfig.xml` rows.
- **Run:** `work/vpbench/vpbench.py newgame` with these settings:
  - Emperor, Standard Continents, eight random majors;
  - a new game saved at turn 0, then autoplayed to turn 20 and saved again;
  - saves `CFClangSmoke-T000` and `CFClangSmoke-T020` in `ModdedSaves\single`;
  - run record `work/test-runs/cf-clang-smoke-20261027`.
- **Result:**
  - Mods activated, the game started, and 20 turns took 66 s (3.3 s per turn). The game then quit normally.
  - `CustomMods.log` shows the startup line correctly formatted: `... - Startup (Version 151 - Build ...)`.
  - The only errors logged are the upstream baseline ones (`ArtDefine_Landmarks` "SPECIAL" validation,
    "Error loading VPUI_loader.lua"), which VC9 runs show too (`work/BASELINE-VERIFIED.md`).
- **Restore:** the original DLL and PDB were put back afterwards, with their hashes checked.

## Releases

- **StackMod releases now ship this build** (decided 27 October 2026), starting with the version after 0.3.4.
  - The source is the same and late turns are 36% faster.
  - On plain VP the build matches upstream's release DLL exactly.
  - AI decisions change only through floating-point rounding.
- **The release steps** are in `work/BUILD-LOCAL.md`, "Release build". `tools/make_release.py` refuses a staged DLL
  that is not a clean clang LTO build of HEAD.
- **For the 600-game stats series**, a clang StackMod build makes the compiler the same on both sides.
