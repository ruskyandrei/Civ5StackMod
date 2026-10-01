"""Profile gamecore samples outside (or inside) native PLAN intervals.

Usage: python work/profile-nonplan.py SAMPLES.bin DLL PDB NATIVE_LOG_DIR [--inside] [--turn N]
PLAN records carry their end tick and duration, so each search covers
[tick - milliseconds, tick]. Prints flat and inclusive shares like
profile-gamecore.py report.
"""
import importlib.util, collections, json, re, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('pg', str(Path(__file__).with_name('profile-gamecore.py'))); pg = importlib.util.module_from_spec(spec); spec.loader.exec_module(pg)
args = [a for a in sys.argv[1:] if not a.startswith('--')]
inside = '--inside' in sys.argv
turn_filter = int(sys.argv[sys.argv.index('--turn') + 1]) if '--turn' in sys.argv else None
samples, dll, pdb, logdir = args[:4]
rx = re.compile(r'STACKDIAG\|(\d+)\|turn=(\d+)\|player=(-?\d+)\|PLAN\|.*milliseconds=(\d+)')
first = re.compile(r'STACKDIAG\|(\d+)\|turn=(\d+)\|')
intervals = []; turn_start = {}
files = sorted(Path(logdir).glob('*-segment-*.log')) or sorted(Path(logdir).glob('*.log'))
for f in files:
    for line in f.open(encoding='utf-8-sig', errors='replace'):
        m = rx.match(line)
        if m:
            end, ms = int(m[1]), int(m[4]); intervals.append((end - ms, end))
        m = first.match(line)
        if m and int(m[2]) not in turn_start:
            turn_start[int(m[2])] = int(m[1])
intervals.sort()
def in_plan(t):
    import bisect
    i = bisect.bisect_right(intervals, (t, 1 << 40)) - 1
    return i >= 0 and intervals[i][0] <= t <= intervals[i][1]
meta = json.loads(Path(samples).with_suffix('.meta.json').read_text()); base, size = meta['dllBase'], meta['dllSize']
image = Path(dll).read_bytes(); sections = pg.text_section(image); sym = pg.Symbols(dll, pdb, base, size)
rows = [r for r in pg.read_samples(samples) if r[2] > 1000]
if turn_filter is not None:
    lo, hi = turn_start[turn_filter], turn_start.get(turn_filter + 1, 1 << 40)
    rows = [r for r in rows if lo <= r[0] < hi]
rows = [r for r in rows if in_plan(r[0]) == inside]
flat = collections.Counter(); inc = collections.Counter(); cache = {}
for tick, eip, d, frames in rows:
    chain = pg.walk(eip, frames, base, size, sections, image, sym, cache)
    flat[chain[0]] += 1
    for n in set(chain): inc[n] += 1
n = max(1, len(rows)); hz = meta['hz']
print('%s samples %d (~%.1fs busy)' % ('inside PLAN' if inside else 'outside PLAN', len(rows), len(rows) / hz))
print('== flat'); [print('%6.2f%% %s' % (100.0 * c / n, k[:150])) for k, c in flat.most_common(30)]
print('== inclusive'); [print('%6.2f%% %s' % (100.0 * c / n, k[:150])) for k, c in inc.most_common(70)]
