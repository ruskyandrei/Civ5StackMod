"""Start gamecore and main-thread samplers for a running replay.

Usage: python work/start-replay-samplers.py RUN_DIR OUT_DIR [--hz 200]
Waits for the replay's native log to name the gamecore thread, then launches
two detached `profile-gamecore.py capture` processes (gamecore + main thread).
Each stops when the game exits.
"""
import importlib.util, json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = r'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
spec = importlib.util.spec_from_file_location('pg', str(ROOT / 'work/profile-gamecore.py')); pg = importlib.util.module_from_spec(spec); spec.loader.exec_module(pg)

run, out = Path(sys.argv[1]), Path(sys.argv[2])
hz = sys.argv[sys.argv.index('--hz') + 1] if '--hz' in sys.argv else '200'
out.mkdir(parents=True, exist_ok=True)
deadline = time.time() + 900
pid = thread = None
while time.time() < deadline and not thread:
    try:
        pid = json.loads((run / 'watcher-manifest.json').read_text(encoding='utf-8-sig'))['Game']
        for log in (run / 'native-segments').glob('*.log'):
            m = re.search(r'\|TURN_PHASE\|.*?thread=(\d+)', log.read_text(encoding='utf-8-sig', errors='replace'))
            if m:
                thread = int(m[1]); break
    except (OSError, KeyError, ValueError):
        pass
    time.sleep(2)
if not thread:
    sys.exit('replay did not start')
k = pg.kernel()
import ctypes as C
created = {}
for tid in pg.threads(k, pid):
    h = k.OpenThread(0x0040 | 0x0800, False, tid)
    if h:
        a, b, c, d = (C.c_ulonglong() for _ in range(4))
        k.GetThreadTimes(h, C.byref(a), C.byref(b), C.byref(c), C.byref(d)); created[tid] = a.value; k.CloseHandle(h)
main = min(created, key=created.get)
for name, tid in (('gamecore', thread), ('main', main)):
    subprocess.Popen([PY, '-B', str(ROOT / 'work/profile-gamecore.py'), 'capture', '--pid', str(pid), '--thread', str(tid), '--hz', hz,
                      '--seconds', '3600', '--output', str(out / (name + '.bin'))],
                     stdout=open(out / (name + '.log'), 'w'), stderr=subprocess.STDOUT, creationflags=0x00000008)  # DETACHED_PROCESS
print(json.dumps(dict(pid=pid, gamecore=thread, main=main, out=str(out))))
