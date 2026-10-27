# Changelog

All releases of Civ5StackMod, newest first. Downloads are on the
[Releases page](https://github.com/ruskyandrei/Civ5StackMod/releases). Upstream
Vox Populi changes are not listed here; each version names the Vox Populi
release it is based on.

## Unreleased

### Performance
- The game DLL is now built with clang and link-time optimisation, as Vox
  Populi's own releases are, instead of Visual C++ 2008. The AI's work in
  late-game turns takes about a third less time; the game's own rendering and
  waiting between turns are unchanged. Games otherwise play the same, apart
  from tiny rounding differences in some calculations.
- The AI no longer recomputes its whole map of threatened tiles each time one
  of its units spots or loses sight of an enemy, or an enemy unit moves, dies
  or is promoted. That cost grew with army sizes and wars; late-game AI turns
  take about a sixth less time on top of the faster build above. Together,
  late-game AI turns take about half the time they did in 0.3.4.

### AI
- Within a turn, the AI keeps counting the enemy units it saw at the start of
  the turn after they move out of sight, as Vox Populi's AI does, instead of
  forgetting them at the next update. Games therefore play differently from
  0.3.4.

## 0.3.4 — 2026-10-27

Based on Vox Populi 5.4.8.

### Fixes
- The game no longer crashes when an AI unit captures a city and liberates or
  razes it, for example when it frees a city-state.
- The game no longer crashes when it picks the defender of a stack that still
  holds a unit at 0 hit points waiting to be removed.

Stacking rules, the stacking AI and the interface are otherwise unchanged from
0.3.3.

## 0.3.3 — 2026-10-16

- Now based on Vox Populi 5.4.8. See the
  [Vox Populi 5.4.8 release notes](https://github.com/LoneGazebo/Community-Patch-DLL/releases/tag/Release-5.4.8)
  for what changed there.

Stacking rules, the stacking AI and the interface are unchanged from 0.3.2.

## 0.3.2 — 2026-10-11

Based on Vox Populi 5.4.7.

### AI
- **Redirected attacks.** When an important city needs a second attack group,
  the AI can call off an attack still forming against a clearly less important
  city and send those units instead. The target has to be at least 50% more
  important, so attacks on cities of similar value are left alone.
- **Siege positions.** Units besieging a city prefer forest, hills and other
  defensive terrain. Melee units avoid waiting where their attack on the city
  would cross a river.
- **Conquered cities.** The AI puppets a captured city instead of annexing it
  when annexing would make its empire unhappy. It no longer razes developed
  conquered cities (size 6 or more) unless revolt is close or the city is in
  danger, and buys their courthouse when it can. It stops razing a city once
  happiness recovers. This prevents the raze-then-resettle pattern on the same
  tile.
- **Holding overseas conquests.** Land units can sail to defend the AI's cities
  on other continents when no enemy warship is near. A city captured by sea
  with no land unit gets a defender bought for it once resistance ends.
  Against a major civ's city overseas, the AI more often chooses a combined
  land and sea attack over a ships-only one.
- **Besieged garrisons.** Units held back to defend a city now attack after the
  rest of the army, so they can finish off wounded besiegers. A healthy melee
  defender may leave the city to make a kill while at least two defenders
  stay. A threatened city with only melee defenders buys a ranged unit, since
  cities do not shoot in this mod.
- The new settings are in `StackingConfig.xml` and described in the
  [list of XML options](docs/stacking-xml-options.md).

### Other
- Longer stacking diagnostics logs by default (only used when diagnostics are
  switched on).

## 0.3.1 — 2026-10-11

Based on Vox Populi 5.4.7.

### AI
- **Mixed stacks.** The AI prefers one melee unit protecting ranged units over
  all-ranged or all-melee stacks, on land and at sea. This applies in battle,
  while gathering, patrolling and staging, and in city garrisons, which now
  keep a melee unit among their ranged defenders.
- **Flanking.** Melee units move next to an enemy stack to give flanking
  bonuses to the attacks that follow in the same turn. Attack estimates now
  include flanking promotions.
- **City sieges.** Attackers surround a city so that it is blockaded and cannot
  heal, when they have enough units to close every side.
- **Second attack group.** A city that is too strong for one army, or a capital
  or wonder city, can draw a second attack group. The two armies attack as one
  force.
- **Medics.** The AI promotes about one medic per six units of an army instead
  of many, since medic bonuses do not add up. Medics stay in stacks without
  another medic, and wounded units move into a medic's stack.

### Interface
- The stack roster lists the units that fight for the tile first. Civilians,
  cargo, aircraft and ships in a city are greyed out, and their tooltip says
  they are not part of the tile's combat stack.

## 0.3.0 — 2026-10-09

- Now based on Vox Populi 5.4.7. See the
  [Vox Populi 5.4.7 release notes](https://github.com/LoneGazebo/Community-Patch-DLL/releases/tag/Release-5.4.7)
  for what changed there.

Stacking rules, the stacking AI and the interface are unchanged from 0.2.1.

## 0.2.1 — 2026-10-04

Based on Vox Populi 5.4.6 plus upstream changes. The game DLL is built from
the same source as 0.2.0; this release only changes the interface.

### Stack roster
- Each unit in the stack roster now has a health bar: green at full health,
  through yellow, to red, with the exact hit points written on it. Movement
  and role follow it on the same line.
- Hovering a tile with two or more visible units of another player opens a
  read-only roster of that stack, to the right of where your own roster sits,
  whether yours is open or not. Its title names the owner, in red when you are
  at war, and shows the stack's capacity. Units you cannot see are not listed.
  On a narrow screen it appears above your own roster instead.

### Fixes
- In observer mode and AI autoplay, old notifications keep expiring after a
  Lua error; before, one error stopped them expiring for the rest of the
  session.

## 0.2.0 — 2026-10-02

Based on Vox Populi 5.4.6 plus upstream changes.

### Moving stacks
- While choosing a **Move Stack** destination, the map shows how far the stack
  can go this turn: green tiles take every unit in the stack, yellow tiles only
  some. The tile under the cursor is drawn more strongly; beyond the shaded
  area it is gray if the stack can get there in later turns and red if no unit
  may go there (terrain, borders, an enemy or a full stack).
- Move Stack now sends the whole stack. Units that cannot arrive this turn,
  including units with no moves left, get a normal multi-turn move order. They
  go as far as they can now, continue on later turns and keep their place at
  the destination. The panel previews "N arrive now; L later; M stay" with turn
  counts, and the result message reports units still on the way.
- New shortcut: hold **Alt** with a stacked unit selected to see the same reach
  and preview under the cursor, and Alt + right-click to move the stack. If no
  unit of the stack can take the tile (an enemy, for example), the click does
  the normal right-click for the selected unit, so attacks still work.
- New setting `UIStackMoveModifier` chooses the shortcut key: 0 Alt (default),
  1 Shift, 2 Ctrl. Shift or Ctrl replace that key's usual right-click behaviour
  for stacked units.

### Barbarians
- Fewer barbarians under stacking. In a test game they ran at about twice plain
  Vox Populi's numbers between turns 40 and 150 (46.8 units on average against
  23.8). With these changes the same game averaged 33.2, and late in the run
  camps fell from about 20 to 12.
  - Only a camp's or city's best defender stays put; other barbarians standing
    there move on.
  - Extra units in a camp count toward the spawn cap.
  - Barbarians no longer gain stack slots from stacking technologies (new
    setting `BarbarianTechnologyCapacity`, default 0).
- The AI sizes camp-clearing parties to the camp's defenders and clears camps
  near city-states first. New settings: `AIBarbarianCampPartyMaximum`,
  `AIBarbarianCampWarRadius`, `AIBarbarianCampCityStateRadius` and
  `AIBarbarianCampCityStateBonus`.

## 0.1.0 — 2026-10-01

First pre-release, based on Vox Populi 5.4.6 plus upstream changes up to
`d79cd781c`.

- Limited unit stacking: several combat units share a tile, two at the start
  and up to six with military technologies, counted separately for land and
  sea.
- Stack combat: the defender is chosen for each attack, mounted and armored
  melee units can flank past the defender to hit ranged and siege units
  behind it, and siege, ranged ships and bombers deal collateral damage to the
  rest of the stack.
- Cities no longer shoot; the ranged units stacked inside defend them, and
  fortifications reduce collateral damage to those units.
- Interface: a stack roster, Move Stack, count badges on crowded tiles, and a
  combat preview showing the chosen defender and collateral victims.
- An AI that builds, moves and attacks with stacks: garrisons by role, assault
  waves with siege, bombardment before storming, reinforcement of its best
  objectives and attempts to retake lost cities.
- Rules and AI behaviour are configurable in `StackingConfig.xml`.
