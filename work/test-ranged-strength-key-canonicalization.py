"""Compare actual production kind1 projected keys with pinned raw DLL57 keys.

Engine/player/plot/religion/aura services are deterministic substitutes, but the
full ranged and wound bodies are actual and byte-matched to the original source.
Compiles the actual22word key/module/current wrapper; no DLL build or game calls.
"""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/ranged-strength-canonical-regression';out.mkdir(exist_ok=True)
unit=(core/'CvUnit.cpp').read_text(encoding='utf-8-sig');header=(core/'CvStackingStrengthCache.h').read_text();module=(core/'CvStackingStrengthCache.cpp').read_text()
old=subprocess.check_output(['git','show','c6067cda5:CvGameCoreDLL_Expansion2/CvUnit.cpp'],cwd=root).decode('utf-8-sig')
raw57=subprocess.check_output(['git','show','dea6f2eaeea535489ed91115adb37c9c5bc4cc01:CvGameCoreDLL_Expansion2/CvUnit.cpp'],cwd=root).decode('utf-8-sig')
def function(text,name):
 a=text.index(name);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
body=function(unit,'int CvUnit::GetMaxRangedCombatStrengthUncached(');reference=function(old,'int CvUnit::GetMaxRangedCombatStrength(')
assert body[body.index('{'):]==reference[reference.index('{'):],'Original ranged math changed'
wound=function(unit,'int CvUnit::GetDamageCombatModifier(')
assert wound[wound.index('{'):]==function(old,'int CvUnit::GetDamageCombatModifier(')[function(old,'int CvUnit::GetDamageCombatModifier(').index('{'):]
assert len(re.findall(r'\biAssumeExtraDamage\b',body))==2 and len(re.findall(r'\biAssumeExtraOtherDamage\b',body))==3
assert '< (pOtherUnit->GetMaxHitPoints() + 1) / 2' in body
scaffold={};tree=ast.parse((root/'work/test-full-melee-strength-cache.py').read_text(encoding='utf-8-sig'))
for n in tree.body:
 if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):
  for target in n.targets:
   if isinstance(target,ast.Name):scaffold[target.id]=n.value.value
getnode=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='getters' for t in n.targets));getters=ast.literal_eval(getnode.func.value).split()
unitnode=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='unitdecl' for t in n.targets))
existing=set(getters)|{'GetBaseCombatStrength','GetDamageCombatModifier','getOwner','getTeam','getDomainType','getDamage','plot','noDefensiveBonus'}
excluded={'if','for','min','max','VALIDATE_OBJECT','GD_INT_GET','GET_PLAYER','atWar','GetBaseRangedCombatStrength','isRangedSupportFire'}
own=set(re.findall(r'(?<![>:\.])\b([A-Za-z_]\w*)\(',body));extra=sorted(own-existing-excluded)
getters+=extra;numeric='\n'.join(' int '+name+'(int value=0)const{return modifiers[G_'+name+']*(1+(value&1));}' for name in getters)
plotMethods={'GetReverseGreatGeneralModifier','GetGiveCombatModToUnit','GetNearbyCityBonusCombatMod','GetCombatModifierFromCapitalDistance'}
for name in plotMethods:
 numeric=numeric.replace('int '+name+'(int value=0)const{return modifiers[G_'+name+']*(1+(value&1));}','int '+name+'(const CvPlot*p=NULL)const{return modifiers[G_'+name+']+(p?p->bonus:0);}')
numeric=numeric.replace('int GetResistancePower(int value=0)const{return modifiers[G_GetResistancePower]*(1+(value&1));}','int GetResistancePower(const CvUnit*p)const{return modifiers[G_GetResistancePower]+(p?p->owner:0);}')
def evaluate(n):
 if isinstance(n,ast.Constant):return n.value
 if isinstance(n,ast.Name) and n.id=='numeric':return numeric
 if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):return evaluate(n.left)+evaluate(n.right)
 raise RuntimeError('Unexpected scaffold expression')
