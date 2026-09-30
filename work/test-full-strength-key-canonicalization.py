"""Actual full attack/defense projected-wound key canonicalization regression.

No production edit. Actual keys, cache/context, complete unchanged attack/defense,
wound and embark math are compiled. Engine services are deterministic substitutes
from the existing full-melee fixture; numeric body equality is pinned to DLL47.
"""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/full-strength-canonical-regression';out.mkdir(exist_ok=True)
text=(core/'CvUnit.cpp').read_text(encoding='utf-8-sig');header=(core/'CvStackingStrengthCache.h').read_text();module=(core/'CvStackingStrengthCache.cpp').read_text()
old=subprocess.check_output(['git','show','3b008c0d4:CvGameCoreDLL_Expansion2/CvUnit.cpp'],cwd=root).decode('utf-8-sig')
raw54=subprocess.check_output(['git','show','0273c8e3e5104493af3be6ae62aec50bb576f7ae:CvGameCoreDLL_Expansion2/CvUnit.cpp'],cwd=root).decode('utf-8-sig')
def function(source,name):
 start=source.index(name);opening=source.index('{',start);end=opening+1;depth=1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end],source[opening:end]
# Read literal scaffold without running/importing the other native test.
scaffold={};tree=ast.parse((root/'work/test-full-melee-strength-cache.py').read_text(encoding='utf-8-sig'))
for node in tree.body:
 if isinstance(node,ast.Assign):
  for target in node.targets:
   if isinstance(target,ast.Name) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):scaffold[target.id]=node.value.value
getter_node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='getters' for t in n.targets))
getters=ast.literal_eval(getter_node.func.value).split();numeric='\n'.join(' int '+name+'(int value=0)const{return modifiers[G_'+name+']*(1+(value&1));}' for name in getters)
unit_node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='unitdecl' for t in n.targets))
def literal_parts(node):
 if isinstance(node,ast.Constant):return node.value
 if isinstance(node,ast.Name) and node.id=='numeric':return numeric
 if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):return literal_parts(node.left)+literal_parts(node.right)
 raise RuntimeError('Unexpected scaffold expression')
unitdecl=literal_parts(unit_node)
for name in ('GetMaxAttackStrength','GetMaxDefenseStrength'):
 declaration=next(line for line in unitdecl.splitlines() if 'int '+name+'(' in line)
 unitdecl=unitdecl.replace(declaration,declaration+'\n'+declaration.replace(name+'(',name+'Canonical(',1)+'\n'+declaration.replace(name+'(',name+'Raw54(',1))
prefix=scaffold['prefix'];services='unsigned int woundModifierCalls=0;\n'+scaffold['services'];enum='enum Getter{'+','.join('G_'+name for name in getters)+',G_Count};\n'
bodies=[];references=[]
for name,counter in (('GetMaxAttackStrength','attackComputes'),('GetMaxDefenseStrength','defenseComputes')):
 actual,body=function(text,'int CvUnit::'+name+'Uncached(');original,originalbody=function(old,'int CvUnit::'+name+'(')
 assert body==originalbody,name+' original math drifted'
 bodies.append(actual.replace('{','{\n ++'+counter+';OnCompute();',1));references.append(original.replace(name+'(',name+'Original(',1))
attack_body=function(text,'int CvUnit::GetMaxAttackStrengthUncached(')[0];defense_body=function(text,'int CvUnit::GetMaxDefenseStrengthUncached(')[0]
assert len(re.findall(r'\biAssumeExtraDamage\b',attack_body))==2 and len(re.findall(r'\biAssumeExtraOtherDamage\b',attack_body))==3
assert len(re.findall(r'\biAssumeExtraDamage\b',defense_body))==2
assert 'GetDamageCombatModifier(false, getDamage() + iAssumeExtraDamage)' in attack_body
assert 'GetDamageCombatModifier(bFromRangedAttack, getDamage() + iAssumeExtraDamage)' in defense_body
assert 'pDefender->getDamage() + iAssumeExtraOtherDamage > 0' in attack_body
assert 'pDefender->getDamage() + iAssumeExtraOtherDamage < (pDefender->GetMaxHitPoints()/2)' in attack_body
leafmath=[]
for name in ('GetDamageCombatModifier','GetEmbarkedUnitDefense'):
 actual,body=function(text,'int CvUnit::'+name+'(');assert body==function(old,'int CvUnit::'+name+'(')[1]
 if name=='GetDamageCombatModifier':actual=actual.replace('{','{\n ++woundModifierCalls;',1)
 leafmath.append(actual)
