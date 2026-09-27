# Stacking development TODO

## Built-in autoplay diagnostics

- [ ] Add optional diagnostics to the VP DLL so autoplay sessions can be observed without injecting a Lua observer. Requested 2026-09-27; planned only. Keep the current `auto_test_1` run on its existing DLL/configuration.
- [ ] Default logging off. Provide an easy runtime toggle and detail-level control through an existing debug/settings interface; keep defaults, sampling intervals, filters and output limits editable in XML where possible. Document which settings require a reload.
- [ ] Record inexpensive per-turn stack statistics: owner/domain capacity, size distribution, city stacks, ranged/melee/anti-cavalry composition, wounded units, and occupancy anomalies. Distinguish structural counts from claims about tactical safety.
- [ ] Add opt-in decision traces for joining/leaving stacks, protector assignment, concentration penalties, target/defender selection and cavalry interception. Record score components and already-computed forecasts so a poor choice can be explained.
- [ ] Correlate actual combat results with those forecasts: primary and collateral victims, HP changes, garrison replacement, and whether movement followed a kill. Distinguish combat deaths from upgrades, transfers and other removals.
- [ ] Include run/build/configuration identifiers, turn and phase, player/unit IDs and tile coordinates. Keep each session's output separate and make it straightforward to associate a log with a saved game.
- [ ] Support long games with configurable summary/detail sampling, player/area/category filters, bounded output and log rotation. Measure sampling and output cost separately from AI computation; make flush behavior explicit for crash/stall investigations.
- [ ] Keep diagnostics observational: no RNG consumption, changed orders/search budgets, or expensive new danger calculations merely to populate a log. Disabled logging should have negligible cost; expensive traces should require explicit opt-in.
- [ ] Validate on the same save with logging off/on: matching gameplay results, correct turn/event counts during autoplay and save/reload, useful battle traces, and measured overhead on a large late-game position.

Current reference: the temporary [autoplay observer](../work/AUTOPLAY-OBSERVER.md) provides structural summaries and periodic snapshots. Existing DLL tactical logs already contain search timings and forecast-cache metrics; reuse and extend those facilities rather than producing duplicate streams. The Lua observer is a prototype for data selection, not evidence that every proposed DLL trace already exists.
