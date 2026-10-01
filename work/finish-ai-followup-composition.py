"""Explicit AI-stage conflict resolutions/lifecycle/configuration seams, work only."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/ai-followup-composed';BASE='d792b4bcb'
def original(name):return subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
files={p.name:p.read_text(encoding='utf-8-sig') for p in OUT.glob('Cv*') if p.suffix in ('.cpp','.h')}
def change(name,old,new,count=1):
    assert files[name].count(old)==count,(name,old[:100],files[name].count(old))
    files[name]=files[name].replace(old,new)
def region(text,signature):
    a=text.index(signature);p=text.index('{',a);depth=0
    tokens=re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|[{}]',text[p:])
    for token in tokens:
        if token.group()=='{':depth+=1
        elif token.group()=='}':
            depth-=1
            if depth==0:return a,p+token.end()
    raise AssertionError('Unbalanced '+signature)
def in_function(name,signature,old,new,count=1):
    a,b=region(files[name],signature);body=files[name][a:b]
    assert body.count(old)==count,(signature,old[:70],body.count(old))
    files[name]=files[name][:a]+body.replace(old,new)+files[name][b:]

off='CvStackingOffensiveAI.cpp';s=files[off]
a=s.index('<<<<<<< composed',s.index('Objective():'));b=s.index('\n    };\n    struct Commitment',a)
assert '>>>>>>> production' in s[a:b] and '>>>>>>> wave' in s[a:b]
ctor='''            assaultTurn(-1),phaseSince(-1),phaseLogged(-1),staffTurn(-1),staffUnits(0),staffSiege(0),staffRanged(0),staffCapture(0),
            productionTurn(-1),productionUnits(0),productionSiege(0),productionRanged(0),productionCapture(0),productionQueued(0),productionGeneration(0),
            lastUsefulTurn(-1),lowestHP(INT_MAX),firstReadyTurn(-1),lastCityProgress(-1),lastCityAttack(-1),cityAttempts(0),fieldContributions(0),
            captureKnown(false),waveComplete(false),wavePathUnknown(false){}'''
s=s[:a]+ctor+s[b:]
a=s.index('<<<<<<< composed',s.index('    void Reset()'));b=s.index('>>>>>>> wave',a)+len('>>>>>>> wave')
s=s[:a]+'''    {
        ResetOpeningReadiness(); ResetProductionPolicy();
        objectives.clear(); commitments.clear(); failures.clear(); marches.clear(); captureRetries.clear(); production.clear(); stalledProduction.clear(); assemblyHolds.clear(); currentTurn=-1; shuttingDown=false;
        if(continuityGeneration==0xffffffffUL) continuityGenerationExhausted=true; else ++continuityGeneration;
    }'''+s[b:]
assert not re.search(r'^(<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)',s,re.M)
files[off]=s
change(off,'#include "CvMilitaryAI.h"','#include "CvMilitaryAI.h"\n#include "CvEconomicAI.h"')

# Changing a commitment changes staffing credit at its previous objective too.
# Keep this invalidation metadata-only, including release and failed transfer.
needle='    void Refresh()'
helper='''    bool EraseCommitment(std::map<Key,Commitment>::iterator i)
    {
        if(i==commitments.end())return false;
        const ObjectiveKey goal=i->second.goal;
        CvStackingOffensiveAI::InvalidateProductionStaff((PlayerTypes)goal.owner,goal.target,(DomainTypes)goal.domain);
        commitments.erase(i);return true;
    }
    bool EraseCommitment(const Key& key) { return EraseCommitment(commitments.find(key)); }
'''
change(off,needle,helper+needle)
for old in ('commitments.erase(i++);','commitments.erase(unitKey);','commitments.erase(key);','commitments.erase(Key(unit->getOwner(),unit->GetID()))'):
    change(off,old,old.replace('commitments.erase','EraseCommitment'),files[off].count(old))
in_function(off,'    void RecordTransfer(', '        c.goal=ObjectiveKey(unit->getOwner(),target,unit->getDomainType());',
'''        if(c.goal.target>=0 && !(c.goal==ObjectiveKey(unit->getOwner(),target,unit->getDomainType())))
            InvalidateProductionStaff((PlayerTypes)c.goal.owner,c.goal.target,(DomainTypes)c.goal.domain);
        c.goal=ObjectiveKey(unit->getOwner(),target,unit->getDomainType());''')

# The declaration is needed by the earlier Refresh claim-erasure pass.
change(off,'    bool shuttingDown=false;','    void AdvanceProductionGeneration(PlayerTypes owner);\n    bool shuttingDown=false;')
in_function(off,'    void Refresh()', '                production.erase(i++);',
'''                AdvanceProductionGeneration((PlayerTypes)i->first.first);
                production.erase(i++);''')
in_function(off,'    void RecordCombatContribution(', '        o.staffTurn=-1; // Actual wounds/losses can expose a replacement-role deficit.',
'''        InvalidateProductionStaff(owner,target,domain); // Actual wounds/losses can expose a replacement-role deficit.''')
in_function(off,'    void RecordTransfer(', '        refreshed->staffTurn=-1;',
'''        InvalidateProductionStaff(unit->getOwner(),target,unit->getDomainType());''')
a,b=region(files[off],'    void Handoff(')
body=files[off][a:b];body=body[:-1]+'    InvalidateProductionOwner(op->GetOwner());\n    }'
files[off]=files[off][:a]+body+files[off][b:]

# Initial observation is not damage progress. A real visible lower HP is,
# whether the contributor was assigned, local, naval, allied or an aircraft.
a,b=region(files[off],'    AssaultPlan AssessAssault(');body=files[off][a:b]
needle='        if(hp<o.lowestHP ||'
assert body.count(needle)==1
body=body.replace(needle,'        if(o.lowestHP!=INT_MAX && hp<o.lowestHP) o.lastCityProgress=currentTurn;\n'+needle)
needle='        result.phase=result.ready?1:0;'
assert body.count(needle)==1
body=body.replace(needle,'        if(result.ready && o.firstReadyTurn<0) o.firstReadyTurn=currentTurn;\n'+needle)
files[off]=files[off][:a]+body+files[off][b:]

# Native births, removals and memberships include units without support claims.
for name in ('CvPlayer.cpp','CvUnit.cpp'):
    files[name]=original(name)
    files[name]=files[name].replace('#include "CvGameCoreDLLPCH.h"','#include "CvGameCoreDLLPCH.h"\n#include "CvStackingOffensiveAI.h"',1)
for signature in ('CvUnit* CvPlayer::initUnit(','CvUnit* CvPlayer::initUnitWithNameOffset(','CvUnit* CvPlayer::initNamedUnit('):
    in_function('CvPlayer.cpp',signature,'\treturn pUnit;','\tCvStackingOffensiveAI::InvalidateProductionOwner(GetID());\n\treturn pUnit;')
in_function('CvPlayer.cpp','void CvPlayer::deleteUnit(','\tm_units.Remove(iID);','\tm_units.Remove(iID);\n\tCvStackingOffensiveAI::InvalidateProductionOwner(GetID());')
in_function('CvUnit.cpp','void CvUnit::setArmyID(','\tm_iArmyId = iNewArmyID;',
'''\tconst bool changed = m_iArmyId != iNewArmyID;
\tm_iArmyId = iNewArmyID;
\tif(changed && m_eOwner != NO_PLAYER) CvStackingOffensiveAI::InvalidateProductionOwner(m_eOwner);''')
in_function('CvPlayer.cpp','CvCity* CvPlayer::addCity()', '\treturn(m_cities.Add());',
'''\tCvCity* city=m_cities.Add();
\tCvStackingOffensiveAI::ProductionCitiesChanged(GetID());
\treturn city;''')
in_function('CvPlayer.cpp','void CvPlayer::deleteCity(', '\tm_cities.Remove(iID);',
'''\tm_cities.Remove(iID);
\tCvStackingOffensiveAI::ProductionCitiesChanged(GetID());''')
# Completed init is important if a native city-founded callback queried a cache.
in_function('CvPlayer.cpp','CvCity* CvPlayer::initCity(', '\treturn pNewCity;',
'''\tCvStackingOffensiveAI::ProductionCitiesChanged(GetID());
\treturn pNewCity;''')
# Ownership transfer goes through source-player remove and destination add/init;
# acquired existing cities additionally invalidate both owners at acquire entry.
a,b=region(files['CvPlayer.cpp'],'CvCity* CvPlayer::acquireCity(')
body=files['CvPlayer.cpp'][a:b]
needle='\tPlayerTypes eOldOwner = pCity->getOwner();'
assert body.count(needle)==1
body=body.replace(needle,needle+'\n\tCvStackingOffensiveAI::ProductionCitiesChanged(eOldOwner);\n\tCvStackingOffensiveAI::ProductionCitiesChanged(GetID());')
files['CvPlayer.cpp']=files['CvPlayer.cpp'][:a]+body+files['CvPlayer.cpp'][b:]

# Every introduced numerical control is registered and present in XML.
settings=json.loads((ROOT/'work/first-wave-staged/proof.json').read_text())['new_settings']
settings += [(r['name'],r['default'],r['min'],r['max']) for r in json.loads((ROOT/'work/ai-production-policy-staged/stage-proof.json').read_text())['settings']]
settings += [('AIOffensiveContributionRadius',2,0,6),('AIAssaultAttackProgressStallTurns',24,0,240)]
rules=original('CvStackingRules.cpp')
needle='\t\t{"AIAssaultAbandonTurns", 24, 6, 100},'
assert rules.count(needle)==1
rows='\n'.join('\t\t{"%s", %d, %d, %d},'%tuple(r) for r in settings)
rules=rules.replace(needle,needle+'\n'+rows)
files['CvStackingRules.cpp']=rules
xmlpath=Path('(1) Community Patch/Database Changes/StackingConfig.xml')
xml=subprocess.check_output(['git','show',BASE+':'+xmlpath.as_posix()],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
needle='    <Row Name="AIAssaultAbandonTurns" Value="24"/>'
assert xml.count(needle)==1
xml=xml.replace(needle,needle+'\n    <!-- Coherent waves, affordable role repair and measured assault progress. -->\n'+
                '\n'.join('    <Row Name="%s" Value="%d"/>'%(r[0],r[1]) for r in settings))
(OUT/'StackingConfig.xml').write_text(xml,encoding='utf-8')

for name,text in files.items():
    assert not re.search(r'^(<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)',text,re.M),name
    (OUT/name).write_text(text,encoding='utf-8')
proof={'control':BASE,'composition_inputs':json.loads((OUT/'composition-inputs.json').read_text()),
       'candidate_hashes':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()},
       'xml_sha256':hashlib.sha256(xml.encode()).hexdigest(),'new_settings':settings,
       'resolved_conflicts':['Objective initializer union','Reset caches + lifetime generation'],
       'production_untouched':True,'pending':'Integrated source-bound tests, native compile and <=10% saved replay acceptance'}
(OUT/'finished-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'files':len(files),'settings':len(settings),'conflicts':0,'production_untouched':True}))
