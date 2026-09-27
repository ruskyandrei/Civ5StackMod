# Extracting natural AI benchmark measures

Latest completed same-save benchmark: Release20260927-024049, DLL SHA256 `55ED510AEF07DA5E0AAC9F0EE3978C577CB38EFB833ED04F91B417912F3C966A`, independently verified from the live process. Its FIFO CvTacticalAI.cpp source hash is `9C9C5171C5A0DB85F177360617708782217E0705D8D111E81BC5EEC162963482`. Final flushed result:3169ms search/5.735s observed; exact012022 final records and2132/256 search work preserved. See [the three-build comparison](test-runs/ai-natural-comparison/COMPARISON-233651-012022-024049.md). Later build status must be checked separately; these hashes identify this tested checkpoint.

Shared natural save reported by root: `StackNaturalDenseT0.Civ5Save`, SHA256 `5254CA0E1635D2E4498B7DE12E3972AC43EFDBD8A271CF02B693CD70DE94CEEF`. Root confirmed ordinary UI save/reload under old233651 preserved all22 fixture IDs/types/HP/moves/terrain, legal capacity and zero unrelated units. The natural fixture is centered at(16,1) with12 connected sites.

## Preserve each run before restarting

After HUMAN_RETURN, copy Lua.log and the relevant PlayerTacticalAILog CSV into a separate per-run evidence directory. For a stall/crash, preserve the last available files and label the run incomplete; do not infer success from missing output. Keep the DLL/save/XML hashes, selected AI player and pre-return game turn with the files. Tactical CSV lacks wall-clock timestamps, so isolate a run and filter its player/turn rather than combining older cases sharing the same target coordinates.

The prepared `work/extract_ai_benchmark.py` only reads input logs. With --output it writes a JSON report to the explicitly chosen output path and prints a compact summary. Example (use the actual copied log directory and CSV player field):

```powershell
& 'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'E:\Projects\Civ5StackMod\work\extract_ai_benchmark.py' `
  --logs 'E:\Projects\Civ5StackMod\work\evidence\natural-dense-old\Logs' `
  --player 'The_Shoshone' --turn 0 --label old233651 `
  --save-sha256 5254CA0E1635D2E4498B7DE12E3972AC43EFDBD8A271CF02B693CD70DE94CEEF `
  --output 'E:\Projects\Civ5StackMod\work\evidence\natural-dense-old\metrics.json'
```

The JSON retains every matching tactical row, cache record, natural snapshot, marker and input log hash. Optional --dll-sha256 records the externally verified loaded DLL. It reports unavailable old-build cache data as null, never zero. The old233651 DLL has no new cache instrumentation.

## Time and search work

- Sum EVERY matching `tactsim around (...) ... finished in N ms` row for the relevant AI turn/player, including retries and small searches with0 completed plans. Also record search count, median/max search time, total used positions, completed positions and searches with no completed plan.
- Use STACKNAT AI_START to the following HUMAN_RETURN for the whole observed turn interval. This includes other players, rendering, Lua snapshots and ordinary game processing, so do not call it pure tactical-search time. Missing HUMAN_RETURN means incomplete observation.
- The C++ search timer begins AFTER initialization, initial scoring and dropSuperfluousUnits. Cache counters include that earlier work; search milliseconds exclude it. Do not derive a precise cost per cache lookup from the search timer.
- Integer0ms is rounded/truncated timer output, not proof of no work. Milliseconds per used position is a useful secondary comparison, but score fixes may change search order, number of searches and completed plans. An end-to-end speed improvement is distinct from a cache-only microbenchmark.

For validation, the extractor reproduces the preserved edited-terrain old run as5 searches,23,641ms,6,900 positions and314 completed plans. Four large searches account for6,897 positions; the fifth0ms/no-completed-plan attempt contributes3 additional positions. That is not the new natural benchmark and must not be used as its old baseline.

## Cache performance and memory

The cache line immediately follows its matching tactical-completion row. The extractor associates them in file order and warns about orphan/duplicate cache rows. It reports aggregate danger and defender hit ratios as sum(hits)/(sum(hits)+sum(misses)); a missing/zero denominator is unavailable.

Each bounded-search line includes danger/defender entries, combined peak entries and limit, retained key bytes and limit, estimated cache bytes, insertion bypasses and nested bypasses. Expected bounds are combined entries<=6000 and key bytes<=624000, with combined retained entries equal to the two entry counts. The first bounded-cache version grew monotonically, so retained and peak entries coincided. Later FIFO versions log true peaks separately from current retained entries/key bytes and danger/defender eviction counts; the extractor understands both formats. A nonzero nested-scope count needs investigation because the underlying tactical search uses global storage.

Use MAX peak entries/key bytes/estimated bytes across sequential searches for the turn's cache peak; do not sum them as resident memory. RAII releases both cache tables/buckets when each outer search ends. Key payload is measured by stored vector capacity; total bytes are an estimate of node/key/value/bucket/allocator overhead, not a process-memory measurement. Existing VP caches and other game allocations are excluded.

Insertion bypasses are allowed. The first bounded version stops admitting after either budget fills; later FIFO versions evict the oldest entry from the currently larger pool to refresh the working set, and bypass keys that cannot fit. Every miss still computes and returns the same forecast. A high bypass count or low late hit ratio may explain limited speedup; it is not evidence of dropped simulation work. Never reduce branch/unit/state budgets or hide failed searches to make timing look better.

## Behavioral evidence

Compare the pre-arm snapshots on the SAME save and identical original-human-unit finish-moves step. After the turn compare every fixture ID/role/position/HP, surviving counts, enemy HP loss, human-threat stationarity, legal occupancy and unrelated-unit count. Specifically inspect threatened bows sharing a tile with a melee protector, unprotected bow stacks, and bows whose reported danger is at least their remaining HP. Sharing a tile is not itself proof of useful protection: compare danger and attacker roles. The per-unit danger is a worst-case forecast, not guaranteed actual future damage.

`exactSetup=true` is required in pre-arm/reattached baseline snapshots. `exactSetup=false` AFTER a played turn is normal because positions/HP/moves/turn changed; do not misclassify it as a save roundtrip failure. Dense turn completion alone is not a protection-quality pass.

## Extractor validation

Read-only tests passed against the preserved old dense logs and synthetic new cache rows, including unavailable old metrics, correct hit ratios, a deliberately exceeded payload bound, natural snapshot fields and progress timestamps. No game, C++ or installed-file changes were made for this review/extraction utility.
