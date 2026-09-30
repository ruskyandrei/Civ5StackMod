# Direct Civ V automation

The project can run Lua against Civ V without opening FireTuner or using mouse/keyboard automation. `tools/civ5_tuner.py` talks directly to the game's existing debug socket. `tools/civ5_control.py` provides common test commands. No new DLL bridge or gameplay change is required. The transport and serializer are independent of the stacking mod and can be carried to a standard VP branch. The optional diagnostics command uses the stacking DLL's existing diagnostics APIs; status reports diagnostics=-1 when those APIs are absent.

The installed SDK supplied the protocol evidence: `FireTuner2.Connection.Request`, `OnMessageRecieved`, `LuaStateManager.QueryLuaStates` and `LuaConsole.RunConsoleCommand`. Messages use little-endian payload length and listener ID, followed by NUL-terminated UTF-8 strings. Requests include `LSQ:` and `CMD:<context ID>:<Lua>`. The connection uses localhost port 4318, already enabled by this PC's `EnableTuner=1` setting.

Keep FireTuner closed. Civ V's socket behaved poorly with competing/repeated short-lived connections, so one local service keeps the game connection open and continuously drains unsolicited output. A deliberate clean service disconnect/reconnect also failed while the game remained responsive: new connections established but Lua-state queries received no reply, and sockets stayed in CLOSE_WAIT. Treat one service as belonging to one game-process lifetime. After losing it, restart the game as well as the service. This is an observed engine limitation, not proof of its internal cause.

Command-line calls use an authenticated HTTP endpoint bound to `127.0.0.1`; its random token is stored in the ignored `work/tuner-session.json`. Do not publish that file. Stop the service before starting another session. `stop` waits for its session file to be removed. Timeouts do not retry commands whose execution outcome is unknown.

## Commands

Use the bundled Python or another Python 3.10+ installation. No third-party packages are required to operate the tools. From the project directory, with Steam signed in:

```powershell
.\tools\launch-civ5.ps1
python tools/civ5_tuner.py serve
```

The launcher selects the actual DX11 executable. It temporarily supplies the standard Steam SDK `steam_appid.txt` development-launch file until the game opens its debug port, then removes the file it created. An existing matching file is preserved. Launching the executable without keeping this file through Steam initialization caused Steam to restart the default DX9 executable on this PC.

Keep `serve` running in its terminal or launch it as a hidden background helper. In another terminal:

```powershell
python tools/civ5_control.py prepare-mods
python tools/civ5_control.py load "E:\path\to\test.Civ5Save"
python tools/civ5_control.py status
python tools/civ5_control.py diagnostics 1
python tools/civ5_control.py autoplay 2 --return-player 0
python tools/civ5_control.py continue
python tools/civ5_control.py status
```

`prepare-mods` activates the currently enabled mod selection; it does not select a different set of mods. Use a save matching that selection. Loading is asynchronous: wait until the InGame context exists and `continue` confirms that the loading screen's activation button is available. Arm bounded autoplay before `continue` when loading an observer save. Choose an alive major civilization as the return player; VP makes that player human at the end, even if it is currently AI-controlled in an observer save. Returning to observer/NO_PLAYER can keep turns advancing after the autoplay counter reaches zero; the convenience command rejects that choice. `halt --return-player 0` returns control to that player, including from an observer whose autoplay counter is already zero.

Diagnostics levels are 0 (off), 1 (Summary), and 2 (Verbose). Lua execution also works in normal play without displaying the diagnostics button:

```powershell
python tools/civ5_tuner.py exec --code "return Game.GetGameTurn()"
python tools/civ5_tuner.py exec --file "E:\path\to\fixture.lua"
python tools/civ5_tuner.py exec --context MainMenu --code "return UI.GetVersionInfo()"
python tools/civ5_tuner.py states
python tools/civ5_control.py menu
python tools/civ5_control.py quit
python tools/civ5_tuner.py stop
```

