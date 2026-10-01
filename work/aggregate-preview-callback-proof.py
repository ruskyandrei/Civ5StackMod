"""Read archived PLAN_PERF callback proof counters; never connect to the game.

Counters reset per search. Scans, bypasses and suspensions are summed; capability
flags are bitwise ORed. Scans count attempts, so flags=0 alone is not a completed
proof. Existing hit counters provide evidence that reuse was actually admitted.
This report cannot attribute time to Context checks or scans without a profiler.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

RECORD = re.compile(r'^STACKDIAG\|(\d+)\|turn=(-?\d+)\|player=(-?\d+)\|PLAN_PERF\|(.*)$')
FIELD = re.compile(r'(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=([^\s;]+)')
PROOF = ('callbackProofScans', 'callbackProofFlags', 'callbackValidationBypasses', 'callbackSuspensions')
HITS = ('dangerHits', 'defenderHits', 'meleeStrengthHits', 'rangedStrengthHits', 'attackStrengthHits', 'defenseStrengthHits')
MISSES = ('dangerMisses', 'defenderMisses', 'meleeStrengthMisses', 'rangedStrengthMisses', 'attackStrengthMisses', 'defenseStrengthMisses')
TIMES = ('setupMs', 'searchMs', 'finalizeMs', 'yieldMs')


def uint(fields, name):
    value = fields.get(name)
    if value is None or not re.fullmatch(r'\d+', value):
        raise ValueError('missing or malformed unsigned PLAN_PERF field: ' + name)
    return int(value)


def records(folder):
    manifest = json.loads((folder / 'replay-manifest.json').read_text(encoding='utf-8-sig'))
    run = manifest.get('NativeRun')
    if not isinstance(run, str) or not re.fullmatch(r'[\w-]+', run):
        raise ValueError('manifest NativeRun is missing/invalid')
    paths = sorted((folder / 'native-segments').glob(run + '-segment-*.log'))
    if not paths:
        raise ValueError('no canonical native segment archives')
    output, ignored_partial = [], 0
    for path in paths:
        data = path.read_text(encoding='utf-8-sig')
        lines = data.splitlines()
        segment_text = path.stem[len(run + '-segment-'):]
        if not segment_text.isdigit():
            raise ValueError('invalid native segment filename')
        segment = int(segment_text)
        if not lines or not lines[0].startswith('STACKDIAG|SESSION|'):
            raise ValueError('native segment header is missing')
        header = dict(FIELD.findall(lines[0].split('|SESSION|', 1)[1]))
        if header.get('run') != run or header.get('segment') != str(segment):
            raise ValueError('native segment identity mismatch')
        if lines and not data.endswith('\n'):
            lines.pop()
            ignored_partial += 1
        for line_number, line in enumerate(lines[1:], 2):
            match = RECORD.fullmatch(line)
            if not match:
                continue
            tick, turn, player, payload = match.groups()
            pairs = FIELD.findall(payload)
            fields = dict(pairs)
            if len(fields) != len(pairs):
                raise ValueError('duplicate PLAN_PERF field')
            target = fields.get('target')
            if target is None or not re.fullmatch(r'-?\d+:-?\d+', target):
                raise ValueError('missing/malformed PLAN_PERF target')
            row = dict(turn=int(turn), player=int(player), target=target,
                       tick=int(tick), segment=segment, line=line_number)
            present = [name in fields for name in PROOF]
            if any(present) and not all(present):
                raise ValueError('partially recorded callback proof fields')
            row['proofRecorded'] = all(present)
            for name in PROOF + HITS + MISSES + TIMES:
                if name in fields:
                    row[name] = uint(fields, name)
            if not row['proofRecorded']:
                row['observation'] = 'fields_unavailable'
            elif row['callbackProofFlags']:
                row['observation'] = 'unsupported_capability_observed'
            elif not row['callbackProofScans']:
                row['observation'] = 'unknown_no_scan'
            else:
                row['observation'] = 'zero_capability_flags_observed'
            row['admittedReuseHits'] = sum(row.get(name, 0) for name in HITS)
            row['reuseObserved'] = row['admittedReuseHits'] > 0
            output.append(row)
    return manifest, output, ignored_partial


def aggregate(rows):
    result = dict(searches=len(rows), proofRecordedSearches=0, unavailableSearches=0,
                  unknownNoScanSearches=0, zeroCapabilityFlagsSearches=0,
                  unsupportedCapabilitySearches=0, reuseObservedSearches=0,
                  callbackProofScans=0, callbackProofFlags=0,
                  callbackValidationBypasses=0, callbackSuspensions=0,
                  searchesWithValidationBypass=0, searchesWithSuspension=0)
    for name in HITS + MISSES + TIMES:
        result[name] = 0
    for row in rows:
        result['reuseObservedSearches'] += int(row['reuseObserved'])
        for name in HITS + MISSES + TIMES:
            result[name] += row.get(name, 0)
        if not row['proofRecorded']:
            result['unavailableSearches'] += 1
            continue
        result['proofRecordedSearches'] += 1
        for name in ('callbackProofScans', 'callbackValidationBypasses', 'callbackSuspensions'):
            result[name] += row[name]
        result['callbackProofFlags'] |= row['callbackProofFlags']
        result['searchesWithValidationBypass'] += int(row['callbackValidationBypasses'] > 0)
        result['searchesWithSuspension'] += int(row['callbackSuspensions'] > 0)
        category = row['observation']
        result[{'unknown_no_scan': 'unknownNoScanSearches',
                'zero_capability_flags_observed': 'zeroCapabilityFlagsSearches',
                'unsupported_capability_observed': 'unsupportedCapabilitySearches'}[category]] += 1
    return result


def grouped(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return [dict(zip(keys, identity), **aggregate(items))
            for identity, items in sorted(groups.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='Write a new derived JSON file; never overwrite')
    args = parser.parse_args()
    manifest, rows, partial = records(args.run_dir.resolve())
    report = dict(nativeRun=manifest['NativeRun'], manifestStatus=manifest.get('Status'),
                  archivedReplayCompleted=str(manifest.get('Status', '')).startswith('completed'),
                  ignoredUnterminatedSegmentLines=partial, totals=aggregate(rows),
                  byTurn=grouped(rows, ('turn',)), byPlayer=grouped(rows, ('player',)),
                  byTurnPlayer=grouped(rows, ('turn', 'player')),
                  byTurnPlayerTarget=grouped(rows, ('turn', 'player', 'target')),
                  searches=rows,
                  limits=['Counters reset per search; flags are ORed, never summed.',
                          'Scans count attempts; zero flags with no scans is unknown.',
                          'Hit counters prove admitted reuse occurred, not support throughout every search.',
                          'Suspension and validation failures may occur after an earlier supported segment.',
                          'PLAN phase times include nested work/yields; they do not measure proof-check overhead.',
                          'Canonical segments only: legacy duplicate -00.log archives are not read.'])
    text = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    print(json.dumps(dict(nativeRun=report['nativeRun'], completed=report['archivedReplayCompleted'],
                          totals=report['totals'], byTurn=report['byTurn']), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
