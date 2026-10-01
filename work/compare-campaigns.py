"""Compare offensive outcomes of whole autoplay campaigns on the same map.

Usage: python work/compare-campaigns.py RUN_DIR [RUN_DIR ...] [--until TURN]
Per run: city captures, war declarations, major-vs-major combats and city attacks
per attacker/defender pair, bombardment and readiness counts from ASSAULT_PLAN,
combined-operation readiness rows (WAR_READINESS/OPERATION_READINESS of type-4
operations) and wall-clock time per 50 turns from the monitor checkpoints.
"""
import collections, glob, json, re, sys
from pathlib import Path

RX = re.compile(r'STACKDIAG\|\d+\|turn=(\d+)\|player=(-?\d+)\|([A-Z_]+)\|(.*)')
MAJORS = range(8)


def field(body, name):
    m = re.search(r'(?:^| )' + name + r'=(-?\d+)', body)
    return int(m[1]) if m else None


def rows(run, until):
    files = sorted((run / 'native-segments').glob('*-segment-*.log'))
    for f in files:
        for line in f.open(encoding='utf-8-sig', errors='replace'):
            m = RX.match(line.rstrip('\r\n'))
            if m and int(m[1]) <= until:
                yield int(m[1]), int(m[2]), m[3], m[4]


def checkpoint_times(run, until):
    points = []
    for f in sorted((run / 'checkpoints').glob('turn-*.json')) or sorted(run.glob('*-checkpoint.json')):
        d = json.loads(f.read_text(encoding='utf-8-sig'))
        data = d.get('data') or (d.get('result', {}).get('values') or [None])[0]
        if isinstance(data, dict) and 'turn' in data:
            points.append((data['turn'], d['utc']))
    from datetime import datetime
    out = {}
    stamps = sorted((t, datetime.fromisoformat(u)) for t, u in points if t <= until)
    for lo in range(0, until, 50):
        a = [s for s in stamps if s[0] >= lo]
        b = [s for s in stamps if s[0] <= lo + 50]
        if a and b and b[-1][0] > a[0][0]:
            out[lo] = (b[-1][1] - a[0][1]).total_seconds() / (b[-1][0] - a[0][0])
    return out


def summarize(run, until):
    pair = collections.defaultdict(lambda: [0, 0, 0])
    captures, declarations = [], []
    plans = collections.Counter()
    combined_ops, combined = set(), []
    for turn, player, cat, body in rows(run, until):
        if cat == 'COMBAT_SUMMARY':
            a, d = field(body, 'attackerOwner'), field(body, 'defenderOwner')
            if a in MAJORS and d in MAJORS:
                p = pair[(a, d)]
                p[0] += 1
                if (field(body, 'defenderCity') or -1) >= 0:
                    p[1] += 1
                    p[2] += max(0, (field(body, 'cityHPBefore') or 0) - (field(body, 'cityHPAfter') or 0))
        elif cat == 'CITY_CAPTURE':
            captures.append((turn, field(body, 'newOwner'), field(body, 'oldOwner')))
        elif cat == 'WAR_DECLARATION':
            declarations.append((turn, player, field(body, 'enemy'), field(body, 'ready')))
        elif cat == 'ASSAULT_PLAN':
            plans['rows'] += 1
            plans['ready'] += field(body, 'phase') == 1
            plans['bombard'] += field(body, 'bombard') == 1
        elif cat == 'OPERATION_STATUS' and field(body, 'type') == 4:
            combined_ops.add((player, field(body, 'operation')))
        elif cat in ('WAR_READINESS', 'OPERATION_READINESS'):
            if (player, field(body, 'operation')) in combined_ops:
                combined.append((turn, player, cat, field(body, 'operation'), field(body, 'total') if cat == 'WAR_READINESS' else field(body, 'core'),
                                 field(body, 'capture') if cat == 'WAR_READINESS' else field(body, 'capturers'), field(body, 'failedMask'), field(body, 'ready')))
    print('==', run.name, 'through turn', until)
    print('captures (turn, new, old):', [c for c in captures if c[2] in MAJORS or c[1] in MAJORS])
    print('captures total:', len(captures), ' war declarations (turn, player, enemy, ready):', declarations)
    print('assault plans:', dict(plans))
    print('major pairs with city attacks or >50 combats: attacker->defender combats/cityAttacks/cityDamage')
    for (a, d), (n, c, dmg) in sorted(pair.items()):
        if c or n > 50:
            print('  p%d->p%d %d/%d/%d' % (a, d, n, c, dmg))
    print('combined operations:', len(combined_ops), ' readiness rows (turn, player, kind, op, units, capture, mask, ready):')
    seen = collections.Counter()
    for r in combined:
        seen[r[3]] += 1
        if seen[r[3]] <= 3:
            print('  ', r)
    print('seconds per turn by 50-turn block:', {k: round(v, 1) for k, v in checkpoint_times(run, until).items()})


if __name__ == '__main__':
    args = sys.argv[1:]
    until = 10 ** 6
    if '--until' in args:
        i = args.index('--until'); until = int(args[i + 1]); del args[i:i + 2]
    for arg in args:
        summarize(Path(arg), until)
