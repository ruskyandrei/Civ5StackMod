"""Read-only extraction of Civ5 stacking AI log measures. No game interaction."""
from __future__ import annotations
import argparse, hashlib, json, re, statistics
from pathlib import Path
SEARCH = re.compile(r"tactsim around \((-?\d+):(-?\d+)\) with agg (\d+) finished in (\d+) ms\. started with (\d+) units and (\d+) enemies on (\d+) plots\. used (\d+) positions, (\d+) completed\.")
CACHE = re.compile(r"stack forecast cache: danger (\d+) hit/(\d+) miss \((\d+) entries\), defender (\d+) hit/(\d+) miss \((\d+) entries\)")
MEMORY = re.compile(r"peak (\d+)/(\d+) entries, key bytes (\d+)/(\d+), estimated bytes (\d+), insertion bypasses (\d+), nested bypasses (\d+)")
LUA = re.compile(r"^\[([\d.]+)\].*?STACKNAT\|([^|]+)\|(.*)$")
KV = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=([^\s]+)")
def values(text):
    result = {}
    for key, value in KV.findall(text):
        if value in ('true', 'false'): result[key] = value == 'true'
        else:
            try: result[key] = int(value)
            except ValueError: result[key] = value
    return result

def tactical(paths, player=None, turn=None):
    searches, warnings, hashes = [], [], {}
    for path in paths:
        payload = path.read_bytes(); hashes[str(path)] = hashlib.sha256(payload).hexdigest().upper()
        previous = None
        for line_no, line in enumerate(payload.decode('utf-8-sig', 'replace').splitlines(), 1):
            parts = line.split(',', 2)
            if len(parts) != 3: continue
            try: line_turn = int(parts[0])
            except ValueError: continue
            line_player = parts[1].strip()
            if player is not None and line_player != player: continue
            if turn is not None and line_turn != turn: continue
            match = SEARCH.search(parts[2])
            if match:
                x, y, aggression, ms, units, enemies, plots, used, completed = map(int, match.groups())
                previous = dict(file=str(path), line=line_no, turn=line_turn, player=line_player,
                    target=[x, y], aggression=aggression, milliseconds=ms, movable_units=units,
                    enemies=enemies, plots=plots, positions=used, completed=completed, cache=None)
                searches.append(previous)
                continue
            match = CACHE.search(parts[2])
            if match:
                if previous is None or previous['turn'] != line_turn or previous['player'] != line_player or previous['cache'] is not None:
                    warnings.append(f'orphan/duplicate cache row: {path}:{line_no}'); continue
                cache = dict(zip(('danger_hits', 'danger_misses', 'danger_entries', 'defender_hits', 'defender_misses', 'defender_entries'), map(int, match.groups())))
                memory = MEMORY.search(parts[2])
                if memory:
                    cache.update(zip(('peak_entries', 'entry_limit', 'key_bytes', 'key_limit', 'estimated_bytes', 'insertion_bypasses', 'nested_bypasses'), map(int, memory.groups())))
                    cache['bounds_ok'] = cache['peak_entries'] <= cache['entry_limit'] and cache['key_bytes'] <= cache['key_limit']
                    cache['entry_counts_consistent'] = cache['peak_entries'] == cache['danger_entries'] + cache['defender_entries']
                previous['cache'] = cache
    return searches, warnings, hashes

def lua_snapshots(path):
    payload = path.read_bytes(); snapshots, markers = [], []; current = None
    for line_no, line in enumerate(payload.decode('utf-8-sig', 'replace').splitlines(), 1):
        match = LUA.match(line)
        if not match: continue
        timestamp, kind, text = match.groups(); timestamp = float(timestamp)
        if kind == 'snapshot':
            current = dict(timestamp=timestamp, line=line_no, fixture=text.split(' ', 1)[0], **values(text), units=[], terrain=[], checks=None)
            snapshots.append(current)
        elif kind == 'unit' and current is not None:
            record = values(text); record['dead_or_replaced'] = 'DEAD_OR_REPLACED' in text; current['units'].append(record)
        elif kind == 'terrain' and current is not None: current['terrain'].append(values(text))
        elif kind == 'checks' and current is not None: current['checks'] = values(text)
        elif kind in ('AI_START', 'AI_END', 'HUMAN_RETURN', 'ERROR', 'monitor-stop', 'formation-outcome'):
            markers.append(dict(timestamp=timestamp, line=line_no, kind=kind, text=text, **values(text)))
    return snapshots, markers, hashlib.sha256(payload).hexdigest().upper()

