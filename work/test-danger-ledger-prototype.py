"""Exact-source stack-ledger regression against the pinned original scalar body.

Compiles actual full scalar, air/city/collateral and native isFriendlyCity bodies
against an exact-source split. Strength/defender services are deterministic stubs.
"""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/danger-ledger-prototype';out.mkdir(exist_ok=True)
controlDanger=subprocess.run(['git','show','1f9ef85a9a8700aec794dbb14b3cce44eddb0533:CvGameCoreDLL_Expansion2/CvDangerPlots.cpp'],cwd=root,capture_output=True,text=True,check=True).stdout
source=root/'work/danger-ledger-candidate' if '--candidate' in sys.argv else core
danger=(source/'CvDangerPlots.cpp').read_text(encoding='utf-8-sig');header=(source/'CvDangerPlots.h').read_text(encoding='utf-8-sig')
combat=(core/'CvUnitCombat.cpp').read_text(encoding='utf-8-sig');unit=(core/'CvUnit.h').read_text(encoding='utf-8-sig');plot=(core/'CvPlot.cpp').read_text(encoding='utf-8-sig')
def function(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
values={}
for node in ast.parse((root/'work/test-projected-stack-danger.py').read_text()).body:
 if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
  for target in node.targets:
   if isinstance(target,ast.Name):values[target.id]=node.value.value
prefix=values['prefix'];services=values['services']
prefix=prefix.replace('int GetPlotIndex()const{return index;}','int getTeam()const;int GetPlotIndex()const{return index;}')
prefix=prefix.replace('int id,owner,domain,hp','int id,owner,team,combatOwner,domain,hp')
prefix=prefix.replace(':id(i),owner(o),domain(DOMAIN_LAND)',':id(i),owner(o),team(o),combatOwner(-1),domain(DOMAIN_LAND)')
prefix=prefix.replace('int getTeam()const{return owner;}int getDomainType()', 'int getTeam()const{return team;}int getCombatOwner(int,const CvPlot&)const{return combatOwner<0?owner:combatOwner;}int getDomainType()')
prefix=re.sub(r'bool CvPlot::isFriendlyCity\(const CvUnit&unit\)const\{.*?\}\n','',prefix)
services=services.replace('int id;vector<int>enemies;', 'int id,team;vector<int>enemies;').replace('int getTeam()const{return id;}', 'int getTeam()const{return team;}')
services=services.replace('namespace TacticalAIHelpers{','static long fieldLeafs=0,cityLeafs=0;\nnamespace TacticalAIHelpers{').replace('retaliation=7;int hit=', '++cityLeafs;retaliation=7;int hit=').replace('{retaliation=6;return max(', '{++fieldLeafs;retaliation=6;return max(')
context=r'''
const int NO_TEAM=-1;
struct CvTeam{bool open[4];bool IsAllowsOpenBordersToTeam(int t)const{return t>=0&&t<4&&open[t];}};
static CvTeam teams[4];
#define GET_TEAM(x) teams[x]
int CvPlot::getTeam()const{return city?city->getTeam():owner;}
'''
container=unit[unit.index('struct SUnitIDValueContainer\n'):unit.index('\nnamespace std {',unit.index('struct SUnitIDValueContainer\n'))]
contents=header[header.index('struct CvDangerPlotContents\n'):header.index('//++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++',header.index('struct CvDangerPlotContents\n'))]
selector_start=header.index('typedef const CvUnit* (*StackDangerDefenderSelector)')
selector_type=header[selector_start:header.index(';',selector_start)+1]
air=function(danger,'static int StackAirStrikeChance(');expected=function(danger,'static int StackExpectedStrikeDamage(');city=function(danger,'static int SimulateStackCityThreats(');scalar=function(controlDanger,'int CvDangerPlotContents::GetStackDanger(')
collateral=function(combat,'std::vector<std::pair<const CvUnit*, int> > CvUnitCombat::GetStackCollateralDamage(');friendly=function(plot,'bool CvPlot::isFriendlyCity(const CvUnit&')
uses=re.findall(r'pUnit->([A-Za-z0-9_]+)\(',scalar)
assert sorted(set(uses))==sorted(['GetID','getOwner','getTeam','ignoreTerrainDamage','ignoreFeatureDamage','extraTerrainDamage','extraFeatureDamage'])
field=scalar[scalar.index(' SUnitIDValueContainer interceptionUses;'):scalar.rindex(' int result = max(0,')]
assert field.count('pUnit->getOwner()')==1 and field.count('pUnit->getTeam()')==1
field=field.replace('pUnit->getOwner()','owner').replace('pUnit->getTeam()','team')
for member in ('m_pPlot','m_apUnits','m_apCities'):field=re.sub(r'\b'+member+r'\b','contents.'+member,field)
tail=scalar[scalar.rindex(' int result = max(0,'):scalar.rindex('}')]
for member in ('m_pPlot','m_iImprovementDamage','m_iFogCount','m_bFlatPlotDamage'):tail=re.sub(r'\b'+member+r'\b','contents.'+member,tail)
prototype=r'''
struct Outcome{SUnitIDValueContainer damage;bool cityCanFall;Outcome():cityCanFall(false){}};
static long outcomeBuilds=0;
static void BuildOutcome(const CvDangerPlotContents&contents,int owner,int team,bool friendly,
 const vector<const CvUnit*>&candidates,const SUnitIDValueContainer&friendlyDamage,
 const SUnitIDValueContainer&enemyDamage,Outcome&outcome){
 ++outcomeBuilds;outcome.damage=friendlyDamage;outcome.cityCanFall=false;
 SUnitIDValueContainer&damage=outcome.damage;
 CvCity*city=friendly?contents.m_pPlot->getPlotCity():NULL;
 if(city){SimulateStackCityThreats(contents,city,candidates,damage,enemyDamage,0,outcome.cityCanFall);return;}
''' + field + r'''
}
static int ExtractOutcome(const CvDangerPlotContents&contents,const CvUnit*pUnit,
 const SUnitIDValueContainer&friendlyDamage,const Outcome&outcome){
 if(!pUnit||!contents.m_pPlot)return 0;
 if(outcome.cityCanFall)return INT_MAX;
 const SUnitIDValueContainer&damage=outcome.damage;
 const int initialDamage=friendlyDamage.GetValue(pUnit->GetID());
''' + tail + r'''
}
// Immutable short lifetime only: production scene guards remain future work.
struct OutcomeBatch{
 const CvDangerPlotContents&contents;const vector<const CvUnit*>&candidates;
 const SUnitIDValueContainer&friendlyDamage;const SUnitIDValueContainer&enemyDamage;
 bool ready,branch;int owner,team;Outcome outcome;
 OutcomeBatch(const CvDangerPlotContents&c,const vector<const CvUnit*>&r,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e):contents(c),candidates(r),friendlyDamage(f),enemyDamage(e),ready(false),branch(false),owner(-1),team(-1){}
 int Get(const CvUnit*u){
  if(!u||!contents.m_pPlot)return 0;
  const bool currentBranch=contents.m_pPlot->isFriendlyCity(*u);
  if(!ready||owner!=u->getOwner()||team!=u->getTeam()||branch!=currentBranch){
   owner=u->getOwner();team=u->getTeam();branch=currentBranch;
   BuildOutcome(contents,owner,team,branch,candidates,friendlyDamage,enemyDamage,outcome);ready=true;
  }
  return ExtractOutcome(contents,u,friendlyDamage,outcome);
 }
};
'''
# Reuse only randomized setup, not the existing projection oracle/metadata tests.
tests=values['tests'];tests=tests[:tests.index('  const vector<int>&ids=c.GetStackDangerDamageIDs();')]
tests=tests.replace('trial<24000','trial<16000').replace('friendly.SetValue(i,(int)(next()%121))','friendly.SetValue(i,(int)(next()%151)-20)').replace('players[p].id=p;','players[p].id=p;players[p].team=p;for(int q=0;q<4;++q)teams[p].open[q]=false;')
tests=tests.replace('target.friendly=trial%3==0;', 'target.city=trial%3==0?&defended:NULL;target.friendly=trial%3==0;')
tests=tests.replace('  for(int i=0;i<10;++i){', '  if(trial%5==0)reverse(candidates.begin(),candidates.end());if(trial%7==0)candidates.push_back(&defenders[1]);\n  for(int i=0;i<10;++i){')
tests+=r'''
  OutcomeBatch batch(c,candidates,friendly,full);long begin=outcomeBuilds;
  for(int i=0;i<5;++i)expect("all members original scalar equals ledger",c.GetStackDanger(&defenders[i],candidates,friendly,full)==batch.Get(&defenders[i]));
  expect("same context one outcome",outcomeBuilds-begin==1);
  vector<const CvUnit*>after=candidates;after.erase(remove(after.begin(),after.end(),&defenders[0]),after.end());OutcomeBatch afterBatch(c,after,friendly,full);
  for(int i=1;i<5;++i)expect("departure roster exact independent outcome",c.GetStackDanger(&defenders[i],after,friendly,full)==afterBatch.Get(&defenders[i]));
  SUnitIDValueContainer changed=friendly;changed.ChangeValue(4,45);OutcomeBatch aaBatch(c,candidates,changed,full);
  for(int i=0;i<5;++i)expect("offstack AA wounds bound exactly",c.GetStackDanger(&defenders[i],candidates,changed,full)==aaBatch.Get(&defenders[i]));
  CvUnit other=defenders[0];other.owner=2;other.team=2;other.combatOwner=trial%2?0:2;teams[0].open[2]=trial%4==0;
  expect("different owner team hidden combatowner branch exact",c.GetStackDanger(&other,candidates,friendly,full)==batch.Get(&other));
  expect("reenter original context exact",c.GetStackDanger(&defenders[2],candidates,friendly,full)==batch.Get(&defenders[2]));
  CvUnit alias=defenders[2];alias.terrainIgnore=!alias.terrainIgnore;expect("rawID alias distinct hazards exact",c.GetStackDanger(&alias,candidates,friendly,full)==batch.Get(&alias));
 }
 for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=p;players[p].team=p;for(int q=0;q<4;++q){teams[p].open[q]=false;if(q!=p)players[p].enemies.push_back(q);}}
 target.city=NULL;target.owner=0;target.terrain=0;target.feature=0;
 CvDangerPlotContents c;c.m_pPlot=&target;vector<const CvUnit*>roster;SUnitIDValueContainer empty;
 for(int i=0;i<5;++i){defenders[i]=CvUnit(10+i,0,&target);defenders[i].strength=1000;roster.push_back(&defenders[i]);}
 attackers[0]=CvUnit(34,1,&near);attackers[0].ranged=true;attackers[0].collateralLimit=0;players[1].units[34]=&attackers[0];c.m_apUnits.push_back(make_pair(1,34));
 fieldLeafs=cityLeafs=0;for(int i=0;i<5;++i)c.GetStackDanger(&defenders[i],roster,empty,empty);long originalLeaves=fieldLeafs+cityLeafs;
 fieldLeafs=cityLeafs=0;OutcomeBatch batch(c,roster,empty,empty);for(int i=0;i<5;++i)batch.Get(&defenders[i]);long splitLeaves=fieldLeafs+cityLeafs;
 expect("five control leaf traversals",originalLeaves==5);expect("one outcome traversal",splitLeaves==1);
 // Prove the off-stack injury case is sensitive, not merely equal in a quiet scene.
 CvUnit interceptor(93,0,&near);interceptor.domain=DOMAIN_AIR;interceptor.strength=500;interceptor.chance=100;interceptor.attempts=4;
 players[0].units[93]=&interceptor;players[0].possible.push_back(make_pair(93,0));attackers[0].domain=DOMAIN_AIR;
 SUnitIDValueContainer hurt;hurt.SetValue(93,100);
 const int aaSafe=c.GetStackDanger(&defenders[0],roster,empty,empty),aaHurt=c.GetStackDanger(&defenders[0],roster,hurt,empty);
 expect("offstack AA injuries materially affect exact original",aaHurt>aaSafe);
 OutcomeBatch safeAA(c,roster,empty,empty),hurtAA(c,roster,hurt,empty);
 expect("outside AA live outcome exact",safeAA.Get(&defenders[0])==aaSafe);
 expect("outside AA dead outcome exact",hurtAA.Get(&defenders[0])==aaHurt);
 // City-fall sentinel preempts even deliberately large unit hazards for everyone.
 target.city=&defended;defended.hp=1;attackers[0].domain=DOMAIN_LAND;attackers[0].ranged=false;
 c.m_iImprovementDamage=90;c.m_iFogCount=8;c.m_bFlatPlotDamage=true;target.terrain=500;
 OutcomeBatch falling(c,roster,empty,empty);
 for(int i=0;i<5;++i){expect("actual capture sentinel",c.GetStackDanger(&defenders[i],roster,empty,empty)==INT_MAX);expect("shared capture sentinel",falling.Get(&defenders[i])==INT_MAX);}
 printf("ledger prototype: %d checks, %d failures; five members originalLeafs=%ld outcomeLeafs=%ld\n",checks,failures,originalLeaves,splitLeaves);return failures?1:0;
}
'''
currentScalar=function(danger,'int CvDangerPlotContents::GetStackDanger(')
def without_optional_selector(body):
 # This normalization is assertion-only. Compile complete actual callback
 # signatures/bodies; prove NULL dispatch preserves every original statement.
 assert body.count('(selector ? selector : CvUnitCombat::SelectStackDefender)')==1
 return body.replace('(selector ? selector : CvUnitCombat::SelectStackDefender)',
                     'CvUnitCombat::SelectStackDefender',1)
if 'void CvDangerPlotContents::GetStackDangerOutcome(' in danger:
 outcomeSource=function(danger,'void CvDangerPlotContents::GetStackDangerOutcome(')
 currentField=outcomeSource[outcomeSource.index(' SUnitIDValueContainer interceptionUses;'):outcomeSource.rindex('}')]
 originalField=scalar[scalar.index(' SUnitIDValueContainer interceptionUses;'):scalar.rindex(' int result = max(0,')]
 assert without_optional_selector(currentField)==originalField.replace('pUnit->getOwner()','defendingOwner').replace('pUnit->getTeam()','defendingTeam'), 'Attack-sequence duplication drift: review upstream math/dependencies'
 extractionSource=function(danger,'int CvDangerPlotContents::GetStackDangerFromOutcome(')
 assert extractionSource[extractionSource.index(' int result = max(0,'):extractionSource.rindex('}')]==scalar[scalar.rindex(' int result = max(0,'):scalar.rindex('}')], 'Damage/hazard extraction drift'
 assert currentScalar.count('enemyDamage, StackDangerDefenderSelector selector)')==1
 normalized=without_optional_selector(currentScalar).replace('enemyDamage, StackDangerDefenderSelector selector)', 'enemyDamage)',1)
 assert normalized==scalar, 'Scalar default changed: review baseline/callback ordering'
 currentScalar+='\n'+outcomeSource+'\n'+extractionSource
contents=contents.replace('\tint GetStackDanger(const CvUnit*', '\tint GetStackDangerControl(const CvUnit*,const std::vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&);\n\tint GetStackDanger(const CvUnit*',1)
controlScalar=scalar.replace('::GetStackDanger(', '::GetStackDangerControl(',1)
tests=tests.replace('  OutcomeBatch batch(c,candidates,friendly,full);long begin=outcomeBuilds;', '  for(int i=0;i<5;++i)expect(\"original control equals actual refactor\",c.GetStackDangerControl(&defenders[i],candidates,friendly,full)==c.GetStackDanger(&defenders[i],candidates,friendly,full));\n  OutcomeBatch batch(c,candidates,friendly,full);long begin=outcomeBuilds;')
fixture=prefix+container+services+context+friendly+selector_type+contents+air+expected+collateral+city+controlScalar+currentScalar+prototype+tests
cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(danger.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),returncode=r.returncode,output=r.stdout+r.stderr,scope='Actual unchanged complete scalar, city/air/collateral forecast bodies and CvPlot.isFriendlyCity body compared against exact-source split prototype. Deterministic numerical strength and selector services. No production changes, native DLL build or game run.'),indent=2),encoding='utf-8')
sys.exit(r.returncode)
