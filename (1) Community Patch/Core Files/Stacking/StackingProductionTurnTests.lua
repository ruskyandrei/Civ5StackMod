-- Manual actual city-production deferral. Definitions only; never advances a turn.
-- Setup -> parent UI EndTurn -> CheckBlocked -> OpenSlot -> CheckOpenSlot ->
-- parent UI EndTurn -> CheckCompleted. Use only a disposable game.
StackProductionTurnTests=StackProductionTurnTests or {passed=0,failed=0}
local P=StackProductionTurnTests
local TAG="STACKPRODTURN1|"
local function log(k,v) print("STACKPRODTURN|"..k.."|"..tostring(v)) end
local function check(k,a,e)
 local ok=a==e;P[ok and "passed" or "failed"]=P[ok and "passed" or "failed"]+1
 log(ok and "PASS" or "FAIL",k.." actual="..tostring(a).." expected="..tostring(e));return ok
end
local function requireThat(k,a,e) assert(check(k,a,e),"precondition: "..k) end
local function unit(s,id) return Players[s.owner]:GetUnitByID(id) end
local function city(s) return assert(Players[s.owner]:GetCityByID(s.city),"Fixture city changed ownership/disappeared") end
local function at(u,p) return u and u:GetX()==p:GetX() and u:GetY()==p:GetY() or false end
local function distance(a,b) return Map.PlotDistance(a:GetX(),a:GetY(),b:GetX(),b:GetY()) end
local function current()
 local s=assert(P.state,"Setup first");assert(Game.GetActivePlayer()==s.owner and Players[s.owner]:IsTurnActive(),"Wait for the next human turn")
 assert(Game.GetAIAutoPlay()==0,"Do not autoplay this fixture");return s,city(s)
