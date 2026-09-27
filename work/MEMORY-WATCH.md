# Bounded Civ5 memory watcher

`work/Watch-CivMemory.ps1` is read-only by default: it takes one sample and writes a new JSONL file under the supplied `work/test-runs` child directory. `-ValidateOnly` checks process identity and prints it without creating a log directory. Use a 64-bit PowerShell host. The watcher verifies the supplied PID, UTC `StartTime.Ticks`, fixed installed `CivilizationV_DX11.exe` path, live status and WOW64 identity through native process handles.

Coordinator-only validation command; replace the measured PID and ticks before running:

```powershell
& 'E:\Projects\Civ5StackMod\work\Watch-CivMemory.ps1' -GameProcessId <PID> -ExpectedStartTicks <UTC_START_TICKS> -RunDirectory 'E:\Projects\Civ5StackMod\work\test-runs\turn240-replay\memory' -ValidateOnly
```

For a bounded replay, the coordinator launches the script in a hidden helper process with the same arguments, removes `-ValidateOnly`, and adds:

```powershell
-Watch -StopOnLimit -MaximumSeconds 180 -SampleSeconds 2 -CompletionSignalPath 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\turn240-memory-done.signal'
```

The signal file must not already exist. Creating it ends monitoring without stopping the game. This guide does not claim that the bounded replay or optional stop path has passed.

`-StopOnLimit` explicitly authorizes stopping this exact test process at either a memory threshold or the duration limit. Without that switch, the watcher records the limit and exits, leaving the game running. Stopping opens a separate process handle and verifies identity again on that handle before calling `TerminateProcess`, so a reused PID cannot redirect termination. A sampling error or identity mismatch never triggers termination. Keep the existing timed guard if protection is required when memory sampling fails.

The watcher stops the test, or records a limit in read-only mode, when any of these conditions occurs:

- Private bytes reach 3.1 GiB.
- Committed plus reserved virtual memory reaches 3.5 GiB.
- Total free virtual memory falls below 256 MiB.
- The largest free virtual block falls below 16 MiB.
- Elapsed time reaches `MaximumSeconds`.

These are conservative diagnostic safeguards, not proven universal Civ5 safety limits. Working set and cumulative CPU time in 100 ns units are recorded separately; neither substitutes for virtual address pressure. `VirtualQueryEx` scans `0x00010000` through `0xFFFEFFFF`, matching the game's crash-report bounds. Sampling does not freeze allocations, so the process can change during a scan. The watcher rejects incomplete or invalid scans rather than reporting partial totals.

Sampling uses `QUERY_INFORMATION | VM_READ`; every native handle closes after use. `RunDirectory` must be a child of the project's `work/test-runs` directory and cannot traverse an existing reparse point. The completion signal must be a direct `.signal` file in the existing `C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog` folder. Output goes to a unique timestamped JSONL file and does not overwrite game files or saves.

Offline validation: `work/Test-WatchCivMemory.ps1` passed 28 checks with no failures. Coverage includes threshold boundaries, path restrictions, PowerShell/C# parsing and compilation, the 48-byte `MBI64` layout and offsets, and safe identity rejection using the test PowerShell process. Those checks sampled no game and never executed termination. Results are in `work/memory-watch-regression/result.json`. The coordinator subsequently recorded one successful read-only DX11 sample: 7,550 regions, no threshold reached, no stop requested. Evidence is `work/test-runs/diagnostics-live-20260927/initial/memory-watch-20260927-085154-579.jsonl`. This proves live enumeration for that process, not replay completion or tested termination behavior.
