"""Bounded T230 battery smoke plus explicitly isolated pre-AI capture fixture.

Use only the disposable Stack-AI-T230 save with guards/service already ready.
The ordinary behavior harness never installs this fixture. This wrapper archives
its Lua and response immediately before continuing, creates one unit/weakens one
city in memory at Egypt's pre-AI update, and lets the AI choose orders normally.
No source save or existing unit is changed by the setup. Subsequent reload of the
unchanged source discards the fixture; engine autosaves must be backed up first.
"""
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('behavior_smoke',ROOT/'work/run-behavior-replay.py')
behavior=importlib.util.module_from_spec(spec)
spec.loader.exec_module(behavior)
Original=behavior.BehaviorReplay

class FixtureReplay(Original):
    def call(self,context,source,label,timeout=None):
        if label=='continue-bounded-behavior':
            if self.args.start_turn!=230 or self.args.stop_turn!=232:
                raise ValueError('This isolated fixture requires T230 to T232')
            setup=(ROOT/'work/ai-followup-capture-fixture.lua').read_text(encoding='utf-8')
            super().call('InGame',setup,'isolated-pre-ai-capture-setup',timeout)
        return super().call(context,source,label,timeout)

behavior.BehaviorReplay=FixtureReplay
if __name__=='__main__':
    raise SystemExit(behavior.main())