unitdecl=evaluate(unitnode)
unitdecl=unitdecl.replace(' int GetBaseRangedCombatStrength()const{return base;}bool isRangedSupportFire()const{return false;}\n', '')
unitdecl=unitdecl.replace(' int GetDamageCombatModifier(bool,int)const;', ' int rangedBase;bool supportFire;\n int GetBaseRangedCombatStrength()const{return rangedBase;}bool isRangedSupportFire()const{return supportFire;}\n bool IsHigherTechThan(int type)const{return unitClass>type;}bool IsLargerCivThan(const CvUnit*p)const{return p&&owner>p->owner;}\n int GetDamageCombatModifier(bool,int)const;')
unitdecl=unitdecl.replace('fallback(2),generic(0),at(NULL)', 'fallback(2),generic(0),at(NULL)')
unitdecl=unitdecl.replace('memset(attacked,0,sizeof(attacked));memset(modifiers,0,sizeof(modifiers));}', 'memset(attacked,0,sizeof(attacked));memset(modifiers,0,sizeof(modifiers));rangedBase=12;supportFire=false;}')
declaration=next(line for line in unitdecl.splitlines() if 'int GetMaxRangedCombatStrength(' in line)
unitdecl=unitdecl.replace(declaration,declaration+'\n'+declaration.replace('GetMaxRangedCombatStrength(','GetMaxRangedCombatStrengthCanonical(',1)+'\n'+declaration.replace('GetMaxRangedCombatStrength(','GetMaxRangedCombatStrengthOriginal(',1)+'\n'+declaration.replace('GetMaxRangedCombatStrength(','GetMaxRangedCombatStrengthRaw57(',1))
prefix=scaffold['prefix'];prefix=prefix.replace('struct CvUnit;struct CvCity;','typedef int UnitTypes;typedef int ReligionTypes;const int NO_RELIGION=-1,NO_PLAYER=-1,AE_GREAT_GENERAL=4;bool MOD_API_AREA_EFFECT_PROMOTIONS=true;\nstruct CvUnit;struct CvCity;struct CvPlayerReligions;struct MinorAI;struct FakeGame;struct CvCityReligions;\nstruct CvUnit;struct CvCity;')
prefix=prefix.replace('bool IsFriendlyUnitAdjacent(int,bool)', 'int getOwner()const{return owner;}bool isInternationalBorder()const{return (index&1)!=0;}CvCity*getOwningCity()const{return city;}int GetEffectiveFlankingBonusAtRange(const CvUnit*,const CvUnit*)const{return flank;}\n bool IsFriendlyUnitAdjacent(int,bool)')
prefix=prefix.replace('int getOwner()const{return owner;}int GetID()const{return id;}int getDamage()const{return damage;}CvPlot*plot()', 'int getTeam()const{return owner;}CvCityReligions*GetCityReligions()const;int getGarrisonRangedAttackModifier()const{return damage%17;}int getOwner()const{return owner;}int GetID()const{return id;}int getDamage()const{return damage;}CvPlot*plot()')
traitsMethods=['GetGoldenAgeCombatModifier','GetAllianceCSStrength','GetCityStateCombatModifier','GetCombatBonusVsHigherTech','GetCombatBonusVsLargerCiv','GetCombatBonusVsHigherPop','GetConquestOfTheWorldCityAttack']
prefix=prefix.replace('struct Traits{int multiple;', 'struct Traits{int value;'+''.join('int '+n+'()const{return value;}' for n in traitsMethods)+'int multiple;').replace('Traits():multiple(3),fightWell(false)', 'Traits():value(0),multiple(3),fightWell(false)')
prefix=prefix.replace('struct CvPlayer{int attackTurns,', 'typedef Traits CvPlayerTraits;\nstruct CvPlayer{int id;CvPlayerReligions*GetReligions()const;MinorAI*GetMinorCivAI()const;bool IsEmpireUnhappy()const{return id==3;}bool isGoldenAge()const{return id==1;}bool isMinorCiv()const{return id==2;}bool isMajorCiv()const{return id!=2;}int GetNumCSAllies()const{return id+1;}int GetCityStateCombatModifier()const{return sapper;}int GetBarbarianCombatBonus(bool)const{return attackMonopoly;}int getTotalPopulation()const{return 13+id*4;}\n int attackTurns,').replace('CvPlayer():attackTurns(0)', 'CvPlayer():id(0),attackTurns(0)')
prefix=prefix.replace('const Traits*GetPlayerTraits()const{return &traits;}', 'Traits*GetPlayerTraits(){return &traits;}const Traits*GetPlayerTraits()const{return &traits;}')
prefix=prefix.replace('struct Globals{CvBaseInfo infos[3];', 'struct Globals{FakeGame&getGame();CvBaseInfo infos[3];')
extraServices=r'''
struct CvCityReligions{int majority;CvCityReligions():majority(-1){}int GetReligiousMajority()const{return majority;}}cityReligions;
CvCityReligions*CvCity::GetCityReligions()const{return &cityReligions;}
struct CvPlayerReligions{int state;CvPlayerReligions():state(-1){}int GetStateReligion()const{return state;}}religions[4];
struct MinorAI{int ally;MinorAI():ally(-1){}int GetAlly()const{return ally;}}minorAIs[4];
CvPlayerReligions*CvPlayer::GetReligions()const{return &religions[id%4];}MinorAI*CvPlayer::GetMinorCivAI()const{return &minorAIs[id%4];}
struct Beliefs{int value;Beliefs():value(3){}int GetCombatModifierFriendlyCities(int,const CvCity*)const{return value;}int GetCombatModifierEnemyCities(int,const CvCity*)const{return value+1;}int GetCombatBonusOwnLands(int,const CvCity*)const{return value+2;}int GetCombatBonusVersusOtherReligionOwnLands(int,const CvCity*)const{return value+3;}int GetCombatBonusTheirLands(int,const CvCity*)const{return value+4;}int GetCombatBonusVersusOtherReligionTheirLands(int,const CvCity*)const{return value+5;}};
struct CvReligion{Beliefs m_Beliefs;CvCity*GetHolyCity()const{return NULL;}}oneReligion;
struct CvGameReligions{const CvReligion*GetReligion(int religion,int)const{return religion==-1?NULL:&oneReligion;}};
struct FakeGame{CvGameReligions religions;CvGameReligions*GetGameReligions(){return &religions;}}game;
FakeGame&Globals::getGame(){return game;}bool atWar(int a,int b){return a!=b;}
int D_BALANCE_MAX_CS_ALLY_STRENGTH=5;
static unsigned rangedComputes=0,woundCalls=0;static int mutateMode=0;
static void OnRanged(){if(mutateMode==1)CvStackingStrengthCache::Invalidate();if(mutateMode==2){CvStackingStrengthCache::Scope nested(64);}}
'''
key=function(unit,'static CvStackingStrengthCache::Key MakeStackStrengthKey(');raw=function(unit,'int CvUnit::GetMaxRangedCombatStrength(')
canonical=r'''
static void CanonicalizeRanged(CvStackingStrengthCache::Key&key,const CvUnit*self,const CvUnit*other,bool attacking,int extra,int otherExtra){
 const int base=self->isRangedSupportFire()?self->GetBaseCombatStrength()/2:self->GetBaseRangedCombatStrength();
 key.values[17]=key.values[18]=0;
 if(base!=0){key.values[17]=self->GetDamageCombatModifier(!attacking,key.values[4]+extra);
  if(attacking&&other){const int damage=key.values[9]+otherExtra;key.values[18]=(damage>0?1:0)|(damage<(key.values[10]+1)/2?2:0);}}
}
'''
wrapper=raw.replace('GetMaxRangedCombatStrength(','GetMaxRangedCombatStrengthCanonical(',1)
assert 'effectiveBase' in wrapper and 'key.values[17]' in wrapper and 'MOD_EVENTS_CAN_MOVE_INTO && bAttacking && pCity' in wrapper
canonical+=wrapper+'\n'+function(raw57,'int CvUnit::GetMaxRangedCombatStrength(').replace('GetMaxRangedCombatStrength(','GetMaxRangedCombatStrengthRaw57(',1)
actual=body.replace('{','{\n ++rangedComputes;OnRanged();',1);reference=reference.replace('GetMaxRangedCombatStrength(','GetMaxRangedCombatStrengthOriginal(',1);wound=wound.replace('{','{\n ++woundCalls;',1)
module='\n'.join(line for line in module.splitlines() if line not in ('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"'))
setup=r'''
using namespace CvStackingStrengthCache;int checks=0,failures=0;void expect(const char*n,bool okay){++checks;if(!okay){++failures;if(failures<20)printf("FAIL %s\n",n);}}
unsigned seed=71353;unsigned next(){seed=seed*1664525u+1013904223u;return seed;}
static void Reset(CvUnit&a,CvUnit&b,CvCity&city,CvPlot*plots){a=CvUnit(1);b=CvUnit(2);a.at=&plots[1];b.at=&plots[3];b.owner=1;city=CvCity();city.at=&plots[3];plots[3].city=&city;for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=p;religions[p].state=-1;minorAIs[p].ally=-1;}}
static Key QueryKey(CvUnit&a,const CvUnit*b,const CvCity*c,bool attack,const CvPlot*from,const CvPlot*to,bool ignore,bool quick,int wounds,int otherWounds){
 const CvPlot*target=to?to:(b?b->plot():(c?c->plot():NULL));Key key=MakeStackStrengthKey(1,&a,b,c,from?from:a.plot(),target,attack,ignore,quick,wounds,otherWounds);CanonicalizeRanged(key,&a,b,attack,wounds,otherWounds);return key;}
static vector<int>Words(const Key&key){return vector<int>(key.values,key.values+22);}
struct PressureStats{unsigned long misses,evictions;unsigned int peak;};
static PressureStats Pressure(CvUnit&a,CvUnit&b,bool attack,bool canonical){Scope scope(64);for(int pass=0;pass<2;++pass)for(int own=0;own<80;++own)for(int other=-10;other<110;++other){
 int expected=a.GetMaxRangedCombatStrengthOriginal(&b,NULL,attack,NULL,NULL,false,true,own,other);
 int value=canonical?a.GetMaxRangedCombatStrengthCanonical(&b,NULL,attack,NULL,NULL,false,true,own,other):a.GetMaxRangedCombatStrengthRaw57(&b,NULL,attack,NULL,NULL,false,true,own,other);
 expect("pressure trace full original ranged result",value==expected);expect("shared pressure capacity unchanged",GetStats().entries<=64);}
 Stats stats=GetStats();PressureStats result={stats.rangedMisses,stats.evictions,stats.peakEntries};return result;}
static void DirtyKey(){Invalidate();}static void NestedKey(){Scope nested(64);}
static DWORD WINAPI ForeignRanged(void*data){CvUnit*a=(CvUnit*)data;Scope skipped(64);unsigned before=rangedComputes;int first=a->GetMaxRangedCombatStrengthCanonical(NULL,NULL,true,NULL,NULL,false,true,7,8);int second=a->GetMaxRangedCombatStrengthCanonical(NULL,NULL,true,NULL,NULL,false,true,7,8);long generation;return !Context(generation)&&first==second&&rangedComputes==before+2?0:1;}

'''
tests=r'''
int main(){CvPlot plots[8];for(int i=0;i<8;++i)plots[i]=CvPlot(i);CvUnit a,b;CvCity city;Reset(a,b,city,plots);expect("native x86",sizeof(void*)==4);
 {Scope scope(16384);for(int trial=0;trial<300;++trial){Reset(a,b,city,plots);a.owner=next()%4;b.owner=next()%4;a.damage=next()%100;b.damage=next()%100;b.maxHP=1+next()%200;a.rangedBase=next()%4?5+next()%40:0;a.base=next()%8;a.supportFire=next()%3==0;a.strongerWounded=next()%4==0;a.fightWounded=next()%4==0;
  for(int g=0;g<G_Count;++g)a.modifiers[g]=(int)(next()%21)-10;
  for(int p=0;p<4;++p){players[p].wounded=(int)(next()%51)-25;players[p].traits.value=next()%9;players[p].traits.fightWell=next()%3==0;religions[p].state=trial%3==0?0:-1;}cityReligions.majority=trial%2?0:-1;
  MOD_BALANCE_RANGED_DEFENSE_UNIT_HEALTH=next()%2!=0;D_WOUNDED_DAMAGE_MULTIPLIER=1+next()%80;Invalidate();map<vector<int>,int>values;
  bool attack=next()%2!=0,ignore=next()%2!=0,quick=next()%2!=0;const CvUnit*other=trial%5?&b:NULL;const CvCity*c=trial%4?NULL:&city;const CvPlot*from=trial%3?&plots[next()%8]:NULL;const CvPlot*to=trial%6?&plots[next()%8]:NULL;
  int choices[]={-b.damage-1,-b.damage,1-b.damage,(b.maxHP+1)/2-b.damage-1,(b.maxHP+1)/2-b.damage,(b.maxHP+1)/2-b.damage+1,70};
  for(int own=-a.damage-6;own<130;own+=3)for(int j=0;j<7;++j){Key key=QueryKey(a,other,c,attack,from,to,ignore,quick,own,choices[j]);int expected=a.GetMaxRangedCombatStrengthOriginal(other,c,attack,from,to,ignore,quick,own,choices[j]);pair<map<vector<int>,int>::iterator,bool>inserted=values.insert(make_pair(Words(key),expected));
   expect("equal canonical key gives equal complete original ranged math",inserted.second||inserted.first->second==expected);
   expect("canonical wrapper preserves full ranged result",a.GetMaxRangedCombatStrengthCanonical(other,c,attack,from,to,ignore,quick,own,choices[j])==expected);
   Key rawKey=MakeStackStrengthKey(1,&a,other,c,from?from:a.plot(),to?to:(other?other->plot():(c?c->plot():NULL)),attack,ignore,quick,own,choices[j]);for(int f=0;f<22;++f)if(f!=17&&f!=18)expect("other key fields unchanged",key.values[f]==rawKey.values[f]);
  }
 }}
 {Scope scope(16384);Reset(a,b,city,plots);b.maxHP=101;b.damage=0;Key a50=QueryKey(a,&b,NULL,true,NULL,NULL,false,true,0,50),a51=QueryKey(a,&b,NULL,true,NULL,NULL,false,true,0,51);expect("ranged oddHP ceiling differs at51",a50.values[18]!=a51.values[18]);
  Key d0=QueryKey(a,&b,NULL,false,NULL,NULL,false,true,7,0),d99=QueryKey(a,&b,NULL,false,NULL,NULL,false,true,7,99);expect("ranged defense ignores projected opponent wounds",d0==d99);
  a.damage=100;a.rangedBase=0;a.supportFire=false;Invalidate();woundCalls=0;const int extreme[]={INT_MIN,INT_MAX};for(int i=0;i<2;++i)expect("zero effective base ignores extreme wounds",a.GetMaxRangedCombatStrengthCanonical(&b,&city,true,NULL,NULL,false,false,extreme[i],extreme[i])==a.GetMaxRangedCombatStrengthOriginal(&b,&city,true,NULL,NULL,false,false,extreme[i],extreme[i]));expect("zero effective base skips newly evaluated wound helper",woundCalls==0);
  a.supportFire=true;a.base=1;Invalidate();woundCalls=0;expect("support combat1 integerhalf is zero",a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,false,INT_MAX,INT_MAX)==0&&woundCalls==0);a.base=2;Invalidate();expect("support combat2 uses positive effective base",a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,false,7,3)==a.GetMaxRangedCombatStrengthOriginal(&b,NULL,true,NULL,NULL,false,false,7,3));
  a.supportFire=false;a.rangedBase=12;a.damage=0;Invalidate();for(int i=0;i<2;++i){expect("NULL opponent ignored extreme wounds even at city",a.GetMaxRangedCombatStrengthCanonical(NULL,&city,true,NULL,NULL,false,true,7,extreme[i])==a.GetMaxRangedCombatStrengthOriginal(NULL,&city,true,NULL,NULL,false,true,7,extreme[i]));expect("defense ignored extreme opponent wounds",a.GetMaxRangedCombatStrengthCanonical(&b,NULL,false,NULL,NULL,false,true,7,extreme[i])==a.GetMaxRangedCombatStrengthOriginal(&b,NULL,false,NULL,NULL,false,true,7,extreme[i]));}
  MOD_EVENTS_CAN_MOVE_INTO=true;for(int quick=0;quick<2;++quick){unsigned before=blockadeEvents;a.GetMaxRangedCombatStrengthCanonical(&b,&city,true,NULL,NULL,false,quick!=0,7,3);a.GetMaxRangedCombatStrengthCanonical(&b,&city,true,NULL,NULL,false,quick!=0,7,3);expect("city script bypass applies even quick",blockadeEvents==before+2);}MOD_EVENTS_CAN_MOVE_INTO=false;
  for(int mode=1;mode<=2;++mode){mutateMode=mode;unsigned before=rangedComputes;a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,false,7,3);a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,false,7,3);expect("generation mutation rejects outcome admission",rangedComputes==before+2);}mutateMode=0;
 }
 {Scope scope(64);Reset(a,b,city,plots);b.maxHP=INT_MAX;
  expect("defense ignores unusable ceiling expression at extreme otherHP",a.GetMaxRangedCombatStrengthCanonical(&b,NULL,false,NULL,NULL,false,true,7,INT_MAX)==a.GetMaxRangedCombatStrengthOriginal(&b,NULL,false,NULL,NULL,false,true,7,INT_MAX));
  b.maxHP=100;for(int mode=1;mode<=2;++mode){keyCallback=mode==1?DirtyKey:NestedKey;unsigned before=rangedComputes;a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,true,7,8);a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,true,7,8);expect("key invalidation preserves guarded admission",rangedComputes==before+2);}keyCallback=NULL;
  b.maxHP=100;Invalidate();{Scope nested(64);unsigned before=rangedComputes;a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,true,7,8);a.GetMaxRangedCombatStrengthCanonical(&b,NULL,true,NULL,NULL,false,true,7,8);expect("nested calls remain private fallback",rangedComputes==before+2);}
  HANDLE thread=CreateThread(NULL,0,ForeignRanged,&a,0,NULL);expect("foreign fixture started",thread!=NULL);if(thread){expect("foreign fixture completes",WaitForSingleObject(thread,10000)==WAIT_OBJECT_0);DWORD code=99;GetExitCodeThread(thread,&code);expect("foreign calls retain private fallback",code==0);CloseHandle(thread);}
 }
 {unsigned before=rangedComputes;a.GetMaxRangedCombatStrengthCanonical(NULL,NULL,true,NULL,NULL,false,true,7,8);a.GetMaxRangedCombatStrengthCanonical(NULL,NULL,true,NULL,NULL,false,true,7,8);expect("inactive calls remain uncached",rangedComputes==before+2);}
 {Scope disabled(0);unsigned before=rangedComputes;a.GetMaxRangedCombatStrengthCanonical(NULL,NULL,true,NULL,NULL,false,true,7,8);a.GetMaxRangedCombatStrengthCanonical(NULL,NULL,true,NULL,NULL,false,true,7,8);expect("zero budget preserves original fallback",rangedComputes==before+2);}
 Reset(a,b,city,plots);D_WOUNDED_DAMAGE_MULTIPLIER=33;MOD_BALANCE_RANGED_DEFENSE_UNIT_HEALTH=true;
 PressureStats rawAttack=Pressure(a,b,true,false),canonicalAttack=Pressure(a,b,true,true),rawDefense=Pressure(a,b,false,false),canonicalDefense=Pressure(a,b,false,true);
 expect("bounded attack trace has fewer duplicate misses",canonicalAttack.misses<rawAttack.misses&&canonicalAttack.evictions<rawAttack.evictions&&canonicalAttack.peak<=64);
 expect("bounded defense trace has fewer duplicate misses",canonicalDefense.misses<rawDefense.misses&&canonicalDefense.evictions<rawDefense.evictions&&canonicalDefense.peak<=64);
 printf("ranged synthetic pressure, limit64: attacking misses%lu->%lu evictions%lu->%lu; defending misses%lu->%lu evictions%lu->%lu. Not native speed.\n",rawAttack.misses,canonicalAttack.misses,rawAttack.evictions,canonicalAttack.evictions,rawDefense.misses,canonicalDefense.misses,rawDefense.evictions,canonicalDefense.evictions);
 printf("ranged canonical production complete actual-math regression: %d checks, %d failures\n",checks,failures);return failures?1:0;}
'''
fixture=prefix+'enum Getter{'+','.join('G_'+g for g in getters)+',G_Count};\n'+unitdecl+header.replace('#pragma once','')+module+extraServices+wound+key+raw+actual+reference+canonical+setup+tests
cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8')
if '--emit-only' in sys.argv:print('Ranged fixture prepared, no compile/run');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for keyname in ('CL','_CL_','LINK'):env.pop(keyname,None)
exe=out/'test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='');(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,source_sha256=hashlib.sha256(unit.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope='Complete actual ranged/wound bodies byte-matched c6067cda5; actual22word key/module/production wrapper vs pinned raw57 kind1 wrapper. Engine/aura/player/religion/plot services deterministic. Fixture execution does not edit production or build/run the DLL/game.'),indent=2),encoding='utf-8');sys.exit(run.returncode)
