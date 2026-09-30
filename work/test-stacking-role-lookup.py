"""Real enum-role loading/lookup and defender filtering vs pinned DLL47 source.

Uses native x86 VC9 and counts actual global-new allocations. The role loader,
lookup/precedence, public role helpers and complete defender selector are source;
database, unit metadata and numerical exchange services are deterministic stubs.
"""
from pathlib import Path
import ast, hashlib, json, os, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'work/stacking-role-lookup-regression'
out.mkdir(exist_ok=True)
core = root / 'CvGameCoreDLL_Expansion2'
source = (core / 'CvStackingRules.cpp').read_text(encoding='utf-8-sig')
original = subprocess.check_output(['git', 'show', '6c863259f:CvGameCoreDLL_Expansion2/CvStackingRules.cpp'], cwd=root).decode('utf-8-sig')
combat = (core / 'CvUnitCombat.cpp').read_text(encoding='utf-8-sig')
unit_header = (core / 'CvUnit.h').read_text(encoding='utf-8-sig')

def function(text, name):
    start = text.index(name)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

def implementation(text):
    private = text[text.index('namespace\n{'):text.index('namespace CvStacking\n')]
    public = '\n'.join(function(text, signature) for signature in ('void ResetCache()', 'int GetInt(', 'bool IsEnabled()', 'bool CanFlank(', 'bool IsAntiCavalry(', 'bool IsFlankTarget(', 'int GetCollateralTargetLimit('))
    return private + '\nnamespace CvStacking{\n' + public + '\n}\n'

scaffold = {}
for node in ast.parse((root / 'work/test-stacking-setting-lookup.py').read_text()).body:
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        for target in node.targets:
            if isinstance(target, ast.Name):
                scaffold[target.id] = node.value.value
