"""Compare retained ordered PLAN_PERF counters without connecting to Civ V."""
from pathlib import Path
import argparse, importlib.util, json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('baseline', type=Path)
parser.add_argument('candidate', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('forecast_reader', Path(__file__).with_name('aggregate-preview-callback-proof.py'))
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
rows = []
for folder in (args.baseline, args.candidate):
    manifest, validated, partial = reader.records(folder)
    assert partial == 0 and manifest['Status'] == 'completed_game_closed_service_stopped'
    full = []
    for path in sorted((folder / 'native-segments').glob(manifest['NativeRun'] + '-segment-*.log')):
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            found = reader.RECORD.fullmatch(line)
            if found:
                _, turn, player, payload = found.groups()
                fields = dict(reader.FIELD.findall(payload))
                full.append(((int(turn), int(player), fields['target']), fields))
    assert len(full) == len(validated) and full
    rows.append(full)
assert len(rows[0]) == len(rows[1])
omit = {'target', 'setupMs', 'searchMs', 'finalizeMs', 'yieldMs', 'yields', 'forecastEstimatedBytes'}
differences, memory, added, removed, checked = [], [], {}, {}, None
for i, ((identity, old), (other, new)) in enumerate(zip(*rows)):
    assert identity == other
    keys = sorted((set(old) & set(new)) - omit)
    assert set(reader.PROOF + reader.HITS + reader.MISSES) <= set(keys)
    if checked is None:
        checked = keys
    assert keys == checked
    changes = {key: [old[key], new[key]] for key in keys if old[key] != new[key]}
    if changes:
        differences.append({'row': i, 'identity': identity, 'differences': changes})
    for key in set(new) - set(old):
        added.setdefault(key, []).append(new[key])
    for key in set(old) - set(new):
        removed.setdefault(key, []).append(old[key])
    if old['forecastEstimatedBytes'] != new['forecastEstimatedBytes']:
        memory.append({'row': i, 'identity': identity, 'bytes': [int(old['forecastEstimatedBytes']), int(new['forecastEstimatedBytes'])]})
result = {'rows': len(rows[0]), 'checkedFields': checked, 'fieldCount': len(checked),
          'differences': differences, 'memoryDifferences': memory, 'addedFields': added,
          'removedFields': removed, 'omitted': sorted(omit),
          'limits': 'Exact retained per-search counters only; added/removed fields and physical estimates reported separately. Timing/yield scheduling excluded. Does not compare gameplay or unrecorded cache work.'}
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'rows': result['rows'], 'fields': len(checked), 'differenceRows': len(differences),
                  'memoryDifferenceRows': len(memory), 'added': sorted(added), 'removed': sorted(removed)}))
raise SystemExit(1 if differences or removed else 0)