def summarize(searches):
    times = [s['milliseconds'] for s in searches]
    used = sum(s['positions'] for s in searches)
    rows = [s['cache'] for s in searches if s['cache'] is not None]
    bounded = [r for r in rows if 'bounds_ok' in r]
    result = dict(searches=len(searches), search_milliseconds=sum(times), median_search_ms=statistics.median(times) if times else None,
        max_search_ms=max(times) if times else None, positions=used, completed=sum(s['completed'] for s in searches),
        searches_without_completed_plan=sum(s['completed'] == 0 for s in searches),
        milliseconds_per_used_position=sum(times)/used if used else None,
        cache_rows=len(rows), memory_guard_rows=len(bounded), bounds_ok=all(r['bounds_ok'] and r['entry_counts_consistent'] for r in bounded) if bounded else None,
        peak_cache_entries=max((r['peak_entries'] for r in bounded), default=None),
        peak_key_bytes=max((r['key_bytes'] for r in bounded), default=None),
        peak_estimated_cache_bytes=max((r['estimated_bytes'] for r in bounded), default=None),
        insertion_bypasses=sum(r['insertion_bypasses'] for r in bounded) if bounded else None,
        nested_bypasses=sum(r['nested_bypasses'] for r in bounded) if bounded else None)
    for name in ('danger', 'defender'):
        hits, misses = sum(r[name+'_hits'] for r in rows), sum(r[name+'_misses'] for r in rows)
        result[name+'_hits'] = hits if rows else None; result[name+'_misses'] = misses if rows else None
        result[name+'_hit_ratio'] = hits/(hits+misses) if hits+misses else None
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs', type=Path, required=True, help='saved per-run log directory')
    parser.add_argument('--player', help='exact player field in tactical CSV, e.g. The_Shoshone')
    parser.add_argument('--turn', type=int, help='AI turn in tactical CSV, before human return increments game turn')
    parser.add_argument('--label', default='unlabelled')
    parser.add_argument('--dll-sha256'); parser.add_argument('--save-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = sorted(args.logs.glob('PlayerTacticalAILog*.csv'))
    searches, warnings, hashes = tactical(paths, args.player, args.turn)
    lua_path = args.logs/'Lua.log'
    snapshots, markers, lua_hash = lua_snapshots(lua_path) if lua_path.exists() else ([], [], None)
    starts = [m for m in markers if m['kind'] == 'AI_START' and (args.turn is None or m.get('turn') == args.turn)]
    start = starts[-1] if starts else None
    end = next((m for m in markers if m['kind'] == 'HUMAN_RETURN' and start and m['timestamp'] > start['timestamp']), None)
    result = dict(label=args.label, dll_sha256=args.dll_sha256, save_sha256=args.save_sha256,
        filters=dict(player=args.player, turn=args.turn), summary=summarize(searches),
        per_player={p:summarize([s for s in searches if s['player']==p]) for p in sorted({s['player'] for s in searches})},
        turn_observation=dict(completed=end is not None, seconds=end['timestamp']-start['timestamp'] if start and end else None,
            start=start, end=end, last_marker=markers[-1] if markers else None),
        searches=searches, snapshots=snapshots, markers=markers, warnings=warnings,
        input_hashes=dict(tactical=hashes, lua=lua_hash))
    if not searches: warnings.append('No matching tactical search rows; this is not a zero-time success.')
    if start and not end: warnings.append('AI_START has no subsequent HUMAN_RETURN; observation is incomplete.')
    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(dict(output=str(args.output), summary=result['summary'], turn_observation=result['turn_observation'], warnings=warnings), indent=2))
    else: print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
