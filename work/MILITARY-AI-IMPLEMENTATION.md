# Military allocation implementation — 2026-09-27

User authorized implementation with mostly offline work and one final smoke launch. Baseline VP5.4.6 stacking source ef54698 ran through turn330 without reported crashes; notification default3 is user-confirmed. Save/log baseline and hashes are preserved under `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/ai-baseline-330`. No save-format fields changed.

Changes and known limits are described in `docs/military-ai-plan.md` and `docs/stacking-configuration.md`. Main new source is `CvStackingAI.cpp`, with small integration hooks in the existing AI. Tactical search remains13units/6000states; no increased search-memory limits.

Offline verification: native VC9 actual-source allocation135/135; native diagnostic observer/policy/IO44/44; Python log summarizer16/16; prior no-op39/39, endpoint16/16, siege41/41, production-placement74/74, combat-cache30100/30100, observer notifications41/41. The large cache count is repeated eviction/state coverage, not independent scenarios or a performance benchmark. Engine pathfinding/world services in the allocation harness are stubs. Logging on/off gives identical allocation outcomes in the controlled fixture; live deterministic equivalence is not claimed.

Build/deployment and final smoke results: pending. No new DLL should be described as installed until the deployment result confirms it. User's next fresh campaign supplies the meaningful longer-term evaluation: rear-city surplus, actual arrivals, siege composition, assembly ages/restarts, defended/lost cities, turn time and memory.
