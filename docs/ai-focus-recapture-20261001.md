# Reinforcement focus and recapture — 1 October 2026

Follow-up to `ai-siege-combined-20261001.md`. Two weaknesses found in the
fresh same-map game:
- armies were spread over too many city objectives;
- civilizations that lost a city almost never tried to take it back.

## Findings

### Armies spread over many objectives

Every visible enemy city that the tactical AI lists becomes a city objective,
up to `AIOffensiveSupportMaximumObjectives` (8) per player. Every objective
asked for reinforcements and offensive production at the same priority, so
units went to the nearest one.

In the fresh game (turns 0–232), the major civilizations' `SIEGE_ROSTER`
samples had:
- one land objective 57 times;
- two to four 77 times;
- five to eight 59 times.

Their land assault plans' first waves were small:

| Units in the first wave | Plans |
|---|---:|
| 0 | 232 |
| 1–3 | 163 |
| 4–7 | 74 |
| 8 or more | 28 |

### Lost cities were not retaken

Only three of the fourteen captures in that game were retaken by the former
owner, and one of those, by Mongolia, came five turns after the loss. For the
others, the former owner's assault plans for the lost city:
- were rare, with few units and a local enemy strength several times their
  own (Arabia after turn 233: 442–920 against 55–127);
- were not blocked by the readiness or tactical gates.

The cause is supply, not the gates:
- A captured city keeps at least half its HP (`CITY_CAPTURE_DAMAGE_PERCENT`).
- The captor's army is still around it.
- The former owner's reinforcements went to its other objectives or stayed in
  its threatened cities (10–18 retained units each).
- A lost city got an objective only while the tactical AI listed it, and not
  at all once the player had eight objectives.

## Changes

1. **Reinforcement focus** (`AIOffensiveFocusObjectives` 2).
   - **Ranking:** each turn, each player's objectives in each domain are ranked
     by promise:
     - the healthy strength already credited to the objective (its army,
       committed units and free units within four tiles), as a percentage of
       the local enemy strength, capped at 200;
     - plus the city's missing HP percentage;
     - minus 4 per tile from the player's nearest city;
     - plus 60 for a live city-attack operation, 100 for a recently lost own
       city, and 30 for an objective already in the focus.
   - **Effect:** only the best two get reinforcement demands and offensive
     production.
     - Units already near another objective still fight there.
     - A unit committed to an objective that dropped out of the focus may be
       redirected.
   - **Log:** `OFFENSIVE_FOCUS` whenever the focused set changes.
2. **Recapture objectives** (`AIRecaptureMemoryTurns` 30).
   - **Objective:** a city lost within 30 turns stays a land objective of its
     former owner while the captor holds it and the two are at war, even
     beyond the eight-objective cap.
   - **Priority:** it gets the 100-point focus bonus and a reinforcement
     priority bonus of 40 (`AIRecaptureFocusBonus`,
     `AIRecaptureDemandPriority`).
   - **Readiness:** unchanged. Reinforcements gather on the safe staging tile;
     the attack still waits for readiness or bombardment.

## Evidence

### Turn-260 replay of campaign 102 (turns 260–271)

Same save as the earlier replays. C11 is this change; C9 the previous build.

| | C9 | C11 |
|---|---:|---:|
| City attacks | 156 | 174 |
| Captures | 3 | 4 |
| Average turn | 24.0 s | 24.9 s |
| Slowest turn | 30.3 s | 28.7 s |

`OFFENSIVE_FOCUS` picked, for example:
- for Songhai, out of four land objectives, its two sieges with forces of
  1,415 and 1,047 strength;
- Rome's two recently lost cities from turn 262, although Rome had no force
  near them yet.

### Fresh game from turn 0 (same map and civilizations)

`work/run-fresh-campaign.ps1` with C11 to turn 270, no crash. This game also
used the new technology capacity bonuses (+1 each for Iron Working, Gunpowder,
Military Science and Robotics, so 6 at most instead of 9). Both changes are
therefore in the comparison below, and they cannot be separated from a
single game.

Compared with the previous fresh game (C9 to turn 232, then C10 to turn 270):

| | Previous fresh game | C11, +1 capacity |
|---|---:|---:|
| Reinforcement dispatches to each player's main target (per 5 turns) | 59% | 71% |
| Distinct dispatch targets per player (per 5 turns) | 2.8 | 2.1 |
| Land objectives per player (roster samples) | 3.2 | 2.5 |
| Land units within 4 tiles of an objective (roster samples) | 6.8 | 6.3 |
| Major-civilization land assault plans with 8 or more units in the first wave | 9% | 6% |
| Combats between major civilizations, turns 0–231 (pairs with city attacks or over 50 combats) | 2,453 | 1,289 |
| City attacks between major civilizations, turns 0–231 | 497 | 301 |
| Major-civilization city captures, turns 0–270 | 18 | 7 |
| Seconds per turn, turns 200–250 | 17.6 (200–231) | 16.1 |
| Seconds per turn, turns 250–270 | 19.7 (C10, 230–270) | 18.2 |

- **Focus.** Reinforcements did concentrate, but the force near objectives
  and the first waves did not grow. Smaller stacks are a likely cause: fewer
  units fit within reach of a city.
- **Captures.**
  - Songhai took four Roman cities: on turn 98, then three on turns 223–230.
  - Mongolia took two city-states and Songhai one.
  - The peer wars of the previous game (Netherlands, Morocco and Babylon
    against Arabia; Carthage against Mongolia) did not happen in this game
    or stayed mostly in the field. The two games diverge from their first
    different decision, so their wars differ.
- **Recapture.** Untested.
  - Rome lost its three cities within seven turns.
  - It focused one of them on turn 225, with no force near it. At another,
    the captor's local strength was 676 on turn 228.
  - Rome made peace with Songhai on turn 231, which ended the objectives.
