"""Exercise actual tactical siege helper source with deterministic forecast/engine stubs."""
from pathlib import Path
import os, subprocess, hashlib, json, sys
root=Path(__file__).resolve().parents[1]
out=root/'work/ai-siege-regression';out.mkdir(exist_ok=True)
raw=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_bytes()
s=raw.decode('utf-8-sig').replace('\r\n','\n')
def extract(start):
 a=s.index(start); b=s.index('{',a); depth=1;i=b+1
 while depth:
  depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
actual='\n'.join(extract(x) for x in ['static bool HasSurvivingStackProtection(', 'static bool CanApproachInProtectedStack(const CvUnit* unit, const CvPlot* destination, int destinationDanger)\n{', 'static bool HasVirtualCityEncirclement(', 'static int ScoreStackPosition('])
blocker_begin=s.index('\t\t\tif (other.eAssignmentType != A_MOVE && other.eAssignmentType != A_MOVE_DOUBLE)',s.index('bool CvTacticalPosition::makeNextAssignments'))
blocker_end=s.index('\n\t\t\t// Swap: blocker wants',blocker_begin)
blocker=s[blocker_begin:blocker_end]
actual+='\nstatic bool AcceptBlocker(const STacticalAssignment& assignment,const STacticalAssignment& other,int iBlockID,int eDomain){for(int once=0;once<1;++once){'+blocker+'\nreturn true;}return false;}\n'
prefix=r'''
#include <vector>
#include <map>
#include <string>
#include <algorithm>
#include <cstdio>
#include <climits>
using namespace std;
const int DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2,NO_TEAM=-1,NUM_DIRECTION_TYPES=6;
struct CvPlot;struct CvCity;
struct SUnitIDValueContainer{map<int,int> v;int GetValue(int id)const{map<int,int>::const_iterator i=v.find(id);return i==v.end()?0:i->second;}void SetValue(int id,int x){v[id]=x;}};
struct CvUnit{
 int id,owner,domain,hp,sourceDanger;bool combat,ranged,cargo,dead,support,defend,native,legal;CvPlot* source;
 CvUnit(int n=1):id(n),owner(0),domain(0),hp(100),sourceDanger(5),combat(true),ranged(false),cargo(false),dead(false),support(false),defend(true),native(true),legal(true),source(NULL){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getDomainType()const{return domain;}int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return 100;}
 bool IsCombatUnit()const{return combat;}bool IsCanAttackRanged()const{return ranged;}bool IsStackingUnit()const{return support;}bool isCargo()const{return cargo;}bool isDelayedDeath()const{return dead;}bool IsCanDefend()const{return defend;}
 bool isNativeDomain(const CvPlot*)const;CvPlot* plot()const{return source;}int GetDanger(const CvPlot*)const{return sourceDanger;}bool canMoveInto(const CvPlot&,int)const{return legal;}
 enum{MOVEFLAG_DESTINATION=4};
};
struct CvPlot{int id,domain;bool imp,city;vector<CvUnit*> members;CvPlot* neighbors[6];CvPlot(int n=1):id(n),domain(0),imp(false),city(false){for(int i=0;i<6;++i)neighbors[i]=NULL;}
 int GetPlotIndex()const{return id;}int getNumUnits()const{return(int)members.size();}CvUnit* getUnitByIndex(int i)const{return members[i];}bool isImpassable(int)const{return imp;}bool isCity()const{return city;}const CvCity* getPlotCity()const{return NULL;}bool needsEmbarkation(const CvUnit*u)const{return u->domain==0&&domain==1;}};
bool CvUnit::isNativeDomain(const CvPlot*p)const{return native&&domain==p->domain;}
struct CvCity{CvPlot*p;CvPlot*plot()const{return p;}int getTeam()const{return 1;}};
struct MapStub{CvPlot**getNeighborsUnchecked(const CvPlot*p){return const_cast<CvPlot**>(p->neighbors);}};
struct GCStub{MapStub map;MapStub&getMap(){return map;}}GC;
struct CvTacticalPosition{map<int,vector<const CvUnit*> > members;map<int,SUnitIDValueContainer> damage;SUnitIDValueContainer enemy;int getPlayer()const{return 0;}const SUnitIDValueContainer&GetUnitDamageDealt()const{return enemy;}};
static bool prefs=true;
static bool StackPreferencesEnabled(){return prefs;}
namespace CvStacking{bool IsEnabled(){return prefs;}bool CanFlank(const CvUnit*){return false;}int GetCollateralTargetLimit(const CvUnit*){return 0;}bool IsAntiCavalry(const CvUnit*){return false;}bool IsCollateralTargetDomain(int d){return d==0;}int GetCityProtection(const CvCity*){return 0;}int GetInt(const char*,int d){return d;}}
struct PlayerStub{vector<CvUnit*> attackers;vector<CvUnit*>GetPossibleAttackers(const CvPlot&,int){return attackers;}}player;
static PlayerStub&GET_PLAYER(int){return player;}
static map<int,int> forecast;
static int code(int id,int plot,const vector<const CvUnit*>&v){int mask=0;for(size_t i=0;i<v.size();++i)mask|=1<<v[i]->id;return plot*100000+id*1000+mask;}
static int GetCachedStackDanger(const CvUnit*u,const CvPlot*p,const vector<const CvUnit*>&v,const SUnitIDValueContainer&,const SUnitIDValueContainer&){map<int,int>::const_iterator i=forecast.find(code(u->id,p->id,v));return i==forecast.end()?999:i->second;}
static void risk(const CvUnit&u,const CvPlot&p,const vector<const CvUnit*>&v,int n){forecast[code(u.id,p.id,v)]=n;}
enum{A_MOVE=1,A_MOVE_DOUBLE=2,A_BLOCKED=3};
struct STacticalAssignment{int iUnitID,iFromPlotIndex,iToPlotIndex,eAssignmentType,eMoveType;STacticalAssignment(int id,int from,int to):iUnitID(id),iFromPlotIndex(from),iToPlotIndex(to),eAssignmentType(A_MOVE),eMoveType(1){}};
struct SUnitStats{const CvUnit*pUnit;int iMovesLeft,iPlotIndex;SUnitStats():pUnit(NULL),iMovesLeft(1),iPlotIndex(2){}};
static map<int,SUnitStats> available;
static const SUnitStats*getAvailableUnitStats(int id){map<int,SUnitStats>::const_iterator i=available.find(id);return i==available.end()?NULL:&i->second;}
static bool isCombatUnit(int m){return m>=1&&m<=3;}static bool isEmbarkedUnit(int m){return m==5;}
static void GetVirtualFriendlyStack(const CvTacticalPosition&pos,const CvPlot*p,const CvUnit*u,int extra,vector<const CvUnit*>&v,SUnitIDValueContainer&d){
 map<int,vector<const CvUnit*> >::const_iterator i=pos.members.find(p->id);if(i!=pos.members.end())v=i->second;
 map<int,SUnitIDValueContainer>::const_iterator j=pos.damage.find(p->id);if(j!=pos.damage.end())d=j->second;
 if(u){if(find(v.begin(),v.end(),u)==v.end())v.push_back(u);d.SetValue(u->id,extra);}}
'''
suffix=r'''
static int checks=0,fail=0;static void expect(const char*n,bool x){++checks;if(!x){++fail;printf("FAIL %s\n",n);}}
int main(){
 CvUnit siege(1),guard(2),other(3);siege.ranged=true;CvPlot src(1),dest(2);siege.source=&src;guard.source=&dest;other.source=&dest;
 vector<const CvUnit*> solo,pair,before;solo.push_back(&siege);pair=solo;pair.push_back(&guard);before.push_back(&guard);
 SUnitIDValueContainer none;CvTacticalPosition pos;pos.members[2]=pair;
 risk(siege,dest,solo,60);risk(siege,dest,pair,3);risk(guard,dest,pair,40);risk(guard,dest,before,40);
 expect("real protection survives",HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));
 risk(siege,dest,solo,3);expect("aggression-scaled hint cannot fake protection",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,1));expect("weak or bypassed protector adds no cover",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));risk(siege,dest,solo,60);
 risk(guard,dest,pair,100);expect("sacrificial protector refused",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));risk(guard,dest,pair,40);
 risk(siege,dest,pair,100);expect("siege itself must survive",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,100));risk(siege,dest,pair,3);
 SUnitIDValueContainer hurt;hurt.SetValue(2,65);expect("virtual protector wounds counted",!HasSurvivingStackProtection(&siege,&dest,pair,hurt,none,3));
 guard.cargo=true;expect("cargo excluded",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));guard.cargo=false;
 guard.support=true;expect("support excluded",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));guard.support=false;
 guard.ranged=true;expect("ranged not a melee escort",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));guard.ranged=false;
 guard.domain=1;expect("wrong domain excluded",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));guard.domain=0;
 guard.dead=true;expect("delayed death excluded",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));guard.dead=false;
 guard.owner=1;expect("foreign escort excluded",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));guard.owner=0;
 prefs=false;expect("preferences disabled preserves fog rule",!HasSurvivingStackProtection(&siege,&dest,pair,none,none,3));prefs=true;
 dest.members.push_back(&guard);
 expect("protected safer approach permitted",CanApproachInProtectedStack(&siege,&dest,3));
 siege.sourceDanger=2;expect("cannot worsen siege danger",!CanApproachInProtectedStack(&siege,&dest,3));siege.sourceDanger=5;
 risk(guard,dest,before,30);expect("cannot worsen ally danger",!CanApproachInProtectedStack(&siege,&dest,3));risk(guard,dest,before,40);
 siege.legal=false;expect("cannot bypass capacity",!CanApproachInProtectedStack(&siege,&dest,3));siege.legal=true;
 expect("same plot is not advance",!CanApproachInProtectedStack(&siege,&src,3));
 dest.members.clear();expect("no imaginary escort",!CanApproachInProtectedStack(&siege,&dest,3));dest.members.push_back(&guard);
 player.attackers.clear();expect("city-only threat awards real join benefit",ScoreStackPosition(&siege,&dest,0,pos)>0);
 risk(siege,dest,solo,3);expect("city-only no benefit no free join",ScoreStackPosition(&siege,&dest,0,pos)==0);risk(siege,dest,solo,60);
 prefs=false;expect("city preference toggle",ScoreStackPosition(&siege,&dest,0,pos)==0);prefs=true;
 CvPlot center(9),ring[6];CvCity city;city.p=&center;CvTacticalPosition enc;
 for(int i=0;i<6;++i){ring[i].id=10+i;center.neighbors[i]=&ring[i];enc.members[10+i].push_back(&guard);}
 expect("six distinct occupied hexes encircle",HasVirtualCityEncirclement(enc,&city));
 enc.members[15].clear();enc.members[10].assign(8,&guard);expect("extra members cannot replace missing hex",!HasVirtualCityEncirclement(enc,&city));
 ring[5].imp=true;expect("impassable side excluded",HasVirtualCityEncirclement(enc,&city));ring[5].imp=false;
 enc.members[15].push_back(&guard);enc.damage[15].SetValue(2,100);expect("virtual casualty cannot blockade",!HasVirtualCityEncirclement(enc,&city));enc.damage[15].v.clear();
 ring[5].domain=1;expect("embarked land cannot naval encircle",!HasVirtualCityEncirclement(enc,&city));CvUnit ship(4);ship.domain=1;enc.members[15].clear();enc.members[15].push_back(&ship);expect("native ship covers water side",HasVirtualCityEncirclement(enc,&city));
 ship.cargo=true;expect("transport cargo no blockade",!HasVirtualCityEncirclement(enc,&city));ship.cargo=false;ring[5].city=true;expect("neighbor city not blockaded",!HasVirtualCityEncirclement(enc,&city));
 STacticalAssignment incoming(1,1,2),exit(3,2,3);available[3].pUnit=&other;
 expect("second full-stack occupant may vacate",AcceptBlocker(incoming,exit,2,0));
 available[3].iMovesLeft=0;expect("spent alternate cannot vacate",!AcceptBlocker(incoming,exit,2,0));available[3].iMovesLeft=1;
 other.cargo=true;expect("cargo cannot free slot",!AcceptBlocker(incoming,exit,2,0));other.cargo=false;
 other.support=true;expect("support cannot free combat slot",!AcceptBlocker(incoming,exit,2,0));other.support=false;
 other.domain=1;expect("other domain cannot free land slot",!AcceptBlocker(incoming,exit,2,0));other.domain=0;
 exit.iToPlotIndex=2;expect("no-op exit rejected",!AcceptBlocker(incoming,exit,2,0));exit.iToPlotIndex=3;
 available[3].iPlotIndex=4;expect("virtual location authoritative",!AcceptBlocker(incoming,exit,2,0));available[3].iPlotIndex=2;
 exit.eAssignmentType=A_BLOCKED;expect("finish cannot free slot",!AcceptBlocker(incoming,exit,2,0));exit.eAssignmentType=A_MOVE;
 incoming.eMoveType=5;expect("embarked land shares native slot",AcceptBlocker(incoming,exit,2,0));incoming.eMoveType=1;
 prefs=false;expect("legacy retains first-blocker restriction",!AcceptBlocker(incoming,exit,2,0));expect("legacy original blocker retained",AcceptBlocker(incoming,exit,3,0));prefs=true;
 printf("siege source regression: %d checks, %d failures\n",checks,fail);return fail?1:0;
}
'''
cpp=out/'siege-source-test.cpp';cpp.write_text(prefix+actual+suffix,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'siege-source-test.exe'
c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'siege.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'source_sha256':hashlib.sha256(raw).hexdigest().upper(),'extracted_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'returncode':r.returncode,'output':r.stdout+r.stderr,'scope':'Actual helper functions compiled with VC9, deterministic engine/forecast stubs; not game combat validation.'},indent=2),encoding='utf-8')
sys.exit(r.returncode)
