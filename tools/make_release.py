"""Build a release zip from the verified staging payload (work/stage_vp.py).

  python tools/make_release.py --version 0.1.0

Requires a clean working tree whose HEAD is the staged commit. Writes
work/release/Civ5StackMod-<version>.zip, a separate symbols zip with the PDB,
and SHA256SUMS.txt. Nothing is published.
"""
import argparse, hashlib, json, re, shutil, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'work/staging/vp-5.4.6-full-eui'
OUT = ROOT / 'work/release'
PDB = 'user-data/MODS/(1) Community Patch/CvGameCore_Expansion2.pdb'
DOCS = ['docs/stacking-playing.md', 'docs/stacking-configuration.md']


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): h.update(block)
    return h.hexdigest().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--upstream', default='upstream/master', help='Upstream ref merged into this build (for the README)')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z.\-]*', args.version): parser.error('Use a simple version such as 0.1.0')
    head = git('rev-parse', 'HEAD')
    if git('status', '--porcelain', '--untracked-files=no'): sys.exit('Working tree has uncommitted changes.')
    manifest = json.loads((STAGE / 'deploy-manifest.json').read_text(encoding='utf-8'))
    if manifest['source_commit'] != head: sys.exit(f"Staging was made from {manifest['source_commit'][:9]}, HEAD is {head[:9]}. Rebuild and stage first.")
    for entry in manifest['files']:
        if sha256(STAGE / entry['staged_path']) != entry['sha256']: sys.exit('Staged file changed: ' + entry['staged_path'])
    upstream = git('merge-base', 'HEAD', args.upstream)
    name = f'Civ5StackMod-{args.version}'
    OUT.mkdir(parents=True, exist_ok=True)
    package, symbols = OUT / (name + '.zip'), OUT / (name + '-symbols.zip')
    for path in (package, symbols):
        if path.exists(): sys.exit(f'{path} already exists; choose another version or remove it.')
    readme = (ROOT / 'tools/release/README.txt').read_text(encoding='utf-8')
    readme = readme.replace('@VERSION@', args.version).replace('@COMMIT@', head[:9]).replace('@UPSTREAM@', upstream[:9])
    count = 0
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(f'{name}/README.txt', readme.replace('\r\n', '\n').replace('\n', '\r\n'))
        for extra in ('tools/release/Install.cmd', 'tools/release/Install.ps1', 'License.rtf'):
            archive.write(ROOT / extra, f'{name}/{Path(extra).name}')
        for doc in DOCS:
            archive.write(ROOT / doc, f'{name}/Docs/{Path(doc).name}')
        for entry in manifest['files']:
            staged = entry['staged_path']
            if staged == PDB: continue
            top, rest = staged.split('/', 1)
            archive.write(STAGE / staged, f"{name}/{'UserData' if top == 'user-data' else 'Game'}/{rest}")
            count += 1
    with zipfile.ZipFile(symbols, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(STAGE / PDB, 'CvGameCore_Expansion2.pdb')
    sums = ''.join(f'{sha256(path)}  {path.name}\n' for path in (package, symbols))
    (OUT / (name + '-SHA256SUMS.txt')).write_text(sums, encoding='utf-8')
    print(json.dumps({'package': str(package), 'megabytes': round(package.stat().st_size / 2 ** 20, 1), 'files': count,
                      'commit': head, 'upstream': upstream, 'dll_sha256': manifest['dll']['sha256']}, indent=1))


if __name__ == '__main__': main()
