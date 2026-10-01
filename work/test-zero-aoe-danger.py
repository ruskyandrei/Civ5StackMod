"""Complete old/new stack danger bodies: skip only zero-AoE survivor updates.

Pinned 490ee12c4 scalar/outcome/control math, actual selectors/exchange,
air/city/collateral and outcome-batch admission; deterministic engine numerical
services. Explicitly compares values and action order, not ledger byte shape.
No native DLL build or game calls. Run with the bundled Python.
"""
from pathlib import Path
import ast, hashlib, json, os, subprocess, sys

root = Path(__file__).resolve().parents[1]
core = root / 'CvGameCoreDLL_Expansion2'
out = root / 'work/zero-aoe-danger-regression'
out.mkdir(exist_ok=True)
control = '490ee12c41530b7d2675636b5f98f73b2bad09c5'
old = subprocess.check_output(['git', 'show', control + ':CvGameCoreDLL_Expansion2/CvDangerPlots.cpp'], cwd=root).decode('utf-8-sig')
danger = (core / 'CvDangerPlots.cpp').read_text(encoding='utf-8-sig')
header = (core / 'CvDangerPlots.h').read_text(encoding='utf-8-sig')
combat = (core / 'CvUnitCombat.cpp').read_text(encoding='utf-8-sig')
unit = (core / 'CvUnit.h').read_text(encoding='utf-8-sig')
tactical = (core / 'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')

def function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

old_loop = '''  for (size_t i = 0; i < candidates.size(); ++i)
   if (candidates[i]->GetCurrHitPoints() > damage.GetValue(candidates[i]->GetID()))
    damage.ChangeValue(candidates[i]->GetID(), max(0, attacker->getAoEDamageOnMove()));'''
common = '''  if (aoeDamage > 0)
   for (size_t i = 0; i < candidates.size(); ++i)
    if (candidates[i]->GetCurrHitPoints() > damage.GetValue(candidates[i]->GetID()))
     damage.ChangeValue(candidates[i]->GetID(), aoeDamage);'''
new_loops = [
    '''  const int aoeDamage = max(0, attacker->getAoEDamageOnMove());
  // Missing and explicitly stored zero wounds have identical GetValue results.
  // Avoid a survivor scan and zero-ledger insertions for ordinary attackers.
''' + common,
    '''  const int aoeDamage = max(0, attacker->getAoEDamageOnMove());
  // Keep positive AoE in its original post-strike order, including duplicates.
''' + common,
]
scalar = function(danger, 'int CvDangerPlotContents::GetStackDanger(')
outcome = function(danger, 'void CvDangerPlotContents::GetStackDangerOutcome(')
old_scalar = function(old, 'int CvDangerPlotContents::GetStackDanger(')
old_outcome = function(old, 'void CvDangerPlotContents::GetStackDangerOutcome(')
for original, candidate, replacement in zip([old_scalar, old_outcome], [scalar, outcome], new_loops):
    assert original.count(old_loop) == candidate.count(replacement) == 1
    assert candidate == original.replace(old_loop, replacement, 1), 'Only the proven zero-AoE block may change'
for signature in ['static int StackAirStrikeChance(', 'static int StackExpectedStrikeDamage(',
                  'static int SimulateStackCityThreats(', 'int CvDangerPlotContents::GetStackDangerFromOutcome(']:
    assert function(danger, signature) == function(old, signature), 'Other forecast math/order changed'
assert danger.replace(new_loops[0], old_loop, 1).replace(new_loops[1], old_loop, 1) == old, 'Production scope exceeds two AoE blocks'

values = {}
for node in ast.parse((root / 'work/test-projected-stack-danger.py').read_text()).body:
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        for target in node.targets:
            if isinstance(target, ast.Name):
                values[target.id] = node.value.value
