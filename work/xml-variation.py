"""Prepare/apply/restore XML-only variation. Preparation writes work only.
No invocation installs files, rebuilds the DLL or launches the game.
"""
from pathlib import Path
import argparse, csv, datetime, hashlib, io, json, shutil, subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work'/'xml-variation'
FILES={'cp':Path('(1) Community Patch/Database Changes/StackingConfig.xml'),
       'vp':Path('(2) Vox Populi/Database Changes/StackingVPConfig.xml')}
SETTINGS={'BaseCapacity':3,'MaximumCapacity':10,'SeaCapacityBonus':1,'CityCapacityBonus':1,
          'MinorCapacityBonus':1,'BarbarianCapacityBonus':2,'CollateralPercent':30,
          'CollateralHPFloorPercent':60,'CollateralMinimumDamage':3,'CityProtectionMaximumPercent':65}
TECHS={'TECH_IRON_WORKING':2,'TECH_GUNPOWDER':1,'TECH_MILITARY_SCIENCE':3,'TECH_ROBOTICS':1}
PROFILES=('main','sea-enabled','no-flanking','no-collateral','no-stacking','no-ai')
def digest(data): return hashlib.sha256(data).hexdigest().upper()
def row(root,table,keys,value):
    parent=root.find(table)
    if parent is None: parent=ET.SubElement(root,table)
    matches=[r for r in parent if all(r.get(k)==str(v) for k,v in keys.items())]
    assert len(matches)<=1,(table,keys)
    target=matches[0] if matches else ET.SubElement(parent,'Row',{k:str(v) for k,v in keys.items()})
    target.set(value[0],str(value[1]))
def xmlbytes(root):
    ET.indent(root,space='  ')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n'
def prepare():
    assert not (OUT/'manifest.json').exists(),'Existing variation snapshot: preserve it; do not replace baselines'
    OUT.mkdir(parents=True,exist_ok=True)
    manifest={'status':'PREPARED; NOT APPLIED; LIVE UNVERIFIED','root':str(ROOT),'files':{},'profiles':list(PROFILES)}
    for name,rel in FILES.items():
        baseline=(ROOT/rel).read_bytes()
        folder=OUT/'baseline'; folder.mkdir(exist_ok=True)
        (folder/(name+'.xml')).write_bytes(baseline)
        manifest['files'][name]={'relative':str(rel),'baseline':digest(baseline),'profiles':{}}
        for profile in PROFILES:
            root=ET.fromstring(baseline)
            if name=='cp':
                for key,value in SETTINGS.items(): row(root,'Stacking_Settings',{'Name':key},('Value',value))
                for key,value in TECHS.items(): row(root,'Stacking_Technologies',{'TechType':key},('CapacityBonus',value))
                for combat in ('UNITCOMBAT_SIEGE','UNITCOMBAT_NAVALRANGED'):
                    row(root,'Stacking_UnitCombatRoles',{'UnitCombatType':combat,'Role':'COLLATERAL_LIMIT'},('Value',1))
                for unitclass,value in {'UNITCLASS_CATAPULT':4,'UNITCLASS_FRIGATE':2,'UNITCLASS_ARTILLERY':2,'UNITCLASS_BOMBER':6}.items():
                    row(root,'Stacking_UnitClassRoles',{'UnitClassType':unitclass,'Role':'COLLATERAL_LIMIT'},('Value',value))
                # Trebuchet deliberately inherits its combat-class limit (1).
                table=root.find('Stacking_UnitClassRoles')
                for r in list(table):
                    if r.get('UnitClassType')=='UNITCLASS_TREBUCHET' and r.get('Role')=='COLLATERAL_LIMIT': table.remove(r)
                row(root,'Stacking_UnitClassRoles',{'UnitClassType':'UNITCLASS_SPEARMAN','Role':'ANTI_CAVALRY'},('Value',0))
                row(root,'Stacking_PromotionRoles',{'PromotionType':'PROMOTION_DRILL_1','Role':'COLLATERAL_LIMIT'},('Value',5))
                for unit,role,value in [('UNIT_CATAPULT','COLLATERAL_LIMIT',3),('UNIT_HORSEMAN','FLANK',0),
                                        ('UNIT_WARRIOR','FLANK',1),('UNIT_ARCHER','FLANK_TARGET',0)]:
                    row(root,'Stacking_UnitRoles',{'UnitType':unit,'Role':role},('Value',value))
                for cls,value in {'BUILDINGCLASS_WALLS':7,'BUILDINGCLASS_CASTLE':13,'BUILDINGCLASS_ARSENAL':17,
                                  'BUILDINGCLASS_MILITARY_BASE':19,'BUILDINGCLASS_BOMB_SHELTER':31}.items():
                    row(root,'Stacking_BuildingClassProtection',{'BuildingClassType':cls},('ProtectionPercent',value))
                row(root,'Stacking_BuildingProtection',{'BuildingType':'BUILDING_WALLS'},('ProtectionPercent',11))
                if profile=='sea-enabled': row(root,'Stacking_CollateralDomains',{'DomainType':'DOMAIN_SEA'},('Enabled',1))
                for p,key in {'no-flanking':'FlankingEnabled','no-collateral':'CollateralEnabled','no-stacking':'Enabled','no-ai':'AIEnabled'}.items():
                    if p==profile: row(root,'Stacking_Settings',{'Name':key},('Value',0))
            else:
                node=root.find('UnitPromotions_Domains/Update/Set'); assert node is not None
                node.set('Attack','-20')
            payload=xmlbytes(root)
            folder=OUT/profile; folder.mkdir(exist_ok=True)
            (folder/(name+'.xml')).write_bytes(payload)
            manifest['files'][name]['profiles'][profile]=digest(payload)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Prepared only:',OUT)
    verify()
