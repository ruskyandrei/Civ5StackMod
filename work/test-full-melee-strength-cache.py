"""Compile actual full melee math and cache wrappers against DLL47 controls.

Engine/player/plot/promotion services are meaningful deterministic substitutes;
the complete attack/defense, wound-modifier and embark-defense bodies are actual
source and checked byte-identically against DLL47. No DLL build or game calls.
"""
from pathlib import Path
import hashlib, json, os, re, subprocess, sys

root=Path(__file__).resolve().parents[1]
core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/full-melee-strength-regression';out.mkdir(exist_ok=True)
text=(core/'CvUnit.cpp').read_text(encoding='utf-8-sig')
control_commit='3b008c0d4'
old=subprocess.check_output(['git','show',control_commit+':CvGameCoreDLL_Expansion2/CvUnit.cpp'],cwd=root).decode('utf-8-sig')
header=(core/'CvStackingStrengthCache.h').read_text()
module=(core/'CvStackingStrengthCache.cpp').read_text()

def function(source,name):
 start=source.index(name);opening=source.index('{',start);end=opening+1;depth=1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end],source[opening:end]

bodies=[];references=[]
for name,counter in (('GetMaxAttackStrength','attackComputes'),('GetMaxDefenseStrength','defenseComputes')):
 actual,body=function(text,'int CvUnit::'+name+'Uncached(')
 original,originalbody=function(old,'int CvUnit::'+name+'(')
 assert body==originalbody,name+' math differs from DLL47'
 bodies.append(actual.replace('{','{\n ++'+counter+';OnCompute();',1))
 references.append(original.replace(name+'(',name+'Original(',1))
leafmath=[]
for name in ('GetDamageCombatModifier','GetEmbarkedUnitDefense'):
 actual,body=function(text,'int CvUnit::'+name+'(')
 assert body==function(old,'int CvUnit::'+name+'(')[1],name+' math differs from DLL47'
 leafmath.append(actual)
key=function(text,'static CvStackingStrengthCache::Key MakeStackStrengthKey(')[0]
wrappers='\n'.join(function(text,'int CvUnit::'+name+'(')[0] for name in ('GetGenericMeleeStrengthModifier','GetMaxRangedCombatStrength','GetMaxAttackStrength','GetMaxDefenseStrength'))
module='\n'.join(line for line in module.splitlines() if line not in ('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"'))

