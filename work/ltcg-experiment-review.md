# Optional unchanged-source VC9 whole-program trial

No production, toolchain or normal builder changes have been made. `prepare-ltcg-experiment.py` writes a proposal manifest only. It validates that only `/GL` and `/LTCG` differ from the tested release flags and emits read-only prerequisite checks and explicit future build commands.

## Existing support and exact command

`VoxPopuli.vcxproj` Release's compile section already selects whole-program optimization, and its link section selects LTCG. The normal `build-vp.ps1` release path supplies `--no-ltcg`, removing both. The Python builder can therefore exercise it without changing the project or scripts:

```powershell
$python = 'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -B -u work/build-vp-msvc.py --config release --jobs 2 --embedded-compiler-debug --pch-memory 400 --check
```

Removing only `--check` would perform a fresh full candidate build. Add `--no-ltcg` for the matched normal control. The PS entry cannot currently opt back into LTCG through remaining arguments because it always passes the disable switch. Do not reinterpret its normal release command as a candidate.

Local compiler help confirms VC9 SP1 compiler15.00.30729.01 accepts `/GL`, `/Z7`, `/fp:precise`, and `/Yc`/`/Yu`; linker9.00.30729.01 exposes `/LTCG:{NOSTATUS,STATUS,PGINSTRUMENT,PGOPTIMIZE,PGUPDATE}`. Modern `/LTCG:INCREMENTAL`, `/GENPROFILE` and `/CGTHREADS` should not be assumed from contemporary documentation; they are not in this linker's advertised options. `/LTCG:STATUS` is available for a later diagnostic wrapper, but the first flags-only trial can keep the existing project's plain `/LTCG` and normal per-step logs.

## Compatibility and scope

The builder recompiles its PCH and all179 current translation units into unique output directories, includes the PCH object in the final link, and keeps the matching toolset/PCH available during link. Whole-program object formats are compiler-version-specific, and PCH-based GL objects retain link-time dependencies on their originating PCH. Keep the exact native VC9 toolchain and existing proprietary libraries rather than trying another linker. These constraints are documented in Microsoft's [GL reference](https://learn.microsoft.com/en-us/cpp/build/reference/gl-whole-program-optimization?view=msvc-170).

Existing native libraries are accepted linker input; cross-module inlining can optimize newly compiled DLL source but cannot recover unseen library or engine EXE bodies. Imported/exported/public interfaces still require their externally visible behavior. `/LTCG` deliberately optimizes known internal function boundaries; it is therefore a compiler transformation trial, not a source-level equivalence proof. Keep `/MD`, exception handling, x86, definitions, source list, library order, `/Ox`, PCH configuration, `/fp:precise`, module definition and link protection/COMDAT/reference options identical. Microsoft's [LTCG reference](https://learn.microsoft.com/en-us/cpp/build/reference/ltcg-link-time-code-generation?view=msvc-170) describes cross-module inlining, internal x86 calling-convention optimization and native input support. Its newer modes are not evidence that our older linker supports them.

`/Z7` retains object debug information; `/DEBUG` creates a final linker PDB. A matching candidate DLL/PDB pair remains required for minidumps. Optimized/inlined stacks, variables and source mapping may differ from the ordinary optimized build. Microsoft's [debug format reference](https://learn.microsoft.com/en-us/cpp/build/reference/z7-zi-zi-debug-information-format?view=msvc-170) confirms this PDB route. `/fp:precise` is already used; do not add `/fp:fast`. Inlining and compiler bugs can still alter observed decisions, so compare exact native events, complete before/after world censuses, save/XML/mod/runtime settings, captures and random-dependent outcomes before accepting any speed result.

## Historical hang and honest cost expectation

The earlier `work/msvc-output/Release/20260924-204732` GL attempt successfully built PCH and173 object files, then its linker was stopped after about168 seconds with no diagnostic output. `work/PAUSED.md` records4.72 seconds of link CPU. That attempt used `/Zi`, not the current `/Z7`. A debug-database/server wait is plausible, but it has not been established as the cause. The new trial keeps the current `/Z7` and `/Zm400`, rather than repeating every old flag. Successful current non-LTCG DLL78 took66.281 seconds and produced a15.284MB DLL plus78.065MB PDB.

There is no trustworthy peak-memory or link-time estimate for the new GL/Z7 version. The old GL object files total163.615MB and its PCH309.592MB on disk; those numbers are not peak RSS or a memory upper bound. Code generation moves to the linker and may require a substantially larger optimizer working set. Local PE headers show `link.exe` is x86 and large-address-aware; this is a64-bit OS, so its theoretical user-address range can reach4GB, with less practically available under fragmentation. Microsoft's [Windows memory limits](https://learn.microsoft.com/en-us/windows/win32/memory/memory-limits-for-windows-releases) gives that architectural limit. No executable header patch is needed or proposed.

Use a bounded future link trial: fresh output, monitor exact link PID/start time, process-tree CPU/progress/private and virtual memory, and retain logs on success, error or timeout. An idle linker should be distinguished from heavy optimization CPU. An operational budget of several minutes is a stop condition, not a claimed expected duration. If it waits again, preserve diagnostic evidence and return to the tested builder; do not retry indefinitely or deploy incomplete output. No full build or native test has been run for this review.