def load():
    data=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    assert data['root']==str(ROOT),'Manifest project mismatch'
    assert set(data['files'])==set(FILES),'Unexpected target mapping'
    for key,rel in FILES.items(): assert data['files'][key]['relative']==str(rel),'Unexpected target path'
    return data
def verify():
    data=load()
    for key,entry in data['files'].items():
        for profile in ('baseline',)+PROFILES:
            raw=(OUT/profile/(key+'.xml')).read_bytes(); ET.fromstring(raw)
            expected=entry['baseline'] if profile=='baseline' else entry['profiles'][profile]
            assert digest(raw)==expected,('Payload hash mismatch',key,profile)
        raw=(ROOT/FILES[key]).read_bytes()
        known=[p for p,h in entry['profiles'].items() if h==digest(raw)]
        print(key,'canonical SHA256',digest(raw),'state=', 'baseline' if digest(raw)==entry['baseline'] else ','.join(known) or 'UNEXPECTED')
    print('All prepared XML and hashes valid; no deployment performed')
def mutate(profile):
    data=load(); verify()
    processes=subprocess.check_output(['tasklist','/FO','CSV','/NH'],text=True,encoding='utf-8',errors='replace')
    running=[r[0] for r in csv.reader(io.StringIO(processes)) if r and r[0].lower().startswith('civilizationv')]
    assert not running,'Close Civilization V first: '+str(running)
    targets=[]
    for key,rel in FILES.items():
        path=(ROOT/rel).resolve(); assert path.is_relative_to(ROOT.resolve())
        current=path.read_bytes(); entry=data['files'][key]
        assert digest(current) in [entry['baseline']]+list(entry['profiles'].values()),'Unexpected canonical edits: '+str(path)
        payload=(OUT/profile/(key+'.xml')).read_bytes()
        expected=entry['baseline'] if profile=='baseline' else entry['profiles'][profile]
        assert digest(payload)==expected
        targets.append((key,path,current,payload))
    backup=OUT/('before-'+profile+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir()
    for key,path,current,payload in targets: (backup/(key+'.xml')).write_bytes(current)
    for key,path,current,payload in targets:
        path.write_bytes(payload); assert digest(path.read_bytes())==digest(payload)
    print('Canonical XML only updated:',profile,'exact previous bytes backed up:',backup)
    print('Next: coordinator restages/deploys (including modinfo MD5), verifies unchanged DLL, restarts, new disposable game')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','verify','apply','restore'))
    parser.add_argument('--profile',choices=PROFILES,default='main')
    args=parser.parse_args()
    if args.action=='prepare': prepare()
    elif args.action=='verify': verify()
    else: mutate('baseline' if args.action=='restore' else args.profile)