getters=('getAttackModifier GetStrengthThisTurnFromPreviousSamePromotionAttacks getCombatModPerAdjacentUnitCombatAttackMod cityAttackModifier getMultiAttackBonus hillsAttackModifier openAttackModifier roughAttackModifier featureAttackModifier terrainAttackModifier GetTerrainModifierAttack getFriendlyLandsAttackModifier unitClassAttackModifier getExtraUnitCombatModifierAttack getExtraDomainAttack attackFortifiedModifier attackWoundedModifier attackFullyHealedModifier attackAbove50HealthModifier attackBelow50HealthModifier getDefenseModifier fortifyModifier rangedDefenseModifier getCombatModPerAdjacentUnitCombatDefenseMod cityDefenseModifier hillsDefenseModifier openDefenseModifier roughDefenseModifier featureDefenseModifier terrainDefenseModifier GetTerrainModifierDefense unitClassDefenseModifier getExtraUnitCombatModifierDefense getExtraDomainDefense GetEmbarkDefensiveModifier').split()
enum='enum Getter{'+','.join('G_'+name for name in getters)+',G_Count};\n'
numeric='\n'.join(' int '+name+'(int value=0)const{return modifiers[G_'+name+']*(1+(value&1));}' for name in getters)
prefix=r'''
#define NOMINMAX
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <climits>
#include <map>
#include <vector>
using namespace std;
#define VALIDATE_OBJECT() ((void)0)
#define ASSERT(value,message) ((void)0)
#define GD_INT_GET(name) D_##name
typedef int UnitCombatTypes;typedef int PlayerTypes;
const int NO_UNITCOMBAT=-1,NO_FEATURE=-1,NO_DOMAIN=-1,DOMAIN_LAND=0,DOMAIN_SEA=1,TERRAIN_HILL=2,AE_SAPPER=3;
int D_POLICY_ATTACK_BONUS_MOD=25,D_BLOCKADED_CITY_ATTACK_MODIFIER=20,D_BARBARIAN_CITY_ATTACK_MODIFIER=0,D_RIVER_ATTACK_MODIFIER=-20,D_AMPHIB_ATTACK_MODIFIER=-50,D_NAVAL_COMBAT_DEFENDER_STRENGTH_MULTIPLIER=120,D_WOUNDED_DAMAGE_MULTIPLIER=33;
bool MOD_ATTRITION=false,MOD_BALANCE_RANGED_DEFENSE_UNIT_HEALTH=true,MOD_EVENTS_CAN_MOVE_INTO=false;
unsigned int fallbackEvents=0,blockadeEvents=0;
void(*keyCallback)()=NULL;
struct CvUnit;struct CvCity;
struct CvPlot{
 int index,bonus,domain,terrain,feature,owner,flank,counts[3];bool hills,open,rough,water,revealed,river,embark;CvCity*city;
 CvPlot(int i=0):index(i),bonus(i%9),domain(DOMAIN_LAND),terrain(0),feature(NO_FEATURE),owner(0),flank(0),hills(false),open(true),rough(false),water(false),revealed(true),river(false),embark(false),city(NULL){memset(counts,0,sizeof(counts));}
 int GetPlotIndex()const{return index;}bool isCity()const{return city!=NULL;}CvCity*getPlotCity()const{return city;}
 bool isHills()const{return hills;}bool isOpenGround()const{return open;}bool isRoughGround()const{return rough;}
 bool isWater()const{return water;}int getDomain()const{return domain;}int getTerrainType()const{return terrain;}int getFeatureType()const{return feature;}
 bool IsFriendlyUnitAdjacent(int,bool)const{return counts[0]+counts[1]+counts[2]>0;}
 int GetNumSpecificFriendlyUnitCombatsAdjacent(int,int combat,void*)const{return counts[combat%3];}
 bool isRevealed(int)const{return revealed;}bool isAdjacent(const CvPlot*other)const{return other&&other!=this&&abs(other->index-index)<=2;}
 bool isRiverCrossing(int)const{return river;}bool IsFriendlyTerritory(int player)const{return player==owner;}
 int GetEffectiveFlankingBonus(const CvUnit*,const CvUnit*,const CvPlot*source)const{return flank+(source?source->bonus:0);}
 int defenseModifier(int,bool improvementOnly,bool)const{return improvementOnly?bonus/3:bonus;}
 bool needsEmbarkation(const CvUnit*)const;
};
int directionXY(const CvPlot*from,const CvPlot*to){return (from->index+to->index)%6;}
struct CvCity{int owner,id,damage,attacked[4];bool blocked;CvPlot*at;
 CvCity():owner(2),id(8),damage(0),blocked(false),at(NULL){memset(attacked,0,sizeof(attacked));}
 int getOwner()const{return owner;}int GetID()const{return id;}int getDamage()const{return damage;}CvPlot*plot()const{return at;}
 int GetNumTimesAttackedThisTurn(int owner)const{return attacked[owner%4];}bool IsBlockadedWaterAndLand()const{if(MOD_EVENTS_CAN_MOVE_INTO)++blockadeEvents;return blocked;}
};
struct Traits{int multiple;bool fightWell;Traits():multiple(3),fightWell(false){}int GetMultipleAttackBonus()const{return multiple;}bool IsFightWellDamaged()const{return fightWell;}};
struct CvPlayer{int attackTurns,attackMonopoly,defenseMonopoly,sapper,wounded;Traits traits;
 CvPlayer():attackTurns(0),attackMonopoly(0),defenseMonopoly(0),sapper(0),wounded(0){}
 int GetAttackBonusTurns()const{return attackTurns;}int GetCombatAttackBonusFromMonopolies(int domain)const{return attackMonopoly+domain;}
 int GetCombatDefenseBonusFromMonopolies(int domain)const{return defenseMonopoly+domain;}
 int GetAreaEffectModifier(int,int,const CvPlot*plot)const{return sapper+(plot?plot->bonus:0);}
 int GetWoundedUnitDamageMod()const{return wounded;}const Traits*GetPlayerTraits()const{return &traits;}
};
typedef CvPlayer CvPlayerAI;CvPlayer players[4];
#define GET_PLAYER(owner) players[(owner)%4]
struct CvBaseInfo{};
struct Globals{CvBaseInfo infos[3];bool valid[3];Globals(){valid[0]=true;valid[1]=false;valid[2]=true;}
 int getNumUnitCombatClassInfos()const{return 3;}CvBaseInfo*getUnitCombatClassInfo(int type){return valid[type]?&infos[type]:NULL;}
 int getInfoTypeForString(const char*,bool)const{return 2;}
}GC;
struct UnitInfo{bool mounted,sendMoveEvent;UnitInfo():mounted(false),sendMoveEvent(false){}bool IsMounted()const{return mounted;}bool IsSendCanMoveIntoEvent()const{return sendMoveEvent;}};
'''
unitdecl=r'''
struct CvUnit{
 int owner,id,damage,maxHP,base,domain,unitClass,unitCombat,attacked[4],fallback,generic,modifiers[G_Count];CvPlot*at;UnitInfo info;
 bool embarked,canEmbark,noDefBonus,riverSafe,amphibious,heavy,fortified,strongerWounded,fightWounded,sendMoveEvent;
 CvUnit(int value=0):owner(0),id(value),damage(0),maxHP(100),base(12),domain(DOMAIN_LAND),unitClass(0),unitCombat(0),fallback(2),generic(0),at(NULL),embarked(false),canEmbark(true),noDefBonus(false),riverSafe(false),amphibious(false),heavy(false),fortified(false),strongerWounded(false),fightWounded(false),sendMoveEvent(false){memset(attacked,0,sizeof(attacked));memset(modifiers,0,sizeof(modifiers));}
 int getOwner()const{return owner;}int GetID()const{return id;}CvPlot*plot()const{return at;}int getDamage()const{return damage;}int GetMaxHitPoints()const{if(keyCallback)keyCallback();return maxHP;}
 int GetNumTimesAttackedThisTurn(int owner)const{return attacked[owner%4];}int getTeam()const{return owner;}int GetBaseCombatStrength()const{return base;}
 int getDomainType()const{return domain;}int getUnitClassType()const{return unitClass;}int getUnitCombatType()const{return unitCombat;}
 const UnitInfo&getUnitInfo()const{return info;}bool isBarbarian()const{return owner==3;}bool noDefensiveBonus()const{return noDefBonus;}
 bool isRiverCrossingNoPenalty()const{return riverSafe;}bool isAmphibious()const{return amphibious;}bool IsCanHeavyCharge()const{return heavy;}
 bool isNativeDomain(const CvPlot*plot)const{return plot&&plot->domain==domain;}bool IsFortified()const{return fortified;}
 bool isEmbarked()const{return embarked;}bool CanEverEmbark()const{return canEmbark;}bool IsStrongerDamaged()const{return strongerWounded;}bool IsFightWellDamaged()const{return fightWounded;}
 int GetNumFallBackPlotsAvailable(const CvUnit&)const{if(MOD_EVENTS_CAN_MOVE_INTO&&info.sendMoveEvent)++fallbackEvents;return fallback;}
 int GetDamageCombatModifier(bool,int)const;int GetEmbarkedUnitDefense()const;
 int GetGenericMeleeStrengthModifier(const CvUnit*,const CvPlot*,bool,bool,const CvPlot*,bool)const;
 int GetGenericMeleeStrengthModifierUncached(const CvUnit*,const CvPlot*,bool,bool,const CvPlot*,bool)const;
 int GetMaxRangedCombatStrength(const CvUnit*,const CvCity*,bool,const CvPlot*,const CvPlot*,bool,bool,int,int)const;
 int GetMaxRangedCombatStrengthUncached(const CvUnit*,const CvCity*,bool,const CvPlot*,const CvPlot*,bool,bool,int,int)const;
 int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int,int)const;
 int GetMaxAttackStrengthUncached(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int,int)const;
 int GetMaxAttackStrengthOriginal(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int,int)const;
 int GetMaxDefenseStrength(const CvPlot*,const CvUnit*,const CvPlot*,bool,bool,int)const;
 int GetMaxDefenseStrengthUncached(const CvPlot*,const CvUnit*,const CvPlot*,bool,bool,int)const;
 int GetMaxDefenseStrengthOriginal(const CvPlot*,const CvUnit*,const CvPlot*,bool,bool,int)const;
'''+numeric+r'''
};
bool CvPlot::needsEmbarkation(const CvUnit*unit)const{return embark&&unit->domain==DOMAIN_LAND;}
'''
services=r'''
unsigned int attackComputes=0,defenseComputes=0,genericComputes=0;int mutateMode=0;
void OnCompute(){if(mutateMode==1)CvStackingStrengthCache::Invalidate();if(mutateMode==2){CvStackingStrengthCache::Scope nested(16384);}}
void dirtyKey(){CvStackingStrengthCache::Invalidate();}
void nestedKey(){CvStackingStrengthCache::Scope nested(16384);}
int CvUnit::GetGenericMeleeStrengthModifierUncached(const CvUnit*other,const CvPlot*battle,bool attacking,bool ignore,const CvPlot*from,bool quick)const{
 ++genericComputes;if(!from)from=at;return generic+(other?other->generic+other->owner:0)+(battle?battle->bonus:0)+(from?from->bonus:0)+(attacking?4:-3)+(ignore?1:0)+(quick?2:5);
}
int CvUnit::GetMaxRangedCombatStrengthUncached(const CvUnit*other,const CvCity*city,bool attacking,const CvPlot*from,const CvPlot*target,bool ignore,bool quick,int extra,int otherExtra)const{
 if(!from)from=at;if(!target)target=other?other->at:(city?city->at:NULL);
 return base*100+(from?from->bonus:0)+(target?target->bonus:0)-damage-extra+(other?other->attacked[owner%4]-other->damage-otherExtra:0)+(city?city->damage+city->attacked[owner%4]:0)+(attacking?11:0)+(ignore?13:0)+(quick?17:0);
}
'''
tests=r'''
using namespace CvStackingStrengthCache;
int checks=0,failures=0;
void expect(const char*name,bool okay){++checks;if(!okay){++failures;if(failures<25)printf("FAIL %s\n",name);}}
unsigned int seed=61783;unsigned int next(){seed=seed*1664525u+1013904223u;return seed;}
void fill(CvUnit&unit){for(int i=0;i<G_Count;++i)unit.modifiers[i]=(int)(next()%25)-12;unit.owner=next()%4;unit.damage=next()%110;unit.maxHP=51+next()%101;unit.base=next()%6==0?0:5+next()%35;unit.domain=next()%3;unit.unitClass=next()%3;unit.unitCombat=(int)(next()%4)-1;unit.fallback=next()%4;unit.generic=(int)(next()%81)-40;unit.info.mounted=next()%2!=0;unit.embarked=next()%4==0;unit.canEmbark=next()%4!=0;unit.noDefBonus=next()%4==0;unit.riverSafe=next()%4==0;unit.amphibious=next()%4==0;unit.heavy=next()%3==0;unit.fortified=next()%3==0;unit.strongerWounded=next()%4==0;unit.fightWounded=next()%4==0;for(int j=0;j<4;++j)unit.attacked[j]=next()%7;}
void configure(CvUnit&a,CvUnit&b,CvPlot*plots,CvCity&city){
 a=CvUnit(1);b=CvUnit(2);a.at=&plots[2];b.at=&plots[3];b.owner=1;city=CvCity();city.at=&plots[3];plots[3].city=&city;
 for(int i=0;i<4;++i)players[i]=CvPlayer();
}
DWORD WINAPI foreign(void*data){CvUnit*a=(CvUnit*)data;Scope skipped(16384);unsigned int before=attackComputes;
 int x=a->GetMaxAttackStrength(NULL,NULL,NULL,false,false,7,0);int y=a->GetMaxAttackStrength(NULL,NULL,NULL,false,false,7,0);
 long generation;Invalidate();return !Context(generation)&&x==y&&attackComputes==before+2?0:1;
}
int main(){
 expect("native x86",sizeof(void*)==4&&sizeof(long)==4);CvPlot plots[12];for(int i=0;i<12;++i)plots[i]=CvPlot(i);CvUnit a(1),b(2);CvCity city;configure(a,b,plots,city);
 {Scope scope(16384);
  for(int trial=0;trial<20000;++trial){
   fill(a);fill(b);a.at=&plots[next()%12];b.at=&plots[next()%12];city.owner=next()%4;city.damage=next()%300;city.blocked=next()%2!=0;for(int i=0;i<4;++i){city.attacked[i]=next()%8;players[i].attackTurns=next()%3;players[i].attackMonopoly=(int)(next()%11)-5;players[i].defenseMonopoly=(int)(next()%11)-5;players[i].sapper=(int)(next()%17)-8;players[i].wounded=(int)(next()%9)-4;players[i].traits.multiple=next()%5;players[i].traits.fightWell=next()%3==0;}
   for(int i=0;i<12;++i){plots[i].domain=next()%3;plots[i].terrain=next()%3;plots[i].feature=(int)(next()%4)-1;plots[i].owner=next()%4;plots[i].bonus=(int)(next()%21)-10;plots[i].flank=(int)(next()%21)-10;plots[i].hills=next()%2!=0;plots[i].open=next()%2!=0;plots[i].rough=next()%2!=0;plots[i].water=next()%2!=0;plots[i].revealed=next()%3!=0;plots[i].river=next()%2!=0;plots[i].embark=next()%3==0;for(int j=0;j<3;++j)plots[i].counts[j]=next()%5;}
   MOD_ATTRITION=next()%2!=0;MOD_BALANCE_RANGED_DEFENSE_UNIT_HEALTH=next()%2!=0;Invalidate();
   const CvPlot*from=trial%5==0?NULL:&plots[next()%12];const CvPlot*target=trial%7==0?NULL:&plots[next()%12];const CvUnit*other=trial%4==0?NULL:&b;bool ignore=next()%2!=0,quick=next()%2!=0,ranged=next()%2!=0;int wounds=(int)(next()%200)-40,otherWounds=(int)(next()%200)-40;
   int attack=a.GetMaxAttackStrengthOriginal(from,target,other,ignore,quick,wounds,otherWounds);int defense=a.GetMaxDefenseStrengthOriginal(target,other,from,ranged,quick,wounds);
   expect("full attack equals DLL47 entire body",a.GetMaxAttackStrength(from,target,other,ignore,quick,wounds,otherWounds)==attack);
   expect("full defense equals DLL47 entire body",a.GetMaxDefenseStrength(target,other,from,ranged,quick,wounds)==defense);
   unsigned int before=attackComputes;expect("repeat full attack avoids all legacy body work",a.GetMaxAttackStrength(from,target,other,ignore,quick,wounds,otherWounds)==attack&&attackComputes==before);
   before=defenseComputes;expect("repeat full defense avoids all legacy body work",a.GetMaxDefenseStrength(target,other,from,ranged,quick,wounds)==defense&&defenseComputes==before);
   expect("combined generic and full entries bounded",GetStats().entries<=16384);
  }
  expect("new hit kinds reported separately",GetStats().attackHits>0&&GetStats().defenseHits>0);
 }
 configure(a,b,plots,city);a.at=&plots[2];plots[2]=CvPlot(2);plots[3]=CvPlot(3);plots[3].city=&city;city.at=&plots[3];
 a.modifiers[G_getMultiAttackBonus]=2;players[0].traits.multiple=3;
 {Scope scope(16384);int first=a.GetMaxAttackStrength(a.at,&plots[3],&b,false,false,0,0);unsigned int before=attackComputes;
  ++city.attacked[0];int second=a.GetMaxAttackStrength(a.at,&plots[3],&b,false,false,0,0);
  expect("simultaneous city+opponent city counter changes full key",second==a.GetMaxAttackStrengthOriginal(a.at,&plots[3],&b,false,false,0,0)&&second!=first&&attackComputes==before+1);
  before=attackComputes;++b.attacked[0];int third=a.GetMaxAttackStrength(a.at,&plots[3],&b,false,false,0,0);
  expect("simultaneous city+opponent unit counter changes full key",third==a.GetMaxAttackStrengthOriginal(a.at,&plots[3],&b,false,false,0,0)&&third!=second&&attackComputes==before+1);
  int range=a.GetMaxRangedCombatStrength(&b,&city,true,a.at,&plots[3],false,false,0,0);++city.attacked[0];
  expect("combined ranged city counter no longer aliases unit counter",a.GetMaxRangedCombatStrength(&b,&city,true,a.at,&plots[3],false,false,0,0)==range+1);
 }
 {Scope scope(16384);plots[2].water=true;plots[2].domain=DOMAIN_SEA;plots[2].river=true;plots[2].flank=7;plots[2].counts[0]=2;a.modifiers[G_getFriendlyLandsAttackModifier]=11;a.modifiers[G_getCombatModPerAdjacentUnitCombatAttackMod]=3;
  int absent=a.GetMaxAttackStrength(NULL,&plots[3],&b,false,false,0,0),explicitFrom=a.GetMaxAttackStrength(a.at,&plots[3],&b,false,false,0,0);
  expect("NULL attack origin is deliberately not normalized",absent==a.GetMaxAttackStrengthOriginal(NULL,&plots[3],&b,false,false,0,0)&&explicitFrom==a.GetMaxAttackStrengthOriginal(a.at,&plots[3],&b,false,false,0,0)&&absent!=explicitFrom);
  expect("NULL destination retains no-city attack branch",a.GetMaxAttackStrength(NULL,NULL,&b,false,false,0,0)==a.GetMaxAttackStrengthOriginal(NULL,NULL,&b,false,false,0,0));
  a.embarked=true;plots[2].embark=false;plots[2].domain=DOMAIN_LAND;Invalidate();
  int absentDefense=a.GetMaxDefenseStrength(NULL,&b,NULL,false,false,0),explicitDefense=a.GetMaxDefenseStrength(a.at,&b,NULL,false,false,0);
  expect("NULL defense plot retains live embarked shortcut",absentDefense==a.GetEmbarkedUnitDefense()&&explicitDefense==a.GetMaxDefenseStrengthOriginal(a.at,&b,NULL,false,false,0)&&absentDefense!=explicitDefense);
  a.embarked=false;unsigned int before=defenseComputes;
  expect("live embark flag variation rejects same NULL-plot key",a.GetMaxDefenseStrength(NULL,&b,NULL,false,false,0)==a.GetMaxDefenseStrengthOriginal(NULL,&b,NULL,false,false,0)&&defenseComputes==before+1);
  plots[2].embark=true;a.canEmbark=true;Invalidate();int embarked=a.GetMaxDefenseStrength(a.at,&b,NULL,false,false,0);a.canEmbark=false;
  expect("CanEverEmbark variation preserves shortcut",embarked==a.GetEmbarkedUnitDefense()&&a.GetMaxDefenseStrength(a.at,&b,NULL,false,false,0)==a.GetMaxDefenseStrengthOriginal(a.at,&b,NULL,false,false,0));
 }
 configure(a,b,plots,city);plots[2]=CvPlot(2);plots[3]=CvPlot(3);plots[3].city=&city;city.at=&plots[3];a.modifiers[G_attackFullyHealedModifier]=11;a.modifiers[G_attackWoundedModifier]=-7;a.modifiers[G_attackAbove50HealthModifier]=17;a.modifiers[G_attackBelow50HealthModifier]=-13;b.maxHP=101;
 {Scope scope(16384);int injuries[]={-20,0,1,49,50,51,100,130};for(int i=0;i<8;++i)expect("odd maxHP wound thresholds and negative projected damage exact",a.GetMaxAttackStrength(a.at,NULL,&b,false,false,injuries[i],injuries[i])==a.GetMaxAttackStrengthOriginal(a.at,NULL,&b,false,false,injuries[i],injuries[i]));
  a.damage=40;a.modifiers[G_rangedDefenseModifier]=9;MOD_BALANCE_RANGED_DEFENSE_UNIT_HEALTH=true;Invalidate();
  int melee=a.GetMaxDefenseStrength(a.at,&b,NULL,false,false,0),ranged=a.GetMaxDefenseStrength(a.at,&b,NULL,true,false,0);
  expect("ranged-defense flag and actual damage math remain distinct",melee==a.GetMaxDefenseStrengthOriginal(a.at,&b,NULL,false,false,0)&&ranged==a.GetMaxDefenseStrengthOriginal(a.at,&b,NULL,true,false,0)&&melee!=ranged);
  a.modifiers[G_getAttackModifier]=-1000;Invalidate();expect("minimum strength clamp unchanged",a.GetMaxAttackStrength(NULL,NULL,NULL,false,false,0,0)==a.base*10);
  a.base=0;Invalidate();expect("zero base attack and defense unchanged",a.GetMaxAttackStrength(NULL,NULL,NULL,false,false,0,0)==0&&a.GetMaxDefenseStrength(NULL,NULL,NULL,false,false,0)==0);
 }
 configure(a,b,plots,city);
 {Scope scope(16384);city.blocked=false;int first=a.GetMaxAttackStrength(NULL,&plots[3],&b,false,false,0,0);city.blocked=true;Invalidate();
  expect("city blockade changes with scene epoch",a.GetMaxAttackStrength(NULL,&plots[3],&b,false,false,0,0)==a.GetMaxAttackStrengthOriginal(NULL,&plots[3],&b,false,false,0,0)&&a.GetMaxAttackStrength(NULL,&plots[3],&b,false,false,0,0)!=first);
  unsigned int before=attackComputes;a.GetMaxAttackStrength(NULL,&plots[3],&b,true,true,0,0);a.damage=23;a.at=&plots[4];b.damage=17;b.maxHP=151;
  expect("live HP and positions remain explicit key dependencies",a.GetMaxAttackStrength(NULL,&plots[3],&b,true,true,0,0)==a.GetMaxAttackStrengthOriginal(NULL,&plots[3],&b,true,true,0,0)&&attackComputes==before+2);
  ++a.modifiers[G_GetStrengthThisTurnFromPreviousSamePromotionAttacks];expect("live same-promotion history changes key without epoch",a.GetMaxAttackStrength(NULL,&plots[3],&b,false,false,0,0)==a.GetMaxAttackStrengthOriginal(NULL,&plots[3],&b,false,false,0,0));
 }
 {Scope scope(16384);configure(a,b,plots,city);a.heavy=true;b.info.sendMoveEvent=true;MOD_EVENTS_CAN_MOVE_INTO=true;
  unsigned int before=attackComputes,eventsBefore=fallbackEvents;
  a.GetMaxAttackStrength(NULL,NULL,&b,false,false,0,0);a.GetMaxAttackStrength(NULL,NULL,&b,false,false,0,0);
  expect("scripted heavy-charge movement hooks retain repeated execution",attackComputes==before+2&&fallbackEvents==eventsBefore+2&&GetStats().attackHits==0);
  a.heavy=false;before=attackComputes;eventsBefore=blockadeEvents;
  a.GetMaxAttackStrength(NULL,&plots[3],&b,false,false,0,0);a.GetMaxAttackStrength(NULL,&plots[3],&b,false,false,0,0);
  expect("scripted city blockade checks retain repeated execution",attackComputes==before+2&&blockadeEvents==eventsBefore+2&&GetStats().attackHits==0);
  MOD_EVENTS_CAN_MOVE_INTO=false;
 }
 {Scope scope(16384);configure(a,b,plots,city);for(int mode=1;mode<=2;++mode){mutateMode=mode;Invalidate();unsigned int before=attackComputes;
   a.GetMaxAttackStrength(NULL,NULL,&b,false,false,7,3);a.GetMaxAttackStrength(NULL,NULL,&b,false,false,7,3);expect("scene/nested mutation during attack compute prevents full-result admission",attackComputes==before+2);
   before=defenseComputes;a.GetMaxDefenseStrength(NULL,&b,NULL,true,false,7);a.GetMaxDefenseStrength(NULL,&b,NULL,true,false,7);expect("scene/nested mutation during defense compute prevents full-result admission",defenseComputes==before+2);
  }mutateMode=0;
  a.GetMaxAttackStrength(NULL,NULL,&b,false,false,7,3);{Scope nested(16384);unsigned int before=attackComputes;a.GetMaxAttackStrength(NULL,NULL,&b,false,false,7,3);a.GetMaxAttackStrength(NULL,NULL,&b,false,false,7,3);expect("nested caller bypasses full cache",attackComputes==before+2);}
  HANDLE thread=CreateThread(NULL,0,foreign,&a,0,NULL);expect("foreign thread started",thread!=NULL);if(thread){expect("foreign thread finishes",WaitForSingleObject(thread,10000)==WAIT_OBJECT_0);DWORD result=99;GetExitCodeThread(thread,&result);expect("foreign caller bypasses owned full cache",result==0);CloseHandle(thread);}
 }
 {Scope scope(16384);configure(a,b,plots,city);for(int mode=1;mode<=2;++mode){keyCallback=mode==1?dirtyKey:nestedKey;unsigned int before=attackComputes;
   a.GetMaxAttackStrength(NULL,NULL,&b,false,false,7,3);a.GetMaxAttackStrength(NULL,NULL,&b,false,false,7,3);
   expect("key construction scene/nested callbacks prevent full attack admission",attackComputes==before+2);
   before=defenseComputes;a.GetMaxDefenseStrength(NULL,&b,NULL,false,false,7);a.GetMaxDefenseStrength(NULL,&b,NULL,false,false,7);
   expect("key construction scene/nested callbacks prevent full defense admission",defenseComputes==before+2);
  }keyCallback=NULL;
 }
 {configure(a,b,plots,city);unsigned int before=attackComputes;a.GetMaxAttackStrength(NULL,NULL,&b,false,false,0,0);a.GetMaxAttackStrength(NULL,NULL,&b,false,false,0,0);expect("inactive callers retain original uncached behavior",attackComputes==before+2);}
 {Scope disabled(0);unsigned int before=defenseComputes;a.GetMaxDefenseStrength(NULL,&b,NULL,false,false,0);a.GetMaxDefenseStrength(NULL,&b,NULL,false,false,0);expect("zero budget retains uncached full defense",defenseComputes==before+2);}
 {Scope scope(16);configure(a,b,plots,city);for(int i=0;i<10000;++i){int attack=a.GetMaxAttackStrengthOriginal(NULL,NULL,&b,false,false,i%173,(i/173)%71);expect("FIFO full attack exact across changing projected wounds",a.GetMaxAttackStrength(NULL,NULL,&b,false,false,i%173,(i/173)%71)==attack);expect("shared generic/full entry budget never expands",GetStats().entries<=16);}
  expect("bounded full+generic FIFO actually evicts",GetStats().evictions>0);printf("full-strength pressure fixture: entries%u limit%u evictions%lu genericMisses%lu attackMisses%lu; shared budget unchanged. Not a game timing measurement.\n",GetStats().entries,GetStats().limit,GetStats().evictions,GetStats().meleeMisses,GetStats().attackMisses);
 }
 {Scope scope(16384);configure(a,b,plots,city);unsigned int before=attackComputes,genericBefore=genericComputes;
  for(int i=0;i<20000;++i)expect("stable full attack exact through cache",a.GetMaxAttackStrength(NULL,NULL,&b,false,false,17,23)==a.GetMaxAttackStrengthOriginal(NULL,NULL,&b,false,false,17,23));
  expect("stable full result calculates original body once",attackComputes==before+1);printf("whole attack original body evaluations: shared %u vs DLL47 20000 repeated queries; generic computations%u. No native speed claim.\n",attackComputes-before,genericComputes-genericBefore);
 }
 printf("whole melee strength actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+enum+unitdecl+header.replace('#pragma once','')+module+services+'\n'.join(leafmath)+key+wrappers+'\n'.join(bodies+references)+tests
cpp=out/'full-melee-strength.cpp';cpp.write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'full-melee-strength.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'full-melee-strength.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(control_commit=control_commit,source_sha256=hashlib.sha256(text.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),compile_returncode=compiled.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr,scope='Actual full attack/defense/wound/embark math bodies byte-matched DLL47 and compiled with actual current keys/cache/wrappers. Engine services including generic modifier are deterministic substitutes; generic/ranged bodies separately checked by test-strength-cache.py. No DLL build or game timing test.'),indent=2)+'\n',encoding='utf-8')
sys.exit(run.returncode)
