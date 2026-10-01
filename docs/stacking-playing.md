# Playing the stacking prototype

This is the development prototype for Vox Populi 5.4.6. The configuration reference is [stacking-configuration.md](stacking-configuration.md); current test coverage and remaining work are recorded in `work/REQUIREMENTS-AUDIT-20260927.md`.

## Start a game

The tested prototype is installed on this PC. Launch Civ V in DX11 windowed mode, choose **Mods**, and enable the tested set:

- (1) Community Patch
- (2) Vox Populi
- (3a) VP - EUI Compatibility Files
- (4a) Squads for VP

Choose **Next**, then **Single Player** from the Mods screen and set up a new game. The stacking changes are part of the Community Patch DLL and EUI files; there is no separate stacking checkbox. Modpack Maker need not be enabled. Use the Mods route again when loading a campaign made with this prototype.

The tested native Release DLL is `work/msvc-output/Release/20260927-105159/CvGameCore_Expansion2.dll`, SHA256 `D25416742EE592C3673DFED18F1C6816D8A4685C91707362C2B5DDA3A26BC3E7`. Gameplay defaults are unchanged; diagnostics default to Off. Build/deployment instructions and recovery options are in [BUILD-LOCAL.md](../work/BUILD-LOCAL.md).

This is an experimental playable build. Focused tests cover actual combat, XML overrides, stack movement, completed production, and save/reload. An earlier build's three-turn AI test completed in about 5.7, 3.8 and 3.0 seconds per observed AI interval, then reloaded with all 46 units and 11 cities matching their recorded state. Protective stacking is demonstrated; deliberate spreading against siege collateral, broad naval/air strategy and long-campaign balance still need playtesting. Multiplayer and unrelated mod combinations have not been validated.

## Capacity and combat

Combat units share a tile up to their owner's current capacity, counted separately for land and sea. Cities use the same combat capacity. Civilian, support, aircraft and carrier-cargo rules retain their separate VP handling.

| Unlock | Added slots | Default capacity |
|---|---:|---:|
| Start | — | 2 |
| Iron Working | 1 | 3 |
| Gunpowder | 1 | 4 |
| Military Science | 1 | 5 |
| Robotics | 1 | 6 |

The defender is selected for each attack using its expected combat outcome. A badly wounded melee unit can therefore yield to a healthier ranged defender. Configured melee cavalry and armor can reach ranged/siege members first, unless an eligible anti-cavalry member intercepts them. Mounted ranged units do not gain a melee attack from this rule.

Siege, ranged ships attacking ground units, and bombers cause limited collateral on other eligible occupants. By default each secondary hit is 20% of the calculated primary hit, subject to the attacker's target limit. Collateral alone cannot take a unit below 50% of its maximum health. The primary hit is measured before overkill is discarded. VP's existing siege penalty against land units remains in place. An intercepted bombing mission that is aborted causes no primary or collateral damage to the target stack.

Cities retain VP's ordinary city damage and garrison absorption. New collateral against occupants is reduced by fortifications: Walls 10%, Castle 15%, Arsenal 20%, Military Base 25% and Bomb Shelter 30%, adding up to a default maximum of 90% protection. A positive collateral hit has a default minimum of 1 damage after protection, subject to the health floor. The normal combat preview shows the chosen defender, collateral victims and applicable city protection; air results are conditional on the bombing mission reaching its target.

## Gifting and completed production

A gifted combat unit stays on its current tile. The resulting stack must fit the recipient's capacity and contain no other owner's combat units of the same domain. To gift one member of your stack, first separate it onto a legal gift tile. A refused gift keeps the unit and its cargo; it does not create a replacement or award gift benefits. The ordinary VP territory, native-domain, diplomacy and unit-type restrictions still apply.

With stacking enabled, a completed ordinary land or sea combat unit waits if the city and every adjacent tile have no legal space. A notification asks you to make room. Its queue entry and stored production remain; keep or select the unit in production and it retries during a normal production update after a slot opens. You can still cancel or reorder production. Additional production accumulates and settles through VP's normal overflow and excess-gold rules when the unit completes.

