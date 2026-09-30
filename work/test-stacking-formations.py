"""Execute actual formation SQL against source XML, without starting Civ V."""
from pathlib import Path
import hashlib, json, sqlite3, xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
cp = root / '(1) Community Patch'
sql_path = cp / 'Database Changes/StackingFormations.sql'
sql = sql_path.read_text(encoding='utf-8-sig')
config = ET.parse(cp / 'Database Changes/StackingConfig.xml')
slots = ET.parse(cp / 'Database Changes/Units/CoreNewUnitFormations.xml')
names = ['MUFORMATION_SMALL_CITY_ATTACK_FORCE', 'MUFORMATION_BASIC_CITY_ATTACK_FORCE', 'MUFORMATION_BIGGER_CITY_ATTACK_FORCE']
settings = {r.attrib['Name']: int(r.attrib['Value']) for r in config.findall('./Stacking_Settings/Row')}
base = [(r.findtext('MultiUnitFormationType'), r.findtext('PrimaryUnitType'), r.findtext('SecondaryUnitType'),
         r.findtext('MultiUnitPositionType'), int(r.findtext('RequiredSlot') == 'true'))
        for r in slots.findall('./MultiUnitFormation_SlotEntries/Row')]
checks = 0

def check(ok, label):
    global checks
    checks += 1
    assert ok, label

def run(overrides=None):
    db = sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE Stacking_Settings(Name TEXT,Value INTEGER); CREATE TABLE MultiUnitFormations(Type TEXT);'
                     'CREATE TABLE MultiUnitFormation_SlotEntries(MultiUnitFormationType TEXT, PrimaryUnitType TEXT,'
                     'SecondaryUnitType TEXT, MultiUnitPositionType TEXT, RequiredSlot INTEGER);')
    values = settings | (overrides or {})
    db.executemany('INSERT INTO Stacking_Settings VALUES (?,?)', values.items())
    db.executemany('INSERT INTO MultiUnitFormations VALUES (?)', [(n,) for n in names])
    db.executemany('INSERT INTO MultiUnitFormation_SlotEntries VALUES (?,?,?,?,?)', base)
    db.executescript(sql)
    return db.execute('SELECT * FROM MultiUnitFormation_SlotEntries').fetchall()

result = run()
for name, extra in zip(names, [6, 8, 10]):
    original = [r for r in base if r[0] == name]
    expanded = [r for r in result if r[0] == name]
    added = expanded[len(original):]
    check(len(expanded) == len(original) + extra, name + ' configurable expansion')
    check(sum(r[4] for r in expanded) == sum(r[4] for r in original), name + ' required core preserved')
    check(sum(r[1] == 'UNITAI_CITY_BOMBARD' for r in added) == extra // 2, name + ' extra real siege slots')
    check(all(r[2] == 'UNITAI_CITY_BOMBARD' for r in added if r[1] == 'UNITAI_CITY_BOMBARD'), name + ' added siege cannot substitute archers')
check(run({'Enabled': 0}) == base, 'stacking disabled retains original formations')
slot_settings = [n for n in settings if n.endswith('Slots') and n.startswith('AIAssault')]
check(run(dict.fromkeys(slot_settings, 0)) == base, 'XML can disable all extra slots')
custom = run({'AIAssaultSmallExtraSiegeSlots': 8, 'AIAssaultSmallExtraFrontSlots': 0})
check(sum(r[0] == names[0] for r in custom) == sum(r[0] == names[0] for r in base) + 8, 'custom role counts applied')
bounded = run({'AIAssaultSmallExtraSiegeSlots': 1000, 'AIAssaultSmallExtraFrontSlots': -4})
check(sum(r[0] == names[0] for r in bounded) == sum(r[0] == names[0] for r in base) + 8, 'SQL bounds match XML supported slot range')
check([r for r in result if r[0] not in names] == [r for r in base if r[0] not in names], 'other formations unchanged')
modinfo = ET.parse(cp / '(1) Community Patch (v 151).modinfo')
updates = [e.text.replace('\\', '/') for e in modinfo.findall('./Actions/OnModActivated/UpdateDatabase')]
check(updates.index('Database Changes/StackingFormations.sql') > updates.index('Database Changes/StackingConfig.xml'), 'formation SQL runs after XML settings')
check(any(e.text == 'Database Changes/StackingFormations.sql' for e in modinfo.findall('./Files/File')), 'formation SQL included in mod package')
project=ET.parse(cp / 'Community Patch.civ5proj')
ns={'p':'http://schemas.microsoft.com/developer/msbuild/2003'}
check(any(e.attrib.get('Include','').replace('\\','/') == 'Database Changes/StackingFormations.sql' for e in project.findall('./p:ItemGroup/p:Content',ns)), 'formation SQL included in project content')
check(any(e.text.replace('\\','/') == 'Database Changes/StackingFormations.sql' for e in project.findall('./p:PropertyGroup/p:ModActions/p:Action/p:FileName',ns)), 'formation SQL registered in project database actions')
out = root / 'work/formation-regression'
out.mkdir(exist_ok=True)
(out / 'result.json').write_text(json.dumps({'checks': checks, 'source_sha256': hashlib.sha256(sql_path.read_bytes()).hexdigest(),
                                          'scope': 'Actual SQL and source XML using SQLite fixtures; live game loader validation pending.'}, indent=2))
print(f'stacking formations: {checks} checks passed')
