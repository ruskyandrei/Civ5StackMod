"""Apply the reviewed, whole-file-qualified DLL86 cold-format stage."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
stage = root / 'work/cold-assertion-formatting-staged'
manifest = json.loads((stage / 'manifest.json').read_text())
prepared = []
for name, old_hash in manifest['original_sha256'].items():
    target = root / name
    raw = target.read_bytes()
    normalized = raw.decode('utf-8-sig').replace('\r\n', '\n')
    assert hashlib.sha256(normalized.encode()).hexdigest() == old_hash, name
    candidate = (stage / name).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(candidate.encode()).hexdigest() == manifest['candidate_sha256'][name], name
    newline = '\r\n' if b'\r\n' in raw else '\n'
    encoded = candidate.replace('\n', newline).encode('utf-8')
    if raw.startswith(b'\xef\xbb\xbf'):
        encoded = b'\xef\xbb\xbf' + encoded
    prepared.append((target, encoded))
for target, encoded in prepared:
    target.write_bytes(encoded)
print('Applied all three hash-qualified files; original BOM/newlines preserved.')