Normal purchases require an available legal placement. Civilian, aircraft and special support production retain their existing rules. Resource, supply, obsolescence and other ordinary training restrictions can still invalidate an order; waiting for space does not bypass them.

## Reading and moving a stack

Select a stacked unit to open the roster. Each row shows health, movement and combat role. Click an owned row to select that unit; click the stack title to collapse or reopen the list. Left-click an empty map hex to dismiss the roster, then select a unit or click its stack badge to reopen it. Large rosters scroll. Compact map flags show a count badge once the configured threshold is reached.

To move a group:

1. Select the unit that should receive priority if destination space is limited.
2. Click **Move Stack** and hover over a destination.
3. Read **N move; M stay** and the per-unit reasons.
4. Right-click the destination to send eligible members. Left-click the map, press Escape or click Cancel to cancel.

The order includes the owned units present when the button was clicked. Neighboring units and another player's units are not added. A later arrival is marked **Outside order**; begin a new order to include it. A member that leaves the source tile is not collected from its new location.

Each member must be able to arrive this turn under its own normal movement rules. Exhausted units, blocked terrain or borders and unavailable stack slots can split the group. The panel warns when melee protection stays behind while ranged members move without another melee protector. This warning describes the group composition; it does not predict every possible enemy response.

Aircraft keep their normal rebase commands. Cargo travels with an eligible carrier without receiving an independent movement order. Move Stack does not issue an attack or declare war. Revealed threats or changing occupancy can stop a unit en route; the result notification distinguishes arrivals, units that stayed and interrupted moves. Squad membership is preserved. Existing linked movement is released when these individual orders are issued.

## Diagnostics

In observer mode or during autoplay, click **Diagnostics** near the top center of the map. The control is available without selecting a unit or opening a stack roster, and hides during normal play. Choose **Off**, **Summary** or **Verbose**; the panel shows the current level and the native logger's status, including the log location or an output error. Escape or Close dismisses the panel.

Logging defaults to Off. Summary records turn diagnostics; Verbose adds detail. This changes logging only and works during normal play or autoplay without injecting a Lua observer. Files use the normal Civ V Logs directory and rotate within configured limits (by default, eight segments of up to 4 MB). Turning logging off keeps files already written.

The selection applies to the currently loaded game session. Returning to normal play hides the controls but keeps the chosen logging level. Loading or reopening a game restores the XML `DiagnosticsLevel` default, so check the level after loading. To enable logging during normal play without displaying a button, set that XML default to 1 or 2 before loading. Developer console equivalents are `Game.SetStackingDiagnosticsLevel(0)`, `(1)` or `(2)`, `Game.GetStackingDiagnosticsLevel()` and `Game.GetStackingDiagnosticsStatus()`.

## Editing the rules

Edit these source files, then stage/deploy and restart Civ V into a fresh test game:

- `(1) Community Patch/Database Changes/StackingConfig.xml`: capacity, technology rows, combat roles, collateral, city protection, AI preferences and UI layout.
- `(2) Vox Populi/Database Changes/StackingVPConfig.xml`: VP's siege attack-strength penalty against land units.

No DLL rebuild is needed for those XML changes. The default base capacity plus technology bonuses totals nine; changing only `MaximumCapacity` to ten does not grant an additional slot. Change the base or a technology bonus as well when configuring ten combat units.

The detailed reference describes role precedence, permitted values, special unit exclusions and rounding. The local native build/deployment workflow is documented in `work/BUILD-LOCAL.md`. Fully restart after changing UI Lua/XML; the full UI reload event is not a reliable VP/EUI testing shortcut in this installation.

## Observer notification cleanup

The VP EUI panel automatically dismisses ordinary observer/autoplay notifications after three game turns, using their original creation turn even after a reload. Newer messages in a notification bundle remain visible. Normal-play notifications and native mandatory-choice protections are preserved. Set `UIObserverNotificationLifetimeTurns` in `StackingConfig.xml` to another turn count, or 0 to disable. This UI change requires restarting the game; it does not require a new DLL.