prefix = '#define NOMINMAX\n' + scaffold['prefix']
db_start = prefix.index('namespace Database {')
prefix = prefix[:db_start] + r'''
#include <set>
typedef int PromotionTypes;typedef __int64 int64;
const int DOMAIN_LAND=2,DOMAIN_SEA=0,DOMAIN_AIR=1;
namespace Database {
 struct Row {
  string name,role;int value,id;bool matched,nullRole;
  Row(const string&n="",int v=0):name(n),value(v),id(0),matched(true),nullRole(false){}
  Row(int i,const string&r,int v,bool match=true,bool null=false):name("REFERENCE"),role(r),value(v),id(i),matched(match),nullRole(null){}
 };
 struct Results {
  vector<Row>rows;size_t next;Row active;string rowText,roleText;
  Results():next(0){}
  bool Step(){rowText.assign(128,'!');roleText.assign(128,'!');if(next>=rows.size())return false;active=rows[next++];rowText=active.name;roleText=active.role;return true;}
  const char*GetText(const char*key){if(!strcmp(key,"Role"))return active.nullRole?NULL:roleText.c_str();if(!strcmp(key,"MatchedType")&&!active.matched)return NULL;return rowText.c_str();}
  int GetInt(const char*key){return !strcmp(key,"ReferenceID")?active.id:active.value;}
 };
 struct Connection {
  bool schema,failSettings,failSchema;int executes;vector<Row>settings;map<string,vector<Row> >roleRows;string failedRoleTable;
  Connection():schema(true),failSettings(false),failSchema(false),executes(0){}
  bool Execute(Results&result,const char*query){++executes;
   if(strstr(query,"sqlite_master")){if(failSchema)return false;if(schema)result.rows.push_back(Row("Stacking_Settings"));return true;}
   if(strstr(query,"SELECT Name, Value FROM Stacking_Settings")){if(failSettings)return false;result.rows=settings;return true;}
   const char*tables[]={"Stacking_UnitCombatRoles","Stacking_UnitClassRoles","Stacking_UnitRoles","Stacking_PromotionRoles"};
   for(int i=0;i<4;++i)if(strstr(query,tables[i])){if(failedRoleTable==tables[i])return false;result.rows=roleRows[tables[i]];return true;}
   return true;
  }
 };
}
struct Globals{Database::Connection*database;Globals():database(NULL){}Database::Connection*GetGameDatabase(){return database;}}GC;
struct CvPlot{};static CvPlot plot;
struct CvUnit {
 int id,owner,combatType,classType,type,domain,hp,maxHP,damage,retaliation;bool combat,cargo,ranged,dead,delayed;set<int>promotions;
 CvUnit(int n=0):id(n),owner(0),combatType(10),classType(20),type(40),domain(DOMAIN_LAND),hp(100),maxHP(100),damage(33),retaliation(13),combat(true),cargo(false),ranged(false),dead(false),delayed(false){}
 int getUnitCombatType()const{return combatType;}int getUnitClassType()const{return classType;}int getUnitType()const{return type;}
 bool isHasPromotion(PromotionTypes p)const{return promotions.count(p)!=0;}bool IsCombatUnit()const{return combat;}bool isCargo()const{return cargo;}bool IsCanAttackRanged()const{return ranged;}int getDomainType()const{return domain;}
 bool IsCanDefend()const{return combat;}bool IsDead()const{return dead;}bool isDelayedDeath()const{return delayed;}int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return maxHP;}int getOwner()const{return owner;}int GetID()const{return id;}const CvPlot*plot()const{return &::plot;}
 bool isBetterDefenderThan(const CvUnit*other,const CvUnit*)const{return !other||hp>other->hp||(hp==other->hp&&id<other->id);}
};
'''
container = unit_header[unit_header.index('struct SUnitIDValueContainer\n'):unit_header.index('\nnamespace std {', unit_header.index('struct SUnitIDValueContainer\n'))]
selector = function(combat, 'const CvUnit* CvUnitCombat::SelectStackDefender(')
selection = r'''
struct CvUnitCombat{static const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool,int);};
static void GetStackExchange(const CvUnit*a,const CvUnit*d,const CvPlot*,const CvPlot*,bool ranged,int extraA,int extraD,int&damage,int&retaliation){damage=max(0,a->damage-extraA/7+d->type%7+extraD/11);retaliation=ranged?0:max(0,d->retaliation-extraD/9);}
'''
selection += function(combat, 'static bool IsStackCombatCandidate(') + '\n' + selector + '\n'
selection += selector.replace('CvUnitCombat::SelectStackDefender', 'OriginalSelector').replace('CvStacking::', 'Original::CvStacking::') + '\n'
tests = r'''
static int checks=0,failures=0;static unsigned int rng=927574;
static unsigned int next(){rng=rng*1664525u+1013904223u;return rng;}
static void expect(const char*name,bool ok){++checks;if(!ok){++failures;if(failures<25)printf("FAIL %s\n",name);}}
static const char*roles[]={"FLANK","ANTI_CAVALRY","FLANK_TARGET","COLLATERAL_LIMIT"};
static int CurrentRole(const CvUnit*unit,const char*name){return Role(unit,ParseRole(name));}
static void reset(){CvStacking::ResetCache();Original::CvStacking::ResetCache();}
static void clear(Database::Connection&db){db.settings.clear();db.roleRows.clear();db.schema=true;db.failSettings=db.failSchema=false;db.failedRoleTable.clear();reset();}
static void equalRoles(const CvUnit*unit){for(int i=0;i<4;++i)expect("all exact role values agree with DLL47",CurrentRole(unit,roles[i])==Original::Role(unit,roles[i]));
 expect("flanking gate agrees with DLL47",CvStacking::CanFlank(unit)==Original::CvStacking::CanFlank(unit));expect("anti-cavalry gate agrees with DLL47",CvStacking::IsAntiCavalry(unit)==Original::CvStacking::IsAntiCavalry(unit));expect("flank-target gate agrees with DLL47",CvStacking::IsFlankTarget(unit)==Original::CvStacking::IsFlankTarget(unit));expect("collateral gate agrees with DLL47",CvStacking::GetCollateralTargetLimit(unit)==Original::CvStacking::GetCollateralTargetLimit(unit));}
int main(){
 expect("native x86 VC9",sizeof(void*)==4);CvUnit unit(1);equalRoles(&unit);equalRoles(NULL);
 Database::Connection db;GC.database=&db;clear(db);
 db.roleRows["Stacking_UnitCombatRoles"].push_back(Database::Row(10,"FLANK",1));db.roleRows["Stacking_UnitClassRoles"].push_back(Database::Row(20,"FLANK",0));reset();equalRoles(&unit);expect("class zero replaces combat default",CurrentRole(&unit,"FLANK")==0);
 db.roleRows["Stacking_PromotionRoles"].push_back(Database::Row(30,"FLANK",1));reset();expect("unowned promotion gives no grant",CurrentRole(&unit,"FLANK")==0);unit.promotions.insert(30);equalRoles(&unit);expect("owned promotion grants after class zero",CurrentRole(&unit,"FLANK")==1);unit.promotions.clear();equalRoles(&unit);expect("late promotion removal remains dynamic",CurrentRole(&unit,"FLANK")==0);
 db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"FLANK",0));unit.promotions.insert(30);reset();equalRoles(&unit);expect("explicit unit zero disables promotion grant",CurrentRole(&unit,"FLANK")==0);
 clear(db);unit.promotions.clear();db.roleRows["Stacking_UnitCombatRoles"].push_back(Database::Row(10,"COLLATERAL_LIMIT",2));db.roleRows["Stacking_UnitClassRoles"].push_back(Database::Row(20,"COLLATERAL_LIMIT",4));db.roleRows["Stacking_PromotionRoles"].push_back(Database::Row(30,"COLLATERAL_LIMIT",7));db.roleRows["Stacking_PromotionRoles"].push_back(Database::Row(31,"COLLATERAL_LIMIT",9));unit.promotions.insert(30);unit.promotions.insert(31);reset();equalRoles(&unit);expect("maximum owned promotion grant",CurrentRole(&unit,"COLLATERAL_LIMIT")==9);
 db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"COLLATERAL_LIMIT",3));reset();equalRoles(&unit);expect("explicit unit lower value replaces max promotion",CurrentRole(&unit,"COLLATERAL_LIMIT")==3);
 for(int r=0;r<4;++r){clear(db);db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,roles[r],INT_MAX));reset();equalRoles(&unit);expect("exact role upper clamp",CurrentRole(&unit,roles[r])==(r==3?32:1));db.roleRows["Stacking_UnitRoles"][0].value=INT_MIN;reset();equalRoles(&unit);expect("exact role lower clamp",CurrentRole(&unit,roles[r])==0);}
 clear(db);db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"COLLATERAL_LIMIT",8,false));db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"FLANK",1,true,true));db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"UnknownRole",22));db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"flank",1));reset();equalRoles(&unit);expect("unknown ref/null role/unknown name/case ignored",CurrentRole(&unit,"COLLATERAL_LIMIT")==0&&CurrentRole(&unit,"FLANK")==0&&Cache().unitRoles.empty()&&Original::Cache().unitRoles.empty());
 db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"COLLATERAL_LIMIT",6));reset();expect("row text lifetime independent after loading",CurrentRole(&unit,"COLLATERAL_LIMIT")==6);Original::Role(&unit,"COLLATERAL_LIMIT");db.roleRows.clear();equalRoles(&unit);expect("configured roles survive database buffer changes",CurrentRole(&unit,"COLLATERAL_LIMIT")==6);reset();equalRoles(&unit);expect("reset discards prior role mappings",CurrentRole(&unit,"COLLATERAL_LIMIT")==0);
 for(int mode=0;mode<4;++mode){clear(db);db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"FLANK",1));db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"COLLATERAL_LIMIT",5));if(mode==0)db.schema=false;if(mode==1)db.failSchema=true;if(mode==2)db.failedRoleTable="Stacking_UnitRoles";if(mode==3)db.settings.push_back(Database::Row("Enabled",0));reset();equalRoles(&unit);expect("missing schema/failure/disabled keeps public gates zero",!CvStacking::CanFlank(&unit)&&CvStacking::GetCollateralTargetLimit(&unit)==0);}
 // Recreate many XML configurations, including duplicate mocked rows, all unit
 // metadata and mutable owned-promotion sets. Numerical values are exact.
 const char*tables[]={"Stacking_UnitCombatRoles","Stacking_UnitClassRoles","Stacking_UnitRoles","Stacking_PromotionRoles"};
 for(int trial=0;trial<2000;++trial){clear(db);const int bases[]={10,20,40,30};for(int table=0;table<4;++table)for(int row=0,n=(int)(next()%14);row<n;++row)db.roleRows[tables[table]].push_back(Database::Row(bases[table]+(int)(next()%5),roles[next()%4],(int)(next()%50)-9,next()%13!=0,next()%31==0));db.settings.push_back(Database::Row("Enabled",next()%5?1:0));db.settings.push_back(Database::Row("FlankingEnabled",(int)(next()%2)));db.settings.push_back(Database::Row("CollateralEnabled",(int)(next()%2)));reset();for(int sample=0;sample<6;++sample){unit.combatType=10+(int)(next()%5);unit.classType=20+(int)(next()%5);unit.type=40+(int)(next()%5);unit.domain=(int)(next()%3);unit.combat=next()%5!=0;unit.cargo=next()%7==0;unit.ranged=next()%2!=0;unit.promotions.clear();for(int p=30;p<35;++p)if(next()%2)unit.promotions.insert(p);equalRoles(&unit);}}
 // The actual full defender selector now exercises the public enum role gates.
 // Its deterministic exchange service isolates filtering/selection agreement.
 clear(db);for(int table=0;table<4;++table)for(int id=0;id<5;++id)for(int r=0;r<4;++r)db.roleRows[tables[table]].push_back(Database::Row((table==0?10:table==1?20:table==2?40:30)+id,roles[r],(id+r)%3));reset();CvUnit party[8],attacker(99);attacker.owner=1;SUnitIDValueContainer wounds;vector<const CvUnit*>members;
 for(int trial=0;trial<6000;++trial){members.clear();wounds.clear();attacker.combatType=10+(int)(next()%5);attacker.classType=20+(int)(next()%5);attacker.type=40+(int)(next()%5);attacker.ranged=next()%2!=0;attacker.domain=(int)(next()%3);for(int j=0;j<8;++j){party[j]=CvUnit(j+1);party[j].combatType=10+(int)(next()%5);party[j].classType=20+(int)(next()%5);party[j].type=40+(int)(next()%5);party[j].hp=(int)(next()%101);party[j].ranged=next()%2!=0;party[j].domain=(int)(next()%3);party[j].cargo=next()%9==0;party[j].dead=next()%17==0;party[j].delayed=next()%19==0;for(int p=30;p<35;++p)if(next()%2)party[j].promotions.insert(p);wounds.SetValue(j+1,(int)(next()%120)-10);members.push_back(&party[j]);}if(trial%7==0)members.push_back(&party[2]);bool ranged=attacker.ranged;int extra=(int)(next()%80);expect("actual defender filtering/scored choice matches DLL47",CvUnitCombat::SelectStackDefender(&attacker,&plot,&plot,members,wounds,ranged,extra)==OriginalSelector(&attacker,&plot,&plot,members,wounds,ranged,extra));}
 // Warm both actual APIs outside the measured allocation interval.
 clear(db);unit=CvUnit(1);db.roleRows["Stacking_UnitRoles"].push_back(Database::Row(40,"COLLATERAL_LIMIT",3));reset();expect("warm collateral values agree",CvStacking::GetCollateralTargetLimit(&unit)==3&&Original::CvStacking::GetCollateralTargetLimit(&unit)==3);volatile unsigned long checksum=0;
 allocations=0;countAllocations=true;for(int i=0;i<100000;++i)checksum+=Original::CvStacking::GetCollateralTargetLimit(&unit);countAllocations=false;const unsigned long oldAllocations=allocations;
 allocations=0;countAllocations=true;for(int i=0;i<100000;++i)checksum+=CvStacking::GetCollateralTargetLimit(&unit);countAllocations=false;const unsigned long currentAllocations=allocations;
 expect("counter detects DLL47 temporary collateral-role heap strings",oldAllocations>=300000);expect("100000 actual collateral-role queries allocate nothing",currentAllocations==0);expect("all measured calls evaluated",checksum==600000);
 printf("Role lookup control: 100000calls %lu allocations DLL47 vs %lu current; actual selector agreement6000\n",oldAllocations,currentAllocations);
 printf("stacking role actual-source checks: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
current_impl = implementation(source)
original_impl = 'namespace Original{\n' + implementation(original) + '\n}\n'
fixture = prefix + container + current_impl + original_impl + selection + tests
cpp = out / 'stacking-role-lookup-test.cpp'
cpp.write_text(fixture, encoding='utf-8')
vc = root / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = root / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc / 'Vc7/bin') + ';' + str(vc / 'Common7/IDE') + ';' + env.get('PATH', '')
env['INCLUDE'] = str(root / 'work/toolchain/sdk/vc9/include') + ';' + str(sdk / 'Include')
env['LIB'] = str(root / 'work/toolchain/sdk/vc9/lib') + ';' + str(sdk / 'Lib')
for key in ('CL', '_CL_', 'LINK'):
    env.pop(key, None)
exe = out / 'stacking-role-lookup-test.exe'
compiled = subprocess.run([str(vc / 'Vc7/bin/cl.exe'), '/nologo', '/EHsc', '/MT', '/O2', '/Z7', '/D_SECURE_SCL=0', '/D_HAS_ITERATOR_DEBUGGING=0', str(cpp), '/Fo' + str(out / 'stacking-role-lookup-test.obj'), '/Fe' + str(exe)], cwd=out, env=env, capture_output=True, text=True, timeout=60)
(out / 'compile.log').write_text(compiled.stdout + compiled.stderr, encoding='utf-8')
if compiled.returncode:
    print(compiled.stdout + compiled.stderr)
    sys.exit(compiled.returncode)
result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=60)
print(result.stdout + result.stderr, end='')
(out / 'result.json').write_text(json.dumps(dict(compile_returncode=compiled.returncode, test_returncode=result.returncode, output=result.stdout + result.stderr, control_commit='6c863259f', current_impl_sha256=hashlib.sha256(current_impl.encode()).hexdigest(), fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(), scope='Actual RulesCache/loaders/Role/Lookup/public role gates vs DLL47 with ephemeral DB text, metadata and mutable promotions; complete actual defender selector with substituted exchange math; native32bitVC9 global-new allocation counts. No DLLbuild/game.'), indent=2), encoding='utf-8')
sys.exit(result.returncode)
