# Civ5StackMod

An experimental unit-stacking and AI development fork of [Vox Populi](https://github.com/LoneGazebo/Community-Patch-DLL) for Civilization V. The current base is **VP 5.4.6**, and development is on `b-stack-prototype`. Upstream history, credits and licensing are preserved.

## Stacking prototype

The prototype adds XML-configurable stack capacity and technology progression, best-defender selection, cavalry flanking and anti-cavalry protection, limited collateral damage, city fortification protection, stack-aware AI, a stack roster, group movement and optional native diagnostics. A first military-allocation pass also addresses garrison retention, rear reserves, recruitment and assembly; further offensive coordination remains planned. Long-campaign stability and broad AI quality are still being tested.

This repository currently shares **development source, not a packaged stacking release**. DLLs and other binaries inherited from upstream are not newly built stacking downloads. The tested installation uses VP with EUI and the standard civilization limit. The build/deployment scripts document the original development PC and contain machine-specific paths; review and configure them before use on another PC.

Start with the [playing guide](docs/stacking-playing.md), [XML configuration reference](docs/stacking-configuration.md), [native build/deployment guide](work/BUILD-LOCAL.md), and [test coverage and remaining limitations](work/REQUIREMENTS-AUDIT-20260927.md). The [stacking TODO](docs/stacking-todo.md) and [military AI plan](docs/military-ai-plan.md) distinguish implemented work from proposed changes. [Military allocation validation](work/MILITARY-AI-IMPLEMENTATION.md) records the later build checkpoint; the [Turn 245 crash investigation](work/CRASH-245-20260927.md) preserves the earlier repairs and bounded replay evidence.

See [repository maintenance](docs/repository-workflow.md) for saving changes and merging future VP releases. Reviewed development scripts, fixtures and notes are tracked under `work`; local compiler downloads, build outputs, backups, saves and raw test evidence are excluded. Report stacking-specific issues in [this fork](https://github.com/ruskyandrei/Civ5StackMod/issues), with the build version and reproduction details.

The following sections describe the upstream project. Their release links lead to ordinary VP, not this stacking prototype.

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
