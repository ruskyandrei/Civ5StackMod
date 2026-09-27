# Native diagnostics core: independent review and policy tests

Reviewed source checkpoint: CvStackingDiagnostics.cpp SHA256 D82BC6B48EAF27EE5AD40381D05A82509FC7BDD1858A43DAA30B94F5125A1F44. No source changes by reviewer; coordinator owns implementation/build/deployment.

## Result

No remaining blocking finding in the reviewed core. `work/test-diagnostics-core.py` compiles the actual logger helpers plus Reset/GetLevel/Enabled/GetStatus/SetLevel/Record using the project's native VC9 compiler and CRT. Engine/config/DB getters are deterministic stubs, and injected open/write failures wrap the real CRT. Actual files are created only under work/diagnostics-core-regression/logs.36 checks pass with0 failures; result/hashes are in work/diagnostics-core-regression/result.json.

Coverage: default Off performs no file opens/writes or DB scan; invalid levels leave state unchanged; owner filter/global records; summary excludes verbose; cached settings; turn-row cap and one truncation marker; next-turn reset; newline/oversize messages; real64KB rotation with at most2 retained files per session; nonzero config fingerprint on later segments; Off/On retains session ring; open/write error latching and explicit retry; long path/filename rejection; actual concurrent Record versus Set/Get calls complete under the recursive lock; TLS status snapshot remains valid; Reset reapplies the XML default and clears session identity.

An initial real IO failure was found: VC9 `_wfopen_s(...,"wb")` denied live readers (Win32 error32 even with FILE_SHARE_READ|FILE_SHARE_WRITE). Coordinator changed it to `_wfsopen(...,_SH_DENYWR)`, allowing readers while denying other writers. The36-check run above uses the corrected actual source and real readback; failed earlier runs were not counted as passes.

## Source-reviewed integration

The core issues no gameplay commands or RNG calls. Histogram sampling uses fixed-size storage and the minimum unit ID as one representative per owner/domain/tile; it excludes cargo, air and support/civilian units as intended. Central settings clamp file count, intervals, row/file limits and histogram indices. CombatScope saves owner/ID/HP before resolution and looks units up again afterward, avoiding retained raw pointers when casualties/capture delete units. The35 stored identities cover the engine's32 damage members plus3 combat roles. Compilation-facing getters/const overloads and battle enums were checked against local headers.

The exact OnPlayerTurn grouping and CombatScope methods were source-reviewed, not executed by this focused policy harness. Native DLL integration/build and live game verification belong to the coordinator. This review does not establish negligible overhead, changed AI performance, save determinism or crash prevention.

## Interpretation limits

The first SESSION header can contain configFNV=00000000 because it precedes the configuration scan; the following CONFIG record supplies the computed fingerprint. Later rotated SESSION headers retain that fingerprint. Raw XML rows are distinguished from effective clamped values. The ring is bounded per loaded-game session; separate processes/games intentionally retain separate prefixes and need ordinary archive management. Composition counts are structural observations, not threat predictions. Diagnostic level changes do not persist through loading a game and do not stop autoplay.