prefix, services = values['prefix'], values['services']
prefix = prefix.replace('#include <vector>', '#include <cstring>\n#include <vector>', 1)
prefix = prefix.replace('struct CvSeeder{};', 'struct CvSeeder{};\nstatic unsigned long valueReads=0,changes=0,zeroChanges=0,hpReads=0,aoeReads=0;\nstatic vector<int> trace;\nstatic void Record(int a,int b,int c){trace.push_back(a);trace.push_back(b);trace.push_back(c);}')
prefix = prefix.replace('bool alive,delayed,active,invisible,ranged,noCapture,civilian,trade,terrainIgnore,featureIgnore;', 'bool defend,cargo,flank,flankTarget,anti;int defense;bool alive,delayed,active,invisible,ranged,noCapture,civilian,trade,terrainIgnore,featureIgnore;')
prefix = prefix.replace('alive(true),delayed(false)', 'defend(true),cargo(false),flank(false),flankTarget(false),anti(false),defense(25),alive(true),delayed(false)')
prefix = prefix.replace('bool IsDead()const{return !alive;}', 'bool IsCanDefend()const{return defend;}bool isCargo()const{return cargo;}bool IsDead()const{return !alive;}')
prefix = prefix.replace('bool isInvisible(int,bool,bool)const{return invisible;}', 'bool isInvisible(int,bool,bool=false)const{return invisible;}int getInvisibleType()const{return 1;}')
prefix = prefix.replace('GetCurrHitPoints()const{return hp;}', 'GetCurrHitPoints()const{++hpReads;return hp;}')
prefix = prefix.replace('getAoEDamageOnMove()const{return aoe;}', 'getAoEDamageOnMove()const{++aoeReads;return aoe;}')
prefix = prefix.replace('bool isCity()const{return city!=NULL;}', 'int getFeatureType()const{return feature;}bool isCity()const{return city!=NULL;}')
prefix = prefix.replace('int GetMaxRangedCombatStrength(', '''int GetRangeCombatDamage(const CvUnit*d,const CvCity*,int,int&,bool,int extra,int other,const CvPlot*,const CvPlot*,bool,bool)const{return max(0,strength-extra/5-d->defense/2+other/4);}
 int GetAirStrikeDefenseDamage(const CvUnit*,bool,const CvPlot*)const{return defense/3;}
 int GetMaxDefenseStrength(const CvPlot*,const CvUnit*,const CvPlot*,bool,bool,int extra)const{return max(1,defense-extra/5);}
 int getMeleeCombatDamage(int a,int d,int&ret,bool,const CvUnit*,int,int)const{ret=max(0,d-a/2);return max(0,a-d/2);}
 bool isBetterDefenderThan(const CvUnit*u,const CvUnit*)const{return !u||defense>u->defense;}
 int GetMaxRangedCombatStrength(''', 1)