key=function(text,'static CvStackingStrengthCache::Key MakeStackStrengthKey(')[0]
wrappers='\n'.join(function(text,'int CvUnit::'+name+'(')[0] for name in ('GetGenericMeleeStrengthModifier','GetMaxRangedCombatStrength','GetMaxAttackStrength','GetMaxDefenseStrength'))
canonical=r'''
static void CanonicalizeProjectedWounds(CvStackingStrengthCache::Key&key,const CvUnit*self,const CvUnit*other,
 int extra,int otherExtra,bool rangedDefense){
 if(key.values[0]!=2&&key.values[0]!=3)return;
 const bool embarked=key.values[0]==3&&((key.values[15]<0&&(key.values[16]&16)!=0)||(key.values[15]>=0&&(key.values[16]&32)!=0&&(key.values[16]&64)!=0));
 const bool usesWounds=!embarked&&self->GetBaseCombatStrength()!=0;
 key.values[17]=usesWounds?self->GetDamageCombatModifier(key.values[0]==3&&rangedDefense,key.values[4]+extra):0;
 if(key.values[0]==2){
  key.values[18]=0;
  if(usesWounds&&other){const int otherDamage=key.values[9]+otherExtra;key.values[18]=(otherDamage>0?1:0)|(otherDamage<key.values[10]/2?2:0);}
 }
}
'''
for name in ('GetMaxAttackStrength','GetMaxDefenseStrength'):
 wrapper=function(text,'int CvUnit::'+name+'(')[0].replace(name+'(',name+'Canonical(',1)
 if 'key.values[17]' not in wrapper or 'GetDamageCombatModifier' not in wrapper:
  raise RuntimeError('Production wrapper is missing the accepted canonical key')
 canonical+='\n'+wrapper
 canonical+='\n'+function(raw54,'int CvUnit::'+name+'(')[0].replace(name+'(',name+'Raw54(',1)
