# DLL102 campaign monitoring — 1 October 2026

The user requested a fresh autoplay from the original turn-zero save used by
the performance-test campaign, with diagnostics and offensive-AI monitoring.
This starts from the preserved human save, rather than generating a new map:

- Source: `work/test-runs/campaign47-20260930-1735/Stack DLL47 Fresh T000.Civ5Save`
- Source SHA256: `EA96E61517D6A579CB5DE5492C9DFC0E7D448CD506A9E61C5800CD856A41B461`
- DLL102 source: `19fa6e5ad`; installed SHA256:
  `5CC28920C2625C3685F9E2484DE4D3C62E476201591794F4DB718F7E7FDC22E4`
- Output: `work/test-runs/campaign102-20261001-offense01`
- Exact initial process:38108, UTC creation ticks639264619765225221
- Native log run: `Stacking-20261001T143422-885-p38108-r1`
- Target:350; Summary diagnostics1, tactical sampling off, standard view,
  quick combat/movement, original five mods. No gameplay changes during this run.

The launcher now accepts `-MaximumSeconds`, defaulting to its existing1,800s
short-test limit. This long campaign explicitly uses28,800s. The startup wrapper
executes the tested behavior-replay startup prefix through its single bounded
continuation, then exits. It does not start a second replay polling controller.
The persistent direct Lua service is used once per game process; no FireTuner
GUI, per-turn injected observer, reconnect or mutation retry is permitted.

`monitor-live-campaign.py` handles checkpoints/replay pages every60s, returns
autoplay to a living major if the original return civilization dies, stops at350
and preserves a final save. The optional manifest `SavePrefix` gives this run a
unique filename. Existing game-save and archive collisions are rejected; archive
creation is exclusive. Forty offline checks cover naming, normal stop,
return-player death, exact guards and failed-session behavior.

CPU and GPU/address-space/progress guards independently archive native segments
and protect the run. Helper40820, persistent service38636, CPU guard25100 and
memory/GPU guard19808 are initial identities; verify the current run manifests,
not unrelated later processes with reused IDs. Read `status.json` and
`monitor-events.jsonl` before doing anything. Only the local helper issues
routine game calls. Loss of process/helper/session or a guard cutoff requires
preserving evidence and reporting an incomplete result, without restarting.

Heartbeat `civ-v-dll102-offensive-campaign` is active on this chat at five-minute
intervals. It stays quiet for routine progress and reports meaningful military
findings, problems or completion. At50/100/150/200/250/300/final350, analyze
archived native logs, replay events and ownership censuses. Keep timings and
record coverage alongside military observations.

Comparison baseline:
`work/campaign102-preparation/comparison-baseline47-offense.json`. The original
campaign had no confirmed conquest before207. By250 it had six conquest events
on five plots, including a barbarian capture and subsequent recovery of Haarlem.
City targets include Panama City, Dublin, Arpinum, Groningen, Utrecht and Rome.
Compare first effective attack, net city damage, essential siege/capture roles,
reinforcement combat contribution, production/supply constraints and actual
10/20-turn holding periods. Separate captures by third parties, temporary flips,
barbarian transfers, recent censored captures and replay-confirmed razing.

Native readiness records are decisions, not executed attacks. Rome's old fleet
was chiefly on naval-superiority missions; check mission and target before
calling a fleet idle or treating it as a city assault. A single same-map campaign
can expose mechanisms and regressions, but cannot establish general balance.
