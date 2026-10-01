"""Compare retained per-search native PLAN_PERF counters, without sampling scaling.

Missing counters are unknown, including packet counters in historical controls.
Canonical segment loading deduplicates copies. Target groups use stable player
and plot identity when a verified map width is supplied; they are aggregates,
not assertions that individual searches or their inputs are identical.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('wall_profile', Path(__file__).with_name('profile-turn-phases.py'))
wall = importlib.util.module_from_spec(spec); spec.loader.exec_module(wall)
COUNTERS = ('dangerHits', 'dangerMisses', 'dangerEvictions', 'outcomeBuilds',
            'outcomeReuses', 'outcomeBypasses', 'packetHits', 'packetBuilds', 'packetBypasses')
TIMINGS = ('setupMs', 'searchMs', 'finalizeMs', 'yieldMs')
PEAKS = ('entries', 'payloadBytes', 'outcomeRetainedBytes', 'outcomePeakRetainedBytes')
METRICS = COUNTERS + TIMINGS + PEAKS
MAX_U32 = (1 << 32) - 1
NOTES = [
    'Counters are actual retained PLAN_PERF observations; no diagnostic-stride scaling or saved-time extrapolation is applied.',
    'Missing counters are unknown, not zero. A complete aggregate is present only when every retained valid row supplies that counter.',
    'Search counters reset per search and are summed. Entries/payload snapshot and per-search peaks are compared with maxima, not sums.',
    'searchMs includes yields and overlaps the PLAN timer; setup/search/finalize fields are not independent total-turn measurements.',
    'Player/target aggregates match stable locations, not exact search states or a one-to-one pairing of individual searches.',
    'outcomeBuilds is version-dependent: before79 it counts local-batch builds;79 also increments it for direct shared-packet builds. packetBuilds is the subset of direct packet builds without a supplying local batch. Do not add these overlapping build fields or interpret their raw delta as local-only work saved.',
    'outcomeReuses retains the existing local-batch reuse field; packetHits is the separate shared-result lookup field.',
    'Even queried scalar entries are admitted after a packet hit/build; changes in shared-table pressure can change hits, misses and evictions.',
    'Dropped rows, incomplete archives or invalid rows can censor counters. A lower miss count alone does not establish equivalent gameplay or faster turns.',
]

def load(directory, run):
    records, quality = wall.load(directory, run)
    if not quality['headers']:
        raise ValueError('No native segments for exact run: ' + run)
    messages = {}
    for header in quality['headers']:
        path = Path(header['path'])
        with path.open(encoding='utf-8-sig', errors='replace') as stream:
            for number, line in enumerate(stream, 1):
                if '|PLAN_PERF|' in line:
                    messages[f'{path.name}:{number}'] = line
    for record in records:
        if record['category'] == 'PLAN_PERF':
            record['raw_message'] = messages.get(record['origin'], '')
    return records, quality

def decode(record, map_width=None):
    values = record['values']; errors = []
    target = values.get('target')
    match = re.fullmatch(r'(\d+):(\d+)', target) if isinstance(target, str) else None
    if not match:
        errors.append('missing_or_invalid_target')
    coordinates = tuple(map(int, match.groups())) if match else None
    if map_width and coordinates and coordinates[0] >= map_width:
        errors.append('target_x_outside_verified_width')
    message = record.get('raw_message', '')
    wire = wall.RECORD.fullmatch(message.rstrip('\r\n'))
    raw_pairs = wall.FIELD.findall(wire.group(5) if wire else message)
    duplicates = [k for k, count in Counter(k for k, v in raw_pairs).items()
                  if count > 1 and k in METRICS + ('target',)]
    if duplicates:
        errors.append('duplicate_fields:' + ','.join(sorted(duplicates)))
    if '[message truncated]' in message:
        errors.append('explicit_message_truncation')
    for key in METRICS:
        if key in values and (type(values[key]) is not int or not 0 <= values[key] <= MAX_U32):
            errors.append(key + ':invalid_native_unsigned_integer')
    if errors:
        return None, errors
    return dict(turn=record['turn'], player=record['player'], target=target,
                target_coordinates=list(coordinates),
                targetPlot=coordinates[1] * map_width + coordinates[0] if map_width else None,
                origin=record.get('origin'), metrics={k: values.get(k) for k in METRICS}), []

def aggregate(rows):
    result = dict(retained_valid_PLAN_PERF_rows=len(rows), counters={}, timings_ms={}, maxima={})
    for keys, name, reducer in ((COUNTERS, 'counters', sum), (TIMINGS, 'timings_ms', sum), (PEAKS, 'maxima', max)):
        for key in keys:
            known = [r['metrics'][key] for r in rows if r['metrics'][key] is not None]
            value = reducer(known) if known else None
            result[name][key] = dict(known_rows=len(known), missing_rows=len(rows)-len(known),
                                    observed_known=value,
                                    complete=value if rows and len(known) == len(rows) else None)
    return result

def analyze(records, quality=None, turns=None, map_width=None):
    quality = quality or {}; rows = []; invalid = []; selected = lambda r: turns is None or r['turn'] in turns
    for record in records:
        if record['category'] != 'PLAN_PERF' or not selected(record):
            continue
        row, errors = decode(record, map_width)
        if errors:
            invalid.append(dict(turn=record['turn'], player=record['player'], origin=record.get('origin'), errors=errors))
        else:
            rows.append(row)
    by_turn = defaultdict(list); by_target = defaultdict(list)
    for row in rows:
        by_turn[row['turn']].append(row)
        by_target[(row['turn'], row['player'], row['target'])].append(row)
    requested = sorted(turns) if turns is not None else sorted(by_turn)
    drops = [dict(turn=r['turn'], player=r['player'], origin=r.get('origin'), category=r['category'], fields=r['values'])
             for r in records if selected(r) and r['category'] in ('TRUNCATED', 'DIAGNOSTIC_COST')]
    warnings = []
    if not rows: warnings.append('No valid retained PLAN_PERF rows: work counters are unknown.')
    if invalid: warnings.append('Invalid PLAN_PERF rows were excluded; totals are incomplete.')
    if quality.get('conflicting_segment_files'): warnings.append('Conflicting segment copies: archive coverage is uncertain.')
    if quality.get('gaps') or quality.get('earlier_segments_missing') or quality.get('incomplete_tails_skipped'):
        warnings.append('Archive is partial; only complete retained records are counted.')
    if quality.get('malformed_records'): warnings.append('Malformed native records were skipped by the canonical loader.')
    if any(r['category'] == 'TRUNCATED' or r['fields'].get('dropped', 0) for r in drops):
        warnings.append('Diagnostic row drops are reported; absent counters can be censored.')
    return dict(archive_quality=quality, warnings=warnings, diagnostic_drop_rows=drops,
                invalid_row_count=len(invalid), invalid_rows=invalid,
                whole_selection=aggregate(rows),
                turns=[dict(turn=t, **aggregate(by_turn[t])) for t in requested],
                turn_player_targets=[dict(turn=k[0], player=k[1], target=k[2],
                    targetPlot=v[0]['targetPlot'], target_coordinates=v[0]['target_coordinates'], **aggregate(v))
                    for k, v in sorted(by_target.items())], plans=rows)

def pair(left, right):
    output = dict(baseline=left, candidate=right, deltas={})
    for group in ('counters', 'timings_ms', 'maxima'):
        output['deltas'][group] = {}
        for key in (left or right or {}).get(group, {}):
            a = left[group][key]['complete'] if left else None
            b = right[group][key]['complete'] if right else None
            output['deltas'][group][key] = b-a if a is not None and b is not None else None
    return output

def compare(left, right, map_width=None):
    by_turn = lambda data: {r['turn']: r for r in data['turns']}
    by_target = lambda data: {(r['turn'], r['player'], r['target']): r for r in data['turn_player_targets']}
    a, b = by_turn(left), by_turn(right); x, y = by_target(left), by_target(right)
    return dict(measurement_notes=NOTES, map_width=map_width,
                target_identity='verified-width plot/player aggregate' if map_width else 'coordinate/player aggregate; plot identity unverified',
                baseline=left, candidate=right,
                whole_selection=pair(left['whole_selection'], right['whole_selection']),
                turns=[dict(turn=t, **pair(a.get(t), b.get(t))) for t in sorted(a.keys() | b.keys())],
                turn_player_targets=[dict(turn=k[0], player=k[1], target=k[2],
                    targetPlot=(x.get(k) or y[k])['targetPlot'], **pair(x.get(k), y.get(k)))
                    for k in sorted(x.keys() | y.keys())])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline_directory', type=Path); parser.add_argument('candidate_directory', type=Path)
    parser.add_argument('--baseline-run', required=True); parser.add_argument('--candidate-run', required=True)
    parser.add_argument('--turn', type=int, action='append'); parser.add_argument('--map-width', type=int)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    if options.map_width is not None and options.map_width <= 0: parser.error('map-width must be positive and verified, never inferred.')
    if options.output.suffix.lower() != '.json': parser.error('output must be a JSON report.')
    inputs = list(options.baseline_directory.glob('*.log')) + list(options.candidate_directory.glob('*.log'))
    if any(options.output.resolve() == path.resolve() or
           (options.output.exists() and options.output.samefile(path)) for path in inputs):
        parser.error('output must not replace a native input log, including an alias.')
    try:
        a, aq = load(options.baseline_directory, options.baseline_run)
        b, bq = load(options.candidate_directory, options.candidate_run)
        left = analyze(a, aq, options.turn, options.map_width); right = analyze(b, bq, options.turn, options.map_width)
    except ValueError as error:
        parser.error(str(error))
    report = compare(left, right, options.map_width)
    report.update(baseline_run=options.baseline_run, candidate_run=options.candidate_run,
                  selected_turns=options.turn, schema='native_PLAN_PERF_cache_comparison_v1')
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(baseline_rows=left['whole_selection']['retained_valid_PLAN_PERF_rows'],
                         candidate_rows=right['whole_selection']['retained_valid_PLAN_PERF_rows'],
                         invalid_rows=left['invalid_row_count']+right['invalid_row_count'], output=str(options.output))))
    return 2 if left['invalid_row_count'] or right['invalid_row_count'] else 0

if __name__ == '__main__': raise SystemExit(main())
