-- Manual disposable-game probes; definitions only, never auto-advance a turn.
-- Load after include("StackingTests"). Setup functions replace only this helper's
-- fixture. Execute() sends normal synchronized DoStackMove missions. Call
-- CheckExecuted() separately after animations/network processing finish.
assert(StackTests, "Load StackingTests first")
StackMovementTests = StackMovementTests or { passed=0, failed=0 }
local M,T = StackMovementTests,StackTests
local function log(kind,name,value) print("STACKMOVE|"..kind.."|"..name.."|"..tostring(value)) end
local function check(name,actual,expected)
 local ok=actual==expected
 if ok then M.passed=M.passed+1 else M.failed=M.failed+1 end
 log(ok and "PASS" or "FAIL",name,"actual="..tostring(actual).." expected="..tostring(expected))
 return ok
end
local function unit(rec) return rec and Players[rec.owner]:GetUnitByID(rec.id) end
local function xy(u) return u:GetX()..","..u:GetY() end
local function same(u,p) return u and u:GetX()==p:GetX() and u:GetY()==p:GetY() end
local function index(plan)
 local byID={}
 for _,m in ipairs(plan.Members) do byID[m.UnitID]=m end
 return byID
end
function M.Summary() log("SUMMARY","checks",M.passed.." passed; "..M.failed.." failed") end
function M.Cleanup()
 local s=M.state
 if not s then return end
 for _,r in ipairs(s.units) do local u=unit(r);if u then u:Kill(false,-1) end end
 for _,b in ipairs(s.plots) do
  local p=Map.GetPlotByIndex(b.id)
  p:SetFeatureType(-1);p:SetResourceType(-1,0)
  p:SetPlotType(b.plotType,false,true,false);p:SetTerrainType(b.terrain,false,true)
  p:SetFeatureType(b.feature)
  if b.resource~=-1 then p:SetResourceType(b.resource,b.resourceCount) end
  p:SetOwner(b.owner,-1,false);p:SetRouteType(b.route)
 end
 if #s.plots>0 then Map.RecalculateAreas() end
 for _,b in ipairs(s.techs) do Teams[b.team]:SetHasTech(b.tech,b.before,b.owner,false,false,true) end
 for _,b in ipairs(s.wars) do if not b.before then Teams[b.team]:MakePeace(b.other) end end
 M.state=nil
 log("CLEANUP","fixture","only this helper's units/terrain/tech changes removed; disposable-game diplomacy history may persist")
end
local function begin(kind)
 M.Cleanup()
 local owner,other=T.Players()
 assert(Players[owner]:IsTurnActive(),"Run during the active human turn")
 assert(Game.GetAIAutoPlay()==0,"Stop autoplay first")
 local source,adjacent=T.Plots()
 local s={kind=kind,owner=owner,other=other,source=source,target=adjacent[1],adjacent=adjacent,
  units={},plots={},techs={},wars={},ids={},extras={},turn=Game.GetGameTurn()}
 M.state=s
 log("SETUP",kind,"source="..xy(source).." target="..xy(s.target).." turn="..s.turn)
 return s
