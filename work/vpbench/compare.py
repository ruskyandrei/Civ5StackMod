"""Compare vpbench autoplay runs: python compare.py RUN_DIR [RUN_DIR ...]"""
import collections, json, re, sys
from pathlib import Path


def load(run):
    run = Path(run)
    status = json.loads((run / 'status.json').read_text(encoding='utf-8'))
    seen = {int(k): v for k, v in json.loads((run / 'turn-seen.json').read_text(encoding='utf-8')).items()}
    messages = json.loads((run / 'replay-messages.json').read_text(encoding='utf-8'))
    points = [json.loads(f.read_text(encoding='utf-8'))['data'] for f in sorted((run / 'checkpoints').glob('turn-*.json'))]
    setup = json.loads((run / 'setup.json').read_text(encoding='utf-8'))
    return dict(name=run.name, status=status, seen=seen, messages=messages, points=points, setup=setup)


def summarize(r):
    s = r['status']; seen = r['seen']; final = r['points'][-1]
    civ = {p['owner']: p['civilization'].replace('CIVILIZATION_', '').replace('MINOR_CIV_', 'cs:').title() for p in r['setup']['players']}
    out = collections.OrderedDict()
    out['wall seconds (T0-T250)'] = s['wallSeconds']
    out['seconds per turn'] = s['secondsPerTurn']
    for lo in range(0, s['endTurn'], 50):
        hi = min(lo + 50, s['endTurn'])
        out[f'  s/turn T{lo}-{hi}'] = round((seen[hi] - seen[lo]) / (hi - lo), 2)
    out['slowest single turn (s, +/-5)'] = round(max(seen[t] - seen[t - 1] for t in seen if t - 1 in seen), 1)
    proc = s.get('process') or {}
    out['process CPU seconds'] = round(proc.get('CPUSeconds', 0))
    out['peak working set (MB)'] = round(proc.get('PeakWorkingSet', 0) / 2 ** 20)
    text = [(m['Turn'], m.get('Player'), m.get('Text') or '') for m in r['messages'] if m['Type'] == 0]
    wars = [(t, x) for t, p, x in text if 'declares war on' in x or 'declared war' in x]
    majors = {p['owner'] for p in r['setup']['players'] if not p['minor']}
    out['war declarations'] = len(wars)
    out['peace treaties'] = sum(1 for t, p, x in text if 'peace' in x.lower())
    caps = [m for m in r['messages'] if m['Type'] == 3]
    out['city captures (replay)'] = len(caps)
    out['  by majors'] = sum(1 for m in caps if m.get('Player') in majors)
    out['  captures by civ'] = dict(collections.Counter(civ.get(m.get('Player'), str(m.get('Player'))) for m in caps))
    out['cities destroyed/razed'] = sum(1 for m in r['messages'] if m['Type'] == 4)
    out['cities founded'] = sum(1 for m in r['messages'] if m['Type'] == 1)
    out['wonders completed'] = sum(1 for t, p, x in text if ' completes ' in x)
    cities = final['cities']
    out['cities at end'] = len(cities)
    out['  held by a non-original owner'] = sum(1 for c in cities if c['owner'] != c['originalOwner'])
    damaged = set(); samples = 0
    for point in r['points']:
        for c in point['cities']:
            if c['hp'] < c['maxHP']:
                samples += 1; damaged.add(c['plot'])
    out['distinct cities seen damaged (snapshots)'] = len(damaged)
    out['damaged city sightings (snapshots)'] = samples
    out['wars in progress at end (pairs incl. city-states)'] = len(final['wars'])
    living = [p for p in final['players'] if not p['minor'] and not p['barbarian']]
    out['living majors at end'] = len(living)
    out['major civs at end: cities/units/techs/score'] = {civ.get(p['owner'], p['owner']): f"{p['cityCount']}/{p['unitCount']}/{p['techs']}/{p['score']}" for p in sorted(living, key=lambda p: -p['score'])}
    out['total units at end (all players)'] = sum(p['unitCount'] for p in final['players'])
    out['war declarations list'] = [f'T{t} {x}' for t, x in wars]
    return out


def main():
    runs = [load(a) for a in sys.argv[1:]]
    rows = [summarize(r) for r in runs]
    keys = list(rows[0])
    print('metric | ' + ' | '.join(r['name'] for r in runs))
    for k in keys:
        if k.endswith('list'): continue
        print(k + ' | ' + ' | '.join(str(row.get(k)) for row in rows))
    for r, row in zip(runs, rows):
        print('\n' + r['name'] + ' war declarations:')
        for line in row['war declarations list']: print('  ' + line.encode('ascii', 'replace').decode())


if __name__ == '__main__': main()