end
local function queue(c)
 local out={}
 for i=0,c:GetOrderQueueLength()-1 do
  local kind,data1,data2,save,rush=c:GetOrderFromQueue(i)
  out[#out+1]={kind=kind,data1=data1,data2=data2,save=save,rush=rush}
 end
 return out
end
local function queueKey(q)
 local out={};for _,r in ipairs(q) do out[#out+1]=table.concat({r.kind,r.data1,r.data2,tostring(r.save),tostring(r.rush)},":") end
 return table.concat(out,"|")
end
local function snapshots(player)
 local out={};for u in player:Units() do out[u:GetID()]={type=u:GetUnitType(),x=u:GetX(),y=u:GetY(),hp=u:GetCurrHitPoints()} end;return out
end
local function natural(p)
 return table.concat({p:GetPlotType(),p:GetTerrainType(),p:GetFeatureType(),p:GetResourceType(-1),p:GetNumResource(),p:GetImprovementType(),p:GetRouteType()},":")
end
local function legalLand(p,owner)
 if not p or p:IsWater() or p:IsImpassable(Players[owner]:GetTeam()) then return false end
 return p:GetOwner()==-1 or p:GetOwner()==owner
end
local function verifyBlockers(s)
 local ok=true
 for _,r in ipairs(s.units) do
  local u=unit(s,r.id);local expected=r.id==s.mover and s.open and s.exit or Map.GetPlotByIndex(r.plot)
  if not u or not at(u,expected) or u:GetCurrHitPoints()~=r.hp then ok=false;log("BLOCKER_CHANGED",r.id) end
  if u then check("blocker capacity "..r.id,u:CanStackAtPlot(u:GetPlot()),true) end
 end
 check("all tracked blockers survive in expected locations",ok,true)
 local same=true;for _,r in ipairs(s.terrain) do if natural(Map.GetPlotByIndex(r.id))~=r.value then same=false;log("TERRAIN_CHANGED",r.id) end end
 check("natural terrain unchanged",same,true)
end
local function trainEvents(s)
 local out={};for _,e in ipairs(s.events) do if e.unitType==s.unitType then out[#out+1]=e end end;return out
end
local function logState(label,s,c)
 local player=Players[s.owner]
 log(label,"turn="..Game.GetGameTurn().." queue="..queueKey(queue(c)).." headProduction100="..c:GetProductionTimes100().." unitBank="..c:GetUnitProduction(s.unitType).." thingsProduced="..c:GetNumThingsProduced().." making="..player:GetUnitClassMaking(s.unitClass).." gold100="..player:GetGoldTimes100().." overflow100="..c:GetTotalOverflowProductionTimes100().." events="..#trainEvents(s))
end
function P.Plan(cityID,unitType,repeatOrder)
 local owner=Game.GetActivePlayer();assert(owner>=0 and Players[owner]:IsTurnActive(),"Use the active human turn")
 assert(Game.GetAIAutoPlay()==0 and not Game.IsGameMultiPlayer(),"Use a disposable single-player game without autoplay")
 local player=Players[owner];local c=cityID and player:GetCityByID(cityID) or player:GetCapitalCity()
 assert(c,"Found a normal capital before testing; this helper never creates a city")
 assert(not c:IsProductionAutomated(),"Disable production automation for the selected test city")
 assert(not c:GetRallyPlot(),"Use a city without a rally destination")
 local id=type(unitType)=="number" and unitType or GameInfoTypes[unitType or "UNIT_WARRIOR"]
 local info=id and GameInfo.Units[id]
 assert(info and info.Domain=="DOMAIN_LAND" and info.Combat>0 and tonumber(info.NumberStackingUnits or 0)<=0,"Use an ordinary land combat unit")
 -- CivLuaCity uses luaL_optint for these flags, not Lua booleans.
 assert(c:CanTrain(id,0,0,0,0),"Choose a currently trainable unit")
 for other in player:Cities() do if other:GetID()~=c:GetID() then assert(other:GetProductionUnit()~=id,"Pause same-unit production in other cities for this controlled test") end end
 local sentinel
 local monument=GameInfoTypes.BUILDING_MONUMENT
 if monument and c:CanConstruct(monument,0,0,0,0) then sentinel=monument end
 if not sentinel then for row in GameInfo.Buildings() do
  local class=GameInfo.BuildingClasses[row.BuildingClass]
  if row.Cost>0 and class and (class.MaxGlobalInstances or -1)<0 and (class.MaxPlayerInstances or -1)<0 and c:CanConstruct(row.ID,0,0,0,0) then sentinel=row.ID;break end
 end end
 assert(sentinel,"Need a legal ordinary building after the unit in the queue")
 local plots,seen={},{}
 for d=-1,5 do
  local p=d==-1 and c:Plot() or Map.PlotDirection(c:GetX(),c:GetY(),d)
  if p and not seen[p:GetPlotIndex()] then
   seen[p:GetPlotIndex()]=true;assert(p:GetNumUnits()==0,"Move existing units out of the city and its adjacent ring first")
   if not p:IsWater() and not p:IsImpassable(player:GetTeam()) then
    assert(legalLand(p,owner),"Use a wholly own/unowned ring")
    plots[#plots+1]=p
   end
  end
 end
 assert(#plots>=2 and plots[1]:GetPlotIndex()==c:Plot():GetPlotIndex(),"Need usable city and neighboring land")
 local source,exitPlot
 for i=2,#plots do for d=0,5 do
  local p=Map.PlotDirection(plots[i]:GetX(),plots[i]:GetY(),d)
  if legalLand(p,owner) and not p:IsCity() and p:GetNumUnits()==0 and distance(c:Plot(),p)==2 then source,exitPlot=plots[i],p;break end
 end;if source then break end end
 assert(source,"Need an empty natural outward step beyond production radius")
 for dx=-3,3 do for dy=-3,3 do
  local p=Map.PlotXYWithRangeCheck(c:GetX(),c:GetY(),dx,dy,3)
  if p then for i=0,p:GetNumUnits()-1 do local u=p:GetUnit(i)
   assert(not u or u:GetOwner()==owner,"Use a quiet site without nearby foreign units")
  end end
 end end
 local need=c:GetUnitProductionNeeded(id);assert(need>0,"Unit must have a positive production cost")
 log("PLAN","city="..c:GetID().." unit="..id.." cost="..need.." legalPlots="..#plots.." release="..source:GetX()..","..source:GetY().." exit="..exitPlot:GetX()..","..exitPlot:GetY().." repeat="..tostring(not not repeatOrder))
 return {owner=owner,city=c:GetID(),unitType=id,unitClass=assert(GameInfoTypes[info.Class]),sentinel=sentinel,plots=plots,source=source,exit=exitPlot,needed=need,repeatOrder=not not repeatOrder}
end
function P.Setup(cityID,unitType,repeatOrder)
 assert(not P.state,"Clean up the prior fixture first")
 local s=P.Plan(cityID,unitType,repeatOrder);P.state=s;P.serial=(P.serial or 0)+1;s.id=Game.GetGameTurn().."-"..P.serial
 local c=city(s);local player=Players[s.owner];s.units={};s.events={};s.terrain={};s.originalUnits=snapshots(player);s.originalQueue=queue(c);s.turn=Game.GetGameTurn()
 for _,p in ipairs(s.plots) do s.terrain[#s.terrain+1]={id=p:GetPlotIndex(),value=natural(p)} end
 s.terrain[#s.terrain+1]={id=s.exit:GetPlotIndex(),value=natural(s.exit)}
 for _,p in ipairs(s.plots) do
  local cap
  repeat
   local u=assert(player:InitUnit(s.unitType,p:GetX(),p:GetY()));assert(at(u,p),"Unexpected spawn relocation")
   u:SetScriptData(TAG..s.id);local r={id=u:GetID(),plot=p:GetPlotIndex(),hp=u:GetCurrHitPoints()};s.units[#s.units+1]=r
   if not s.spawnXP then s.spawnXP=u:GetExperienceTimes100() end
   cap=cap or u:GetStackingLimit(p);assert(cap>=2 and cap<=10,"Use capacity2..10")
   local occupied=0;for i=0,p:GetNumUnits()-1 do local x=p:GetUnit(i);if x and x:IsCombatUnit() and x:GetDomainType()==DomainTypes.DOMAIN_LAND then occupied=occupied+1 end end
   requireThat("created blocker remains legal "..u:GetID(),u:CanStackAtPlot(p),true)
   u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP)
   if p:GetPlotIndex()==s.source:GetPlotIndex() then s.mover=u:GetID() end
  until occupied>=cap
 end
 -- Existing VP supply/resource rules remain authoritative; don't confuse a
 -- queue eligibility rejection with the new space deferral being tested.
 assert(c:CanTrain(s.unitType,1,0,0,0),"Supply/resources now prohibit training: cleanup and use a lower-capacity/coastal site")
 local capPenalty=tonumber(GameDefines.MAX_UNIT_SUPPLY_PRODMOD or 0);local perUnit=tonumber(GameDefines.PRODUCTION_PENALTY_PER_UNIT_OVER_SUPPLY or 0)
 if capPenalty>0 and perUnit>0 then assert(player:GetNumUnitsOutOfSupply()+2<math.floor(capPenalty/perUnit),"Need supply margin for the completed unit; cleanup and choose a smaller natural ring/lower cap") end
 assert(player:GetGold()>=math.max(50,-player:CalculateGoldRate()*3),"Need enough gold to avoid unrelated debt disbanding")
 c:ClearOrderQueue()
 -- PushOrder save/force are integers; pop/append use lua_toboolean.
 c:PushOrder(OrderTypes.ORDER_TRAIN,s.unitType,-1,s.repeatOrder and 1 or 0,false,true,0)
 c:PushOrder(OrderTypes.ORDER_CONSTRUCT,s.sentinel,-1,0,false,true,0)
 c:SetUnitProduction(s.unitType,s.needed)
 requireThat("seeded real train order",c:GetProductionUnit(),s.unitType)
 requireThat("completed production threshold",c:GetProductionTimes100(),s.needed*100)
 requireThat("all city/ring slots blocked",c:CanPlaceUnitHere(s.unitType),false)
 s.queue=queue(c);s.making=player:GetUnitClassMaking(s.unitClass);s.things=c:GetNumThingsProduced();s.stock=c:GetProductionTimes100();s.allBefore=snapshots(player)
 assert(GameEvents.CityTrained and GameEvents.CityTrained.Add,"CityTrained hook unavailable")
 P.handler=function(owner,cityID,newID,bGold,bFaith)
  if P.state~=s or owner~=s.owner or cityID~=s.city then return end
  local u=unit(s,newID);local e={id=newID,unitType=u and u:GetUnitType()or-1,gold=bGold,faith=bFaith,turn=Game.GetGameTurn(),xp=u and u:GetExperienceTimes100()or-1,productionXP=c:GetProductionExperience(s.unitType)}
  if u and e.unitType==s.unitType and not s.allBefore[newID] then u:SetScriptData(TAG..s.id) end
  s.events[#s.events+1]=e;log("CITY_TRAINED","id="..newID.." type="..e.unitType.." turn="..e.turn.." gold="..tostring(bGold).." faith="..tostring(bFaith).." xp100="..e.xp)
 end
 GameEvents.CityTrained.Add(P.handler)
 logState("READY_BLOCKED",s,c)
 log("NEXT","Use the normal UI EndTurn once; after the next human turn call CheckBlocked(). Helper never advances turns.")
end
function P.CheckBlocked()
 local s,c=current();assert(Game.GetGameTurn()>s.turn,"Use normal UI EndTurn first")
 requireThat("still eligible to train",c:CanTrain(s.unitType,1,0,0,0),true)
 check("blocked queue preserved exactly",queueKey(queue(c)),queueKey(s.queue))
 check("blocked making counter unchanged",Players[s.owner]:GetUnitClassMaking(s.unitClass),s.making)
 check("blocked completion count unchanged",c:GetNumThingsProduced(),s.things)
 check("blocked unit bank retained",c:GetProductionTimes100()>=s.stock,true)
 check("no CityTrained reward event while blocked",#trainEvents(s),0)
 local added=0;for u in Players[s.owner]:Units() do if not s.allBefore[u:GetID()] and u:GetUnitType()==s.unitType then added=added+1 end end
 check("no completed unit created while blocked",added,0)
 requireThat("placement remains blocked",c:CanPlaceUnitHere(s.unitType),false)
 verifyBlockers(s);s.blockedTurn=Game.GetGameTurn();s.blockedStock=c:GetProductionTimes100();s.blocked=true
 logState("BLOCKED_VERIFIED",s,c);P.Summary()
end
function P.OpenSlot()
 local s,c=current();assert(s.blocked and not s.open,"CheckBlocked before opening a slot")
 assert(s.exit:GetNumUnits()==0,"Outward destination acquired an occupant")
 local u=assert(unit(s,s.mover));assert(not u:IsBusy() and not u:IsFighting(),"Wait for unit")
 u:SetActivityType(ActivityTypes.ACTIVITY_AWAKE);u:SetMoves(u:MaxMoves())
 requireThat("outward step legal",u:CanMoveOrAttackInto(s.exit,0,1),true)
 u:PushMission(MissionTypes.MISSION_MOVE_TO,s.exit:GetX(),s.exit:GetY(),0,0,1)
 log("MOVE","Wait for ordinary one-tile movement, then CheckOpenSlot()")
end
function P.CheckOpenSlot()
 local s,c=current();local u=assert(unit(s,s.mover))
 if u:IsBusy() or u:IsFighting() or not at(u,s.exit) then log("WAIT","Outward move not complete; retry CheckOpenSlot");return false end
 u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP);s.open=true;s.openTurn=Game.GetGameTurn()
 requireThat("one legal production slot now available",c:CanPlaceUnitHere(s.unitType),true)
 check("opening slot does not itself complete production",#trainEvents(s),0)
 check("queue still retained before next turn",queueKey(queue(c)),queueKey(s.queue))
 verifyBlockers(s);logState("READY_COMPLETION",s,c)
 log("NEXT","Use normal UI EndTurn once, then CheckCompleted() at the next human turn")
 return true
end
function P.CheckCompleted()
 local s,c=current();assert(s.open and Game.GetGameTurn()>s.openTurn,"Open slot and use normal UI EndTurn first")
 local events=trainEvents(s);check("exactly one normal CityTrained event",#events,1)
 local made=0;local produced
 for u in Players[s.owner]:Units() do if not s.allBefore[u:GetID()] and u:GetUnitType()==s.unitType then made=made+1;produced=u end end
 check("exactly one completed unit exists",made,1)
 check("completion counter increases once",c:GetNumThingsProduced(),s.things+1)
 check("completed old unit bank consumed normally",c:GetUnitProduction(s.unitType),0)
 check("making counter after completion",Players[s.owner]:GetUnitClassMaking(s.unitClass),s.making-(s.repeatOrder and 0 or 1))
 local q=queue(c);check("queue length after completion",#q,s.repeatOrder and 2 or 1)
 check("queue advances to sentinel building",q[1]and q[1].data1 or-1,s.sentinel)
 check("sentinel order type",q[1]and q[1].kind or-1,OrderTypes.ORDER_CONSTRUCT)
 if s.repeatOrder then check("repeat unit inserted exactly once",q[2]and q[2].data1 or-1,s.unitType);check("repeat flag retained",q[2]and q[2].save or false,true) end
 if #events==1 then
  check("trained event is not gold purchase",events[1].gold,false);check("trained event is not faith purchase",events[1].faith,false)
  if produced then check("event names the created unit",events[1].id,produced:GetID()) end
  local speed=assert(GameInfo.GameSpeeds[Game.GetGameSpeedType()].ExperiencePercent,"Missing game-speed XP percent")
  check("normal production XP awarded once",events[1].xp,s.spawnXP+events[1].productionXP*speed)
 end
 if produced then
  check("unit appears in sole released ring slot",at(produced,s.source),true)
  check("completed unit capacity legal",produced:CanStackAtPlot(produced:GetPlot()),true)
  produced:SetScriptData(TAG..s.id);s.produced=produced:GetID()
 end
 verifyBlockers(s);s.complete=true;logState("COMPLETE_VERIFIED",s,c);P.Summary()
 return P.failed==0
end
function P.Summary() log("SUMMARY",P.passed.." passed; "..P.failed.." failed") end
function P.Cleanup()
 local s=P.state;if not s then return end
 if P.handler then GameEvents.CityTrained.Remove(P.handler);P.handler=nil end
 for _,r in ipairs(s.units) do local u=unit(s,r.id);assert(not u or (not u:IsBusy() and not u:IsFighting()),"Wait for fixture units") end
 for _,r in ipairs(s.units) do local u=unit(s,r.id);if u and u:GetScriptData()==TAG..s.id then u:Kill(false,-1) end end
 for _,e in ipairs(s.events) do local made=unit(s,e.id);if made and made:GetScriptData()==TAG..s.id then made:Kill(false,-1) end end
 P.state=nil;log("CLEANUP","Tracked units/hook removed. City queue, production, economy and turns remain changed; discard this disposable world without saving.")
end
function P.Try(name,...)
 local ok,result=pcall(assert(P[name],"Unknown fixture function"),...);if not ok then log("ERROR",name..": "..tostring(result)) end;return ok,result
end
