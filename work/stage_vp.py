"""Stage the exact VP 5.4.6 FullEUI payload without touching the installation.

Uses released modinfo metadata and validates its file/import list against civ5proj.
Only staged copies of file checksums are updated. Upstream source stays untouched.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
STAGE = WORK / 'staging' / 'vp-5.4.6-full-eui'
MODS = [
    '(1) Community Patch', '(2) Vox Populi',
    '(3a) VP - EUI Compatibility Files', '(4a) Squads for VP',
    '(5) Modpack Maker for VP',
]
USER_ROOT = Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5")
GAME_ROOT = Path(r"E:\SteamLibrary\steamapps\common\Sid Meier's Civilization V")
DLL_REL = '(1) Community Patch/CvGameCore_Expansion2.dll'
VERSION = '5.4.6'
COMMIT = 'dcb33a654cd9e8efb038a0733b4025e19cbcd8ba'
KNOWN_UPSTREAM_MISSING_ACTIONS = {
    '(1) Community Patch': ['Database Changes/Text/en_US/CoreGameOptionTextChanges.xml'],
}


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest().upper()


def contained(base, child):
    resolved = child.resolve()
    if resolved == base.resolve() or base.resolve() not in resolved.parents:
        raise ValueError(f'Path is outside intended parent: {child}')
    return resolved


def normalized(path):
    return path.replace('\\', '/')


def excluded(folder, relative):
    parts = Path(relative).parts
    name = parts[-1].lower()
    if folder in MODS[:2] and parts[0].lower() == 'lua':
        return True
    if Path(name).suffix in {'.civ5proj', '.civ5sln', '.civ5suo'}:
        return True
    if folder == MODS[0] and name == 'manual install.txt':
        return True
    if folder == MODS[1] and name in {'instructions.txt', 'promotion icons for vp.txt'}:
        return True
    if folder == MODS[2] and name == 'instructions.txt':
        return True
    return False


def copy_file(source, destination):
    source = source.resolve()
    destination = contained(STAGE, destination)
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        'staged_path': destination.relative_to(STAGE).as_posix(),
        'source': str(source),
        'source_sha256': digest(source),
        'sha256': digest(destination),
        'md5': digest(destination, 'md5'),
        'bytes': destination.stat().st_size,
    }


def source_specs():
    sys.path.insert(0, str(ROOT / 'scripts'))
    from generate_modinfo import parse_civ5proj
    specs = []
    for folder in MODS:
        base = ROOT / folder
        projects = list(base.glob('*.civ5proj'))
        infos = list(base.glob('*.modinfo'))
        assert len(projects) == len(infos) == 1, folder
        data = parse_civ5proj(projects[0])
        info = ET.parse(infos[0]).getroot()
        project_files = {normalized(x['path']): x['import'] for x in data['files']}
        release_files = {normalized(x.text): x.get('import') for x in info.find('Files')}
        assert len(project_files) == len(data['files']), f'Duplicate project files: {folder}'
        assert project_files == release_files, f'Project and released modinfo differ: {folder}'
        assert f'({VERSION})' in info.findtext('Properties/Teaser'), folder
        # The generator only reads the first PropertyGroup, so retain released properties.
        specs.append((folder, base, infos[0], info, project_files))
    return specs


def validate_modinfo(stage, folder, expected_exclusions):
    base = stage / 'user-data' / 'MODS' / folder
    info_path = next(base.glob('*.modinfo'))
    info = ET.parse(info_path).getroot()
    seen_missing = []
    verified = 0
    for entry in info.find('Files'):
        relative = normalized(entry.text)
        path = contained(base, base / relative)
        if not path.is_file():
            assert relative in expected_exclusions, f'Unexpected missing file: {folder}/{relative}'
            seen_missing.append(relative)
        else:
            assert digest(path, 'md5') == entry.get('md5'), f'MD5 mismatch: {path}'
            verified += 1
    assert set(seen_missing) == set(expected_exclusions), folder
    assert not (base / 'LUA').exists() if folder in MODS[:2] else True
    action_count = 0
    known_missing_actions = []
    for action in info.findall('Actions/*/*'):
        path = contained(base, base / normalized(action.text))
        if not path.is_file():
            relative = normalized(action.text)
            assert relative in KNOWN_UPSTREAM_MISSING_ACTIONS.get(folder, []), f'Missing action target: {path}'
            assert (base / relative).with_suffix('.sql').is_file(), 'Expected upstream SQL replacement absent'
            known_missing_actions.append(relative)
            continue
        action_count += 1
    entry_count = 0
    for entry in info.findall('EntryPoints/EntryPoint'):
        path = contained(base, base / normalized(entry.get('file')))
        assert path.is_file(), f'Missing entry point: {path}'
        entry_count += 1
    if folder == MODS[0]:
        assert info.findtext('Actions/OnGetDLLPath/SetDllPath') == 'CvGameCore_Expansion2.dll'
        assert info.findtext('Properties/ReloadAudioSystem') == '1'
    return {'mod': folder, 'files_verified': verified,
            'expected_eui_exclusions': len(seen_missing),
            'actions_verified': action_count, 'entrypoints_verified': entry_count,
            'known_upstream_missing_actions_preserved': known_missing_actions}


def verify_stage():
    manifest = json.loads((STAGE / 'deploy-manifest.json').read_text(encoding='utf-8'))
    for file in manifest['files']:
        path = contained(STAGE, STAGE / file['staged_path'])
        assert path.is_file() and digest(path) == file['sha256'], f'Payload mismatch: {path}'
    checks = [validate_modinfo(STAGE, folder, manifest['expected_excluded_files'][folder]) for folder in MODS]
    expected = {file['staged_path'] for file in manifest['files']}
    actual = {p.relative_to(STAGE).as_posix() for tree in ('user-data', 'game')
              for p in (STAGE / tree).rglob('*') if p.is_file()}
    assert expected == actual, f'Stale/unlisted payload: {actual - expected}'
    print(json.dumps({'status': 'verified', 'stage': str(STAGE), 'files': len(expected), 'checks': checks}, indent=2))


def stage_payload(dll_override=None, pdb_override=None):
    contained(WORK, STAGE)
    commit = subprocess.check_output(
        ['git', '-c', f'safe.directory={ROOT.as_posix()}', '-C', str(ROOT), 'rev-parse', 'HEAD'],
        text=True).strip()
    ancestry = subprocess.run(
        ['git', '-c', f'safe.directory={ROOT.as_posix()}', '-C', str(ROOT),
         'merge-base', '--is-ancestor', COMMIT, commit], check=False)
    assert ancestry.returncode == 0, f'Staging requires a descendant of Release-{VERSION}, found {commit}'
    STAGE.mkdir(parents=True, exist_ok=True)
    files = []
    exclusions = {}
    mappings = []
    templates = {}
    for folder, base, template, info, project_files in source_specs():
        target = STAGE / 'user-data' / 'MODS' / folder
        target.mkdir(parents=True, exist_ok=True)
        exclusions[folder] = []
        templates[str(template)] = digest(template)
        new_hashes = {}
        for relative in project_files:
            source = contained(base, base / relative)
            assert source.is_file(), f'Missing source file: {source}'
            if excluded(folder, relative):
                exclusions[folder].append(relative)
                # The official installer excludes these while retaining their metadata entries.
                new_hashes[relative] = digest(source, 'md5')
                continue
            if f'{folder}/{relative}' == DLL_REL and dll_override:
                source = dll_override.resolve()
            copied = copy_file(source, target / relative)
            files.append(copied)
            new_hashes[relative] = copied['md5']
        metadata = template.read_text(encoding='utf-8-sig')
        def update_hash(match):
            relative = normalized(match.group(3))
            return match.group(1) + new_hashes[relative] + match.group(2) + match.group(3) + match.group(4)
        metadata = re.sub(r'(<File md5=")[^"]+(" import="[01]">)([^<]+)(</File>)', update_hash, metadata)
        destination = contained(STAGE, target / template.name)
        destination.write_text(metadata, encoding='utf-8-sig', newline='\n')
        # Non-file XML is kept semantically identical to the release metadata.
        updated = ET.parse(destination).getroot()
        for name in ('Properties', 'Dependencies', 'References', 'Blocks', 'Actions', 'EntryPoints'):
            before = info.find(name)
            after = updated.find(name)
            assert (ET.tostring(before) if before is not None else None) == (ET.tostring(after) if after is not None else None), (folder, name)
        files.append({'staged_path': destination.relative_to(STAGE).as_posix(), 'source': str(template),
                      'source_sha256': templates[str(template)], 'transformation': 'refresh_file_md5_only',
                      'sha256': digest(destination), 'md5': digest(destination, 'md5'), 'bytes': destination.stat().st_size})
        mappings.append({'source_relative': f'user-data/MODS/{folder}',
                         'destination': str(USER_ROOT / 'MODS' / folder), 'kind': 'directory',
                         'deployment': 'replace_named_directory_after_backup'})
    if pdb_override:
        files.append(copy_file(pdb_override, STAGE / 'user-data' / 'MODS' / MODS[0] / 'CvGameCore_Expansion2.pdb'))
    for folder in ('UI_bc1', 'VPUI'):
        src = ROOT / folder
        dest = STAGE / 'game' / 'Assets' / 'DLC' / folder
        for source in sorted(src.rglob('*')):
            if source.is_file():
                files.append(copy_file(source, dest / source.relative_to(src)))
        mappings.append({'source_relative': f'game/Assets/DLC/{folder}',
                         'destination': str(GAME_ROOT / 'Assets' / 'DLC' / folder), 'kind': 'directory',
                         'deployment': 'replace_named_directory_after_backup'})
    singletons = [
        ('VPUI Text/VPUI_tips_en_us.xml', 'user-data/Text/VPUI_tips_en_us.xml', USER_ROOT / 'Text' / 'VPUI_tips_en_us.xml'),
        ('Expansion2_VoxPopuli.Civ5Pkg', 'game/Assets/DLC/Expansion2/Expansion2.Civ5Pkg', GAME_ROOT / 'Assets' / 'DLC' / 'Expansion2' / 'Expansion2.Civ5Pkg'),
        ('MinorCivSounds_VoxPopuli.xml', 'game/Assets/DLC/Expansion2/Sounds/XML/MinorCivSounds_VoxPopuli.xml', GAME_ROOT / 'Assets' / 'DLC' / 'Expansion2' / 'Sounds' / 'XML' / 'MinorCivSounds_VoxPopuli.xml'),
    ]
    for source, staged, destination in singletons:
        files.append(copy_file(ROOT / source, STAGE / staged))
        mappings.append({'source_relative': staged, 'destination': str(destination), 'kind': 'file',
                         'deployment': 'replace_file_after_backup'})
    for template, expected in templates.items():
        assert digest(Path(template)) == expected, f'Source metadata modified: {template}'
    dll = next(x for x in files if x['staged_path'] == 'user-data/MODS/' + DLL_REL)
    manifest = {
        'schema': 1, 'version': VERSION, 'component': 'FullEUI', 'source_commit': commit,
        'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'stage_root': str(STAGE),
        'method': 'Release civ5proj file lists and modinfo metadata, FullEUI VPSetupData.iss mapping; staged md5 refreshed',
        'dll': dll, 'mappings': mappings, 'expected_excluded_files': exclusions,
        'known_upstream_missing_actions_preserved': KNOWN_UPSTREAM_MISSING_ACTIONS,
        'cache_after_backup': str(USER_ROOT / 'cache'),
        'untouched': ['All custom mods outside the five named VP folders', 'Saves and ModdedSaves', 'config.ini', 'Source files'],
        'notes': ['This script stages only and never writes to the installed game or user-data directory.',
                  'CP/VP root LUA files intentionally absent per FullEUI mapping; their release metadata entries remain.',
                  'Replace only mapped directories; do not replace the whole MODS or Assets/DLC directories.',
                  'Source-provided release DLL is used unless --dll supplies the freshly compiled DLL.',
                  'Modpack Maker is staged as distributed but does not need enabling for a gameplay smoke test.',
                  'Upstream CP metadata incorrectly references CoreGameOptionTextChanges.xml although the existing file is .sql; preserved and reported, not fixed.'],
        'files': sorted(files, key=lambda x: x['staged_path']),
    }
    (STAGE / 'deploy-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    readme = (f'VP {VERSION} FullEUI staging\n\n'
              f'Source: {commit}\nDLL SHA256: {dll["sha256"]}\nDLL source: {dll["source"]}\n\n'
              'See deploy-manifest.json for exact destinations and file hashes. This is not an installer.\n'
              'Back up mapped folders/files before deployment. Leave all other mods, saves, and configuration untouched.\n'
              'Refresh with: python work/stage_vp.py --dll <built-DLL> [--pdb <matching-PDB>]\n'
              'Verify with: python work/stage_vp.py --verify\n')
    (STAGE / 'README.txt').write_text(readme, encoding='utf-8')
    verify_stage()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, help='Freshly built DLL to stage instead of upstream release binary')
    parser.add_argument('--pdb', type=Path, help='Optional matching debug symbols')
    parser.add_argument('--verify', action='store_true', help='Read-only validation of existing staging')
    args = parser.parse_args()
    if args.verify:
        verify_stage()
    else:
        stage_payload(args.dll, args.pdb)
