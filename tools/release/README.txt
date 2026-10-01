Civ V Stack Mod @VERSION@
==========================

Vox Populi with limited unit stacking: several combat units per tile, stack
defender selection, cavalry flanking, collateral damage from siege and
bombardment, and an AI that plans and fights with stacks.

This package is a complete, modified copy of Vox Populi (EUI version), built
from https://github.com/ruskyandrei/Civ5StackMod at commit @COMMIT@.
It is based on Vox Populi 5.4.6 plus the upstream changes up to @UPSTREAM@.
It replaces a normal Vox Populi installation; you cannot have both at once.

Requirements
------------
- Civilization V with both expansions (Gods & Kings, Brave New World), Windows.
- No other copy of Vox Populi or EUI installed. The installer moves existing
  ones to a backup folder.
- The "43 Civs" variant and the no-EUI variant are not supported.

Install (automatic)
-------------------
1. Extract the whole zip to any folder.
2. Close Civilization V.
3. Double-click Install.cmd.
   If Civ V is installed under Program Files, right-click Install.cmd and
   choose "Run as administrator".
4. Start Civ V, open MODS, enable these four mods and click Next:
     (1) Community Patch
     (2) Vox Populi
     (3a) VP - EUI Compatibility Files
     (4a) Squads for VP
   Then choose Single Player and set up a game as usual.

The installer finds your user data folder and your Steam game folder. If it
cannot, it tells you which option to pass, for example:
  Install.cmd -GameDirectory "D:\Games\Sid Meier's Civilization V"
"Install.cmd -DryRun" shows what would be done without changing anything.

Install (manual)
----------------
1. Close Civilization V.
2. In Documents\My Games\Sid Meier's Civilization 5\MODS, remove any existing
   folders named "(1) Community Patch", "(2) Vox Populi", "(3a) VP - EUI
   Compatibility Files", "(3b) 43 Civs Community Patch", "(4a) Squads for VP"
   and "(5) Modpack Maker for VP". Also delete the "cache" folder next to MODS.
3. In the game folder (Steam: right-click the game, Manage, Browse local
   files), remove Assets\DLC\UI_bc1 and Assets\DLC\VPUI if they exist.
4. Copy the contents of this package's "UserData" folder into
   Documents\My Games\Sid Meier's Civilization 5.
5. Copy the contents of this package's "Game" folder into the game folder,
   replacing files when asked.
6. Enable the four mods as described above.

Uninstall
---------
Delete the folders listed in manual steps 2 and 3. To get plain Civ V back,
also let Steam verify the game files (this restores Expansion2.Civ5Pkg). To go
back to normal Vox Populi, run its official installer. The installer's backup
folder (StackMod-backup-... in your Civ V user data folder) holds everything it
replaced.

Notes
-----
- Start a new game. Saves from normal Vox Populi may load, but continuing
  them is untested.
- How stacking plays and how to configure it: see the Docs folder.
- All players in a multiplayer game need this exact package.
- Rules and AI behaviour are configured in
  MODS\(1) Community Patch\Database Changes\StackingConfig.xml.
  Restart the game after editing it and start a new game.
- Game and AI logging is not changed by the installer.

Licence
-------
Vox Populi and this mod are distributed under the terms in License.rtf.
Source code: https://github.com/ruskyandrei/Civ5StackMod
Vox Populi: https://github.com/LoneGazebo/Community-Patch-DLL
