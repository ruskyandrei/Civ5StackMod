# Playing the stacking prototype

This is the development prototype for Vox Populi 5.4.6. The configuration reference is [stacking-configuration.md](stacking-configuration.md); current test coverage and remaining work are recorded in `work/REQUIREMENTS-AUDIT-20260927.md`.

## Capacity and combat

Combat units share a tile up to their owner's current capacity, counted separately for land and sea. Cities use the same combat capacity. Civilian, support, aircraft and carrier-cargo rules retain their separate VP handling.

| Unlock | Added slots | Default capacity |
|---|---:|---:|
| Start | — | 2 |
| Iron Working | 1 | 3 |
| Gunpowder | 2 | 5 |
| Military Science | 2 | 7 |
| Robotics | 2 | 9 |

The defender is selected for each attack using its expected combat outcome. A badly wounded melee unit can therefore yield to a healthier ranged defender. Configured melee cavalry and armor can reach ranged/siege members first, unless an eligible anti-cavalry member intercepts them. Mounted ranged units do not gain a melee attack from this rule.

Siege, ranged ships attacking ground units, and bombers cause limited collateral on other eligible occupants. By default each secondary hit is 20% of the calculated primary hit, subject to the attacker's target limit. Collateral alone cannot take a unit below 50% of its maximum health. The primary hit is measured before overkill is discarded. VP's existing siege penalty against land units remains in place. An intercepted bombing mission that is aborted causes no primary or collateral damage to the target stack.

Cities retain VP's ordinary city damage and garrison absorption. New collateral against occupants is reduced by fortifications: Walls 10%, Castle 15%, Arsenal 20%, Military Base 25% and Bomb Shelter 30%, adding up to a default maximum of 90% protection. A positive collateral hit has a default minimum of 1 damage after protection, subject to the health floor. The normal combat preview shows the chosen defender, collateral victims and applicable city protection; air results are conditional on the bombing mission reaching its target.

## Gifting and completed production

A gifted combat unit stays on its current tile. The resulting stack must fit the recipient's capacity and contain no other owner's combat units of the same domain. To gift one member of your stack, first separate it onto a legal gift tile. A refused gift keeps the unit and its cargo; it does not create a replacement or award gift benefits. The ordinary VP territory, native-domain, diplomacy and unit-type restrictions still apply.

Completed production retains one VP exception to the capacity limit: if the city and all adjacent plots have no legal placement, the completed unit is placed in the city anyway. This can create an over-capacity city stack; move the excess unit out. Normal purchases require an available legal placement. Keep a free slot near a producing city when practical. This fallback has not been changed by the prototype.

## Reading and moving a stack

Select a stacked unit to open the roster. Each row shows health, movement and combat role. Click an owned row to select that unit; click the stack title to collapse or reopen the list. Large rosters scroll. Compact map flags show a count badge once the configured threshold is reached.

To move a group:

1. Select the unit that should receive priority if destination space is limited.
2. Click **Move Stack** and hover over a destination.
3. Read **N move; M stay** and the per-unit reasons.
4. Right-click the destination to send eligible members. Left-click the map, press Escape or click Cancel to cancel.

The order includes the owned units present when the button was clicked. Neighboring units and another player's units are not added. A later arrival is marked **Outside order**; begin a new order to include it. A member that leaves the source tile is not collected from its new location.

Each member must be able to arrive this turn under its own normal movement rules. Exhausted units, blocked terrain or borders and unavailable stack slots can split the group. The panel warns when melee protection stays behind while ranged members move without another melee protector. This warning describes the group composition; it does not predict every possible enemy response.

Aircraft keep their normal rebase commands. Cargo travels with an eligible carrier without receiving an independent movement order. Move Stack does not issue an attack or declare war. Revealed threats or changing occupancy can stop a unit en route; the result notification distinguishes arrivals, units that stayed and interrupted moves. Squad membership is preserved. Existing linked movement is released when these individual orders are issued.

## Editing the rules

Edit these source files, then stage/deploy and restart Civ V into a fresh test game:

- `(1) Community Patch/Database Changes/StackingConfig.xml`: capacity, technology rows, combat roles, collateral, city protection, AI preferences and UI layout.
- `(2) Vox Populi/Database Changes/StackingVPConfig.xml`: VP's siege attack-strength penalty against land units.

No DLL rebuild is needed for those XML changes. The default technology bonuses sum to nine; changing only `MaximumCapacity` to ten does not grant an additional slot. Change the base or a technology bonus as well when configuring ten combat units.

The detailed reference describes role precedence, permitted values, special unit exclusions and rounding. The local native build/deployment workflow is documented in `work/BUILD-LOCAL.md`. Fully restart after changing UI Lua/XML; the full UI reload event is not a reliable VP/EUI testing shortcut in this installation.