The general `exec` command defaults to InGame. Context names are resolved again for each request, so reloads do not use retained unit pointers or obsolete context IDs. Ambiguous names such as LoadMenu are rejected. Return primitives, dense arrays or tables with string keys; userdata/functions need conversion to ordinary values. Nil return positions are preserved as JSON null. Empty Lua tables become JSON objects.

## Bounds and lifecycle

Civ V rejected long console commands despite accepting larger socket packets. The client uploads source in 256-byte chunks, each escaped command below 1,400 bytes, then executes it inside the selected engine context. A small serializer is installed once per context. Results are emitted in short hexadecimal chunks so console limits and UTF-8 boundaries do not truncate structured data.

Source is limited to 64 KiB; results to 256 KiB, 10,000 serialized values and depth 16. Ordinary command output is capped at 128 records/256 KiB, with a dropped-record count; structured results have a separate bounded channel. Idle operation drains engine messages without polling the map, scanning units or executing Lua. The service allows one command at a time and rejects competing jobs rather than queueing them across a reload.

Additional observations useful when porting the workflow:

- The SDK's receive guard is 524,288 bytes. Its length field counts the text payload, including terminating NUL bytes, and excludes both four-byte header fields. Replies can contain several NUL-separated strings. TCP reads can split either header or payload, so the client reads exact lengths rather than assuming one read equals one message.
- The listener ID is a response correlation ID, not a message-type field. Broadcast ID `0xFFFFFFFF` carries `O` output records, `L` context-list updates and `Closing` notices. Console commands normally return an empty acknowledgment; Lua `return` values are not supplied by that acknowledgment. Our wrapper serializes them through correlated print markers.
- Console rejection occurred with commands above roughly two KiB in the probes; this is an empirical range rather than a verified constant in the closed-source executable. A 256-byte upload becomes at most 1,024 bytes of Lua decimal escapes, leaving room for the assignment and context prefix. Keeping individual source commands below 1,400 bytes worked. Multiline user source is preserved inside uploaded byte strings instead of being flattened or stripping its comments.
- Lua 5.1 does not accept JSON-style Unicode string escapes. Source is encoded as UTF-8 bytes using three-digit decimal Lua escapes. Results are chunked as ASCII hex and reassembled before UTF-8 decoding, preserving characters even when a chunk boundary splits a multibyte sequence.
- Lua contexts are separate environments. Use InGame for loaded-game APIs and menu-specific contexts for their callbacks. VP activation rebuilds menu contexts; game load builds a different InGame context. Never retain a raw context ID from a previous load. The helper stores no unit/city userdata between calls.
- The result wrapper runs `loadstring` and `pcall`, preserving global writes and existing game functions. Syntax/runtime errors and serialization errors are ordinary structured failures. Cyclic tables, non-finite numbers, userdata/functions and sparse numeric-key tables are rejected. Format unusually precise floating-point values as strings when exact textual precision matters; ordinary numbers use Lua 5.1's `tostring`.
- VP's load-screen activation callback is local in the EUI version. The convenience command checks that its activation button is visible, then performs that callback's engine actions: close the screen, clear the pause player and allow popups. Context existence alone is not proof loading has completed.
- `GameOptionTypes.GAMEOPTION_QUICK_MOVEMENT` is nil in the tested game. Use `Game.SetOption('GAMEOPTION_QUICK_MOVEMENT', true)` and verify `PreGame.GetQuickMovement()`. Quick combat also accepts its string key. The autoplay convenience command enables both options explicitly.
- `SetAIAutoPlay` ignores a request when the new counter equals the old counter, including changes to the requested return player. The helper changes the counter first when necessary. A zero counter in observer mode does not itself stop turn advancement; `halt` transitions through a positive counter and back to zero in one Lua call to return control. An alive major return civilization is required, but its current `IsHuman()` flag can be false because autoplay changed its slot to computer control.
- `Events.PlayerChoseToLoadGame` is asynchronous. Use matching installed/enabled mods, an existing save header, then confirm the loaded turn and player before continuing. Loading the preserved test file did not modify that file. No existing user saves are written by these convenience commands.
- `UI.ExitGame()` and `Events.ExitToMainMenu()` are asynchronous too. An accepted request is not proof the process has exited or menus have finished rebuilding. Verify process exit/context readiness before launching a replacement. The launcher deliberately refuses to overlap an existing Civ V process.

