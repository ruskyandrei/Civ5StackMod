# Offline native diagnostics summary

`work/summarize-stacking-diagnostics.py` reads the native schema-1 logger output from `CvStackingDiagnostics.cpp`. It does not launch the game, attach to its process, change settings, or alter input logs. Python3.9+ standard library is sufficient.

Actual rolling data filenames start **Stacking-**, for example `Stacking-20260927T093000-123-p1234-r1-00.log`. `StackingDiagnostics-path.log` is the engine path locator and normally contains no diagnostic session. The summarizer accepts both filename patterns but requires a `STACKDIAG|SESSION|schema=1 ...` header.

From the project directory:

```powershell
python work/summarize-stacking-diagnostics.py "C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\Logs" --output work/diagnostics-summary.json
```

Omit `--output` to print JSON to stdout without writing any files. Use `--run "Stacking-...-pPID-rN"` to select an exact run ID from a SESSION header. Otherwise each run is kept separate. The directory scan is nonrecursive. For reproducible analysis, use an archived directory copied after normal exit; live files may rotate or gain rows during reading. An unterminated last line is excluded and reported as a potentially incomplete write.

The JSON reports:

- Counts by category, player and game turn, plus file hashes, complete original session/build headers and CONFIG records.
- True segment order from SESSION headers, missing ranges and absent earlier segments. Slot suffixes wrap, so they are not chronological segment numbers. Identical duplicate segments are counted once; conflicting duplicates are both retained with a warning.
- Process virtual-memory peaks in KB, including committed+reserved, and minimum free space/largest free block. These values describe virtual address space, not physical RAM or a proven leak. Tick values are `GetTickCount`, not clock timestamps; no duration inference is made from them.
- Full `LONG_PLAN` fields and locations, per-turn `TRUNCATED` markers, message truncation markers, malformed row examples and turn rewinds.
- Combat begin/end and unit/city before/after record counts, unmatched brackets unmatched unit identities and duplicate post-combat identities. `COMBAT_MEMBER` can list one unit in multiple roles, so before identities are deduplicated for matching with `COMBAT_AFTER`. An absent post-combat identity is not automatically called a death; capture/removal can also change identity.

These are **retained-record totals**. A rolling overwrite, player filter, logging level, budget truncation or missing file can hide events. Matching combat brackets do not prove all intermediate records were captured, and an empty anomaly list does not prove an error-free game. Raw `configFNV`/`fnv1a` values are preserved as strings, including leading zeros. Source segment0 can initially show a zero config hash before CONFIG rows calculate the actual hash; use the CONFIG record and subsequent headers when interpreting configuration provenance.

Run offline parser regressions with:

```powershell
python work/test-diagnostics-summary.py
```

The13 tests use temporary synthetic native-format fixtures. They cover modulo segment ordering, duplicates, separate runs, memory metrics, truncated/partial/malformed rows, repeated combat roles, incomplete combat records and input overwrite refusal (including hardlinks). They do not manufacture native runtime evidence.
