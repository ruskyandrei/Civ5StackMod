"""Compare offensive behaviour between replay runs, turn by turn.

Usage: python work/compare-offense.py RUN_DIR [RUN_DIR ...]
Counts all ranged/melee combats and city attacks (COMBAT_SUMMARY), city damage,
city captures, early and end-of-turn IMMEDIATE_CITY shots, FIRE_REFUSAL rows and
plan execution failures per turn, plus the attacking players of city shots.
"""
import collections, re, sys
from pathlib import Path

RX = re.compile(r'STACKDIAG\|\d+\|turn=(\d+)\|player=(-?\d+)\|([A-Z_]+)\|(.*)')


def field(body, name):
    m = re.search(r'(?:^| )' + name + r'=(-?\d+)', body)
    return int(m[1]) if m else None


def summarize(run):
    files = sorted((run / 'native-segments').glob('*-segment-*.log')) or sorted((run / 'native-segments').glob('*.log'))
    t = collections.defaultdict(collections.Counter); shooters = collections.defaultdict(collections.Counter)
    for f in files:
        for line in f.open(encoding='utf-8-sig', errors='replace'):
            m = RX.match(line.rstrip('\r\n'))
            if not m:
                continue
            turn, player, cat, body = int(m[1]), int(m[2]), m[3], m[4]
            c = t[turn]
            if cat == 'COMBAT_SUMMARY':
                c['combats'] += 1
                c['unitDamage'] += max(0, field(body, 'hpLostPresent') or 0) if (field(body, 'defenderCity') or -1) < 0 else 0
            if cat == 'COMBAT_SUMMARY' and (field(body, 'defenderCity') or -1) >= 0:
                c['cityAttacks'] += 1
                before, after = field(body, 'cityHPBefore'), field(body, 'cityHPAfter')
                if before is not None and after is not None:
                    c['cityDamage'] += max(0, before - after)
                shooters[turn][field(body, 'attackerOwner')] += 1
            elif cat == 'CITY_CAPTURE':
                c['captures'] += 1
            elif cat == 'IMMEDIATE_CITY' and 'stationary_range_order' in body:
                c['immediateShots'] += 1
            elif cat == 'END_TURN_FIRE':
                c['endTurnCity' if 'kind=city' in body else 'endTurnUnit'] += 1
            elif cat == 'FIRE_REFUSAL':
                c['fireRefusals'] += 1
            elif cat == 'PLAN_EXEC_FAIL':
                c['execFails'] += 1
            elif cat == 'SIEGE_REASSESS':
                c['siegeReassess'] += 1
    print('==', run.name)
    keys = ['combats', 'unitDamage', 'cityAttacks', 'cityDamage', 'captures', 'immediateShots', 'endTurnCity', 'endTurnUnit', 'fireRefusals', 'execFails', 'siegeReassess']
    print('turn ' + ' '.join('%14s' % k for k in keys) + '  city shots by player')
    for turn in sorted(t):
        print('%4d ' % turn + ' '.join('%14d' % t[turn][k] for k in keys) + '  ' +
              ' '.join('p%d:%d' % kv for kv in sorted(shooters[turn].items())))


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        summarize(Path(arg))