The default engine timeout is 15 seconds for generic requests and 120 seconds for lifecycle commands. Context discovery, helper/source upload and execution share a total budget. A timeout while awaiting a dispatched command is ambiguous and invalidates the engine connection; the client never resends it. An expired upload budget before dispatch does not run the uploaded source. Lua/native execution cannot be safely preempted by a client timeout. A lost connection ends that service's usable engine session; close it and start a new service/game deliberately. There is no automatic replay of mutations.

This removes computer-use input from launch, activation, save loading, Lua fixtures, diagnostics, bounded autoplay, menu return and quit. Civ V still runs its graphical executable. Minimized progress, renderer-free execution and fresh-game setup have not been verified by these tests. Visual inspection can still help diagnose graphical/UI issues.

## Validation

Offline tests exercise actual framing, fragmented reads, context validation, stale response IDs, bounded output, timeout without retry, result chunks and the serializer in the existing Lua 5.1 validation runtime. Run `python tools/test_civ5_tuner.py`; its Lua checks use the locally installed `work/lua-validation` runtime used by the project's other UI fixtures.

Native smoke tests on 30 September 2026 used the installed DLL35. With FireTuner closed and no computer-use input, the tools launched Civ V, activated VP, loaded the preserved turn-zero campaign save, read typed/Unicode JSON results and deliberate Lua errors, enabled Summary diagnostics, ran exactly two autoplay turns and returned to human player 0. A 100-row structured result crossed the console-size boundary successfully. The same connection survived menu return, mod reactivation and save reload: the InGame ID changed from 245 to 538, with turn zero and the correct human restored. Starting and halting a 20-turn counter while the load screen remained paused returned to human 0 without advancing a turn.

The deliberate reconnect test then required recycling that isolated paused test process. It was terminated without overwriting a user save; no turn-processing crash was observed. Two earlier API-driven quits closed normally.

Final native checks on a freshly launched DX11 process passed a 20,134-byte multiline script with 1,000 comment lines, typed/Unicode results, 200 console prints (128 retained/72 dropped), cyclic-result and syntax errors, malformed JSON-job rejection and unauthenticated request rejection. The same connection remained usable after all these failures. The check took about 1.6 seconds, including the long upload and deliberate output flood; it is not a game-turn performance measurement. The final API-driven quit exited normally with code 0. The service/session file and temporary Steam app-ID file were removed. The original auto_275 save and installed DLL35 hashes remained unchanged. Eleven offline test cases pass.

## Porting to standard VP

The separate workflow commit contains only the tools and documentation; it adds no native source, mod SQL/XML, or UI panels. Cherry-pick it onto a VP development branch and adjust the launch path or supply `-GameDirectory`. The generic socket service, serializer, Lua execution and menu/save commands work independently of the stacking rules. The convenience diagnostics command intentionally checks for the existing stacking APIs and reports their absence on an ordinary DLL. Replace that command with the diagnostics APIs/settings appropriate to the receiving branch, or use generic Lua fixtures.

The game-level smoke tests were run with this installed VP/stacking DLL, not a separate stock-VP build. The initial menu protocol/results tests did not require an activated stacking DLL. Portability of transport is established by using the existing engine protocol; full ordinary-VP campaign compatibility still needs a smoke test on that branch. A receiving branch also needs either the local Lua 5.1 validation runtime for serializer tests or an equivalent Lua 5.1 environment; operation itself remains standard-library-only Python.
