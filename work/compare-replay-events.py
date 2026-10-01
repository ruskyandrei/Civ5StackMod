"""Compare ordered decision/combat records of two replays for chosen turns.

Usage: python work/compare-replay-events.py BASE_RUN CAND_RUN FIRST_TURN LAST_TURN
Keeps PLAN (minus milliseconds), COMBAT*, CITY_CAPTURE, CAPTURE_*, RECRUIT,
PLAN_EXEC_FAIL/PLAN_RETRY and IMMEDIATE_CITY records; strips the clock prefix.
Timing/cache rows (PLAN_PERF, TURN_PHASE, ...) are ignored.
"""
import re, sys
from pathlib import Path
KEEP = re.compile(r'^(PLAN|COMBAT\w*|CITY_CAPTURE|CAPTURE_\w+|RECRUIT|PLAN_EXEC_FAIL|PLAN_RETRY|IMMEDIATE_CITY\w*|ASSAULT_\w+|OPERATION_\w+)$')
RX = re.compile(r'STACKDIAG\|\d+\|turn=(\d+)\|player=(-?\d+)\|([A-Z_]+)\|(.*)')
def events(run, lo, hi):
    files = sorted((Path(run) / 'native-segments').glob('*-segment-*.log')) or sorted((Path(run) / 'native-segments').glob('*.log'))
    out = []
    for f in files:
        for line in f.open(encoding='utf-8-sig', errors='replace'):
            m = RX.match(line.rstrip('\r\n'))
            if m and lo <= int(m[1]) <= hi and KEEP.match(m[3]):
                body = re.sub(r' milliseconds=\d+', '', m[4])
                out.append('%s|%s|%s|%s' % (m[1], m[2], m[3], body))
    return out
a, b = events(sys.argv[1], int(sys.argv[3]), int(sys.argv[4])), events(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
print('baseline %d records, candidate %d records' % (len(a), len(b)))
for i, (x, y) in enumerate(zip(a, b)):
    if x != y:
        print('FIRST DIFFERENCE at record %d' % i); print(' base:', x[:400]); print(' cand:', y[:400]); sys.exit(1)
if len(a) != len(b):
    print('length differs; common prefix identical'); sys.exit(1)
import collections
print('IDENTICAL:', dict(collections.Counter(r.split('|')[2] for r in a).most_common(12)))
