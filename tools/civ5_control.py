"""Convenience commands for the persistent Civ V Lua service."""
import argparse
import json
from pathlib import Path

import civ5_tuner as tuner

STATUS = """
return {turn=Game.GetGameTurn(),activePlayer=Game.GetActivePlayer(),
 autoplay=Game.GetAIAutoPlay(),diagnostics=(Game.GetStackingDiagnosticsLevel and Game.GetStackingDiagnosticsLevel() or -1),
 quickCombat=PreGame.GetQuickCombat(),quickMovement=PreGame.GetQuickMovement(),
 multiplayer=PreGame.IsMultiplayerGame()}
"""


def run(args, context, source):
    result = tuner.call_service(args.session, "exec", {
        "context": context, "source": source, "timeout": args.timeout}, args.timeout)
    if not result.get("ok"):
        raise tuner.TunerError(result.get("error", "Lua command failed"))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session", default=str(tuner.DEFAULT_SESSION))
    p.add_argument("--timeout", type=float, default=120)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("prepare-mods")
    load = sub.add_parser("load")
    load.add_argument("save", type=Path)
    sub.add_parser("continue")
    diag = sub.add_parser("diagnostics")
    diag.add_argument("level", type=int, choices=(0, 1, 2))
    autoplay = sub.add_parser("autoplay")
    autoplay.add_argument("turns", type=int)
    autoplay.add_argument("--return-player", type=int, default=0)
    halt = sub.add_parser("halt")
    halt.add_argument("--return-player", type=int, default=0)
    sub.add_parser("quit")
    sub.add_parser("menu")
    args = p.parse_args()
    try:
        if args.command == "status":
            result = run(args, "InGame", STATUS)
        elif args.command == "prepare-mods":
            contexts = tuner.call_service(args.session, "states", {"timeout": args.timeout}, args.timeout)
            if any(c["name"] == "InGame" for c in contexts.get("contexts", [])):
                raise tuner.TunerError("Prepare mods from the main menu, outside a loaded game")
            run(args, "LegalScreen", "UIManager:DequeuePopup(ContextPtr)")
            result = run(args, "ModsBrowser", "assert(#Modding.GetEnabledModsByActivationOrder()>0,'No mods enabled');OnNextButtonClicked();return 'activated'")
        elif args.command == "load":
            save = args.save.resolve(strict=True)
            if save.suffix.lower() != ".civ5save":
                raise tuner.TunerError("Expected a .Civ5Save file")
            path = tuner.lua_string(str(save).replace("\\", "/"))
            source = "local path=" + path + ";assert(PreGame.GetFileHeader(path),'Unreadable save');Events.PlayerChoseToLoadGame(path);return 'requested'"
            result = run(args, "ModsSinglePlayer", source)
        elif args.command == "continue":
            # The VP LoadScreen callback is local; use the exact engine actions
            # in that callback only once its activation button is visible.
            result = run(args, "LoadScreen", "assert(not Controls.ActivateButton:IsHidden(),'Loading is not complete');assert(not PreGame.IsMultiplayerGame(),'Single player only');Events.LoadScreenClose();Game.SetPausePlayer(-1);UI.SetDontShowPopups(false);return 'continued'")
        elif args.command == "diagnostics":
            result = run(args, "InGame", f"assert(Game.SetStackingDiagnosticsLevel and Game.FlushStackingDiagnostics,'Stacking diagnostics APIs are unavailable in this DLL');Game.SetStackingDiagnosticsLevel({args.level});Game.FlushStackingDiagnostics();" + STATUS)
        elif args.command in ("autoplay", "halt"):
            if not 0 <= args.return_player <= 63:
                raise tuner.TunerError("Specify an alive major return player (0–63)")
            source = f"assert(not PreGame.IsMultiplayerGame(),'Single player only');local p=Players[{args.return_player}];assert(p and p:IsAlive() and not p:IsObserver() and not p:IsMinorCiv() and not p:IsBarbarian(),'Return player must be an alive major civilization');"
            if args.command == "halt":
                source += f"if Game.GetAIAutoPlay()==0 and Players[Game.GetActivePlayer()]:IsObserver() then Game.SetAIAutoPlay(1,{args.return_player}) end;Game.SetAIAutoPlay(0,{args.return_player});"
            else:
                if not 1 <= args.turns <= 10000:
                    raise tuner.TunerError("Specify 1–10000 autoplay turns")
                source += f"Game.SetOption('GAMEOPTION_QUICK_COMBAT',true);Game.SetOption('GAMEOPTION_QUICK_MOVEMENT',true);if Game.GetAIAutoPlay()=={args.turns} then Game.SetAIAutoPlay({args.turns+1},{args.return_player}) end;Game.SetAIAutoPlay({args.turns},{args.return_player});"
            result = run(args, "InGame", source + STATUS)
        elif args.command == "menu":
            result = run(args, "InGame", "assert(Game.GetAIAutoPlay()==0,'Stop autoplay before returning to menu');Events.ExitToMainMenu();return 'menu requested'")
        else:
            states = tuner.call_service(args.session, "states", {"timeout": args.timeout}, args.timeout)
            context = "InGame" if any(c["name"] == "InGame" for c in states.get("contexts", [])) else "MainMenu"
            result = run(args, context, "UI.ExitGame();return 'quit requested'")
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (tuner.TunerError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
