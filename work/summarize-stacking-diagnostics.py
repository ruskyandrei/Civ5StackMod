#!/usr/bin/env python3
"""Summarize schema-1 native stacking logs offline; read-only unless --output is supplied."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

SESSION = re.compile(r'^STACKDIAG\|SESSION\|(.+)$')
RECORD = re.compile(r'^STACKDIAG\|(\d+)\|turn=(-?\d+)\|player=(-?\d+)\|([^|]+)\|(.*)$')
FIELD = re.compile(r'(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=([^\s;]+)')
COMBAT_CATEGORIES = ('COMBAT_BEGIN', 'COMBAT_MEMBER', 'COMBAT_AFTER', 'COMBAT_CITY_BEFORE', 'COMBAT_CITY_AFTER', 'COMBAT_END')

def fields(text):
    result = {}
    for key, value in FIELD.findall(text):
        result[key] = int(value) if key not in ('configFNV', 'fnv1a') and re.fullmatch(r'-?\d+', value) else value
    return result

def sorted_counts(value):
    return dict(sorted(value.items(), key=lambda item: str(item[0])))

def discover(directory):
    return sorted({p for pattern in ('Stacking-*.log', 'StackingDiagnostics*.log') for p in directory.glob(pattern) if p.is_file()})

def load_segment(path):
    raw = path.read_bytes()
    lines = raw.decode('utf-8-sig', errors='replace').splitlines()
    first = SESSION.fullmatch(lines[0]) if lines else None
    if not first:
        return None
    header = fields(first[1])
    build = re.search(r'(?:^|\s)build=(.*?)\s+level=', first[1])
    if build: header['build'] = build[1]
    if not isinstance(header.get('run'), str) or not isinstance(header.get('segment'), int):
        return None
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest().upper(),
            'header': header, 'raw_session_header': lines[0], 'lines': lines, 'terminated': not raw or raw.endswith(b'\n')}

def summarize(paths):
    grouped = defaultdict(list)
    ignored = []
    for path in paths:
        segment = load_segment(Path(path))
        if segment is None:
            ignored.append(str(Path(path).resolve()))
        else:
            grouped[segment['header']['run']].append(segment)
    output = {'summary_schema': 1, 'runs': [], 'ignored_files_without_valid_session_header': ignored,
              'scope': 'Retained diagnostic records only. Missing, overwritten, filtered or truncated records are not evidence that no event occurred. Memory is process virtual address space in KB, not physical RAM. GetTickCount is not a wall-clock timestamp.'}
    for run_id, all_segments in sorted(grouped.items()):
        segments = sorted(all_segments, key=lambda x: (x['header']['segment'], x['path']))
        by_category, by_player, by_turn = Counter(), defaultdict(Counter), defaultdict(Counter)
        turn_players = defaultdict(Counter)
        memory_peaks, memory_lows = {}, {}
        longs, truncations, shortened, malformed, configs = [], [], [], [], []
        combat = {}
        segment_info, warnings = [], []
        seen_segments = {}
        last_turn = None
        rewind_rows = []
        for segment in segments:
            header = segment['header']; number = header['segment']
            info = {key: segment[key] for key in ('path', 'bytes', 'sha256', 'raw_session_header')}
            info['header'] = header
            if number in seen_segments:
                if seen_segments[number] == segment['sha256']:
                    info['duplicate_ignored'] = True; segment_info.append(info); continue
                warnings.append(f'Conflicting files for segment {number}; both counted. Resolve duplicates before treating totals as authoritative.')
            seen_segments[number] = segment['sha256']
            segment_info.append(info)
            if header.get('schema') != 1:
                warnings.append(f'Unsupported schema {header.get("schema")} in {segment["path"]}; rows not interpreted.')
                continue
            if not segment['terminated']:
                warnings.append(f'Unterminated final line in segment {number}; it is excluded as a potentially incomplete write.')
            for line_number, text in enumerate(segment['lines'][1:], 2):
                if not segment['terminated'] and line_number == len(segment['lines']):
                    continue
                match = RECORD.fullmatch(text)
                if not match:
                    if text.strip(): malformed.append({'file': segment['path'], 'line': line_number, 'text': text})
                    continue
                tick, turn, player = map(int, match.group(1, 2, 3))
                category, message = match.group(4, 5)
                values = fields(message)
                origin = {'file': segment['path'], 'segment': number, 'line': line_number, 'tick_ms': tick, 'turn': turn, 'player': player}
                by_category[category] += 1; by_player[player][category] += 1
                by_turn[turn][category] += 1; turn_players[turn][player] += 1
                if last_turn is not None and turn < last_turn:
                    rewind_rows.append(dict(origin, previous_turn=last_turn))
                last_turn = turn
                detail = dict(origin, fields=values, message=message)
                if category == 'LONG_PLAN': longs.append(detail)
                if category == 'CONFIG': configs.append(detail)
                if category == 'TRUNCATED': truncations.append(detail)
                if '[message truncated]' in message: shortened.append(detail)
                if category == 'MEMORY':
                    metrics = {key: values[key] for key in ('committedKB', 'reservedKB', 'freeKB', 'largestFreeKB') if isinstance(values.get(key), int)}
                    if 'committedKB' in metrics and 'reservedKB' in metrics:
                        metrics['committedPlusReservedKB'] = metrics['committedKB'] + metrics['reservedKB']
                    for key, value in metrics.items():
                        if key not in memory_peaks or value > memory_peaks[key]['value']:
                            memory_peaks[key] = dict(origin, value=value)
                        if key in ('freeKB', 'largestFreeKB') and (key not in memory_lows or value < memory_lows[key]['value']):
                            memory_lows[key] = dict(origin, value=value)
                if category in COMBAT_CATEGORIES and isinstance(values.get('combat'), int):
                    serial = values['combat']
                    record = combat.setdefault(serial, {'counts': Counter(), 'before': set(), 'after': set(), 'first': origin, 'last': origin, 'absent': 0, 'delayed_death': 0, 'duplicate_after': []})
                    record['counts'][category] += 1; record['last'] = origin
                    if isinstance(values.get('owner'), int) and isinstance(values.get('id'), int):
                        identity = (values['owner'], values['id'])
                        if category == 'COMBAT_MEMBER': record['before'].add(identity)
                        if category == 'COMBAT_AFTER':
                            if identity in record['after']: record['duplicate_after'].append(dict(origin, owner=identity[0], id=identity[1]))
                            record['after'].add(identity)
                            record['absent'] += values.get('present') == 0
                            record['delayed_death'] += values.get('delayedDeath') == 1
        numbers = sorted(seen_segments)
        gaps = [[a + 1, b - 1] for a, b in zip(numbers, numbers[1:]) if b > a + 1]
        if numbers and numbers[0] > 0: warnings.append('Earlier segments are absent, commonly because rolling files overwrote them; totals cover retained files only.')
        if gaps: warnings.append('There are missing segments within the retained sequence.')
        combat_rows = []
        for serial, record in sorted(combat.items()):
            counts = record['counts']
            combat_rows.append({'combat': serial, 'counts': {key: counts[key] for key in COMBAT_CATEGORIES},
                'unique_units_before': len(record['before']), 'unique_units_after': len(record['after']),
                'before_without_after': [list(x) for x in sorted(record['before'] - record['after'])],
                'after_without_before': [list(x) for x in sorted(record['after'] - record['before'])],
                'begin_and_end_observed_once': counts['COMBAT_BEGIN'] == counts['COMBAT_END'] == 1,
                'unit_identity_sets_match': record['before'] == record['after'],
                'duplicate_after_identities': record['duplicate_after'],
                'after_absent_records': record['absent'], 'after_delayed_death_records': record['delayed_death'],
                'first_record': record['first'], 'last_record': record['last']})
        output['runs'].append({'run': run_id, 'files': segment_info, 'retained_segment_numbers': numbers,
            'earlier_segments_absent': bool(numbers and numbers[0] > 0), 'missing_segment_ranges': gaps,
            'warnings': warnings, 'record_count': sum(by_category.values()), 'counts_by_category': sorted_counts(by_category),
            'counts_by_player': {str(k): {'total': sum(v.values()), 'categories': sorted_counts(v)} for k, v in sorted(by_player.items())},
            'counts_by_turn': {str(k): {'total': sum(v.values()), 'categories': sorted_counts(v), 'players': {str(p): n for p, n in sorted(turn_players[k].items())}} for k, v in sorted(by_turn.items())},
            'memory': {'sample_count': by_category['MEMORY'], 'peaks_KB': memory_peaks, 'minimum_free_KB': memory_lows},
            'configuration_records': configs, 'long_plans': longs, 'row_budget_truncations': truncations, 'message_truncations': shortened,
            'turn_rewinds': rewind_rows,
            'combat': {'counts': {key: by_category[key] for key in COMBAT_CATEGORIES}, 'observed_serials': len(combat_rows),
                'bracketed_once': sum(x['begin_and_end_observed_once'] for x in combat_rows),
                'unbracketed_or_duplicate_serials': [x['combat'] for x in combat_rows if not x['begin_and_end_observed_once']],
                'unit_identity_mismatch_serials': [x['combat'] for x in combat_rows if not x['unit_identity_sets_match']],
                'duplicate_after_identity_serials': [x['combat'] for x in combat_rows if x['duplicate_after_identities']],
                'events': combat_rows,
                'interpretation': 'COMBAT_MEMBER may list the same unit in multiple roles; distinct identities are deduplicated only for before/after matching. Absence after combat can include capture/removal and is not labeled death. Matching brackets do not guarantee untruncated or exhaustive records.'},
            'malformed_record_count': len(malformed), 'malformed_examples': malformed[:20]})
    return output

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Directory containing retained native log segments (nonrecursive)')
    parser.add_argument('--run', help='Exact SESSION run ID to select; default keeps runs separate')
    parser.add_argument('--output', type=Path, help='Write JSON here instead of stdout; must not replace an input log')
    args = parser.parse_args(argv)
    if not args.directory.is_dir(): parser.error('directory does not exist')
    paths = discover(args.directory)
    result = summarize(paths)
    if args.run: result['runs'] = [r for r in result['runs'] if r['run'] == args.run]
    if not result['runs']:
        print('No matching supported session headers found. Actual rolling files normally start Stacking-, not StackingDiagnostics-.', file=sys.stderr)
        return 2
    data = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        target = args.output.resolve()
        if target in {p.resolve() for p in paths} or target.suffix.lower() == '.log' or (target.exists() and any(target.samefile(p) for p in paths)):
            parser.error('--output must not replace a log, including through a hardlink')
        target.write_text(data, encoding='utf-8')
        print(f'Summarized {len(result["runs"])} run(s), {sum(r["record_count"] for r in result["runs"])} retained records: {target}')
    else:
        print(data, end='')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
