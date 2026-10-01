"""Per-turn wall time, tactical-search time and heaviest players for replay runs.

Usage: python work/summarize-replay-turns.py RUN_DIR [RUN_DIR ...]
Turn span = first native record of a turn to the first record of the next turn
(the same convention as profile-campaign-log.py). The final turn of a replay
has no successor and is reported without a span.
"""
import collections, re, sys
from pathlib import Path

RECORD = re.compile(r'STACKDIAG\|(\d+)\|turn=(\d+)\|player=(-?\d+)\|([A-Z_]+)\|(.*)')
SKIP = {'TURN_PHASE', 'TURN_UPDATE_GAP', 'PLAN_PACKET_PROBE', 'PLAN_KERNEL_PROBE', 'PATH_SAMPLE'}


def segments(run):
    files = sorted((run / 'native-segments').glob('*-segment-*.log'))
    return files or sorted((run / 'native-segments').glob('*.log'))


def summarize(run):
    first = {}; plan = collections.defaultdict(int); plan_player = collections.defaultdict(lambda: collections.defaultdict(int))
    gaps = collections.defaultdict(int); slow = []
    for path in segments(run):
        for line in path.open(encoding='utf-8-sig', errors='replace'):
            m = RECORD.match(line)
            if not m:
                continue
            tick, turn, player, cat, rest = int(m[1]), int(m[2]), int(m[3]), m[4], m[5]
            if cat not in SKIP and turn not in first:
                first[turn] = tick
            if cat == 'PLAN':
                ms = int(re.search(r'milliseconds=(\d+)', rest)[1])
                plan[turn] += ms; plan_player[turn][player] += ms
                if ms >= 2000:
                    slow.append((turn, player, ms, re.search(r'target=(\S+)', rest)[1], re.search(r'states=(\d+)', rest)[1]))
            elif cat == 'TURN_UPDATE_GAP':
                gaps[turn] += int(re.search(r'elapsedMs=(\d+)', rest)[1])
    turns = sorted(first)
    print('==', run.name)
    print('turn   span_s  plan_s  gaps_s  top players (plan s)')
    for i, t in enumerate(turns):
        span = (first[turns[i + 1]] - first[t]) / 1000.0 if i + 1 < len(turns) and turns[i + 1] == t + 1 else None
        top = sorted(plan_player[t].items(), key=lambda kv: -kv[1])[:4]
        print('%4d  %7s  %6.1f  %6.1f  %s' % (t, '%.1f' % span if span is not None else '-', plan[t] / 1000.0, gaps[t] / 1000.0,
                                         ' '.join('p%d:%.1f' % (p, ms / 1000.0) for p, ms in top)))
    if slow:
        print('searches >= 2s:', ', '.join('t%d p%d %.1fs %s n=%s' % (t, p, ms / 1000.0, tg, st) for t, p, ms, tg, st in slow))


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        summarize(Path(arg))
