# Civ5StackMod

A fork of [Vox Populi](https://github.com/LoneGazebo/Community-Patch-DLL) for Civilization V that replaces one-unit-per-tile with **limited unit stacking**, and teaches the AI to fight with stacks. The current base is **VP 5.4.6** plus later upstream changes; development is on `master`. Upstream history, credits and licensing are preserved.

## Summary

- Several combat units can share a tile: two at the start, more with military technologies.
- A stack is not a single super-unit. The defender is chosen per attack, cavalry can reach the weak units behind the front line, and siege damages the whole stack. Large stacks are strong against melee and vulnerable to artillery.
- Cities no longer shoot. They are defended by the ranged units stacked inside them, and fortifications shield those units from siege.
- The AI builds, moves and attacks with stacks: it garrisons cities by role, gathers assault waves with real siege, bombards before storming, reinforces its best objectives and tries to retake lost cities.
- Everything is configurable in XML without rebuilding the DLL; see the [list of all XML options](docs/stacking-xml-options.md).
- AI turn times are similar to plain VP: in one 250-turn autoplay benchmark the mod took 6.1 s per turn against 6.5 s for VP.

This is an early pre-release. Multiplayer, the 43-civ variant and the no-EUI variant are untested.

## Install

Download the package from the [Releases page](https://github.com/ruskyandrei/Civ5StackMod/releases), extract it and run `Install.cmd`. It is a complete modified copy of Vox Populi (EUI version) and replaces a normal VP installation; existing files are moved to a backup folder. Requires Civilization V with both expansions on Windows. Start a new game with (1) Community Patch, (2) Vox Populi, (3a) VP - EUI Compatibility Files and (4a) Squads for VP enabled.

## How it works

### Stack capacity

Combat units share a tile up to their owner's capacity, counted separately for land and sea. Civilians, support units and aircraft keep their VP rules.

| Unlock | Capacity |
|---|---:|
| Start | 2 |
| Iron Working | 3 |
| Gunpowder | 4 |
| Military Science | 5 |
| Robotics | 6 |

### Combat

| Mechanic | Rule |
|---|---|
| Defender selection | For each attack, the stack member with the best expected outcome defends. A wounded melee unit yields to a healthier one. |
| Flanking | Mounted and armored melee units bypass the defender and hit archers and siege in the stack, unless an anti-cavalry unit (spear, pike, tercio, rifle, or Formation and Anti-Tank promotions) intercepts. |
| Collateral damage | Siege units, ranged ships firing at land, and bombers also hit other units in the stack: 20% of the primary hit, on 2 to 5 extra units depending on the weapon. Collateral cannot take a unit below 50% health. |
| Siege against units | Siege keeps a 33% attack penalty against land units, so it softens stacks rather than destroying them. |

### Cities

- Cities have no ranged attack of their own; the ranged units inside provide the defensive fire.
- Walls, Castle, Arsenal, Military Base and Bomb Shelter reduce collateral damage to units in the city (10% to 30% each, up to 90% combined). The protection shrinks as the city loses health.
- A finished unit with no free stacking space waits in the production queue, with a notification, until a slot opens.

### Interface

- A stack roster lists the units on a tile with a colour-coded health bar, movement and role. Hovering another player's stack shows its roster beside yours.
- **Move Stack** sends a whole stack to a destination; units that cannot arrive this turn keep going on later turns. While choosing, tiles every unit can reach this turn are green, tiles only some can reach are yellow, and the tile under the cursor turns gray when the stack can only get there in later turns or red when it cannot go there.
- Holding **Alt** with a stacked unit selected shows the same preview under the cursor, and Alt + right-click gives the same order. The key is set by `UIStackMoveModifier`.
- Map flags collapse into a count badge on crowded tiles, and the combat preview shows the chosen defender and collateral victims.

## High-level changes to the AI

| Area | Change |
|---|---|
| Tactical combat | Simulates stack defenders, flanking and collateral when choosing moves; keeps protector and ranged pairs together and spreads out under artillery threat. |
| City defence | Assigns a garrison plus ranged defenders by role, sized to the visible threat; releases surplus units from safe rear cities. |
| War opening | Declares a city-attack war only once the army is staged near the target. |
| Assaults | Gathers a coherent wave with the required siege, stages it out of danger, bombards while gathering and reserves a unit for the capture. |
| Objectives | Sends reinforcements and production to its two most promising city objectives per domain, and keeps a recently lost city as a recapture target. |
| Idle fire | Ranged and siege units that would otherwise stand idle fire at a target in range at the end of the turn. |
| Performance | Caches exact combat-strength and danger forecasts inside each tactical search, with bounded per-turn path budgets. |
| Fixes | Corrects several VP tactical-AI and crash bugs found along the way, including a city-capture crash. |

Optional native diagnostics log AI decisions, combat and timing; they are off by default.

## Documentation

- [Playing guide](docs/stacking-playing.md)
- [All XML options](docs/stacking-xml-options.md) and the [detailed configuration reference](docs/stacking-configuration.md)
- [Offensive AI design](docs/decisive-wars-implementation.md) and the [military AI plan](docs/military-ai-plan.md)
- [Building and deploying](work/BUILD-LOCAL.md). The scripts contain paths from the development PC; adjust them before use elsewhere.
- [Repository maintenance](docs/repository-workflow.md), including merging new VP releases

Report stacking-specific issues in [this fork](https://github.com/ruskyandrei/Civ5StackMod/issues), with the release version and reproduction details.

The following sections describe the upstream project. Their release links lead to ordinary VP, not this mod.

## What is Vox Populi

Started in 2014, Vox Populi (formerly known as the "Community Balance Patch/Overhaul") is a collaborative effort to improve Civilization V's AI and gameplay. It consists of a collection of mods (see below) that are designed to work together seamlessly.

* The Community Patch (CP) is the base mod
	* Contains the gamecore DLL, which is based on C++ code linked against the official Civ V SDK
    * Contains bugfixes (also for multiplayer), performance improvements and many AI enhancements, but minimal gameplay changes
    * Can be used standalone and is the basis for many other mods
* Vox Populi
	* Expands and changes the core mechanics of the game, offering an entirely new Civilization V experience that feels and plays like an evolution of the series
	* Includes City-State Diplomacy by Gazebo, Civ 4 Diplomacy Features by Putmalk and More Luxuries by Barathor
* EUI (optional)
	* Enhanced User Interface

## Where can I learn more

Check out the [forum](https://forums.civfanatics.com/forums/community-patch-project.497/). 

## How can I play this

* You need the latest version of Civilization V (1.0.3.279) with all expansions and DLC.
* [This thread](https://forums.civfanatics.com/threads/community-patch-how-to-install.528034/) on CivFanatics contains a link to the latest release, along with installation instructions.
* You may also download the automatic installer for your desired version from the [Releases page](https://github.com/LoneGazebo/Community-Patch-DLL/releases).

## Development and debugging

See `DEVELOPMENT.md` file for more information.
