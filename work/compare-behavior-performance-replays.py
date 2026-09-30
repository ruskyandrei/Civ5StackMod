"""Compare completed same-save behavior replays using archived evidence only.

Checks both world-before/world-after player, unit, city and war rows plus the
ordered native PLAN, COMBAT*, CITY_CAPTURE, IMMEDIATE_CITY and capture-execution
records. Removes native clock prefixes and PLAN milliseconds only, and replaces
each archive's own native session ID with one marker. Other semantic fields,
ordering, duplicate events, damage, unit IDs, HP, movement and search counts stay.

Missing/empty census, incomplete native archives, unsafe stop proof or changed
source/preparation cannot qualify as agreement. Optional --output writes a new
derived JSON report; no game connection or save mutation. Exit0=agreement,
exit1=valid disagreement, exit2=invalid/incomplete input. Empty action categories
remain explicitly uncovered; this is not proof for other saved positions.
Recorded prepared views must match unless --allow-cross-view explicitly allows
that one controlled difference. Cross-view qualification requires recorded
actual mode on both sides; historical archives are labeled unknown, not guessed.
Sampled tactical-profiler controls are also reported separately. Recorded on/off
differences require --allow-cross-tactical-sampling for semantic comparison; such
runs explicitly differ in that recorded control. The equality field covers only
view and tactical sampling, not engine threading/configuration or log settings.
Historical unknown sampling is
accepted for ordinary semantics, never inferred to be off.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import tempfile

SESSION = re.compile(r'^STACKDIAG\|SESSION\|(.+)$')
RECORD = re.compile(r'^STACKDIAG\|(\d+)\|turn=(-?\d+)\|player=(-?\d+)\|([^|]+)\|(.*)$')
FIELD = re.compile(r'(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=([^\s;]+)')
PLAN_TIMING = re.compile(r'(?<!\S)milliseconds=-?\d+(?=\s|;|$)')
UNIT_COLUMNS = ('id', 'type', 'x', 'y', 'damage', 'maximumHP', 'moves', 'domain', 'baseMelee', 'baseRanged')
CITY_COLUMNS = ('id', 'name', 'originalOwner', 'x', 'y', 'damage', 'maximumHP', 'strength', 'population')
CITY_ACTIONS = ('IMMEDIATE_CITY', 'CAPTURE_ORDER', 'CAPTURE_RESULT', 'CAPTURE_FALLBACK')
SOURCE_FIELDS = ('SaveSHA256', 'StartTurn', 'StopTurn', 'ReturnPlayer', 'DiagnosticLevel', 'QuickCombat', 'QuickMovement')


class InvalidEvidence(ValueError):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidEvidence(f'{path}: {exc}') from exc


def array(value, label):
    if value == {}:
        return []
    if isinstance(value, list):
        return value
    raise InvalidEvidence(f'{label}: expected array (empty Lua{{}} accepted)')


def integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidEvidence(f'{label}: expected integer')
    return value


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def first_difference(before, after):
    for index in range(max(len(before), len(after))):
        left = before[index] if index < len(before) else None
        right = after[index] if index < len(after) else None
        if left != right:
            return dict(index=index, baseline=left, candidate=right)
    return None


def rows_comparison(before, after):
    return dict(counts=[len(before), len(after)], equal=before == after,
                first_difference=first_difference(before, after),
                baseline_only=sorted((Counter(before) - Counter(after)).elements())[:10],
                candidate_only=sorted((Counter(after) - Counter(before)).elements())[:10])


def world(path, expected_turn):
    data = read_json(path)
    if not isinstance(data, dict) or data.get('expectedTurn') != expected_turn:
        raise InvalidEvidence(f'{path.name}: census expectedTurn differs from manifest')
    columns = {}
    for key, required in (('unitColumns', UNIT_COLUMNS), ('cityColumns', CITY_COLUMNS)):
        values = array(data.get(key), path.name + ':' + key)
        if any(not isinstance(value, str) for value in values) or len(set(values)) != len(values) or not set(required).issubset(values):
            raise InvalidEvidence(f'{path.name}:{key}: missing/duplicate column definitions')
        columns[key] = values
    result = dict(players=[], units=[], cities=[], wars=[])
    seen_owners = set()
    for player in array(data.get('players'), path.name + ':players'):
        if not isinstance(player, dict):
            raise InvalidEvidence(f'{path.name}: invalid player row')
        owner = integer(player.get('owner'), 'player owner')
        if not 0 <= owner <= 63 or owner in seen_owners:
            raise InvalidEvidence(f'{path.name}: duplicate/invalid player owner {owner}')
        seen_owners.add(owner)
        if not isinstance(player.get('civilization'), str):
            raise InvalidEvidence(f'{path.name}: missing civilization')
        integer(player.get('team'), 'player team')
        for flag in ('human', 'minor', 'barbarian'):
            if not isinstance(player.get(flag), bool):
                raise InvalidEvidence(f'{path.name}: missing/invalid {flag} flag')
        # Retain all non-census metadata fields; do not silently discard additions.
        result['players'].append((owner, canonical({key: value for key, value in player.items() if key not in ('units', 'cities', 'wars')})))
        for kind, column_key in (('units', 'unitColumns'), ('cities', 'cityColumns')):
            seen_ids = set()
            for row in array(player.get(kind), f'{path.name}:owner{owner}:{kind}'):
                if not isinstance(row, list) or len(row) != len(columns[column_key]):
                    raise InvalidEvidence(f'{path.name}: malformed {kind} census row')
                values = dict(zip(columns[column_key], row))
                identity = integer(values['id'], kind + ' ID')
                if identity < 0 or identity in seen_ids:
                    raise InvalidEvidence(f'{path.name}: duplicate/invalid {kind} ID {owner}:{identity}')
                seen_ids.add(identity)
                for key in UNIT_COLUMNS if kind == 'units' else CITY_COLUMNS:
                    if key == 'name':
                        if not isinstance(values[key], str):
                            raise InvalidEvidence(f'{path.name}: invalid city name')
                    else:
                        integer(values[key], kind + ':' + key)
                result[kind].append((owner, identity, canonical(values)))
            # Empty lists are legal for an individual barbarian/cityless owner.
        opponents = array(player.get('wars'), f'{path.name}:owner{owner}:wars')
        seen_opponents = set()
        for other in opponents:
            integer(other, 'war opponent')
            if not 0 <= other <= 63 or other == owner or other in seen_opponents:
                raise InvalidEvidence(f'{path.name}: duplicate/invalid war opponent')
            seen_opponents.add(other)
            result['wars'].append((owner, other))
    for kind in result:
        result[kind].sort()
    if not result['players'] or not result['units'] or not result['cities']:
        raise InvalidEvidence(f'{path.name}: nonzero player/unit/city census required')
    return result


def source_proof(folder):
    manifest = read_json(folder / 'replay-manifest.json')
    if not isinstance(manifest, dict) or not str(manifest.get('Status', '')).startswith('completed'):
        raise InvalidEvidence(f'{folder}: replay has no completed manifest')
    missing = [field for field in SOURCE_FIELDS if field not in manifest]
    if missing:
        raise InvalidEvidence(f'{folder}: missing manifest fields {missing}')
    save_sha = manifest['SaveSHA256']
    if not isinstance(save_sha, str) or not re.fullmatch(r'[0-9A-Fa-f]{64}', save_sha) or manifest.get('SaveSHA256After', '').upper() != save_sha.upper():
        raise InvalidEvidence(f'{folder}: preserved-source SHA proof missing or changed')
    start, stop, returning = [integer(manifest[key], key) for key in ('StartTurn', 'StopTurn', 'ReturnPlayer')]
    if not 0 <= start < stop or not 0 <= returning <= 63:
        raise InvalidEvidence(f'{folder}: invalid bounded turn interval/return player')
    prepared, stopped = manifest.get('Prepared'), manifest.get('Stopped', {})
    # A safe --resume-prepared recovery can finish a replay whose first
    # preparation validation failed before manifest.Prepared was assigned.
    # Its verified paused state remains explicit in the resume history.
    if prepared is None:
        resumes = array(manifest.get('ResumeAttempts', []), 'ResumeAttempts')
        prepared = resumes[-1].get('verified', {}) if resumes else {}
    if not isinstance(prepared, dict) or not isinstance(stopped, dict):
        raise InvalidEvidence(f'{folder}: invalid preparation/stop proof')
    if not (prepared.get('turn') == start and prepared.get('autoplay') == stop-start
            and prepared.get('observer') is True and isinstance(prepared.get('activePlayer'), int)
            and prepared.get('pausePlayer') == prepared.get('activePlayer')
            and prepared.get('diagnostics') == manifest['DiagnosticLevel']
            and prepared.get('quickCombat') is manifest['QuickCombat']
            and prepared.get('quickMovement') is manifest['QuickMovement']):
        raise InvalidEvidence(f'{folder}: missing exact paused observer preparation')
    if not (stopped.get('turn') == stop and stopped.get('autoplay') == 0 and stopped.get('activePlayer') == returning
            and stopped.get('human') is True and stopped.get('observer') is False and stopped.get('returnPlayerAlive') is True):
        raise InvalidEvidence(f'{folder}: missing exact bounded human-stop proof')
    run = manifest.get('NativeRun')
    if not isinstance(run, str) or not re.fullmatch(r'[\w-]+', run):
        raise InvalidEvidence(f'{folder}: NativeRun missing/invalid')
    dll_sha = manifest.get('SHA256', '')
    if not isinstance(dll_sha, str) or not re.fullmatch(r'[0-9A-Fa-f]{64}', dll_sha) or dll_sha.upper() != str(manifest.get('ExpectedDLLSHA256', '')).upper():
        raise InvalidEvidence(f'{folder}: loaded DLL SHA proof missing/mismatched')
    metadata = {key: manifest[key] for key in SOURCE_FIELDS}
    metadata['SourceMode'] = manifest.get('SourceMode', 'observer')
    if metadata['SourceMode'] not in ('observer', 'human'):
        raise InvalidEvidence(f'{folder}: unsupported source mode')
    if metadata['SourceMode'] == 'human' and not (
            prepared.get('sourceMode') == 'human' and prepared.get('sourceActivePlayer') == returning
            and prepared.get('restoredAutoplay') == 0):
        raise InvalidEvidence(f'{folder}: missing explicit human-source transition proof')
    metadata['SaveSHA256'] = save_sha.upper()
    mods = array(manifest.get('EnabledMods'), 'EnabledMods')
    if not mods:
        raise InvalidEvidence(f'{folder}: enabled-mod evidence missing')
    metadata['EnabledMods'] = sorted((str(mod['ModID']).lower(), integer(mod['Version'], 'mod version')) for mod in mods)
    if len({mod[0] for mod in metadata['EnabledMods']}) != len(mods):
        raise InvalidEvidence(f'{folder}: duplicate enabled-mod identities')
    return manifest, metadata


def native(folder, manifest):
    run = manifest['NativeRun']
    segments = {}
    for path in (folder / 'native-segments').glob('*.log'):
        with path.open(encoding='utf-8-sig') as stream:
            match = SESSION.fullmatch(stream.readline().rstrip('\r\n'))
        if not match:
            continue
        header = dict(FIELD.findall(match[1]))
        if header.get('run') != run:
            continue
        try:
            number = int(header['segment'])
        except (ValueError, KeyError) as exc:
            raise InvalidEvidence(f'{path}: invalid native segment header') from exc
        if number not in segments or path.stat().st_size > segments[number].stat().st_size:
            segments[number] = path
    numbers = sorted(segments)
    if not numbers or numbers != list(range(numbers[-1] + 1)):
        raise InvalidEvidence(f'{folder}: missing/noncontiguous native segments {numbers}')
    records = []
    for number in numbers:
        with segments[number].open(encoding='utf-8-sig') as stream:
            next(stream)
            for index, line in enumerate(stream, 2):
                if not line.endswith('\n'):
                    raise InvalidEvidence(f'{segments[number]}:{index}: incomplete native tail')
                match = RECORD.fullmatch(line.rstrip('\r\n'))
                if not match:
                    if line.strip():
                        raise InvalidEvidence(f'{segments[number]}:{index}: malformed native record')
                    continue
                category = match[4]
                if not (category == 'PLAN' or category == 'COMBAT' or category.startswith('COMBAT_')
                        or category == 'CITY_CAPTURE' or category in CITY_ACTIONS):
                    continue
                detail = match[5]
                if category == 'PLAN':
                    detail = PLAN_TIMING.sub('', detail).strip()
                detail = detail.replace(run, '{NATIVE_RUN}')
                records.append((int(match[2]), int(match[3]), category, detail))
    if not any(record[2] == 'PLAN' for record in records):
        raise InvalidEvidence(f'{folder}: no semantic PLAN evidence')
    return records, numbers


def sampling_evidence(folder, manifest, prepared):
    requested = manifest.get('TacticalSamplingMode', 'preserve')
    if requested not in ('preserve', 'off', 'on'):
        raise InvalidEvidence(f'{folder}: invalid requested tactical sampling mode')
    if ('tacticalSamplingRequested' in prepared
            and prepared['tacticalSamplingRequested'] != requested):
        raise InvalidEvidence(f'{folder}: prepared tactical sampling request differs from manifest')
    available = prepared.get('tacticalSamplingAPIAvailable')
    valid = prepared.get('tacticalSamplingValueValid')
    actual = prepared.get('tacticalSampling')
    for flag in (available, valid):
        if flag is not None and type(flag) is not bool:
            raise InvalidEvidence(f'{folder}: invalid tactical sampling API/value flag')
    known = valid is True and type(actual) is bool
    if (valid is True and not known) or (available is True and not known):
        raise InvalidEvidence(f'{folder}: tactical sampling API lacks a boolean result')
    if valid is False and actual is not None:
        raise InvalidEvidence(f'{folder}: invalid tactical sampling result marked known')
    if requested != 'preserve' and (not known or available is not True or actual is not (requested == 'on')):
        raise InvalidEvidence(f'{folder}: explicit tactical sampling request lacks actual paused proof')
    for field, value in (('TacticalSamplingAPIAvailable', available), ('TacticalSamplingPrepared', actual),
                         ('TacticalSamplingOriginal', prepared.get('tacticalSamplingOriginal'))):
        if field in manifest and manifest[field] != value:
            raise InvalidEvidence(f'{folder}: inconsistent {field} evidence')
    stopped = manifest.get('Stopped', {})
    stop_value = stopped.get('tacticalSampling')
    if known and not (stopped.get('tacticalSamplingValueValid') is True
                     and type(stop_value) is bool and stop_value is actual
                     and stopped.get('tacticalSamplingAPIAvailable') is available):
        raise InvalidEvidence(f'{folder}: tactical sampling changed or lacks final status proof')
    if 'TacticalSamplingStopped' in manifest and manifest['TacticalSamplingStopped'] != stop_value:
        raise InvalidEvidence(f'{folder}: inconsistent stopped tactical sampling evidence')
    return dict(requested=requested, recorded=known, api_available=available,
                enabled=actual if known else None, original=prepared.get('tacticalSamplingOriginal'),
                stopped=stop_value, provenance='recorded_boolean' if known else 'unknown')


def read(folder):
    folder = Path(folder)
    manifest, metadata = source_proof(folder)
    snapshots = {stage: world(folder / f'world-{stage}.json', manifest['StartTurn' if stage == 'before' else 'StopTurn']) for stage in ('before', 'after')}
    records, segments = native(folder, manifest)
    prepared = manifest.get('Prepared')
    if prepared is None:
        resumes = manifest.get('ResumeAttempts', [])
        prepared = resumes[-1].get('verified', {}) if resumes else {}
    requested = manifest.get('ViewMode', 'preserve')
    if requested not in ('preserve', 'standard', 'strategic'):
        raise InvalidEvidence(f'{folder}: invalid requested view mode')
    actual = prepared.get('strategicView')
    known = prepared.get('viewAPIAvailable') is True and type(actual) is bool
    late = manifest.get('ViewPreparation')
    if late is not None:
        if (not isinstance(late, dict) or late.get('semantics') != 'late_paused_view_preparation'
                or late.get('viewModeRequested') != requested
                or any(late.get(key) != prepared.get(key) for key in
                       ('turn', 'activePlayer', 'pausePlayer', 'autoplay', 'viewAPIAvailable', 'strategicView'))):
            raise InvalidEvidence(f'{folder}: late view proof differs from final paused preparation')
        initial = manifest.get('PreparedInitial')
        if not isinstance(initial, dict) or initial.get('viewModeOriginal') != prepared.get('viewModeOriginal'):
            raise InvalidEvidence(f'{folder}: initial/final original view evidence differs')
    elif 'PreparedInitial' in manifest:
        raise InvalidEvidence(f'{folder}: final prepared view lacks late-apply proof')
    if requested != 'preserve' and (not known or actual is not (requested == 'strategic')):
        raise InvalidEvidence(f'{folder}: explicit requested view lacks actual paused preparation proof')
    for key, value in (('ViewModeOriginal', prepared.get('viewModeOriginal')),
                       ('ViewModePrepared', actual)):
        if key in manifest and manifest[key] != value:
            raise InvalidEvidence(f'{folder}: inconsistent {key} evidence')
    view = dict(requested=requested, recorded=known, strategic=actual if known else None,
                original=prepared.get('viewModeOriginal'), stopped=manifest.get('Stopped', {}).get('strategicView'),
                late_preparation_recorded=late is not None,
                preparation_provenance='late_verified' if late is not None else 'historical_recorded_preparation')
    sampling = sampling_evidence(folder, manifest, prepared)
    return dict(manifest=manifest, metadata=metadata, view=view, sampling=sampling,
                snapshots=snapshots, records=records, segments=segments)


def compare(baseline, candidate, allow_cross_view=False, allow_cross_tactical_sampling=False):
    before, after = read(baseline), read(candidate)
    views_known = before['view']['recorded'] and after['view']['recorded']
    views_equal = before['view']['strategic'] == after['view']['strategic'] if views_known else None
    if allow_cross_view and not views_known:
        raise InvalidEvidence('Cross-view comparison requires recorded actual prepared modes on both sides; use a fresh control')
    sampling_known = before['sampling']['recorded'] and after['sampling']['recorded']
    sampling_equal = before['sampling']['enabled'] == after['sampling']['enabled'] if sampling_known else None
    if allow_cross_tactical_sampling and not sampling_known:
        raise InvalidEvidence('Cross-sampling comparison requires recorded actual boolean controls on both sides; use a fresh control')
    census = {}
    for stage in ('before', 'after'):
        census[stage] = {kind: rows_comparison(before['snapshots'][stage][kind], after['snapshots'][stage][kind]) for kind in ('players', 'units', 'cities', 'wars')}
        census[stage]['all_rows_equal'] = all(census[stage][kind]['equal'] for kind in ('players', 'units', 'cities', 'wars'))
    left, right = before['records'], after['records']
    categories = sorted(set(record[2] for record in left+right) | set(CITY_ACTIONS) | {'PLAN', 'COMBAT_SUMMARY', 'CITY_CAPTURE'})
    per_category = {}
    for category in categories:
        a, b = [row for row in left if row[2] == category], [row for row in right if row[2] == category]
        per_category[category] = dict(counts=[len(a), len(b)], sequence_equal=a == b, first_difference=first_difference(a, b), covered=bool(a and b))
    source_equal = (before['metadata'] == after['metadata'] and (views_equal is not False or allow_cross_view)
                    and (sampling_equal is not False or allow_cross_tactical_sampling))
    view_and_tactical_sampling_controls_equal = (False if views_equal is False or sampling_equal is False else
                                                 True if views_equal is True and sampling_equal is True else None)
    return dict(schema=1, baseline=before['manifest']['NativeRun'], candidate=after['manifest']['NativeRun'],
                loadedDLLSHA256=[before['manifest']['SHA256'], after['manifest']['SHA256']], source_and_preparation_equal=source_equal,
                source_metadata=[before['metadata'], after['metadata']], snapshots=census,
                view_comparison=dict(recorded_on_both_sides=views_known, actual_modes_equal=views_equal,
                    explicit_cross_view_allowed=allow_cross_view, intentional_cross_view=allow_cross_view and views_equal is False,
                    evidence=[before['view'], after['view']]),
                tactical_sampling_comparison=dict(recorded_on_both_sides=sampling_known,
                    actual_controls_equal=sampling_equal, explicit_cross_sampling_allowed=allow_cross_tactical_sampling,
                    intentional_cross_sampling=allow_cross_tactical_sampling and sampling_equal is False,
                    evidence=[before['sampling'], after['sampling']]),
                view_and_tactical_sampling_controls_equal=view_and_tactical_sampling_controls_equal,
                native_semantics=dict(record_counts=[len(left), len(right)], segment_numbers=[before['segments'], after['segments']],
                                      sequence_equal=left == right, first_difference=first_difference(left, right), categories=per_category),
                before_census_equal=census['before']['all_rows_equal'], after_census_equal=census['after']['all_rows_equal'],
                all_compared_semantics_equal=source_equal and census['before']['all_rows_equal'] and census['after']['all_rows_equal'] and left == right,
                limits='Exact retained snapshot/semantic comparison for this bounded replay only. UTC/PID/native clock prefixes and PLAN milliseconds are excluded; own run IDs normalized. '
                       'Other semantic fields and event ordering retained. No empty-census equivalence; uncovered categories are not exercised-branch evidence. '
                       'World snapshots are expected-turn tags supported by prepared/stopped manifest proof. Unrecorded historical view modes remain unknown; ordinary comparisons do not establish view equality in that case. '
                       'Explicit cross-view allowance excludes only the recorded prepared-view difference; all source/census/native requirements remain. '
                       'Explicit cross-sampling allowance excludes only the recorded sampled-profiler difference for semantics. Unknown historical sampling is not assumed off. '
                       'view_and_tactical_sampling_controls_equal covers only those two recorded controls; engine threading/configuration/log settings are not checked and engine-config equality is not established. '
                       'Source and final return-player turns may be partial; this tool does not compare wall performance or unrecorded game state.')


def self_test():
    with tempfile.TemporaryDirectory(prefix='civ5-behavior-comparison-') as temporary:
        a, b = Path(temporary)/'a', Path(temporary)/'b'
        def write(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding='utf-8')
        manifest = dict(Status='completed_closed', SaveSHA256='A'*64, SaveSHA256After='A'*64, StartTurn=250, StopTurn=252, ReturnPlayer=0,
                        DiagnosticLevel=1, QuickCombat=True, QuickMovement=True, SHA256='B'*64, ExpectedDLLSHA256='B'*64,
                        EnabledMods=[dict(ModID='fixture-mod', Version=1)],
                        Prepared=dict(turn=250, autoplay=2, observer=True, activePlayer=8, pausePlayer=8, diagnostics=1, quickCombat=True, quickMovement=True),
                        Stopped=dict(turn=252, autoplay=0, activePlayer=0, human=True, observer=False, returnPlayerAlive=True))
        snapshot = dict(expectedTurn=250, unitColumns=list(UNIT_COLUMNS), cityColumns=list(CITY_COLUMNS),
                        players=[dict(owner=0, civilization='CIV0', team=0, human=False, minor=False, barbarian=False,
                                      units=[[1,3,2,4,5,100,120,2,10,0],[2,4,3,5,0,100,60,2,0,15]],
                                      cities=[[7,'Fixture',0,2,4,0,400,2500,9]], wars=[]),
                                 dict(owner=63, civilization='BARB', team=63, human=False, minor=False, barbarian=True, units={}, cities={}, wars={})])
        for directory, run, milliseconds in ((a, 'Stacking-a', 50), (b, 'Stacking-b', 15)):
            write(directory/'replay-manifest.json', dict(manifest, NativeRun=run))
            for stage, turn in (('before',250),('after',252)):
                value=copy.deepcopy(snapshot);value['expectedTurn']=turn
                if stage=='after':value['players'][0]['human']=True
                if directory==b:value['players'].reverse();value['players'][-1]['units'].reverse()
                write(directory/f'world-{stage}.json',value)
            log=f'STACKDIAG|SESSION|run={run} segment=0 build=fixture level=1\nSTACKDIAG|100|turn=251|player=0|PLAN|target=2:4 states=8 assignments=2 milliseconds={milliseconds} origin={run}\nSTACKDIAG|101|turn=251|player=0|COMBAT_SUMMARY|combat=1 rolledPrimary=20 cityHPAfter=1\nSTACKDIAG|102|turn=251|player=0|IMMEDIATE_CITY|target=354 action=capture_after_fire\nSTACKDIAG|103|turn=251|player=0|CAPTURE_ORDER|target=354 unit=1\nSTACKDIAG|104|turn=251|player=0|CAPTURE_RESULT|target=354 captured=1\nSTACKDIAG|105|turn=251|player=0|CITY_CAPTURE|plot=354 oldOwner=1 newOwner=0\n'
            (directory/'native-segments').mkdir();(directory/'native-segments'/'segment0.log').write_text(log,encoding='utf-8')
            (directory/'native-segments'/'rolling-copy.log').write_text(log,encoding='utf-8')
        equal=compare(a,b);assert equal['all_compared_semantics_equal'] and equal['native_semantics']['record_counts']==[6,6]
        assert equal['view_comparison']['recorded_on_both_sides'] is False
        try: compare(a,b,True)
        except InvalidEvidence as exc: assert 'fresh control' in str(exc)
        else: raise AssertionError('Unknown historical view admitted as controlled cross-view')
        for directory, run in ((a,'Stacking-a'),(b,'Stacking-b')):
            recorded=copy.deepcopy(manifest)
            recorded.update(NativeRun=run,ViewMode='standard',ViewModeOriginal=False,ViewModePrepared=False)
            recorded['Prepared'].update(viewAPIAvailable=True,strategicView=False,viewModeOriginal=False)
            write(directory/'replay-manifest.json',recorded)
        assert compare(a,b)['all_compared_semantics_equal']
        strategic=read_json(b/'replay-manifest.json')
        strategic.update(ViewMode='strategic',ViewModePrepared=True)
        strategic['Prepared']['strategicView']=True
        write(b/'replay-manifest.json',strategic)
        assert not compare(a,b)['all_compared_semantics_equal']
        allowed=compare(a,b,True)
        assert allowed['all_compared_semantics_equal'] and allowed['view_comparison']['intentional_cross_view']
        late_version=copy.deepcopy(strategic)
        late_version['PreparedInitial']=copy.deepcopy(late_version['Prepared'])
        late_version['PreparedInitial']['strategicView']=False
        late_version['ViewPreparation']={key:late_version['Prepared'][key] for key in
            ('turn','activePlayer','pausePlayer','autoplay','viewAPIAvailable','strategicView')}
        late_version['ViewPreparation'].update(semantics='late_paused_view_preparation',viewModeRequested='strategic',before=False,toggled=True)
        write(b/'replay-manifest.json',late_version)
        late_equal=compare(a,b,True)
        assert late_equal['all_compared_semantics_equal'] and late_equal['view_comparison']['evidence'][1]['late_preparation_recorded']
        late_version['ViewPreparation']['strategicView']=False;write(b/'replay-manifest.json',late_version)
        try: compare(a,b,True)
        except InvalidEvidence: pass
        else: raise AssertionError('Initial immediate mode overrode mismatched final late proof')
        strategic['QuickMovement']=False;strategic['Prepared']['quickMovement']=False
        write(b/'replay-manifest.json',strategic)
        assert not compare(a,b,True)['source_and_preparation_equal']
        strategic['QuickMovement']=True;strategic['Prepared']['quickMovement']=True
        strategic['Prepared']['strategicView']=False;write(b/'replay-manifest.json',strategic)
        try: compare(a,b,True)
        except InvalidEvidence: pass
        else: raise AssertionError('Explicit view request without matching actual view admitted')
        for directory, run in ((a,'Stacking-a'),(b,'Stacking-b')):
            write(directory/'replay-manifest.json',dict(manifest,NativeRun=run))
        assert compare(a,b)['tactical_sampling_comparison']['recorded_on_both_sides'] is False
        assert compare(a,b)['view_and_tactical_sampling_controls_equal'] is None
        try: compare(a,b,allow_cross_tactical_sampling=True)
        except InvalidEvidence as exc: assert 'fresh control' in str(exc)
        else: raise AssertionError('Historical unknown sampling admitted as controlled difference')
        def with_sampling(run, mode, enabled):
            value=copy.deepcopy(manifest)
            value.update(NativeRun=run, ViewMode='standard', ViewModeOriginal=False, ViewModePrepared=False,
                TacticalSamplingMode=mode, TacticalSamplingAPIAvailable=True, TacticalSamplingPrepared=enabled,
                TacticalSamplingOriginal=enabled if mode=='preserve' else False, TacticalSamplingStopped=enabled)
            value['Prepared'].update(viewAPIAvailable=True, strategicView=False, viewModeOriginal=False,
                tacticalSamplingRequested=mode,tacticalSamplingAPIAvailable=True,tacticalSamplingValueValid=True,
                tacticalSampling=enabled,tacticalSamplingOriginal=value['TacticalSamplingOriginal'])
            value['Stopped'].update(tacticalSamplingRequested=mode,tacticalSamplingAPIAvailable=True,
                tacticalSamplingValueValid=True,tacticalSampling=enabled)
            return value
        for directory, run in ((a,'Stacking-a'),(b,'Stacking-b')):
            write(directory/'replay-manifest.json',with_sampling(run,'off',False))
        controlled=compare(a,b)
        assert controlled['all_compared_semantics_equal'] and controlled['view_and_tactical_sampling_controls_equal'] is True
        assert controlled['tactical_sampling_comparison']['actual_controls_equal'] is True
        on=with_sampling('Stacking-b','on',True);write(b/'replay-manifest.json',on)
        different=compare(a,b)
        assert not different['all_compared_semantics_equal'] and different['view_and_tactical_sampling_controls_equal'] is False
        allowed=compare(a,b,allow_cross_tactical_sampling=True)
        assert allowed['all_compared_semantics_equal'] and allowed['view_and_tactical_sampling_controls_equal'] is False
        assert allowed['tactical_sampling_comparison']['intentional_cross_sampling'] is True
        changed=copy.deepcopy(on);changed['QuickMovement']=False;changed['Prepared']['quickMovement']=False
        write(b/'replay-manifest.json',changed)
        assert not compare(a,b,allow_cross_tactical_sampling=True)['source_and_preparation_equal']
        invalid_cases=[]
        changed=copy.deepcopy(on);changed['Prepared']['tacticalSampling']=False;invalid_cases.append(changed)
        changed=copy.deepcopy(on);changed['Prepared']['tacticalSampling']=1;invalid_cases.append(changed)
        changed=copy.deepcopy(on);changed['Stopped']['tacticalSampling']=False;invalid_cases.append(changed)
        changed=copy.deepcopy(on);changed['Prepared'].pop('tacticalSamplingValueValid');invalid_cases.append(changed)
        changed=copy.deepcopy(on);changed['TacticalSamplingPrepared']=False;invalid_cases.append(changed)
        for changed in invalid_cases:
            write(b/'replay-manifest.json',changed)
            try: compare(a,b,allow_cross_tactical_sampling=True)
            except InvalidEvidence: pass
            else: raise AssertionError('Invalid/changed tactical sampling evidence admitted')
        write(b/'replay-manifest.json',with_sampling('Stacking-b','preserve',False))
        assert compare(a,b)['all_compared_semantics_equal'] and compare(a,b)['view_and_tactical_sampling_controls_equal'] is True
        absent=copy.deepcopy(manifest);absent.update(NativeRun='Stacking-b',TacticalSamplingMode='preserve',
            TacticalSamplingAPIAvailable=False,TacticalSamplingPrepared=None,TacticalSamplingOriginal=None,TacticalSamplingStopped=None)
        absent['Prepared'].update(tacticalSamplingRequested='preserve',tacticalSamplingAPIAvailable=False,tacticalSamplingValueValid=False)
        write(b/'replay-manifest.json',absent)
        assert compare(a,b)['all_compared_semantics_equal'] and compare(a,b)['view_and_tactical_sampling_controls_equal'] is None
        absent['TacticalSamplingMode']='off';absent['Prepared']['tacticalSamplingRequested']='off'
        write(b/'replay-manifest.json',absent)
        try: compare(a,b)
        except InvalidEvidence: pass
        else: raise AssertionError('Explicit off admitted old API omission')
        for directory, run in ((a,'Stacking-a'),(b,'Stacking-b')):
            write(directory/'replay-manifest.json',dict(manifest,NativeRun=run))
        human=read_json(b/'replay-manifest.json');human['SourceMode']='human'
        human['Prepared'].update(sourceMode='human',sourceActivePlayer=0,restoredAutoplay=0)
        write(b/'replay-manifest.json',human)
        assert not compare(a,b)['source_and_preparation_equal']
        human['Prepared']['sourceActivePlayer']=1;write(b/'replay-manifest.json',human)
        try: compare(a,b)
        except InvalidEvidence: pass
        else: raise AssertionError('Unproven human-source transition admitted')
        write(b/'replay-manifest.json',dict(manifest,NativeRun='Stacking-b'))
        recovered=read_json(b/'replay-manifest.json');recovered['ResumeAttempts']=[dict(verified=recovered.pop('Prepared'))];write(b/'replay-manifest.json',recovered)
        assert compare(a,b)['all_compared_semantics_equal']
        unitfile=b/'world-after.json';saved=read_json(unitfile);changed=copy.deepcopy(saved);changed['players'][-1]['units'][0][4]=9;write(unitfile,changed)
        assert not compare(a,b)['after_census_equal'];write(unitfile,saved)
        empty=copy.deepcopy(saved)
        for player in empty['players']:player['units']={};player['cities']={}
        write(unitfile,empty)
        try:compare(a,b)
        except InvalidEvidence:pass
        else:raise AssertionError('Empty census admitted')
        write(unitfile,saved)
        duplicate=copy.deepcopy(saved);duplicate['players'][-1]['units'].append(duplicate['players'][-1]['units'][0]);write(unitfile,duplicate)
        try:compare(a,b)
        except InvalidEvidence:pass
        else:raise AssertionError('Duplicate unit admitted')
        write(unitfile,saved)
        for path in (b/'native-segments').glob('*.log'):
            path.write_text(path.read_text().replace('states=8','states=9'),encoding='utf-8')
        assert not compare(a,b)['native_semantics']['sequence_equal']
        for path in (b/'native-segments').glob('*.log'):
            path.write_text(path.read_text().replace('states=9','states=8').replace('cityHPAfter=1','cityHPAfter=2'),encoding='utf-8')
        assert not compare(a,b)['all_compared_semantics_equal']
        for path in (b/'native-segments').glob('*.log'):
            path.write_text(path.read_text().replace('cityHPAfter=2','cityHPAfter=1').rstrip('\n'),encoding='utf-8')
        try:compare(a,b)
        except InvalidEvidence:pass
        else:raise AssertionError('Truncated native admitted')
    print(json.dumps(dict(ok=True, offline=True, gameCalls=0, checks='source/stop proof, before/after sorted nonzero census, duplicate rejection, timing/run-ID normalization, segment deduplication, PLAN/combat mismatches, truncated-log rejection, sampling known/unknown/explicit controls and intentional cross-sampling distinction')))


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('baseline',type=Path,nargs='?')
    parser.add_argument('candidate',type=Path,nargs='?')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--allow-cross-view',action='store_true',help='Allow only a recorded actual prepared-view difference; both archives must record mode')
    parser.add_argument('--allow-cross-tactical-sampling',action='store_true',help='Allow only a recorded sampled-profiler difference for semantics; both controls must be known, engine settings remain unchecked')
    args=parser.parse_args()
    if args.self_test:self_test();return 0
    if args.baseline is None or args.candidate is None:parser.error('baseline and candidate run directories required')
    if args.output and (args.output.suffix.lower()!='.json' or args.output.name in ('replay-manifest.json','world-before.json','world-after.json') or args.output.parent.name=='native-segments'):
        parser.error('--output must be a derived .json, not an archived input')
    try:result=compare(args.baseline,args.candidate,args.allow_cross_view,args.allow_cross_tactical_sampling)
    except (InvalidEvidence,OSError,UnicodeError,KeyError,TypeError,ValueError) as exc:
        result=dict(ok=False,all_compared_semantics_equal=False,error=str(exc));exit_code=2
    else:exit_code=0 if result['all_compared_semantics_equal'] else 1
    rendered=json.dumps(result,indent=2,ensure_ascii=True)+'\n'
    if args.output:args.output.write_text(rendered,encoding='utf-8')
    print(rendered,end='')
    return exit_code


if __name__=='__main__':
    raise SystemExit(main())