module='\n'.join(line for line in module.splitlines() if line not in ('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"'))
# Reuse actual existing deterministic profile setup, not its tests/main.
setup=scaffold['tests'].split('int main(){')[0]
tests=r'''
static vector<int> Words(const Key&key){return vector<int>(key.values,key.values+22);}
static Key AttackKey(CvUnit&a,const CvUnit*b,const CvPlot*from,const CvPlot*target,bool ignore,bool quick,int selfExtra,int otherExtra){
 const CvCity*city=target&&target->isCity()?target->getPlotCity():NULL;
 Key k=MakeStackStrengthKey(2,&a,b,city,from,target,true,ignore,quick,selfExtra,otherExtra);CanonicalizeProjectedWounds(k,&a,b,selfExtra,otherExtra,false);return k;
}
static Key DefenseKey(CvUnit&a,const CvUnit*b,const CvPlot*from,const CvPlot*target,bool ranged,bool quick,int selfExtra){
 const CvCity*city=target&&target->isCity()?target->getPlotCity():NULL;
 Key k=MakeStackStrengthKey(3,&a,b,city,from,target,false,false,quick,selfExtra,0);k.values[16]|=(ranged?8:0)|(a.isEmbarked()?16:0)|(a.CanEverEmbark()?32:0)|(target&&target->needsEmbarkation(&a)?64:0);CanonicalizeProjectedWounds(k,&a,b,selfExtra,0,ranged);return k;
}
struct Trace{unsigned long misses,evictions;unsigned entries,peak;};
static Trace Pressure(CvUnit&a,CvUnit&b,bool canonical){Scope scope(64);for(int pass=0;pass<2;++pass)for(int own=0;own<100;++own)for(int other=-10;other<110;++other){
 int expected=a.GetMaxAttackStrengthOriginal(NULL,NULL,&b,false,true,own,other);
 int actual=canonical?a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,true,own,other):a.GetMaxAttackStrengthRaw54(NULL,NULL,&b,false,true,own,other);
 expect("bounded pressure original full math",actual==expected);expect("shared entry budget remains64",GetStats().entries<=64);}
 Stats s=GetStats();Trace t={s.attackMisses,s.evictions,s.entries,s.peakEntries};return t;}
int main(){
 CvPlot plots[12];for(int i=0;i<12;++i)plots[i]=CvPlot(i);CvUnit a(1),b(2);CvCity city;configure(a,b,plots,city);expect("native x86",sizeof(void*)==4);
 {Scope scope(16384);for(int trial=0;trial<400;++trial){fill(a);fill(b);a.at=&plots[next()%12];b.at=&plots[next()%12];city.damage=next()%250;city.owner=next()%4;
  for(int p=0;p<4;++p){players[p].wounded=(int)(next()%61)-30;players[p].traits.fightWell=next()%3==0;players[p].traits.multiple=next()%7;players[p].attackMonopoly=(int)(next()%21)-10;players[p].defenseMonopoly=(int)(next()%21)-10;}
  MOD_BALANCE_RANGED_DEFENSE_UNIT_HEALTH=next()%2!=0;MOD_ATTRITION=next()%2!=0;D_WOUNDED_DAMAGE_MULTIPLIER=(int)(next()%100)-15;
  Invalidate();map<vector<int>,int>attacks,defenses;
  const CvPlot*from=trial%3==0?NULL:&plots[next()%12];const CvPlot*target=trial%4==0?NULL:&plots[next()%12];const CvUnit*other=trial%5==0?NULL:&b;
  bool ignore=next()%2!=0,quick=next()%2!=0,ranged=next()%2!=0;
  const int otherWounds[]={-b.damage-1,-b.damage,1-b.damage,b.maxHP/2-b.damage-1,b.maxHP/2-b.damage,b.maxHP/2-b.damage+1,100,137};
  for(int own=-a.damage-10;own<=130;own+=3)for(int j=0;j<8;++j){
   Key k=AttackKey(a,other,from,target,ignore,quick,own,otherWounds[j]);int original=a.GetMaxAttackStrengthOriginal(from,target,other,ignore,quick,own,otherWounds[j]);
   pair<map<vector<int>,int>::iterator,bool>stored=attacks.insert(make_pair(Words(k),original));expect("equal canonical attack key implies equal original full strength",stored.second||stored.first->second==original);
   expect("canonical full attack wrapper agrees",a.GetMaxAttackStrengthCanonical(from,target,other,ignore,quick,own,otherWounds[j])==original);
   Key raw=MakeStackStrengthKey(2,&a,other,target&&target->isCity()?target->getPlotCity():NULL,from,target,true,ignore,quick,own,otherWounds[j]);
   for(int field=0;field<22;++field)if(field!=17&&field!=18)expect("attack preserves every other key word",raw.values[field]==k.values[field]);
   Key d=DefenseKey(a,other,from,target,ranged,quick,own);int originalD=a.GetMaxDefenseStrengthOriginal(target,other,from,ranged,quick,own);
   pair<map<vector<int>,int>::iterator,bool>storedD=defenses.insert(make_pair(Words(d),originalD));expect("equal canonical defense key implies equal original full strength",storedD.second||storedD.first->second==originalD);
   expect("canonical full defense wrapper agrees",a.GetMaxDefenseStrengthCanonical(target,other,from,ranged,quick,own)==originalD);
  }
 }}
 configure(a,b,plots,city);D_WOUNDED_DAMAGE_MULTIPLIER=33;MOD_BALANCE_RANGED_DEFENSE_UNIT_HEALTH=true;
 {Scope scope(16384);b.maxHP=101;b.damage=0;Key below=AttackKey(a,&b,NULL,NULL,true,true,0,49),half=AttackKey(a,&b,NULL,NULL,true,true,0,50);
  expect("oddHP floor half boundary retained",below.values[18]!=half.values[18]);
  a.damage=20;Key fallback=AttackKey(a,&b,NULL,NULL,true,true,-20,3),live=AttackKey(a,&b,NULL,NULL,true,true,0,3);
  expect("nonpositive assumed own damage uses live fallback",fallback.values[17]==live.values[17]);
  for(int kind=0;kind<2;++kind){Key k=MakeStackStrengthKey(kind,&a,&b,&city,NULL,NULL,true,false,false,-7,71);Key original=k;CanonicalizeProjectedWounds(k,&a,&b,-7,71,true);expect("generic and ranged kinds keep raw wound fields",k==original);}
  a.modifiers[G_attackWoundedModifier]=23;a.modifiers[G_attackFullyHealedModifier]=-11;a.modifiers[G_attackAbove50HealthModifier]=47;a.modifiers[G_attackBelow50HealthModifier]=-31;
  expect("other wounded predicate kept",a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,true,true,0,0)==a.GetMaxAttackStrengthOriginal(NULL,NULL,&b,true,true,0,0)&&a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,true,true,0,1)==a.GetMaxAttackStrengthOriginal(NULL,NULL,&b,true,true,0,1));
  a.GetMaxAttackStrengthCanonical(NULL,&plots[3],&b,false,false,7,3);++city.attacked[a.owner];expect("city counter still keyed",a.GetMaxAttackStrengthCanonical(NULL,&plots[3],&b,false,false,7,3)==a.GetMaxAttackStrengthOriginal(NULL,&plots[3],&b,false,false,7,3));
  ++b.attacked[a.owner];++a.modifiers[G_GetStrengthThisTurnFromPreviousSamePromotionAttacks];expect("opponent and samepromo counters still keyed",a.GetMaxAttackStrengthCanonical(NULL,&plots[3],&b,false,false,7,3)==a.GetMaxAttackStrengthOriginal(NULL,&plots[3],&b,false,false,7,3));
 }
 {Scope scope(16384);configure(a,b,plots,city);for(int mode=1;mode<=2;++mode){keyCallback=mode==1?dirtyKey:nestedKey;unsigned before=attackComputes;
  a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,false,7,3);a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,false,7,3);expect("canonical key invalidation prevents admission",attackComputes==before+2);}keyCallback=NULL;
  for(int mode=1;mode<=2;++mode){mutateMode=mode;unsigned before=defenseComputes;a.GetMaxDefenseStrengthCanonical(NULL,&b,NULL,true,false,7);a.GetMaxDefenseStrengthCanonical(NULL,&b,NULL,true,false,7);expect("original math callbacks reject canonical admission",defenseComputes==before+2);}mutateMode=0;
  {Scope nested(16384);unsigned before=attackComputes;a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,false,7,3);a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,false,7,3);expect("nested context unchanged fallback",attackComputes==before+2);}
 }
 {Scope scope(16384);configure(a,b,plots,city);a.heavy=true;b.info.sendMoveEvent=true;MOD_EVENTS_CAN_MOVE_INTO=true;unsigned before=fallbackEvents;
  a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,false,7,3);a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,false,7,3);expect("scripted heavy callbacks unchanged",fallbackEvents==before+2);a.heavy=false;before=blockadeEvents;
  a.GetMaxAttackStrengthCanonical(NULL,&plots[3],&b,false,false,7,3);a.GetMaxAttackStrengthCanonical(NULL,&plots[3],&b,false,false,7,3);expect("scripted city callbacks unchanged",blockadeEvents==before+2);MOD_EVENTS_CAN_MOVE_INTO=false;}
 {Scope scope(16384);configure(a,b,plots,city);
  const int extremes[]={INT_MIN,INT_MAX};
  for(int i=0;i<2;++i){
   expect("null opponent ignores extreme other wounds",a.GetMaxAttackStrengthCanonical(NULL,NULL,NULL,true,true,7,extremes[i])==a.GetMaxAttackStrengthOriginal(NULL,NULL,NULL,true,true,7,extremes[i]));
   expect("null opponent has constant observable state",AttackKey(a,NULL,NULL,NULL,true,true,7,extremes[i]).values[18]==0);
  }
  a.base=0;a.damage=100;b.damage=99;Invalidate();woundModifierCalls=0;
  for(int i=0;i<2;++i){
   expect("zero base attack ignores both extreme wound arguments",a.GetMaxAttackStrengthCanonical(NULL,NULL,&b,false,false,extremes[i],extremes[i])==a.GetMaxAttackStrengthOriginal(NULL,NULL,&b,false,false,extremes[i],extremes[i]));
   expect("zero base defense ignores extreme own wounds",a.GetMaxDefenseStrengthCanonical(NULL,&b,NULL,false,false,extremes[i])==a.GetMaxDefenseStrengthOriginal(NULL,&b,NULL,false,false,extremes[i]));
  }
  expect("zero base keys do not newly evaluate wound helper",woundModifierCalls==0);
  a.base=12;a.embarked=true;Invalidate();woundModifierCalls=0;
  for(int i=0;i<2;++i)expect("null plot embarked shortcut ignores extreme own wounds",a.GetMaxDefenseStrengthCanonical(NULL,&b,NULL,true,false,extremes[i])==a.GetMaxDefenseStrengthOriginal(NULL,&b,NULL,true,false,extremes[i]));
  expect("embarked key skips new wound helper",woundModifierCalls==0);
  a.embarked=false;plots[5].embark=true;a.canEmbark=true;Invalidate();woundModifierCalls=0;
  for(int i=0;i<2;++i)expect("explicit plot embark shortcut ignores extreme own wounds",a.GetMaxDefenseStrengthCanonical(&plots[5],&b,NULL,false,false,extremes[i])==a.GetMaxDefenseStrengthOriginal(&plots[5],&b,NULL,false,false,extremes[i]));
  expect("explicit embark key skips new wound helper",woundModifierCalls==0);
 }
 configure(a,b,plots,city);Trace raw=Pressure(a,b,false),canon=Pressure(a,b,true);
 expect("canonical trace retains shared bounded capacity",raw.peak<=64&&canon.peak<=64);expect("equivalent-wound pressure genuinely reduces full misses",canon.misses<raw.misses);expect("equivalent-wound pressure reduces evictions",canon.evictions<raw.evictions);
 printf("canonical wound synthetic pressure: raw misses%lu evictions%lu; canonical misses%lu evictions%lu; both limit64. No native-speed claim.\n",raw.misses,raw.evictions,canon.misses,canon.evictions);
 printf("projected-wound canonical production actual-key/full-math regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+enum+unitdecl+header.replace('#pragma once','')+module+services+'\n'.join(leafmath)+key+wrappers+'\n'.join(bodies+references)+canonical+setup+tests
cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8')
if '--emit-only' in sys.argv:print('Fixture source prepared; no compile/run');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(text.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),returncode=run.returncode,output=run.stdout+run.stderr,scope='Actual production22word key/canonical full wrappers and cache/context vs pinned raw DLL54 wrappers; unchanged DLL47 full attack/defense/wound/embark bodies. Only key17/18 canonicalized for kinds2/3. Deterministic generic/player/plot/promotion services; synthetic bounded pressure is not native gain. No production edit/DLLbuild/gamecall.'),indent=2),encoding='utf-8');sys.exit(run.returncode)
