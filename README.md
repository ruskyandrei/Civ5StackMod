# Community-Patch-DLL

This is the repository for the Civ V SDK + Vox Populi Mod. 

## Local stacking prototype

This checkout contains a unit-stacking prototype based on Vox Populi 5.4.6, on branch `b-stack-prototype`. It adds XML-configurable capacity and combat rules, AI stack forecasts/preferences, a stack roster and group movement. Release20260927-093917 (`Release-5.4.6-6-gb7731f6 Clean`) is built and deployment-verified on this PC. Its native diagnostics controls and an actual combat trace work in game; a fresh-process Off/Verbose comparison matched all captured fields for 60 units and 30 cities after one autoplay turn. The bounded late-game replay is still pending. Earlier focused runtime evidence retains its original build provenance.

Start with the [playing guide](docs/stacking-playing.md), [XML configuration reference](docs/stacking-configuration.md), [native build/deployment guide](work/BUILD-LOCAL.md), and [test coverage and remaining limitations](work/REQUIREMENTS-AUDIT-20260927.md). Local saves, test evidence, backups, toolchains and compiled binaries remain under `work` outside Git. The upstream project description follows.

Built-in autoplay diagnostics, the latest AI refinements and their completed offline checks are tracked alongside remaining runtime work in [the stacking TODO](docs/stacking-todo.md). The [Turn 245 crash investigation](work/CRASH-245-20260927.md) confirms an allocation failure; its underlying long-history/memory-growth cause and crash prevention remain unproved.

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