services = services.replace('static bool cityEnabled=true;', 'static bool enabled=true,selectionEnabled=true,cityEnabled=true;')
services = services.replace('bool IsEnabled(){return true;}', 'bool IsEnabled(){return enabled;}bool CanFlank(const CvUnit*u){return u->flank;}bool IsAntiCavalry(const CvUnit*u){return u->anti;}bool IsFlankTarget(const CvUnit*u){return u->flankTarget;}')
services = services.replace('int GetInt(const char*,int d){return d;}', 'int GetInt(const char*n,int d){return !strcmp(n,"DefenderSelectionEnabled")?(selectionEnabled?1:0):d;}')
services = services.replace(function(services, ' const CvUnit*SelectStackDefender('), ' const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool,int);')
services = services.replace(function(services, ' const CvUnit*SelectStackDefenderForCity('), ' const CvUnit*SelectStackDefenderForCity(const CvCity*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&);')
services = services.replace('static bool IsStackCombatCandidate(const CvUnit*u,const SUnitIDValueContainer&d){return u&&u->alive&&!u->delayed&&u->hp>d.GetValue(u->id);}', '')
services = services.replace('int id;vector<int>enemies;', 'CvDangerPlots*GetDangerPlots()const;int id;vector<int>enemies;')
services = services.replace('retaliation=7;int hit=', 'Record(1,a->id,wounds);Record(2,guard?guard->id:-999,garrisonWounds);retaliation=7;int hit=')
services = services.replace('{retaliation=6;return max(', '{Record(3,a->id,d->id);Record(4,wounds,defenderWounds);retaliation=6;return max(')
container = unit[unit.index('struct SUnitIDValueContainer\n'):unit.index('\nnamespace std {', unit.index('struct SUnitIDValueContainer\n'))]
container = container.replace('int GetValue(int iUnitID) const\n\t{', 'int GetValue(int iUnitID) const\n\t{\n        ++valueReads;')
container = container.replace('void ChangeValue(int iUnitID, int iChange)\n\t{', 'void ChangeValue(int iUnitID, int iChange)\n\t{\n        ++changes;if(iChange==0)++zeroChanges;')
contents = header[header.index('struct CvDangerPlotContents\n'):header.index('//++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++', header.index('struct CvDangerPlotContents\n'))]
contents = contents.replace('\tint GetStackDanger(const CvUnit*', '\tint OriginalStackDanger(const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&);\n\tvoid OriginalOutcome(PlayerTypes,TeamTypes,bool,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,SUnitIDValueContainer&,bool&);\n\tint GetStackDanger(const CvUnit*', 1)
selection = '\n'.join(function(combat, s) for s in ['static bool IsStackCombatCandidate(', 'static void GetStackExchange(', 'const CvUnit* CvUnitCombat::SelectStackDefender(', 'const CvUnit* CvUnitCombat::SelectStackDefenderForCity('])
selection = selection.replace('const bool bUseStackRules =', 'for(size_t k=0;k<candidates.size();++k)Record(5,candidates[k]?candidates[k]->GetID():-999,candidates[k]?extraDamage.GetValue(candidates[k]->GetID()):0);\n\tconst bool bUseStackRules =', 1)
shared = '\n'.join(function(danger, s) for s in ['static int StackAirStrikeChance(', 'static int StackExpectedStrikeDamage(', 'static int SimulateStackCityThreats(', 'int CvDangerPlotContents::GetStackDangerFromOutcome('])
collateral = function(combat, 'std::vector<std::pair<const CvUnit*, int> > CvUnitCombat::GetStackCollateralDamage(')
batch = function(tactical, 'struct StackDangerOutcomeBatch\n') + ';'
support = r'''
struct CvDangerPlots{
 vector<CvDangerPlotContents>m_DangerPlots;CvDangerPlots(){m_DangerPlots.resize(1);}
 bool IsDirty()const{return false;}const vector<int>*GetStackDangerDamageIDs(const CvPlot&){return NULL;}
 bool GetStackDangerOutcome(const CvPlot&p,const CvUnit*u,const vector<const CvUnit*>&c,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e,SUnitIDValueContainer&d,bool&fall,int&result);
 bool TryGetStackDangerFromOutcome(const CvPlot&p,const CvUnit*u,const SUnitIDValueContainer&f,const SUnitIDValueContainer&d,bool fall,int&result){result=m_DangerPlots[0].GetStackDangerFromOutcome(u,f,d,fall);return true;}
};
static CvDangerPlots maps[4];CvDangerPlots*CvPlayer::GetDangerPlots()const{return &maps[id];}
static bool buildOriginal=false;
bool CvDangerPlots::GetStackDangerOutcome(const CvPlot&p,const CvUnit*u,const vector<const CvUnit*>&c,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e,SUnitIDValueContainer&d,bool&fall,int&result){
 CvDangerPlotContents&x=m_DangerPlots[0];if(buildOriginal)x.OriginalOutcome(u->getOwner(),u->getTeam(),p.isFriendlyCity(*u),c,f,e,d,fall);else x.GetStackDangerOutcome(u->getOwner(),u->getTeam(),p.isFriendlyCity(*u),c,f,e,d,fall);
 result=x.GetStackDangerFromOutcome(u,f,d,fall);return true;
}
const int NO_PLAYER=-1,NO_TEAM=-1;static bool MOD_EVENTS_CAN_MOVE_INTO=false;
static bool MOD_GLOBAL_SUBS_UNDER_ICE_IMMUNITY=false;const int FEATURE_ICE=-1;
static unsigned long gStackForecastRevision=1,gStackOutcomeBuilds=0,gStackOutcomeReuses=0,gStackOutcomeBypasses=0;
static long gStackForecastSceneEpoch=1;static size_t gStackOutcomeCurrentBytes=0,gStackOutcomePeakBytes=0,gStackKeyPayloadLimit=0;
static bool IsStackForecastOwner(){return true;}static bool StackForecastContext(){return true;}
'''
tests = r'''
static int checks=0,failures=0;static unsigned seed=461927;static unsigned Next(){seed=seed*1664525u+1013904223u;return seed;}
static void Check(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<12)printf("FAIL %s\n",n);}}
static void ResetPlayers(){for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=p;for(int q=0;q<4;++q)if(q!=p)players[p].enemies.push_back(q);}}
static vector<pair<int,int> > Shape(const SUnitIDValueContainer&x){vector<pair<int,int> >v;for(SUnitIDValueContainer::const_iterator i=x.begin();i!=x.end();++i)v.push_back(*i);return v;}
static void ValuesEqual(const SUnitIDValueContainer&a,const SUnitIDValueContainer&b){for(int id=-100;id<=110;++id)Check("all raw ID wounds equal",a.GetValue(id)==b.GetValue(id));}
int main(){
 Check("genuine32bitVC9",sizeof(void*)==4&&sizeof(size_t)==4);
 CvPlot target(0),closePlot(1),farPlot(17);CvCity friendlyCity(0,0,&target),hostileCity(7,1,&closePlot);CvUnit units[6],actors[12];
 long representationDifferences=0,zeroCallsSaved=0;vector<const CvUnit*>roster;
 for(int trial=0;trial<3500;++trial){
  ResetPlayers();roster.clear();CvDangerPlotContents c;c.m_pPlot=&target;c.m_iFogCount=Next()%7;c.m_iImprovementDamage=Next()%31;c.m_bFlatPlotDamage=Next()%2!=0;
  target.city=trial%4==0?&friendlyCity:NULL;target.friendly=trial%4==0;target.embark=trial%11==0;friendlyCity.hp=Next()%301;friendlyCity.protection=Next()%91;
  CvStacking::selectionEnabled=trial%5!=0;CvStacking::enabled=trial%13!=0;
  SUnitIDValueContainer wounds,enemy;
  for(int i=0;i<6;++i){int id=i==0?0:(i==1?-7:i+8);units[i]=CvUnit(id,0,&target);units[i].hp=30+Next()%101;units[i].maxHP=units[i].hp+Next()%40;units[i].defense=10+Next()%55;units[i].strength=20+Next()%90;units[i].anti=Next()%2!=0;units[i].flankTarget=Next()%2!=0;units[i].ranged=Next()%2!=0;units[i].alive=Next()%17!=0;units[i].delayed=Next()%19==0;units[i].cargo=Next()%23==0;units[i].domain=i==5?DOMAIN_AIR:DOMAIN_LAND;units[i].chance=Next()%151;units[i].attempts=1+Next()%3;units[i].terrainIgnore=Next()%2!=0;units[i].featureIgnore=Next()%2!=0;players[0].units[id]=&units[i];players[0].possible.push_back(make_pair(id,0));if(i<5)roster.push_back(&units[i]);if(trial%3==0||Next()%2)wounds.SetValue(id,trial%7==0?0:(int)(Next()%141)-20);}
  wounds.SetValue(99,(int)(Next()%111));CvUnit outside(99,0,&closePlot);outside.domain=DOMAIN_AIR;outside.strength=350;outside.attempts=4;players[0].units[99]=&outside;players[0].possible.push_back(make_pair(99,0));
  if(trial%3==0)roster.push_back(&units[1]);if(trial%7==0)reverse(roster.begin(),roster.end());if(trial%17==0)units[4].owner=2;
  for(int i=0;i<12;++i){int id=i%6,owner=1+i%2;actors[i]=CvUnit(id,owner,(trial+i)%11==0?&target:(i%3?&closePlot:&farPlot));actors[i].hp=25+Next()%100;actors[i].ranged=Next()%2!=0;actors[i].flank=Next()%2!=0;actors[i].strength=25+Next()%85;actors[i].domain=i%5==0?DOMAIN_AIR:DOMAIN_LAND;actors[i].collateralLimit=Next()%6;actors[i].alive=Next()%19!=0;actors[i].delayed=Next()%17==0;actors[i].noCapture=Next()%3==0;actors[i].evasion=Next()%101;actors[i].aoe=trial%3==0?0:(int)(Next()%9)-3;players[owner].units[id]=&actors[i];c.m_apUnits.push_back(make_pair(owner,id));if(trial%13==0)c.m_apUnits.push_back(make_pair(owner,id));enemy.SetValue(id,(int)(Next()%81)-9);}
  players[1].cities[7]=&hostileCity;c.m_apCities.push_back(make_pair(1,7));if(trial%29==0)c.m_apCities.push_back(make_pair(1,88));
  for(int q=0;q<6;++q){trace.clear();int oldValue=c.OriginalStackDanger(&units[q],roster,wounds,enemy);vector<int>oldTrace=trace;unsigned long oldZero=zeroChanges;trace.clear();int newValue=c.GetStackDanger(&units[q],roster,wounds,enemy);
   Check("complete scalar numeric result",oldValue==newValue);Check("selector and strike order/inputs",oldTrace==trace);
   SUnitIDValueContainer a,b;bool fallA=false,fallB=false;trace.clear();unsigned long start=zeroChanges;c.OriginalOutcome(units[q].getOwner(),units[q].getTeam(),target.isFriendlyCity(units[q]),roster,wounds,enemy,a,fallA);unsigned long controlZero=zeroChanges-start;oldTrace=trace;trace.clear();start=zeroChanges;c.GetStackDangerOutcome(units[q].getOwner(),units[q].getTeam(),target.isFriendlyCity(units[q]),roster,wounds,enemy,b,fallB);
   Check("full outcome capture flag",fallA==fallB);Check("outcome selector/strike ordering",oldTrace==trace);Check("extraction agrees old scalar",c.GetStackDangerFromOutcome(&units[q],wounds,b,fallB)==oldValue);ValuesEqual(a,b);Check("zero-only changes removed",zeroChanges-start<=controlZero);zeroCallsSaved+=controlZero-(zeroChanges-start);
   if(Shape(a)!=Shape(b))++representationDifferences;
  }
 }
 ResetPlayers();CvStacking::enabled=CvStacking::selectionEnabled=true;target.city=NULL;target.embark=false;target.friendly=false;roster.clear();SUnitIDValueContainer empty;
 for(int i=0;i<5;++i){units[i]=CvUnit(10+i,0,&target);units[i].hp=500;units[i].maxHP=500;units[i].defense=25;roster.push_back(&units[i]);}
 CvDangerPlotContents c;c.m_pPlot=&target;actors[0]=CvUnit(44,1,&closePlot);actors[0].ranged=true;actors[0].collateralLimit=0;actors[0].aoe=0;players[1].units[44]=&actors[0];c.m_apUnits.push_back(make_pair(1,44));
 SUnitIDValueContainer a,b;bool fallA=false,fallB=false;unsigned long zeroStart=zeroChanges,readStart=valueReads,hpStart=hpReads;c.OriginalOutcome(0,0,false,roster,empty,empty,a,fallA);unsigned long oldZero=zeroChanges-zeroStart,oldReads=valueReads-readStart,oldHP=hpReads-hpStart;
 zeroStart=zeroChanges;readStart=valueReads;hpStart=hpReads;c.GetStackDangerOutcome(0,0,false,roster,empty,empty,b,fallB);unsigned long newZero=zeroChanges-zeroStart,newReads=valueReads-readStart,newHP=hpReads-hpStart;
 ValuesEqual(a,b);Check("zero AoE removes5writes",oldZero==5&&newZero==0);Check("zero AoE removes5survivorreads",oldHP==newHP+5);Check("zero AoE removes5valuequeries",oldReads==newReads+5);
 Check("representation caveat is real",Shape(a)!=Shape(b)&&a.GetHash()!=b.GetHash());Check("sparse scalar storage remains inline",a.m_aExtraStorage.capacity()>0&&b.m_aExtraStorage.capacity()==0);
 for(int aoe=-9;aoe<=9;++aoe){actors[0].aoe=aoe;roster.push_back(&units[1]);reverse(roster.begin(),roster.end());a.clear();b.clear();c.OriginalOutcome(0,0,false,roster,empty,empty,a,fallA);c.GetStackDangerOutcome(0,0,false,roster,empty,empty,b,fallB);ValuesEqual(a,b);if(aoe>0)Check("positive AoE complete shape/order unchanged",Shape(a)==Shape(b)&&a.GetHash()==b.GetHash());roster.erase(find(roster.begin(),roster.end(),&units[1]));}
 actors[0].aoe=3;actors[0].strength=100;SUnitIDValueContainer almostDead;almostDead.SetValue(11,499);roster.clear();roster.push_back(&units[1]);roster.push_back(&units[1]);roster.push_back(&units[2]);c.OriginalOutcome(0,0,false,roster,almostDead,empty,a,fallA);c.GetStackDangerOutcome(0,0,false,roster,almostDead,empty,b,fallB);ValuesEqual(a,b);Check("positive duplicates/casualties order unchanged",Shape(a)==Shape(b));
 actors[0].aoe=0;roster.clear();for(int i=0;i<5;++i)roster.push_back(&units[i]);maps[0].m_DangerPlots[0]=c;
 for(size_t cap=0;cap<=128;cap+=8){gStackKeyPayloadLimit=cap;int oldResult=-1,newResult=-1;bool oldReady=false,newReady=false;size_t oldBytes=0,newBytes=0;
  {buildOriginal=true;StackDangerOutcomeBatch batch(&target,roster,empty,empty);Check("control batch returns one leaf",batch.TryGet(&units[0],&target,roster,empty,empty,oldResult));oldReady=batch.ready;oldBytes=batch.retainedBytes;Check("control retained capacity obeys cap",gStackOutcomeCurrentBytes<=cap);}
  Check("control scoped storage releases",gStackOutcomeCurrentBytes==0);
  {buildOriginal=false;StackDangerOutcomeBatch batch(&target,roster,empty,empty);Check("candidate batch returns one leaf",batch.TryGet(&units[0],&target,roster,empty,empty,newResult));newReady=batch.ready;newBytes=batch.retainedBytes;Check("candidate retained capacity obeys cap",gStackOutcomeCurrentBytes<=cap);if(batch.ready){int repeat=-1;Check("retained outcome extracts same exact result",batch.TryGet(&units[0],&target,roster,empty,empty,repeat)&&repeat==newResult);}}
  Check("candidate scoped storage releases",gStackOutcomeCurrentBytes==0);Check("budget does not change numerical result",oldResult==newResult);if(cap==0)Check("capacity admission change explicitly covered",!oldReady&&newReady&&oldBytes==0&&newBytes==0);
 }
 Check("random scenarios exercise shape differences",representationDifferences>0);Check("random scenarios eliminate zero writes",zeroCallsSaved>0);
 printf("zero-AoE actual-source: %d checks,%d failures; randomizedShapeDifferences%ld zeroWritesEliminated%ld; controlledSurvivorReads%lu->%lu zeroWrites%lu->%lu; numeric/order exact, representation/capacity may differ\n",checks,failures,representationDifferences,zeroCallsSaved,oldHP,newHP,oldZero,newZero);return failures?1:0;
}
'''
old_scalar = old_scalar.replace('::GetStackDanger(', '::OriginalStackDanger(', 1)
old_outcome = old_outcome.replace('::GetStackDangerOutcome(', '::OriginalOutcome(', 1)
# Constants must precede actual city-selector body; support needs defined contents.
constant_declarations = 'static bool MOD_GLOBAL_SUBS_UNDER_ICE_IMMUNITY=false;const int FEATURE_ICE=-1;\n'
support = support.replace(constant_declarations.strip(), '')
fixture = prefix + 'struct CvDangerPlots;\n' + container + services + contents + constant_declarations + selection + collateral + shared + old_scalar + old_outcome + scalar + outcome + support + batch + tests
(out / 'test.cpp').write_text(fixture, encoding='utf-8')
vc = root / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = root / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc / 'Vc7/bin') + ';' + str(vc / 'Common7/IDE') + ';' + env.get('PATH', '')
env['INCLUDE'] = str(root / 'work/toolchain/sdk/vc9/include') + ';' + str(sdk / 'Include')
env['LIB'] = str(root / 'work/toolchain/sdk/vc9/lib') + ';' + str(sdk / 'Lib')
for name in ('CL', '_CL_', 'LINK'):
    env.pop(name, None)
exe = out / 'test.exe'
compiled = subprocess.run([str(vc / 'Vc7/bin/cl.exe'), '/nologo', '/EHsc', '/MT', '/O2', '/Z7', '/D_SECURE_SCL=0', '/D_HAS_ITERATOR_DEBUGGING=0', str(out / 'test.cpp'), '/Fo' + str(out / 'test.obj'), '/Fe' + str(exe)], cwd=out, env=env, capture_output=True, text=True, timeout=60)
(out / 'compile.log').write_text(compiled.stdout + compiled.stderr)
if compiled.returncode:
    print(compiled.stdout + compiled.stderr)
    sys.exit(compiled.returncode)
run = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=60)
print(run.stdout + run.stderr, end='')
(out / 'result.json').write_text(json.dumps(dict(returncode=run.returncode, output=run.stdout + run.stderr, control=control, only_two_exact_zero_aoe_blocks_changed=True, fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(), scope='Complete actual old/new scalar/outcome/air/city/collateral/selector/exchange and current outcome-batch admission. Numerical engine services deterministic; shape/hash/capacity differences explicit. No native DLL build/game.'), indent=2))
sys.exit(run.returncode)
