from pathlib import Path
import sys,json,hashlib
r=Path(r'E:\Projects\Civ5StackMod');sys.path.insert(0,str(r/'work/lua-validation'))
from lupa.lua51 import LuaRuntime
paths=[r/'(1) Community Patch/Core Files/Stacking/StackingTests.lua',r/'(1) Community Patch/Core Files/Stacking/StackingXMLVariationTests.lua']
payload=[p.read_text(encoding='utf-8-sig') for p in paths]
lua=LuaRuntime(unpack_returned_tuples=True);lua.globals().print=lambda *a:None
for source in payload:lua.execute(source)
# Definitions-only load intentionally has no game globals.
lua.execute(r'''
checks=0
function expect(a,b,label) checks=checks+1;assert(a==b,label..': '..tostring(a)..' != '..tostring(b)) end
function raises(fn,label)local ok=pcall(fn);expect(ok,false,label)end
function iter(rows)local n=0;return function()n=n+1;return rows[n]end end
Game={GetActivePlayer=function()return 0 end}
Players={[0]={GetTeam=function()return 0 end},[1]={GetTeam=function()return 1 end}}
function plot(id,x,y)
 local p={id=id,x=x,y=y,owner=-1,units={},terrain=1,feature=-1,water=false,city=false,imp=false}
 function p:GetPlotIndex()return self.id end;function p:GetX()return self.x end;function p:GetY()return self.y end
 function p:GetOwner()return self.owner end;function p:IsWater()return self.water end;function p:IsMountain()return false end
 function p:IsCity()return self.city end;function p:IsImpassable(team)expect(type(team),'number','impassability receives numeric team');return self.imp end
 function p:GetNumUnits()return #self.units end;function p:GetTerrainType()return self.terrain end;function p:GetFeatureType()return self.feature end
 function p:GetPlotCity()return self.cityObject end
 return p
end
local existing=plot(0,0,0);existing.city=true
near=plot(1,3,0);far=plot(2,10,0)
near.neighbors={plot(11,2,0),plot(12,4,0),plot(13,3,1),plot(14,3,-1),plot(15,2,1),plot(16,4,-1)}
far.neighbors={plot(21,9,0),plot(22,11,0),plot(23,10,1),plot(24,10,-1),plot(25,9,1),plot(26,11,-1)}
local plots={existing,near,far}
Map={GetNumPlots=function()return #plots end,GetPlotByIndex=function(i)return plots[i+1]end,PlotDistance=function(x,y,a,b)return math.abs(x-a)+math.abs(y-b)end,PlotDirection=function(x,y,d)for _,p in ipairs(plots)do if p.x==x and p.y==y then return (p.neighbors or {})[d+1]end end end}
local p=StackTests.Plots();expect(p,near,'ordinary unit patch need not exclude near city')
p=StackTests.Plots('target');expect(p,far,'target city excludes distance3')
local a;p,a=StackTests.Plots('source');expect(p,near,'air field target remains usable');expect(a[1].x,4,'airbase selects distance4 neighbor instead of distance2')
far.imp=true;raises(function()StackTests.Plots('target')end,'reject city patch on impassable feature');far.imp=false
far.neighbors[1].imp=true;raises(function()StackTests.Plots('target')end,'reject impassable neighbor');far.neighbors[1].imp=false
GameInfoTypes={UNIT_WARRIOR=1,TERRAIN_COAST=1,PROMOTION_DRILL_1=9}
local units={};local sequence=0;relocate=false
function makeUnit(owner,p)
 sequence=sequence+1
 local u={id=sequence,x=p.x,y=p.y,hp=100,busy=false,fighting=false,out=false,legal=true}
 function u:GetID()return self.id end;function u:GetX()return self.x end;function u:GetY()return self.y end
 function u:IsBusy()return self.busy end;function u:IsFighting()return self.fighting end;function u:IsOutOfAttacks()return self.out end
 function u:GetCurrHitPoints()return self.hp end;function u:GetMaxHitPoints()return 100 end
 function u:Kill(delay,who)expect(type(delay),'boolean','Kill delay bool');expect(who,-1,'Kill player');self.killed=true end
 function u:CanRangeStrikeAt(x,y)return self.legal end
 function u:GetRangeCombatDamage(d,c,random)expect(random,true,'real roll bool');return 10 end
 function u:GetStackAttackPreview(p,ranged)expect(type(ranged),'boolean','preview ranged bool');return {CityProtection=0,CollateralCount=2,DefenderID=2}end
 function u:GetStackRoleInfo()return {CollateralTargets=1}end
 function u:PushMission(m,x,y,flags,append,manual)expect(flags,0,'mission flags');expect(append,0,'mission append integer');expect(manual,1,'mission manual integer');self.missions=(self.missions or 0)+1 end
 function u:SetHasPromotion(id,value)expect(type(value),'boolean','promotion bool')end
 function u:SetBaseRangedCombatStrength(n)expect(type(n),'number','ranged strength integer')end
 units[owner..':'..u.id]=u;return u
end
for id,player in pairs(Players) do
 local owner=id
 function player:GetUnitByID(n)return units[owner..':'..n]end
 function player:InitUnit(kind,x,y)local u=makeUnit(owner,{x=x,y=y});if relocate then u.x=x+1 end;return u end
end
local spawn=StackTests.Spawn(0,'UNIT_WARRIOR',near);expect(spawn.x,near.x,'exact spawn')
relocate=true;raises(function()StackTests.Spawn(0,'UNIT_WARRIOR',near)end,'reject relocated spawn');relocate=false
expect(#StackTests.spawned,2,'relocated fixture still tracked for cleanup')
local last=Players[0]:GetUnitByID(StackTests.spawned[2].id);last.busy=true;StackTests.shot={old=true}
raises(StackTests.Cleanup,'busy cleanup refuses');expect(spawn.killed,nil,'cleanup checks all before any kills');expect(StackTests.shot.old,true,'busy cleanup retains pending state')
last.busy=false;StackTests.Cleanup();expect(#StackTests.spawned,0,'cleanup clears tracking');expect(StackTests.shot,nil,'cleanup clears stale shot')
GameInfo={Stacking_Settings=function()return iter({})end}
MissionTypes={MISSION_RANGE_ATTACK=9}
local attacker=makeUnit(0,near);local primary=makeUnit(1,far);local secondary=makeUnit(1,far)
local function shot()return {owner=0,enemy=1,attacker=attacker.id,target=far,primary=primary.id,before={[primary.id]={hp=100,max=100},[secondary.id]={hp=100,max=100}},preview={CityProtection=0}}end
StackTests.passed=0;StackTests.failed=0;StackTests.shot=shot()
raises(StackTests.CheckShot,'check needs a requested attack')
attacker.busy=true;raises(StackTests.Fire,'busy Fire rejected');expect(StackTests.shot.fired,nil,'busy does not spend fixture');attacker.busy=false
attacker.legal=false;raises(StackTests.Fire,'illegal Fire rejected');expect(StackTests.shot.fired,nil,'illegal shot not spent');attacker.legal=true
StackTests.Fire();expect(attacker.missions,1,'one ordinary mission');expect(StackTests.shot.rawDamage,10,'real deterministic roll recorded')
raises(StackTests.Fire,'duplicate Fire rejected')
local count=StackTests.passed;expect(StackTests.CheckShot(),false,'wait for unspent queued attack');expect(StackTests.passed,count,'wait adds no evidence');expect(StackTests.shot.checked,nil,'wait retains evidence')
attacker.busy=true;expect(StackTests.CheckShot(),false,'wait busy attacker');attacker.busy=false
secondary.fighting=true;expect(StackTests.CheckShot(),false,'wait fighting defender');secondary.fighting=false
attacker.out=true;primary.hp=90;secondary.hp=98
expect(StackTests.CheckShot(),true,'normal exact HP resolution retained');expect(StackTests.failed,0,'native test assertions pass');count=StackTests.passed
expect(StackTests.CheckShot(),true,'repeated completed check harmless');expect(StackTests.passed,count,'repeated check no duplicate evidence')
-- Exercise actual XML SetupSeaCollateral with a source whose first neighbor is
-- blocked coast and next is clear adjacent coast; no city or terrain mutation API.
local core=StackTests
local source=plot(31,30,0);source.water=true
local blocked=plot(32,31,0);blocked.water=true;blocked.feature=99
local target=plot(33,30,1);target.water=true
source.neighbors={blocked,target};local seaPlots={source,blocked,target}
Map.GetNumPlots=function()return #seaPlots end;Map.GetPlotByIndex=function(i)return seaPlots[i+1]end
Map.PlotDirection=function(x,y,d)for _,p in ipairs(seaPlots)do if p.x==x and p.y==y then return (p.neighbors or {})[d+1]end end end
Teams={[0]={},[1]={}}
for _,team in pairs(Teams)do function team:DeclareWar(e,defensive,owner)expect(type(defensive),'boolean','declareWar bool')end end
GameInfo.Stacking_Technologies=function()return iter({})end
GameInfo.Stacking_CollateralDomains=function()return iter({{DomainType='DOMAIN_SEA',Enabled=1}})end
local made={};local illegalSea=false
StackTests={Cleanup=function()end,Players=function()return 0,1 end,Check=function(name,a,b)expect(a,b,name);return a==b end,Spawn=function(owner,name,p)local u=makeUnit(owner,p);u.legal=not illegalSea;made[#made+1]={owner=owner,name=name,plot=p,u=u};return u end}
StackXMLTests.SetupSeaCollateral();expect(#made,7,'sea attacker plus six defenders');expect(made[1].plot,source,'clear native source');expect(StackTests.shot.target,target,'select adjacent clear target');for i=2,7 do expect(made[i].plot,target,'all sea victims exact target')end
blocked.feature=99;target.imp=true;raises(StackXMLTests.SetupSeaCollateral,'reject no clear adjacent sea pair');target.imp=false
illegalSea=true;raises(StackXMLTests.SetupSeaCollateral,'actual legal sea shot required');illegalSea=false
StackTests=core
''')
result={'lua51_syntax_and_inert_load':True,'checks':lua.globals().checks,'failures':0,'hashes':{str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in paths},'scope':'Actual Lua helpers with deterministic map/unit stubs: spacing/passability/spawn/lifecycle/adjacent-sea checks. No game, turn, build, install or process control; live engine behavior remains an integration check.'}
(r/'work/xml-fixture-regression').mkdir(exist_ok=True)
(r/'work/xml-fixture-regression/result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
