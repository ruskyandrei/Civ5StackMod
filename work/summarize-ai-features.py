"""Summarise the stacking AI feature diagnostics of one session (DiagnosticsLevel >= 1).

usage: summarize-ai-features.py LOG_PREFIX [--bucket 25]
LOG_PREFIX is the session prefix in the Civ V Logs folder, e.g.
"Stacking-20261011T133630-582-p10596-r1"; every rolling segment is read.

Reports, per bucket of turns and summed over AI majors and city-states:
land/sea stack mix (mixed, all-ranged, all-melee stacks of two or more),
medics and medics sharing a tile, melee attacks on units and the share
flanked, objectives and those with a full blockade or a support group, the
support-group gate/join/abort/redirect events, conquest decisions (puppet,
kept from razing, unrazed, courthouses bought), city unit purchases and
garrison sorties.
"""
import argparse, glob, os, re, sys
from collections import defaultdict

LOGS = os.path.expanduser(r"~\Documents\My Games\Sid Meier's Civilization 5\Logs")
ROW = re.compile(r'^STACKDIAG\|\d+\|turn=(\d+)\|player=(-?\d+)\|([A-Z_]+)\|(.*)$')
FIELD = re.compile(r'(\w+)=(-?\d+)')
KEYS = ['landMixed', 'landAllRanged', 'landAllMelee', 'seaMixed', 'seaAllRanged', 'seaAllMelee',
        'medics', 'medicsStacked', 'objectives', 'blockadedTargets', 'supportGroups', 'meleeAttacks', 'flankedAttacks']


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('prefix'); p.add_argument('--bucket', type=int, default=25); p.add_argument('--logs', default=LOGS)
    a = p.parse_args()
    files = sorted(glob.glob(os.path.join(a.logs, a.prefix + '-*.log')))
    if not files:
        sys.exit('no log segments for ' + a.prefix)
    features = defaultdict(lambda: defaultdict(int))   # bucket -> key -> sum
    samples = defaultdict(int)                          # bucket -> player-turn rows
    events = defaultdict(int)
    blockade_turns = set(); support_targets = set()
    last_turn = 0
    for name in files:
        with open(name, encoding='utf-8', errors='replace') as stream:
            for line in stream:
                m = ROW.match(line.rstrip('\n'))
                if not m:
                    continue
                turn, player, category, rest = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
                last_turn = max(last_turn, turn)
                if category == 'AI_FEATURES':
                    b = turn // a.bucket
                    values = dict((k, int(v)) for k, v in FIELD.findall(rest))
                    for k in KEYS:
                        features[b][k] += values.get(k, 0)
                    samples[b] += 1
                    if values.get('blockadedTargets', 0):
                        blockade_turns.add((player, turn))
                elif category == 'OFFENSIVE_SUPPORT' and 'action=support_group_joined' in rest:
                    events['support_group_joined'] += 1
                    t = re.search(r'target=(\d+)', rest)
                    support_targets.add((player, t.group(1) if t else '?'))
                elif category == 'OFFENSIVE_SUPPORT' and 'action=group_aborted' in rest:
                    events['support_group_aborted'] += 1
                elif category == 'OPERATION_GATE' and 'reason=support_group_wanted' in rest:
                    events['support_group_wanted_checks'] += 1
                elif category == 'OFFENSIVE_SUPPORT' and 'action=group_redirected' in rest:
                    events['support_group_redirected'] += 1
                elif category == 'CONQUEST':
                    m2 = re.search(r'action=(\w+)', rest)
                    events['conquest_' + (m2.group(1) if m2 else '?')] += 1
                elif category == 'CITY_PURCHASE':
                    events['city_purchases'] += 1
                elif category == 'GARRISON_SORTIE':
                    events['garrison_sorties'] += 1
                elif category == 'CITY_CAPTURE':
                    events['city_captures'] += 1
    print('segments=%d lastTurn=%d' % (len(files), last_turn))
    header = ['turns', 'rows'] + KEYS + ['flank%']
    print('\t'.join(header))
    for b in sorted(features):
        f = features[b]
        flank = 100.0 * f['flankedAttacks'] / f['meleeAttacks'] if f['meleeAttacks'] else 0.0
        print('\t'.join(['%d-%d' % (b * a.bucket, b * a.bucket + a.bucket - 1), str(samples[b])] +
                        [str(f[k]) for k in KEYS] + ['%.0f' % flank]))
    tot = defaultdict(int)
    for f in features.values():
        for k in KEYS:
            tot[k] += f[k]
    land = tot['landMixed'] + tot['landAllRanged'] + tot['landAllMelee']
    sea = tot['seaMixed'] + tot['seaAllRanged'] + tot['seaAllMelee']
    if land:
        print('land stacks: mixed %.0f%%, all-ranged %.0f%%, all-melee %.0f%%' % (
            100.0 * tot['landMixed'] / land, 100.0 * tot['landAllRanged'] / land, 100.0 * tot['landAllMelee'] / land))
    if sea:
        print('sea stacks: mixed %.0f%%, all-ranged %.0f%%, all-melee %.0f%%' % (
            100.0 * tot['seaMixed'] / sea, 100.0 * tot['seaAllRanged'] / sea, 100.0 * tot['seaAllMelee'] / sea))
    if tot['medics']:
        print('medics: %.0f%% of medic-turns shared a tile with another unit' % (100.0 * tot['medicsStacked'] / tot['medics']))
    if tot['meleeAttacks']:
        print('melee attacks on units: %d, flanked %.0f%%' % (tot['meleeAttacks'], 100.0 * tot['flankedAttacks'] / tot['meleeAttacks']))
    print('player-turns with a fully blockaded target city: %d' % len(blockade_turns))
    print('support groups: %d joined on %d (player, target) pairs, %d aborted, %d gate checks wanting one' % (
        events['support_group_joined'], len(support_targets), events['support_group_aborted'], events['support_group_wanted_checks']))
    print('support groups redirected from less important attacks: %d' % events['support_group_redirected'])
    print('conquest: %d puppeted (unhappy), %d puppeted instead of razed, %d unrazed, %d courthouses bought' % (
        events['conquest_puppet_unhappy'], events['conquest_puppet_not_razed'], events['conquest_unraze'],
        events['conquest_bought_courthouse']))
    print('city defender purchases: %d, garrison sorties: %d' % (events['city_purchases'], events['garrison_sorties']))
    print('city captures logged: %d' % events['city_captures'])


if __name__ == '__main__':
    main()
