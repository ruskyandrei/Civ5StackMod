"""Compose one existing diagnostic phase onto the verified DLL93 source."""
from pathlib import Path
import argparse, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e38b19798'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
changes = []
for relative in ('CvGameCoreDLL_Expansion2/CvTacticalAI.cpp', 'work/profile-turn-phases.py'):
    old = subprocess.check_output(['git', 'show', BASE + ':' + relative], cwd=ROOT).decode('utf-8-sig').replace('\r\n', '\n')
    path = ROOT / relative
    raw = path.read_bytes()
    assert raw.decode('utf-8-sig').replace('\r\n', '\n') == old, relative
    if relative.endswith('.cpp'):
        anchor = 'void TacticalAIHelpers::UpdatePlotDistanceToTarget(PlayerTypes ePlayer, CvPlot* pTargetPlot)\n{\n'
        assert old.count(anchor) == 1
        addition = '\tCvStackingDiagnostics::TurnPhaseScope phase(ePlayer,"target_distance_fields"); // TARGET_DISTANCE_FIELD_TIMING_DIAGNOSTIC_ONLY\n'
        new = old.replace(anchor, anchor + addition)
        assert new.replace(addition, '') == old
    else:
        anchor = '("immediate_city_opportunities", "stacking_offensive_moves")'
        addition = '("immediate_city_opportunities", "stacking_offensive_moves", "target_distance_fields")'
        assert old.count(anchor) == 1
        new = old.replace(anchor, addition)
        assert new.replace(addition, anchor) == old
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    newline = '\r\n' if b'\r\n' in raw else '\n'
    changes.append((path, bom + new.replace('\n', newline).encode(), old, new))
proof = {'baseline': BASE, 'applied': args.apply, 'whole_reverse_exact': True,
         'scope': 'One diagnostic phase only; original floods and field copies unchanged.',
         'files': {str(path.relative_to(ROOT)): {'control_sha256': hashlib.sha256(old.encode()).hexdigest(),
                                               'candidate_sha256': hashlib.sha256(new.encode()).hexdigest()}
                   for path, _, old, new in changes}}
if args.apply:
    for path, data, _, _ in changes:
        path.write_bytes(data)
(ROOT / 'work/target-distance-field/production-timing-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof))
