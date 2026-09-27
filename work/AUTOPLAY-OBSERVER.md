# Read-only autoplay observer

Load `work/StackingAutoplayObserver.lua` into the current game's FireTuner InGame context, then explicitly start it:

```lua
StackAutoplayObserver.Start(0,10)
StackAutoplayObserver.Status()
-- Detach logging when finished:
StackAutoplayObserver.Stop()
```

`Start(0,10)` observes the whole current game load until manual Stop or context unload. Zero means no elapsed-turn limit. A positive first argument from1 to10000 sets an elapsed-game-turn bound; for example `Start(50,10)` takes the initial sample and observes up to50 subsequent game turns. The second argument controls detailed unit records, normally every10 elapsed turns; occupancy anomalies also trigger details. Aggregates are sampled once per new game turn, independent of human-turn returns.

**Stop stops only this observer. It does not stop AI autoplay, end a turn, pause the game or close it.** The helper never issues orders, changes movement/HP/technology/terrain, creates units, changes configuration, saves a game or enables autoplay. It uses no full-world GetDanger calls. Loading definitions does not start observation.

A saved game does not preserve these Lua callback subscriptions. After loading another save or restarting the game, load the helper definitions into the new InGame context and call Start again. This is reattaching the observer, not a `Reattach()` API. Stop the old observer before intentionally reloading its definitions in the same context.

## Reading the evidence

Lua.log records `STACKAUTO` markers. OWNER records summarize each living player's units and same-owner/domain stack-size histogram. UNIT details include identity, type/domain/plot/coordinates, HP/maxHP, remaining movement, capacity, role flags and relevant exclusions. Ordinary combat-capacity counts are separated from native placement-legality results; civilian/support/air/cargo legality is not treated as a combat-capacity failure.

`rangedWithoutMelee` describes composition only. It does not prove exposure to a reachable enemy or an AI mistake. An occupancy flag can be transient during game processing, and native placement rejection is not necessarily a numerical over-cap stack. Samples taken from PlayerDoTurn occur before that player's later unit-AI update; they are labelled by turn and trigger player, not presented as complete combat traces.

SCAN_START and BEGIN/END timestamps allow approximate observation-cost checks. Lua log timestamp resolution and buffering limit precision; no measured late-game overhead guarantee is implied. Work grows with the number of living units, and detailed records add log volume. Existing tactical/performance/casualty logs remain necessary to assess searches, decisions and losses. A starting or pre-battle save makes suspicious cases reproducible; structural snapshots alone cannot identify every attack or explain its chosen defender.

Archive logs by session before restarting. Some tactical CSV logs are buffered, so retain a final copy after normal exit as well as live snapshots. The observer does not flush or clear engine logs. Its callback error handling detaches observation and reports an error; it does not stop the game.
