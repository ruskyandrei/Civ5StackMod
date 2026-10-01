"""Apply a staged observer after qualifying all thirteen control files."""
from pathlib import Path
import argparse
import hashlib
import json

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stage-directory', type=Path, required=True)
args = parser.parse_args()
stage = args.stage_directory.resolve()
manifest = json.loads((stage / 'manifest.json').read_text())
core = root / 'CvGameCoreDLL_Expansion2'
for name, expected in manifest['original_whole_files_sha256'].items():
    text = (core / name).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(text.encode()).hexdigest() == expected, name
prepared = []
for name, expected in (('CvTacticalAI.cpp', manifest['candidate_sha256']),
                       ('CvStackingDiagnostics.cpp', manifest['diagnostics_candidate_sha256'])):
    target = core / name
    raw = target.read_bytes()
    candidate = (stage / name).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(candidate.encode()).hexdigest() == expected, name
    newline = '\r\n' if b'\r\n' in raw else '\n'
    encoded = candidate.replace('\n', newline).encode('utf-8')
    if raw.startswith(b'\xef\xbb\xbf'):
        encoded = b'\xef\xbb\xbf' + encoded
    prepared.append((target, encoded))
for target, encoded in prepared:
    target.write_bytes(encoded)
print('Applied observer to two files after thirteen whole-file checks; BOM/newlines preserved.')
