"""Native actual-source collateral/fortification and production reservation checks."""
from pathlib import Path
import os, subprocess, sys, re, json, hashlib
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/todo-integration-regression';out.mkdir(exist_ok=True)
def body(file,signature):
 s=(core/file).read_text(encoding='utf-8-sig');a=s.index(signature);b=s.index('{',a);n=1;i=b+1
 while n:n+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
policy=(core/'CvStackingAIPolicy.h').read_text().replace('#pragma once','')
prefix=r'''
#include <vector>
#include <deque>
#include <map>
#include <string>
#include <algorithm>
#include <cstdio>
using namespace std;
typedef long long int64;typedef int BuildingTypes;typedef int UnitAITypes;
const int DOMAIN_LAND=2,DOMAIN_SEA=0,DOMAIN_AIR=1,MAX_DAMAGE_MEMBER_COUNT=32;
map<string,int>settings;bool enabled=true;
struct CvCityBuildings{map<int,int>counts;int GetNumBuilding(int t)const{return counts.count(t)?counts.find(t)->second:0;}};
struct CvCity{mutable CvCityBuildings buildings;int hp,maxHP;CvCity():hp(300),maxHP(300){}CvCityBuildings*GetCityBuildings()const{return &buildings;}int GetMaxHitPoints()const{return maxHP;}int getDamage()const{return maxHP-hp;}};
struct CvPlot;struct CvUnit{
 int id,owner,domain,hp,limit;bool defend,dead,cargo,civilian,trade;
 CvUnit(int i,int o=1):id(i),owner(o),domain(DOMAIN_LAND),hp(100),limit(2),defend(true),dead(false),cargo(false),civilian(false),trade(false){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}int getDomainType()const{return domain;}
 int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return 100;}bool IsCanDefend()const{return defend;}bool isCargo()const{return cargo;}bool IsDead()const{return dead;}bool isDelayedDeath()const{return dead;}
 bool IsCivilianUnit()const{return civilian;}bool isTrade()const{return trade;}bool isEnemy(int team,const CvPlot*)const{return team!=owner;}
};
struct CvPlot{CvCity*city;bool water;CvPlot(CvCity*c):city(c),water(false){}bool isCity()const{return city!=NULL;}CvCity*getPlotCity()const{return city;}bool needsEmbarkation(const CvUnit*)const{return water;}};
struct SUnitIDValueContainer{map<int,int>v;int GetValue(int id)const{return v.count(id)?v.find(id)->second:0;}};
namespace CvStacking{
 struct CacheType{map<int,int>effectiveBuildingProtection;}cache;
 CacheType&Cache(){return cache;}bool IsEnabled(){return enabled;}int GetInt(const char*n,int f){return settings.count(n)?settings[n]:f;}
 int GetCityProtection(const CvCity*,int extraCityDamage=0);
 int GetCollateralTargetLimit(const CvUnit*u){return u->limit;}bool IsCollateralTargetDomain(int d){return d==DOMAIN_LAND;}
}
struct CvUnitCombat{static vector<pair<const CvUnit*,int> >GetStackCollateralDamage(const CvUnit*,const CvPlot*,const CvUnit*,int,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const CvUnit* =NULL,int=0,int=0);};
enum{UNITAI_ATTACK,UNITAI_DEFENSE,UNITAI_COUNTER,UNITAI_FAST_ATTACK,UNITAI_RANGED,UNITAI_CITY_BOMBARD,UNITAI_ATTACK_SEA,UNITAI_RESERVE_SEA,UNITAI_ESCORT_SEA,UNITAI_GENERAL};
const int AI_OPERATION_STATE_MOVING_TO_TARGET=3;
struct OperationSlot{int m_iOperationID,m_iArmyID,m_iSlotID;OperationSlot(int o=-1,int a=-1,int s=-1):m_iOperationID(o),m_iArmyID(a),m_iSlotID(s){}bool operator==(const OperationSlot&b)const{return m_iOperationID==b.m_iOperationID&&m_iArmyID==b.m_iArmyID&&m_iSlotID==b.m_iSlotID;}};
struct CvArmyFormationSlot{int id;CvArmyFormationSlot():id(-1){}bool IsFree()const{return id<0;}};
struct CvFormationSlotEntry{int m_primaryUnitType;CvFormationSlotEntry(int r=UNITAI_ATTACK):m_primaryUnitType(r){}};
struct CvArmyAI{vector<CvArmyFormationSlot>slots;vector<CvFormationSlotEntry>roles;int GetID()const{return 7;}size_t GetNumFormationEntries()const{return slots.size();}CvArmyFormationSlot*GetSlotStatus(size_t i){return &slots[i];}CvFormationSlotEntry GetSlotInfo(size_t i){return roles[i];}};
struct CvAIOperation{
 int m_eOwner,m_iID,m_eCurrentState;bool cityAttack;CvArmyAI*army;
 deque<OperationSlot>m_viListOfUnitsWeStillNeedToBuild;vector<OperationSlot>m_viListOfUnitsCitiesHaveCommittedToBuild;
 CvAIOperation():m_eOwner(0),m_iID(1),m_eCurrentState(3),cityAttack(true),army(NULL){}
 CvArmyAI*GetArmy(int){return army;}bool IsSlotCommitted(size_t)const;void RefreshReinforcementRequests();OperationSlot PeekAtNextUnitToBuild();bool CommitToBuildNextUnit(OperationSlot);bool UncommitToBuildUnit(OperationSlot);
};
namespace CvStackingOffensiveAI{bool Enabled(int){return enabled;}bool IsCityAttack(const CvAIOperation*o){return o->cityAttack;}}
'''
actual='namespace CvStacking {\n'+body('CvStackingRules.cpp','int GetCityProtection(')+'\n}\n'
actual+=body('CvUnitCombat.cpp','static bool IsStackCombatCandidate(')+'\n'
actual+=body('CvUnitCombat.cpp','struct StackCollateralOrder')+';\n'
actual+=body('CvUnitCombat.cpp','std::vector<std::pair<const CvUnit*, int> > CvUnitCombat::GetStackCollateralDamage(')+'\n'
for f in ['bool CvAIOperation::IsSlotCommitted(','void CvAIOperation::RefreshReinforcementRequests(','OperationSlot CvAIOperation::PeekAtNextUnitToBuild(','bool CvAIOperation::CommitToBuildNextUnit(','bool CvAIOperation::UncommitToBuildUnit(']:actual+=body('CvAIOperation.cpp',f)+'\n'
tests=r'''
int checks=0,failed=0;void check(bool ok,const char*n){++checks;if(!ok){++failed;printf("FAIL: %s\n",n);}}
void combat(){CvCity city;CvPlot plot(&city);CvUnit siege(1,0),ship(2,0),bomber(3,0),a(10),b(11),c(12);ship.domain=DOMAIN_SEA;bomber.domain=DOMAIN_AIR;bomber.limit=5;
 CvStacking::cache.effectiveBuildingProtection[1]=60;CvStacking::cache.effectiveBuildingProtection[2]=60;city.buildings.counts[1]=city.buildings.counts[2]=1;
 vector<const CvUnit*>units;units.push_back(&a);units.push_back(&b);units.push_back(&c);SUnitIDValueContainer damage;
 CvUnit*attackers[3]={&siege,&ship,&bomber};
 for(int i=0;i<3;++i){CvUnit*u=attackers[i];
  city.hp=300;vector<pair<const CvUnit*,int> >v=CvUnitCombat::GetStackCollateralDamage(u,&plot,NULL,50,units,damage);
  check(v.size()==(i==2?3:2)&&v[0].second==1,"full city cap mitigates siege/naval/bomber collateral");
  city.hp=150;v=CvUnitCombat::GetStackCollateralDamage(u,&plot,NULL,50,units,damage);check(v[0].second==5,"half city protection scales before collateral");
  city.hp=0;v=CvUnitCombat::GetStackCollateralDamage(u,&plot,NULL,50,units,damage);check(v[0].second==10,"zero city no fortification collateral protection");
  city.hp=300;v=CvUnitCombat::GetStackCollateralDamage(u,&plot,NULL,50,units,damage,NULL,0,150);check(v[0].second==5,"virtual prior city hits match live half health");
  check(CvStacking::GetCityProtection(&city)==90,"virtual forecast did not mutate city");
 }
 city.hp=150;a.hp=52;b.hp=50;c.hp=40;
 vector<pair<const CvUnit*,int> >v=CvUnitCombat::GetStackCollateralDamage(&siege,&plot,NULL,50,units,damage);check(v.size()==1&&v[0].second==2,"secondary HP floor preserved");
 a.hp=55;v=CvUnitCombat::GetStackCollateralDamage(&siege,&plot,NULL,50,units,damage,&a,4);check(v.size()==1&&v[0].second==1,"ordinary garrison absorption separate");
 a.hp=b.hp=c.hp=100;settings["CityProtectionScalesWithHP"]=0;check(CvStacking::GetCityProtection(&city)==90,"XML disabling restores full legacy protection");settings.clear();
 city.buildings.counts.clear();check(CvStacking::GetCityProtection(&city)==0,"removed buildings no stale protection");city.buildings.counts[1]=1;city.hp=150;check(CvStacking::GetCityProtection(&city)==30,"captured buildings and HP read live");
 city.hp=300;check(CvStacking::GetCityProtection(&city)==60,"healing restores configured protection");
 settings["CityProtectionMaximumPercent"]=100;city.buildings.counts[2]=1;check(CvUnitCombat::GetStackCollateralDamage(&siege,&plot,NULL,50,units,damage).empty(),"full immunity setting honored");
 city.hp=150;check(!CvUnitCombat::GetStackCollateralDamage(&siege,&plot,NULL,50,units,damage).empty(),"damaged city loses configured immunity");
 settings["CollateralPercent"]=0;check(CvUnitCombat::GetStackCollateralDamage(&siege,&plot,NULL,50,units,damage).empty(),"collateral off preserved");settings.clear();enabled=false;check(CvStacking::GetCityProtection(&city)==0,"stacking off");enabled=true;
}
void production(){CvAIOperation op;CvArmyAI army;op.army=&army;army.slots.resize(5);army.roles.resize(5);army.roles[0].m_primaryUnitType=UNITAI_GENERAL;
 op.RefreshReinforcementRequests();check(op.m_viListOfUnitsWeStillNeedToBuild.size()==4,"expanded default allows four distinct proactive production slots");settings["AIOffensiveProductionMaximumUnits"]=2;
 op.RefreshReinforcementRequests();check(op.m_viListOfUnitsWeStillNeedToBuild.size()==2,"bounded proactive production before casualties");
 OperationSlot s=op.PeekAtNextUnitToBuild();check(s.m_iSlotID==1,"support/general not queued");check(op.CommitToBuildNextUnit(s),"first city reserves exactly once");check(!op.CommitToBuildNextUnit(s),"second city cannot reserve same slot");
 check(op.IsSlotCommitted(1),"reserve recruitment can exclude promised slot");op.RefreshReinforcementRequests();check(op.m_viListOfUnitsWeStillNeedToBuild.size()==1,"in-training counted toward production cap");
 OperationSlot second=op.PeekAtNextUnitToBuild();check(second.m_iSlotID==2,"next city gets different slot");check(op.CommitToBuildNextUnit(second),"second unique promise");
 op.RefreshReinforcementRequests();check(op.m_viListOfUnitsWeStillNeedToBuild.empty(),"no third request while two in training");
 check(op.UncommitToBuildUnit(s),"cancelled build releases promise");check(!op.IsSlotCommitted(1),"cancelled slot free to reserve");
 army.slots[1].id=42;op.RefreshReinforcementRequests();check(op.PeekAtNextUnitToBuild().m_iSlotID==3,"filled slot never requested again");
 settings["AIOffensiveProductionMaximumUnits"]=0;op.RefreshReinforcementRequests();check(op.m_viListOfUnitsWeStillNeedToBuild.empty(),"XML can disable additional production");settings.clear();
 op.m_eCurrentState=1;op.m_viListOfUnitsWeStillNeedToBuild.push_back(OperationSlot(1,7,4));op.RefreshReinforcementRequests();check(op.m_viListOfUnitsWeStillNeedToBuild.size()==1,"initial recruitment untouched");
 op.m_eCurrentState=3;op.cityAttack=false;op.RefreshReinforcementRequests();check(op.m_viListOfUnitsWeStillNeedToBuild.size()==1,"non-city operations untouched");
}
int main(){combat();production();printf("todo integration: %d checks, %d failures\n",checks,failed);return failed?1:0;}
'''
cpp=out/'integration-source-test.cpp';cpp.write_text(prefix+policy+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'integration-source-test.exe'
c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'integration.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr)
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'returncode':r.returncode,'output':r.stdout+r.stderr,'extracted_sha256':hashlib.sha256(actual.encode()).hexdigest(),'scope':'Actual source building protection, collateral calculation and production reservations, deterministic services; no game process.'},indent=2))
sys.exit(r.returncode)
