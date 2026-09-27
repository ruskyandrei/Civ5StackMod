"""Run the actual production-turn Lua fixture through strict native-API contracts.
This checks helper argument types/flow with a small simulated world, not DLL behavior.
"""
from pathlib import Path
import sys,json,hashlib,re
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'work/lua-validation'));from lupa.lua51 import LuaRuntime
fixture=(root/'(1) Community Patch/Core Files/Stacking/StackingProductionTurnTests.lua').read_text(encoding='utf-8-sig')
# Pin the mixed native parsing contracts that caused the live fixture failure.
city=(root/'CvGameCoreDLL_Expansion2/Lua/CvLuaCity.cpp').read_text(encoding='utf-8-sig')
unit=(root/'CvGameCoreDLL_Expansion2/Lua/CvLuaUnit.cpp').read_text(encoding='utf-8-sig')
for name in ('CanTrain','CanConstruct'):
 body=city[city.index('int CvLuaCity::l'+name+'('):];body=body[:body.index('//------------------------------------------------------------------------------')]
 for slot in range(3,7):assert 'luaL_optint(L, '+str(slot)+', 0)' in body
body=city[city.index('int CvLuaCity::lPushOrder('):];body=body[:body.index('//------------------------------------------------------------------------------')]
assert 'lua_tointeger(L, 5)' in body and 'lua_toboolean(L, 6)' in body and 'lua_toboolean(L, 7)' in body and 'luaL_optint(L, 8, 0)' in body
body=unit[unit.index('int CvLuaUnit::lKill('):];body=body[:body.index('//------------------------------------------------------------------------------')];assert 'lua_toboolean(L, 2)' in body
stub=r'''
logs={};print=function(...)logs[#logs+1]={...}end
local function number(x,label)assert(type(x)=='number','integer binding '..label..' rejects '..type(x))end
local function boolean(x,label)assert(type(x)=='boolean','boolean binding '..label..' rejects '..type(x))end
contractCalls={train=0,construct=0,push=0,mission=0,kill=0}
Game={GetActivePlayer=function()return 0 end,GetAIAutoPlay=function()return 0 end,IsGameMultiPlayer=function()return false end,GetGameTurn=function()return turn end,GetGameSpeedType=function()return 0 end}
turn=1;nextID=100;units={};queueData={};bank=0;things=0;making=0;trained=nil
OrderTypes={ORDER_TRAIN=1,ORDER_CONSTRUCT=2};DomainTypes={DOMAIN_LAND=2};ActivityTypes={ACTIVITY_SLEEP=1,ACTIVITY_AWAKE=2};MissionTypes={MISSION_MOVE_TO=3}
GameDefines={MAX_UNIT_SUPPLY_PRODMOD=70,PRODUCTION_PENALTY_PER_UNIT_OVER_SUPPLY=5}
GameInfoTypes={UNIT_WARRIOR=83,UNITCLASS_WARRIOR=9,BUILDING_MONUMENT=1}
GameInfo={Units={[83]={Domain='DOMAIN_LAND',Combat=10,NumberStackingUnits=0,Class='UNITCLASS_WARRIOR'}},BuildingClasses={ORDINARY={MaxGlobalInstances=-1,MaxPlayerInstances=-1}},GameSpeeds={[0]={ExperiencePercent=75}},Buildings=function()local done=false;return function()if not done then done=true;return {ID=2,Cost=40,BuildingClass='ORDINARY'}end end end}
plots={}
for id=0,3 do
 local p={id=id,x=id,y=0,units={}}
 function p:GetX()return self.x end;function p:GetY()return 0 end;function p:GetPlotIndex()return self.id end;function p:GetPlotType()return 0 end;function p:GetTerrainType()return 0 end;function p:GetFeatureType()return -1 end;function p:GetResourceType(team)number(team,'resource team');return -1 end;function p:GetNumResource()return 0 end;function p:GetImprovementType()return -1 end;function p:GetRouteType()return -1 end;function p:GetOwner()return 0 end;function p:GetNumUnits()return #self.units end;function p:GetUnit(i)number(i,'plot unit index');return self.units[i+1]end;function p:IsWater()return false end;function p:IsImpassable(team)number(team,'impassability team');return false end;function p:IsCity()return self.id==0 end
 plots[id]=p
end
Map={GetPlotByIndex=function(id)number(id,'plot index');return plots[id]end,PlotDistance=function(x,y,xx,yy)return (x==3 or xx==3)and 2 or math.abs(x-xx)end,PlotDirection=function(x,y,d)if x==0 then return d==0 and plots[1]or(d==1 and plots[2]or nil)elseif x==1 and d==0 then return plots[3]end end,PlotXYWithRangeCheck=function(x,y,dx,dy,r)return dx==0 and dy==0 and plots[0]or nil end}
local function erase(p,u)for i,v in ipairs(p.units)do if v==u then table.remove(p.units,i);return end end end
player={};city={}
function player:IsTurnActive()return true end;function player:GetCapitalCity()return city end;function player:GetCityByID(id)number(id,'city id');return city end;function player:GetTeam()return 0 end
function player:Cities()local done=false;return function()if not done then done=true;return city end end end
function player:Units()local ids={};for id in pairs(units)do ids[#ids+1]=id end;table.sort(ids);local i=0;return function()i=i+1;return ids[i]and units[ids[i]]or nil end end
function player:GetUnitByID(id)number(id,'unit id');return units[id]end
function player:GetUnitClassMaking(id)number(id,'unit class');return making end;function player:GetNumUnitsOutOfSupply()return 0 end;function player:GetGold()return 1360 end;function player:GetGoldTimes100()return 136000 end;function player:CalculateGoldRate()return 5 end
function player:InitUnit(kind,x,y)
 number(kind,'unit type');number(x,'init x');number(y,'init y');local p=plots[x];local u={id=nextID,p=p,hp=100,xp=75,tag='',kind=kind};nextID=nextID+1
 function u:GetID()return self.id end;function u:GetOwner()return 0 end;function u:GetUnitType()return self.kind end;function u:GetX()return self.p.x end;function u:GetY()return self.p.y end;function u:GetPlot()return self.p end;function u:GetCurrHitPoints()return self.hp end;function u:GetExperienceTimes100()return self.xp end;function u:GetStackingLimit(p)assert(p);return 2 end;function u:IsCombatUnit()return true end;function u:GetDomainType()return 2 end;function u:CanStackAtPlot(p)assert(p);return #p.units<=2 end
 function u:SetScriptData(s)assert(type(s)=='string');self.tag=s end;function u:GetScriptData()return self.tag end;function u:FinishMoves()end;function u:SetActivityType(n)number(n,'activity')end;function u:SetMoves(n)number(n,'moves')end;function u:MaxMoves()return 120 end;function u:IsBusy()return false end;function u:IsFighting()return false end
 function u:CanMoveOrAttackInto(p,a,b)assert(p);number(a,'declare flag');number(b,'destination flag');return true end
 function u:PushMission(m,x,y,f,append,manual)for _,n in ipairs({m,x,y,f,append,manual})do number(n,'mission')end;contractCalls.mission=contractCalls.mission+1;erase(self.p,self);self.p=plots[x];self.p.units[#self.p.units+1]=self end
 function u:Kill(delay,owner)boolean(delay,'kill delay');number(owner,'kill owner');contractCalls.kill=contractCalls.kill+1;erase(self.p,self);units[self.id]=nil end
 p.units[#p.units+1]=u;units[u.id]=u;return u
end
function city:GetID()return 1087 end;function city:GetX()return 0 end;function city:GetY()return 0 end;function city:Plot()return plots[0]end;function city:IsProductionAutomated()return false end;function city:GetRallyPlot()return nil end
function city:CanTrain(id,a,b,c,d)number(id,'CanTrain unit');for _,v in ipairs({a,b,c,d})do number(v,'CanTrain flag')end;contractCalls.train=contractCalls.train+1;return true end
function city:CanConstruct(id,a,b,c,d)number(id,'CanConstruct building');for _,v in ipairs({a,b,c,d})do number(v,'CanConstruct flag')end;contractCalls.construct=contractCalls.construct+1;return id~=1 or not fallback end
function city:GetUnitProductionNeeded(id)number(id,'unit cost');return 20 end;function city:GetOrderQueueLength()return #queueData end
function city:GetOrderFromQueue(i)number(i,'queue index');local q=queueData[i+1];if not q then return -1,0,0,false,false end;return q.kind,q.data1,q.data2,q.save,false end
function city:GetProductionUnit()return queueData[1]and queueData[1].kind==1 and queueData[1].data1 or -1 end
function city:ClearOrderQueue()queueData={};making=0 end
function city:PushOrder(kind,d1,d2,save,pop,append,force)
 for _,v in ipairs({kind,d1,d2,save,force})do number(v,'PushOrder integer')end;boolean(pop,'PushOrder pop');boolean(append,'PushOrder append');assert(pop==false and append==true and force==0);contractCalls.push=contractCalls.push+1
 queueData[#queueData+1]={kind=kind,data1=d1,data2=kind==1 and 0 or d2,save=save~=0};if kind==1 then making=making+1 end
end
function city:SetUnitProduction(id,n)number(id,'production unit');number(n,'production');bank=n*100 end;function city:GetProductionTimes100()return bank end;function city:GetUnitProduction(id)number(id,'unit bank');return math.floor(bank/100)end;function city:GetNumThingsProduced()return things end;function city:GetTotalOverflowProductionTimes100()return 0 end;function city:GetProductionExperience(id)number(id,'production XP enum');return 7 end
function city:CanPlaceUnitHere(id)number(id,'placement unit');for i=0,2 do if #plots[i].units<2 then return true end end;return false end
Players={[0]=player}
GameEvents={CityTrained={Add=function(fn)assert(type(fn)=='function');trained=fn end,Remove=function(fn)assert(fn==trained);trained=nil end}}
function CompleteNormally()
 local s=StackProductionTurnTests.state;assert(city:CanPlaceUnitHere(83));local q=queueData[1];if q.save then queueData[#queueData+1]={kind=q.kind,data1=q.data1,data2=q.data2,save=true};making=making+1 end
 making=making-1;local u=player:InitUnit(83,s.source.x,0);u.xp=600;things=things+1;trained(0,1087,u.id,false,false);bank=0;table.remove(queueData,1)
end
'''
results=[]
for repeat,fallback in [(False,False),(True,True)]:
 lua=LuaRuntime(unpack_returned_tuples=True);lua.execute('assert(loadstring(...))',fixture);lua.execute(fixture);lua.execute(stub);lua.globals().fallback=fallback
 lua.globals().StackProductionTurnTests.Setup(None,'UNIT_WARRIOR',repeat)
 lua.execute('turn=2;bank=bank+500;StackProductionTurnTests.CheckBlocked();StackProductionTurnTests.OpenSlot();StackProductionTurnTests.CheckOpenSlot();turn=3;CompleteNormally();StackProductionTurnTests.CheckCompleted()')
 assert lua.eval('StackProductionTurnTests.failed')==0
 passed=lua.eval('StackProductionTurnTests.passed');lua.execute('StackProductionTurnTests.Cleanup()');assert lua.eval('next(units)')is None and lua.eval('trained')is None
 results.append({'repeat':repeat,'building_fallback':fallback,'fixture_checks':passed,'failures':0,'contract_calls':{k:lua.globals().contractCalls[k]for k in ['train','construct','push','mission','kill']}})
out=root/'work/production-turn-binding-regression';out.mkdir(exist_ok=True);result={'source_sha256':hashlib.sha256(fixture.encode()).hexdigest().upper(),'cases':results,'native_contracts_checked':'City.CanTrain/CanConstruct four optint flags; PushOrder integer save/force and boolean pop/append; Unit.CanMoveOrAttackInto/PushMission integer flags; Unit.Kill boolean delay; enum getters typed','scope':'actual helper executed across ordinary and repeat simulated turn sequences with strict API-contract stubs; no live engine or production-deferral proof'};(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