end
local function spawn(s,owner,kind,p,member)
 local typeID=assert(GameInfoTypes[kind],"Unknown fixture unit "..kind)
 local u=assert(Players[owner]:InitUnit(typeID,p:GetX(),p:GetY()),"Cannot create "..kind)
 assert(same(u,p),"Fixture unit spawned on a different plot")
 u:SetMoves(u:MaxMoves())
 local rec={owner=owner,id=u:GetID(),kind=kind}
 s.units[#s.units+1]=rec
 if member then s.ids[#s.ids+1]=u:GetID() end
 return u
end
local function setupPair(kind)
 local s=begin(kind)
 local leader=spawn(s,s.owner,"UNIT_WARRIOR",s.source,true)
 local archer=spawn(s,s.owner,"UNIT_ARCHER",s.source,true)
 local worker=spawn(s,s.owner,"UNIT_WORKER",s.source,true)
 s.leader=leader:GetID();s.archer=archer:GetID();s.worker=worker:GetID()
 for _,id in ipairs(s.ids) do
  local u=Players[s.owner]:GetUnitByID(id)
  if u.AssignToSquad then u:AssignToSquad(4) end
 end
 return s,leader,archer,worker
end
local function backupPlot(s,p)
 for _,b in ipairs(s.plots) do if b.id==p:GetPlotIndex() then return end end
 s.plots[#s.plots+1]={id=p:GetPlotIndex(),plotType=p:GetPlotType(),terrain=p:GetTerrainType(),
  feature=p:GetFeatureType(),resource=p:GetResourceType(-1),resourceCount=p:GetNumResource(),owner=p:GetOwner(),route=p:GetRouteType()}
end
function M.Preview(queueLater)
 local s=assert(M.state,"Call a setup function first")
 local leader=assert(Players[s.owner]:GetUnitByID(s.leader),"Leader no longer exists")
 local plan=leader:GetStackMovePreview(s.target,s.source,s.ids,queueLater)
 s.preview=plan
 log("PREVIEW",s.kind,plan.Moving.." move; "..plan.Staying.." stay; protectorStays="..tostring(plan.ProtectorStays)..
  " queueLater="..tostring(queueLater or false))
 for _,m in ipairs(plan.Members) do
  log("MEMBER",m.UnitID,"reason="..m.Reason.." canMove="..tostring(m.CanMove).." uncertain="..tostring(m.Uncertain)..
   " movesAtTarget="..m.MovesLeft.." turns="..tostring(m.Turns))
 end
 return plan,index(plan)
end
local function reachAt(reach,p)
 for _,r in ipairs(reach.Plots) do if r.X==p:GetX() and r.Y==p:GetY() then return r.Arriving end end
 return 0
end
-- A plot exactly `distance` steps from the source, avoiding cities and water.
local function plotAt(s,distance)
 for i=0,Map.GetNumPlots()-1 do
  local p=Map.GetPlotByIndex(i)
  if Map.PlotDistance(p:GetX(),p:GetY(),s.source:GetX(),s.source:GetY())==distance and
     p:GetArea()==s.source:GetArea() and (p:GetOwner()==-1 or p:GetOwner()==s.owner) and
     not p:IsWater() and not p:IsCity() and not p:IsImpassable(Players[s.owner]:GetTeam()) and p:GetNumUnits()==0 then
   return p
  end
 end
end
function M.Ready()
 local s=setupPair("ready")
 local plan,rows=M.Preview()
 check("three same-tile members",#plan.Members,3)
 check("warrior moves",rows[s.leader].CanMove,true)
 check("archer moves",rows[s.archer].CanMove,true)
 check("worker follows separate civilian rules",rows[s.worker].CanMove,true)
 M.Summary();return s
end
function M.Full()
 local s,leader=setupPair("full destination")
 local cap=leader:GetStackingLimit(s.target)
 assert(cap<=20,"This bounded fixture expects capacity <=20")
 for i=1,cap do spawn(s,s.owner,"UNIT_WARRIOR",s.target,false) end
 local plan,rows=M.Preview()
 check("full rejects warrior",rows[s.leader].Reason,"Capacity")
 check("full rejects archer",rows[s.archer].Reason,"Capacity")
 check("full combat stack still permits worker",rows[s.worker].CanMove,true)
 M.Summary();return s
end
function M.Partial()
 local s,leader=setupPair("one combat slot")
 local cap=leader:GetStackingLimit(s.target)
 assert(cap<=20,"This bounded fixture expects capacity <=20")
 for i=1,cap-1 do spawn(s,s.owner,"UNIT_WARRIOR",s.target,false) end
 -- Reverse IDs to verify selected-first priority is independent of incoming order.
 s.ids={s.worker,s.archer,s.leader}
 local plan,rows=M.Preview()
 check("selected unit first",plan.Members[1].UnitID,s.leader)
 check("selected unit reserves only combat slot",rows[s.leader].CanMove,true)
 check("second combat member respects reservation",rows[s.archer].Reason,"Capacity")
 check("civilian needs no combat slot",rows[s.worker].CanMove,true)
 M.Summary();return s
end
function M.Exhausted()
 local s,leader=setupPair("exhausted protector")
 leader:SetMoves(0)
 local plan,rows=M.Preview()
 check("exhausted member stays",rows[s.leader].Reason,"NoMoves")
 check("ranged member can move",rows[s.archer].CanMove,true)
 check("protector warning",plan.ProtectorStays,true)
 M.Summary();return s
end
function M.FrozenIDs()
 local s=setupPair("frozen member IDs")
 local late=spawn(s,s.owner,"UNIT_ARCHER",s.source,false)
 local neighbor=spawn(s,s.owner,"UNIT_SPEARMAN",s.adjacent[2],false)
 s.extras={late:GetID(),neighbor:GetID()}
 local plan,rows=M.Preview()
 check("snapshot keeps original three",#plan.Members,3)
 check("new source arrival excluded",rows[late:GetID()]==nil,true)
 check("neighbor excluded",rows[neighbor:GetID()]==nil,true)
 local worker=Players[s.owner]:GetUnitByID(s.worker)
 worker:SetXY(s.adjacent[3]:GetX(),s.adjacent[3]:GetY())
 plan,rows=M.Preview()
 check("snapshot member leaving source stays",rows[s.worker].Reason,"LeftSource")
 M.Summary();return s
end
function M.Reach()
 local s,leader=setupPair("stack reach")
 local reach=leader:GetStackMoveReach(s.source,s.ids)
 log("REACH",s.kind,reach.Members.." members; "..reach.Eligible.." eligible; "..#reach.Plots.." plots")
 check("reach counts snapshot members",reach.Members,3)
 check("all members can move this turn",reach.Eligible,3)
 check("adjacent target takes every member",reachAt(reach,s.target),3)
 check("source tile is not a destination",reachAt(reach,s.source),0)
 local plan=M.Preview()
 check("reach agrees with preview at target",reachAt(reach,s.target),plan.Moving)
 leader:SetMoves(0)
 reach=leader:GetStackMoveReach(s.source,s.ids)
 check("exhausted member leaves the eligible count",reach.Eligible,2)
 check("remaining members still reach target",reachAt(reach,s.target),2)
 M.Summary();return s
end
function M.Queued()
 local s,leader=setupPair("queued exhausted member")
 leader:SetMoves(0)
 local plan,rows=M.Preview()
 check("exhausted member stays without queueing",rows[s.leader].Reason,"NoMoves")
 plan,rows=M.Preview(true)
 check("exhausted member is queued",rows[s.leader].Reason,"Queued")
 check("queued member is ordered",rows[s.leader].CanMove,true)
 check("queued member arrives in a later turn",(rows[s.leader].Turns or 0)>=1,true)
 check("member with moves arrives now",rows[s.archer].Reason,"Ready")
 check("queueing moves the whole stack",plan.Moving,3)
 check("no protector warning when the protector follows",plan.ProtectorStays,false)
 M.Summary();return s
end
function M.Far(distance)
 local s,leader=setupPair("distant target")
 s.target=assert(plotAt(s,distance or 6),"No empty land plot at that distance")
 local plan,rows=M.Preview()
 check("distant target is a later turn",rows[s.leader].Reason,"LaterTurn")
 check("later-turn estimate reported",(rows[s.leader].Turns or 0)>=1,true)
 plan,rows=M.Preview(true)
 check("distant warrior queued",rows[s.leader].Reason,"Queued")
 check("distant archer queued",rows[s.archer].Reason,"Queued")
 check("every member ordered",plan.Moving,3)
 M.Summary();return s
end
function M.ProbeTerrain()
 local s=assert(M.state)
 local p=s.target;local team=Players[s.owner]:GetTeam()
 log("TERRAIN","target","xy="..xy(p).." mountain="..tostring(p:IsMountain()).." plotType="..p:GetPlotType()..
  " terrain="..p:GetTerrainType().." impassable="..tostring(p:IsImpassable(team)).." route="..p:GetRouteType())
 for _,id in ipairs(s.ids) do
  local u=Players[s.owner]:GetUnitByID(id)
  if u then log("TERRAIN",id,"crossMountains="..tostring(u:CanCrossMountains())..
   " moveImpassable="..tostring(u:CanMoveImpassable()).." allTerrain="..tostring(u:CanMoveAllTerrain())..
   " normalCanEnter="..tostring(u:CanMoveOrAttackInto(p,0,1))) end
 end
end
function M.BlockedTerrain()
 local s=setupPair("mountain target")
 backupPlot(s,s.target)
 s.target:SetFeatureType(-1);s.target:SetResourceType(-1,0)
 s.target:SetPlotType(PlotTypes.PLOT_MOUNTAIN,false,true,false)
 -- VP represents mountains with an actual impassable terrain row; changing
 -- the plot elevation alone leaves a grass mountain passable by design.
 s.target:SetTerrainType(GameInfoTypes.TERRAIN_MOUNTAIN,false,true)
 s.target:SetRouteType(-1)
 Map.RecalculateAreas()
 M.ProbeTerrain()
 check("fixture is mountain",s.target:IsMountain(),true)
 check("fixture is impassable terrain",s.target:IsImpassable(Players[s.owner]:GetTeam()),true)
 local plan,rows=M.Preview()
 check("mountain blocks warrior",rows[s.leader].Reason,"TerrainOrBorders")
 check("mountain blocks archer",rows[s.archer].Reason,"TerrainOrBorders")
 check("mountain blocks worker",rows[s.worker].Reason,"TerrainOrBorders")
 check("mountain moves nobody",plan.Moving,0)
 M.Summary();return s
end
function M.Enemy()
 local s=setupPair("enemy target")
 local teamID,otherTeam=Players[s.owner]:GetTeam(),Players[s.other]:GetTeam()
 local team=Teams[teamID]
 s.wars[#s.wars+1]={team=teamID,other=otherTeam,before=team:IsAtWar(otherTeam)}
 if not team:IsAtWar(otherTeam) then team:DeclareWar(otherTeam,false,s.owner) end
 assert(team:IsAtWar(otherTeam),"Cannot establish disposable enemy fixture")
 local enemy=spawn(s,s.other,"UNIT_WARRIOR",s.target,false)
 s.enemy=enemy:GetID();s.enemyHP=enemy:GetCurrHitPoints()
 local plan,rows=M.Preview()
 check("enemy rejects all moves",plan.Moving,0)
 for _,id in ipairs(s.ids) do check("enemy reason "..id,rows[id].Reason,"Enemy") end
 M.Summary();return s
end
function M.NeutralBorder(other)
 local s=setupPair("neutral closed border")
 local teamID=Players[s.owner]:GetTeam()
 if not other then
  for i=0,GameDefines.MAX_MAJOR_CIVS-1 do
   local p=Players[i]
   if p and p:IsAlive() and p:GetTeam()~=teamID and not Teams[teamID]:IsAtWar(p:GetTeam()) and
      not Teams[p:GetTeam()]:IsAllowsOpenBordersToTeam(teamID) then other=i;break end
  end
 end
 assert(other and Players[other]:IsAlive(),"Need a living neutral civilization with closed borders; start a fresh disposable game")
 local otherTeam=Players[other]:GetTeam()
 assert(not Teams[teamID]:IsAtWar(otherTeam),"Choose a neutral civilization")
 assert(not Teams[otherTeam]:IsAllowsOpenBordersToTeam(teamID),"Choose closed borders")
 backupPlot(s,s.target);s.target:SetOwner(other,-1,false)
 s.neutralTeam=otherTeam
 local plan,rows=M.Preview()
 check("closed border rejects warrior",rows[s.leader].Reason,"TerrainOrBorders")
 check("closed border rejects archer",rows[s.archer].Reason,"TerrainOrBorders")
 check("preview did not declare war",Teams[teamID]:IsAtWar(otherTeam),false)
 -- Workers may cross under VP's separate civilian rules; do not falsely require them to stay.
 M.Summary();return s
end
function M.ForeignStack(other)
 local s=setupPair("foreign combat occupant")
 local teamID=Players[s.owner]:GetTeam()
 if not other then
  for i=0,GameDefines.MAX_MAJOR_CIVS-1 do
   local p=Players[i]
   if i~=s.owner and p and p:IsAlive() and not Teams[teamID]:IsAtWar(p:GetTeam()) then other=i;break end
  end
 end
 assert(other and other~=s.owner and not Teams[teamID]:IsAtWar(Players[other]:GetTeam()),
  "Need a living neutral/teammate player; do not change war solely for this fixture")
 spawn(s,other,"UNIT_WARRIOR",s.target,false)
 local leader=Players[s.owner]:GetUnitByID(s.leader)
 check("shared API rejects foreign combat stacking",leader:CanStackAtPlot(s.target),false)
 local plan,rows=M.Preview()
 check("group preview also rejects foreign combat stacking",rows[s.leader].CanMove,false)
 check("ranged group member also respects foreign stack",rows[s.archer].CanMove,false)
 if leader:GetStackingLimit(s.target)>1 then check("foreign restriction has a distinct reason",rows[s.leader].Reason,"ForeignStack") end
 M.Summary();return s
end
function M.Air()
 local s=begin("air exclusion")
 local city=Players[s.owner]:GetCapitalCity()
 assert(city,"Need an existing player city for a legal bomber base")
 s.source=city:Plot()
 local target
 for d=0,5 do
  local p=Map.PlotDirection(s.source:GetX(),s.source:GetY(),d)
  if p and not p:IsWater() and not p:IsMountain() and not p:IsCity() and p:GetNumUnits()==0 then target=p;break end
 end
 s.target=assert(target,"No empty land tile beside player capital")
 local leader=spawn(s,s.owner,"UNIT_WARRIOR",s.source,true)
 local bomber=spawn(s,s.owner,"UNIT_BOMBER",s.source,true)
 s.leader=leader:GetID();s.air=bomber:GetID()
 local plan,rows=M.Preview()
 check("bomber stays as aircraft",rows[s.air].Reason,"Aircraft")
 check("bomber receives no ordinary move",rows[s.air].CanMove,false)
 M.Summary();return s
end
function M.Cargo()
 local s=begin("carrier and cargo")
 local source,target
 local team=Players[s.owner]:GetTeam()
 local function legalCoast(p)
  return p and p:IsWater() and p:GetTerrainType()==GameInfoTypes.TERRAIN_COAST and
   p:GetFeatureType()==-1 and not p:IsImpassable(team) and not p:IsCity() and
   p:GetOwner()==-1 and p:GetNumUnits()==0
 end
 for i=0,Map.GetNumPlots()-1 do
  local p=Map.GetPlotByIndex(i)
  if legalCoast(p) then
   for d=0,5 do
    local n=Map.PlotDirection(p:GetX(),p:GetY(),d)
    if legalCoast(n) then source,target=p,n;break end
   end
  end
  if source then break end
 end
 s.source=assert(source,"Need empty non-ice coastal pair; no ocean/embark rules are bypassed");s.target=target
 local carrier=spawn(s,s.owner,"UNIT_CARRIER",source,true)
 local fighter=spawn(s,s.owner,"UNIT_FIGHTER",source,true)
 s.leader=carrier:GetID();s.cargo=fighter:GetID()
 log("FIXTURE","carrier route","source="..xy(source).." destination="..xy(target)..
  " normalCanEnter="..tostring(carrier:CanMoveOrAttackInto(target,0,1)))
 assert(carrier:CanMoveOrAttackInto(target,0,1),"Carrier fixture has no legal normal movement; choose another coastal pair")
 check("fighter loads using native carrier rules",fighter:IsCargo(),true)
 assert(fighter:IsCargo(),"Cargo fixture not established; no cargo claim is valid")
 local plan,rows=M.Preview()
 check("cargo excluded from independent move",rows[s.cargo].Reason,"Cargo")
 check("cargo gets no independent mission",rows[s.cargo].CanMove,false)
 check("carrier can move",rows[s.leader].CanMove,true)
 log("NOTE","cargo","Execute should move cargo WITH carrier despite no passenger mission; report must not say passenger stayed")
 M.Summary();return s
end
function M.Execute(queueLater)
 local s=assert(M.state,"Set up a scenario first")
 s.queueLater=queueLater
 assert(Game.GetGameTurn()==s.turn,"Fixture changed turns; set it up again")
 assert(Players[s.owner]:IsTurnActive(),"Owner must be active")
 local leader=assert(Players[s.owner]:GetUnitByID(s.leader))
 s.before={}
 for _,rec in ipairs(s.units) do
  local u=unit(rec)
  if u then
   local carrier=u:GetTransportUnit()
   s.before[rec.owner..":"..rec.id]={x=u:GetX(),y=u:GetY(),hp=u:GetCurrHitPoints(),squad=u:GetSquadNumber(),
    transport=carrier and carrier:GetID() or -1}
  end
 end
 s.executed=leader:DoStackMove(s.target,s.source,s.ids,queueLater)
 s.executedRows=index(s.executed)
 local sent=0
 for _,m in ipairs(s.executed.Members) do
  if m.Sent then sent=sent+1 end
  check("only eligible members sent "..m.UnitID,not m.Sent or m.CanMove,true)
 end
 log("EXECUTED",s.kind,"sent="..sent.."; wait for animations, then CheckExecuted()")
 if s.neutralTeam then check("move did not declare war",Teams[Players[s.owner]:GetTeam()]:IsAtWar(s.neutralTeam),false) end
 return s.executed
end
function M.CheckExecuted()
 local s=assert(M.state,"No fixture")
 assert(s.executed,"Call Execute first")
 for _,m in ipairs(s.executed.Members) do
  local u=Players[s.owner]:GetUnitByID(m.UnitID)
  -- Later-turn orders keep their mission; only wait for their current animation.
  local queued=m.Reason=="Queued"
  if u and (u:IsBusy() or (not queued and u:GetActivityType()==ActivityTypes.ACTIVITY_MISSION)) then
   log("WAIT",s.kind,"unit "..m.UnitID.." still executing; call again later");return false
  end
 end
 for _,rec in ipairs(s.units) do
  local u=unit(rec);local before=s.before[rec.owner..":"..rec.id]
  check("unit survives "..rec.id,u~=nil,true)
  if u and before then
   local m=rec.owner==s.owner and s.executedRows[rec.id] or nil
   local carrierMove=before.transport>=0 and s.executedRows[before.transport]
   if m and m.Sent and m.Reason=="Queued" then
    check("queued member keeps its move order "..rec.id,u:GetActivityType()==ActivityTypes.ACTIVITY_MISSION or same(u,s.target),true)
   elseif m and m.Sent then
    check("sent member arrives "..rec.id,same(u,s.target),true)
   elseif carrierMove and carrierMove.Sent then
    check("cargo follows native transport "..rec.id,same(u,s.target),true)
   else
    check("unsent/nonmember stays "..rec.id,u:GetX()==before.x and u:GetY()==before.y,true)
   end
   check("squad membership preserved "..rec.id,u:GetSquadNumber(),before.squad)
   check("movement did not attack/damage "..rec.id,u:GetCurrHitPoints(),before.hp)
  end
 end
 if s.neutralTeam then check("after execution still at peace",Teams[Players[s.owner]:GetTeam()]:IsAtWar(s.neutralTeam),false) end
 M.Summary();return true
end
function M.Visual(count,combatOnly)
 local s=begin("visual roster "..tostring(count or 10))
 count=count or 10
 assert(count>=2 and count<=20,"Use a bounded 2..20 unit visual fixture")
 local leader=spawn(s,s.owner,"UNIT_WARRIOR",s.source,true);s.leader=leader:GetID()
 local teamID=Players[s.owner]:GetTeam();local team=Teams[teamID]
 for row in GameInfo.Stacking_Technologies() do
  local id=GameInfoTypes[row.TechType]
  if id and not team:IsHasTech(id) then
   s.techs[#s.techs+1]={team=teamID,owner=s.owner,tech=id,before=false}
   team:SetHasTech(id,true,s.owner,false,false,true)
  end
 end
 local cap=leader:GetStackingLimit(s.source)
 if combatOnly then assert(cap>=count,"For ten combat units set MaximumCapacity/BaseCapacity XML to10 and restart first") end
 local combatCount=combatOnly and count or math.min(count-1,cap)
 local kinds={"UNIT_ARCHER","UNIT_SPEARMAN","UNIT_HORSEMAN","UNIT_CATAPULT","UNIT_WARRIOR"}
 for i=2,count do
  local kind=i<=combatCount and kinds[1+((i-2)%#kinds)] or "UNIT_WORKER"
  local u=spawn(s,s.owner,kind,s.source,true)
  u:SetDamage(math.min(u:GetMaxHitPoints()-1,(i-1)*5))
  if i%3==0 then u:SetMoves(0) elseif i%3==1 then u:SetMoves(math.floor(u:MaxMoves()/2)) end
 end
 log("VISUAL","fixture",count.." units, "..combatCount.." combat (capacity "..cap.."); source="..xy(s.source))
 log("VISUAL","checks","select/cycle every row; inspect HP/moves/roles; count badge; collapse/expand; move preview; 1534x862 and1920x1080")
 M.Select();return s
end
function M.Select()
 local s=assert(M.state)
 Events.SerialEventUnitFlagSelected(s.owner,s.leader)
 if UI and UI.LookAtSelectionPlot then UI.LookAtSelectionPlot() end
end
log("LOADED","commands","Ready/Full/Partial/Exhausted/FrozenIDs/BlockedTerrain/Enemy/NeutralBorder/ForeignStack/Air/Cargo/Reach/Queued/Far/Visual; Execute([queueLater]) then CheckExecuted; Cleanup")
