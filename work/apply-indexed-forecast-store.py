"""Apply the frozen whole-file-qualified forecast storage stage."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
stage = root / 'work/indexed-forecast-store-staged'
proof = json.loads((stage / 'production-staging-proof.json').read_text())
target = root / proof['path']
raw = target.read_bytes()
original = raw.decode('utf-8-sig').replace('\r\n', '\n')
assert hashlib.sha256(original.encode()).hexdigest() == proof['sourceSHA256']
candidate = (stage / 'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
assert hashlib.sha256(candidate.encode()).hexdigest() == proof['candidateSHA256']
newline = '\r\n' if b'\r\n' in raw else '\n'
encoded = candidate.replace('\n', newline).encode('utf-8')
if raw.startswith(b'\xef\xbb\xbf'):
    encoded = b'\xef\xbb\xbf' + encoded
target.write_bytes(encoded)
print('Applied hash-qualified whole Tactical source; original BOM/newlines retained.')
