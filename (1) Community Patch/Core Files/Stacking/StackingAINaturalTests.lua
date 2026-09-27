-- Natural-terrain, disposable-game benchmarks. Loading defines functions only.
-- No terrain, river, resource, improvement, technology or city edits.
StackAINaturalTests = StackAINaturalTests or {}
local N=StackAINaturalTests
local TAG="STACKNAT1|"
local F={"id","kind","human","ai","turn","center","target","source","alternate","guardMoves","focus","pairs","enemies","expected","role","initialPlot","initialHP","initialMoves","type","initialID"}
local function log(k,v) print("STACKNAT|"..k.."|"..tostring(v)) end
local function plot(i) return i and i>=0 and Map.GetPlotByIndex(i) or nil end
local function index(p) return p:GetPlotIndex() end
local function xy(p) return p:GetX()..","..p:GetY() end
local function dist(a,b) return Map.PlotDistance(a:GetX(),a:GetY(),b:GetX(),b:GetY()) end
local function decode(raw)
 if type(raw)~="string" or string.sub(raw,1,#TAG)~=TAG then return nil end
 local values={};for v in string.gmatch(string.sub(raw,#TAG+1),"([^|]+)") do values[#values+1]=v end
 if #values~=#F then return nil end
 local d={}
 for i,k in ipairs(F) do d[k]=(k=="id" or k=="kind" or k=="role") and values[i] or tonumber(values[i]);if d[k]==nil then return nil end end
 return d
end
local function encode(d)
 local v={};for _,k in ipairs(F) do v[#v+1]=tostring(assert(d[k],"missing metadata "..k)) end
 return TAG..table.concat(v,"|")
end
local function allTagged()
 local records={}
 for player=0,GameDefines.MAX_MAJOR_CIVS-1 do
  if Players[player] then for u in Players[player]:Units() do
   local d=decode(u:GetScriptData());if d then records[#records+1]={u=u,d=d} end
  end end
 end
 return records
end
local function players()
 local human=Game.GetActivePlayer();assert(human>=0,"load a game")
 for ai=0,GameDefines.MAX_MAJOR_CIVS-1 do
  if ai~=human and Players[ai]:IsAlive() and Players[ai]:GetTeam()~=Players[human]:GetTeam() then return human,ai end
 end
 error("need two independent living major players")
end
local function ring(center,radius)
 local list,seen={},{}
 for dx=-radius,radius do for dy=-radius,radius do
  local p=Map.PlotXYWithRangeCheck(center:GetX(),center:GetY(),dx,dy,radius)
  if p and not seen[index(p)] then seen[index(p)]=true;list[#list+1]=p end
 end end
 table.sort(list,function(a,b)return index(a)<index(b)end);return list
end
local function unused(p)
 if not p or p:IsCity() or p:GetOwner()~=-1 or p:GetNumUnits()~=0 or p:GetImprovementType()~=-1 then return false end
 local f=GameInfo.Features[p:GetFeatureType()]
 return not(f and (f.NaturalWonder==true or f.NaturalWonder==1))
end
local function usable(p,human,ai)
 return unused(p) and not p:IsWater() and not p:IsMountain() and p:GetRouteType()==-1 and
  not p:IsImpassable(Players[human]:GetTeam()) and not p:IsImpassable(Players[ai]:GetTeam())
end
local function guardClear(center,radius)
 for _,p in ipairs(ring(center,radius)) do if not unused(p) then return false end end
 return true
end
local function findFormation(human,ai)
 for i=0,Map.GetNumPlots()-1 do
  local r=plot(i)
  if usable(r,human,ai) and guardClear(r,2) then
   for pd=0,5 do
    local source=Map.PlotDirection(r:GetX(),r:GetY(),pd)
    if usable(source,human,ai) then for td=0,5 do
     local target=Map.PlotDirection(r:GetX(),r:GetY(),td)
     if usable(target,human,ai) and dist(source,target)==2 then for ad=0,5 do
      local alternate=Map.PlotDirection(r:GetX(),r:GetY(),ad)
      if usable(alternate,human,ai) and index(alternate)~=index(source) and index(alternate)~=index(target) and
       dist(source,alternate)==1 and dist(target,alternate)==1 and
       alternate:GetTerrainType()==r:GetTerrainType() and alternate:GetFeatureType()==r:GetFeatureType() and alternate:IsHills()==r:IsHills() then
       return r,source,target,alternate
      end
     end end
    end end
   end
  end
 end
 error("No empty natural formation site with comparable adjacent choices; use another map or inspect Plan()")
end
local function connected(center,human,ai,radius)
 local result,queue,seen={},{center},{[index(center)]=true};local pos=1
 while pos<=#queue do
  local p=queue[pos];pos=pos+1;result[#result+1]=p
  for d=0,5 do
   local q=Map.PlotDirection(p:GetX(),p:GetY(),d)
   if q and not seen[index(q)] and dist(center,q)<=radius and usable(q,human,ai) then seen[index(q)]=true;queue[#queue+1]=q end
  end
 end
 table.sort(result,function(a,b)local da,db=dist(a,center),dist(b,center);return da==db and index(a)<index(b) or da<db end)
 return result
end
local function findDense(human,ai,needed)
 for i=0,Map.GetNumPlots()-1 do
  local c=plot(i)
  if usable(c,human,ai) and guardClear(c,4) then
   local sites=connected(c,human,ai,3)
   if #sites>=needed then return c,sites end
  end
 end
 error("No unused connected natural land patch for dense fixture; use a larger land map, not terrain edits")
end
function N.Plan(kind,options)
 options=options or {};local human,ai=players()
 if kind=="formation" then
  local r,p,t,a=findFormation(human,ai)
  log("plan","formation human="..human.." ai="..ai.." R="..xy(r).." P="..xy(p).." enemy="..xy(t).." alternative="..xy(a))
 else
  local pairs=math.floor(options.pairs or 8);local enemies=math.floor(options.enemies or 6)
  assert(pairs>=1 and pairs<=12 and enemies>=1 and enemies<=12,"benchmark size outside helper bounds")
  local c,sites=findDense(human,ai,pairs+math.ceil(enemies/2))
  log("plan","dense human="..human.." ai="..ai.." center="..xy(c).." connectedSites="..#sites.." AI="..(pairs*2).." enemies="..enemies)
 end
end
local function current(rec)
 local u=Players[rec.owner]:GetUnitByID(rec.id)
 if not u then return nil end
 local d=decode(u:GetScriptData())
 if d and N.state and d.id==N.state.id and d.initialID==rec.initialID then return u end
 return nil
end
local function persist(s)
 for _,r in ipairs(s.units) do
  local u=Players[r.owner]:GetUnitByID(r.id)
  if u then
   local d={};for _,k in ipairs(F) do d[k]=s[k] end
   d.role=r.role;d.initialPlot=r.initialPlot;d.initialHP=r.initialHP;d.initialMoves=r.initialMoves;d.type=r.type;d.initialID=r.initialID
   u:SetScriptData(encode(d))
  end
 end
end
local function spawn(s,owner,kind,p,role)
 local t=assert(GameInfoTypes[kind],"unknown unit "..kind)
 local u=assert(Players[owner]:InitUnit(t,p:GetX(),p:GetY()),"unit creation failed")
 local rec={owner=owner,id=u:GetID(),initialID=u:GetID(),type=t,role=role,initialPlot=index(p),initialHP=u:GetCurrHitPoints(),initialMoves=u:GetMoves()}
 s.units[#s.units+1]=rec
 -- Tag every newly created unit immediately so failed setup cleanup is safe.
 persist(s)
 return rec,u
end
function N.Stop(reason)
 if N.pre then GameEvents.PlayerPreAIUnitUpdate.Remove(N.pre);N.pre=nil end
 if N.finish then GameEvents.PlayerEndTurnCompleted.Remove(N.finish);N.finish=nil end
 if N.humanReturn then Events.ActivePlayerTurnStart.Remove(N.humanReturn);N.humanReturn=nil end
 if N.armed then log("monitor-stop",reason or "manual") end
 N.armed=false
end
function N.Cleanup()
 N.Stop("cleanup")
 local fixture=N.state and N.state.id
 if not fixture then log("cleanup","no attached fixture; call Reattach() first");return end
 local count=0
 for _,r in ipairs(allTagged()) do if r.d.id==fixture then r.u:Kill(false,-1);count=count+1 end end
 N.state=nil
 log("cleanup","removed only tagged fixture units="..count.."; reload pre-fixture save to restore war/fog/turn history")
end
local function begin(kind,options)
 assert(#allTagged()==0,"A tagged fixture exists: Reattach() it, or clean it up before creating another")
 local human,ai=players();assert(Game.GetAIAutoPlay()==0,"keep human threats under human control")
 assert(Players[human]:IsTurnActive() and not Players[ai]:IsTurnActive(),"set up during sequential human turn")
 N.serial=(N.serial or 0)+1
 local s={id=kind.."-"..Game.GetGameTurn().."-"..human.."-"..N.serial,kind=kind,human=human,ai=ai,turn=Game.GetGameTurn(),
  center=-1,target=-1,source=-1,alternate=-1,guardMoves=GameDefines.MOVE_DENOMINATOR or 60,focus=(options.focus==false and 0 or 1),
  pairs=0,enemies=0,expected=0,units={},valid=false}
 N.state=s
 return s
end
local function updateInitial(s)
 for _,r in ipairs(s.units) do local u=current(r);assert(u,"fixture lost during setup")
  r.initialPlot=index(u:GetPlot());r.initialHP=u:GetCurrHitPoints();r.initialMoves=u:GetMoves()
 end
 persist(s)
end
local function terrainLine(p)
 local rivers={};for d=0,5 do rivers[#rivers+1]=p:IsRiverCrossing(d) and "1" or "0" end
 return "index="..index(p).." xy="..xy(p).." plotType="..p:GetPlotType().." terrain="..p:GetTerrainType().." feature="..p:GetFeatureType().." route="..p:GetRouteType().." resource="..p:GetResourceType(-1).." quantity="..p:GetNumResource().." owner="..p:GetOwner().." rivers="..table.concat(rivers,"")
end
local function reachesThisTurn(path,target)
 local last=path[#path]
 if not last or last.X~=target:GetX() or last.Y~=target:GetY() then return false end
 -- GeneratePath uses TC_UI: exhausting movement adds1 to the displayed turn.
 return last.Turn-(last.RemainingMovement==0 and 1 or 0)==0
end
function N.MeasureFormation()
 local s=assert(N.state,"set up or Reattach first");assert(s.kind=="formation")
 local ranged,guard
 for _,r in ipairs(s.units) do if r.role=="ranged" then ranged=current(r) elseif r.role=="guard" then guard=current(r) end end
 assert(ranged and guard,"missing formation units")
 local r,p,a,t=plot(s.center),plot(s.source),plot(s.alternate),plot(s.target)
 assert(index(ranged:GetPlot())==s.center and index(guard:GetPlot())==s.source,"measure only the original saved setup")
 local originalMoves=guard:GetMoves();local baseline=ranged:GetDanger();local covered,guardRisk,alternate
 local ok,err=pcall(function()
  guard:SetXY(r:GetX(),r:GetY());covered=ranged:GetDanger();guardRisk=guard:GetDanger()
  guard:SetXY(a:GetX(),a:GetY());alternate=ranged:GetDanger()
 end)
 guard:SetXY(p:GetX(),p:GetY());guard:SetMoves(originalMoves)
 if not ok then error(err) end
 local moves=s.guardMoves
 local costR=r:MovementCost(guard,p,moves);local costA=a:MovementCost(guard,p,moves)
 local pathR=guard:GeneratePath(r,1);local pathA=guard:GeneratePath(a,1)
 local directR=#pathR==2 and reachesThisTurn(pathR,r) and guard:CanStackAtPlot(r)
 local directA=#pathA==2 and reachesThisTurn(pathA,a) and guard:CanStackAtPlot(a)
 for d=0,5 do
  local q=Map.PlotDirection(p:GetX(),p:GetY(),d)
  if q and (q:GetNumUnits()==0 or index(q)==s.center) then
   local path=guard:GeneratePath(q,1)
   if reachesThisTurn(path,q) and guard:CanStackAtPlot(q) then
    log("guard-alternative","xy="..xy(q).." cost="..q:MovementCost(guard,p,moves).." river="..tostring(p:IsRiverCrossingToPlot(q)).." "..terrainLine(q))
   end
  end
 end
 local counterPath=guard:GeneratePath(t,1);local immediateCounter=reachesThisTurn(counterPath,t)
 s.valid=baseline>covered and alternate>covered and guardRisk<guard:GetCurrHitPoints() and costR>=moves and costA>=moves and directR and directA and not immediateCounter
 log("formation-counterattack-this-turn",immediateCounter)
 log("formation-measure","alone="..baseline.." covered="..covered.." alternative="..alternate.." guardRisk="..guardRisk.." costR="..costR.." costA="..costA.." directPaths="..tostring(directR and directA).." valid="..tostring(s.valid))
 log("formation-rivers","PtoR="..tostring(p:IsRiverCrossingToPlot(r)).." PtoAlt="..tostring(p:IsRiverCrossingToPlot(a)).." enemyToR="..tostring(t:IsRiverCrossingToPlot(r)).." enemyToAlt="..tostring(t:IsRiverCrossingToPlot(a)))
 log("formation-limits","natural terrain is unenclosed; protector may have other legal choices; exact positions/danger must be reviewed")
 return s.valid
end
function N.Formation(options)
 options=options or {};local previous=N.state
 local ok,err=pcall(function()
  local s=begin("formation",options);local r,p,t,a=findFormation(s.human,s.ai)
  s.center=index(r);s.source=index(p);s.target=index(t);s.alternate=index(a);s.pairs=1;s.enemies=options.enemies or 2;s.expected=2+s.enemies
  assert(s.enemies>=1 and s.enemies<=2,"formation supports1-2 stationary threats without tech edits")
  Teams[Players[s.human]:GetTeam()]:DeclareWar(Players[s.ai]:GetTeam(),false,s.human)
  local rr,ru=spawn(s,s.ai,options.rangedType or "UNIT_ARCHER",r,"ranged");ru:FinishMoves()
  local gr,gu=spawn(s,s.ai,options.guardType or "UNIT_PIKEMAN",p,"guard");gu:SetMoves(s.guardMoves)
  assert(gu:GetStackingLimit(r)>=2,"formation requires capacity2; no technologies were changed")
  for i=1,s.enemies do
   local rec,u=spawn(s,s.human,options.threatType or "UNIT_SWORDSMAN",t,"enemy"..i)
   assert(u:CanStackAtPlot(t),"enemy stack exceeds current capacity");u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP)
  end
  updateInitial(s);N.MeasureFormation();N.Snapshot("setup-complete")
  log("save-next","use normal UI Save Game BEFORE Arm(); record filename and DLL hash; helper has not advanced a turn")
 end)
 if not ok then
  if N.state~=previous then N.Cleanup();N.state=previous end
  error(err)
 end
end
function N.Dense(options)
 options=options or {};local previous=N.state
 local ok,err=pcall(function()
  local s=begin("dense",options);s.pairs=math.floor(options.pairs or 8);s.enemies=math.floor(options.enemies or 6);s.expected=s.pairs*2+s.enemies
  assert(s.pairs>=1 and s.pairs<=12 and s.enemies>=1 and s.enemies<=12,"benchmark size outside helper bounds")
  local enemySites=math.ceil(s.enemies/2);local c,sites=findDense(s.human,s.ai,s.pairs+enemySites)
  s.center=index(c);s.target=index(c)
  Teams[Players[s.human]:GetTeam()]:DeclareWar(Players[s.ai]:GetTeam(),false,s.human)
  for i=1,s.enemies do
   local p=sites[math.ceil(i/2)];local rec,u=spawn(s,s.human,options.threatType or "UNIT_LONGSWORDSMAN",p,"enemy"..i)
   assert(u:CanStackAtPlot(p),"enemy pair exceeds current capacity");u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP)
  end
  for i=1,s.pairs do
   local p=sites[enemySites+i];local rec,u=spawn(s,s.ai,options.guardType or "UNIT_PIKEMAN",p,"melee"..i)
   assert(u:GetStackingLimit(p)>=2,"AI pair requires capacity2; no technologies were changed")
   spawn(s,s.ai,options.rangedType or "UNIT_COMPOSITE_BOWMAN",p,"bow"..i)
  end
  s.valid=true;updateInitial(s);N.Snapshot("setup-complete")
  log("save-next","use normal UI Save Game BEFORE Arm(); reuse that exact save for each DLL; no terrain or technology changes")
 end)
 if not ok then
  if N.state~=previous then N.Cleanup();N.state=previous end
  error(err)
 end
end
function N.Reattach(fixtureID)
 N.Stop("reattach")
 local found={}
 for _,r in ipairs(allTagged()) do if not fixtureID or r.d.id==fixtureID then found[#found+1]=r end end
 assert(#found>0,"no matching saved fixture metadata")
 local first=found[1].d;local s={units={},valid=false}
 for _,k in ipairs(F) do s[k]=first[k] end
 local seen,roles={},{}
 for _,r in ipairs(found) do
  assert(r.d.id==s.id,"multiple fixtures found; call Reattach(id)")
  local d,u=r.d,r.u
  for i=1,14 do local k=F[i];assert(d[k]==s[k],"inconsistent saved fixture header "..k) end
  assert(not seen[d.initialID],"duplicate saved fixture ID");seen[d.initialID]=true
  assert(not roles[d.role],"duplicate fixture role");roles[d.role]=true
  local expectedOwner=string.sub(d.role,1,5)=="enemy" and s.human or s.ai
  assert(u:GetOwner()==expectedOwner,"fixture unit changed owner")
  s.units[#s.units+1]={owner=u:GetOwner(),id=u:GetID(),initialID=d.initialID,role=d.role,type=d.type,initialPlot=d.initialPlot,initialHP=d.initialHP,initialMoves=d.initialMoves}
 end
 if #found==s.expected then
  if s.kind=="formation" then assert(roles.ranged and roles.guard,"missing formation roles")
  else for i=1,s.pairs do assert(roles["melee"..i] and roles["bow"..i],"missing dense pair role") end end
  for i=1,s.enemies do assert(roles["enemy"..i],"missing enemy role") end
 end
 table.sort(s.units,function(a,b)return a.initialID<b.initialID end)
 N.state=s
 log("reattached",s.id.." found="..#s.units.." expected="..s.expected.." savedSetupTurn="..s.turn)
 N.Snapshot("reattached")
 return s.id
end
function N.Snapshot(label)
 local s=assert(N.state,"set up or Reattach first");local aliveCount=0;local initial=true;local stationary=true;local capacity=true;local touched={};local roles={}
 log("snapshot",s.id.." label="..(label or "manual").." gameTurn="..Game.GetGameTurn().." human="..s.human.." ai="..s.ai)
 for _,rec in ipairs(s.units) do
  local u=current(rec)
  if u and u:GetCurrHitPoints()>0 then
   aliveCount=aliveCount+1;local p=u:GetPlot();roles[rec.role]=u;touched[index(p)]=p
   local match=u:GetID()==rec.initialID and index(p)==rec.initialPlot and u:GetCurrHitPoints()==rec.initialHP and u:GetMoves()==rec.initialMoves and u:GetUnitType()==rec.type
   initial=initial and match
   if rec.owner==s.human and index(p)~=rec.initialPlot then stationary=false end
   if not u:CanStackAtPlot(p) then capacity=false end
   log("unit","owner="..rec.owner.." id="..u:GetID().." initialID="..rec.initialID.." role="..rec.role.." type="..u:GetUnitType().." xy="..xy(p).." HP="..u:GetCurrHitPoints().." moves="..u:GetMoves().." danger="..u:GetDanger().." cap="..u:GetStackingLimit(p).." baseMelee="..u:GetBaseCombatStrength().." baseRanged="..u:GetBaseRangedCombatStrength().." defense100="..u:GetMaxDefenseStrength(p,nil,nil,false).." matchesSetup="..tostring(match))
  else initial=false;log("unit","owner="..rec.owner.." id="..rec.id.." role="..rec.role.." DEAD_OR_REPLACED") end
 end
 local terrainIDs={};for i in pairs(touched) do terrainIDs[#terrainIDs+1]=i end;table.sort(terrainIDs)
 for _,i in ipairs(terrainIDs) do log("terrain",terrainLine(touched[i])) end
 initial=initial and aliveCount==s.expected and Game.GetGameTurn()==s.turn
 local outsiders=0
 for _,p in ipairs(ring(plot(s.center),s.kind=="dense" and 3 or 2)) do for i=0,p:GetNumUnits()-1 do
  local u=p:GetUnit(i);local d=u and decode(u:GetScriptData());if not d or d.id~=s.id then outsiders=outsiders+1 end
 end end
 log("checks","alive="..aliveCount.." expected="..s.expected.." exactSetup="..tostring(initial).." humanThreatsStationary="..tostring(stationary).." capacity="..tostring(capacity).." unrelatedUnitsInArea="..outsiders)
 if s.kind=="formation" then
  local r,g=roles.ranged,roles.guard
  log("formation-outcome",r and g and index(r:GetPlot())==index(g:GetPlot()) and "PROTECTED_STACK" or "NO_PROTECTIVE_JOIN")
 end
 return initial and capacity and outsiders==0
end
function N.Arm(maxReturns)
 local s=assert(N.state,"set up or Reattach first");assert(not N.armed,"already armed")
 assert(Game.GetActivePlayer()==s.human and Game.GetAIAutoPlay()==0,"keep human threats human controlled")
 assert(N.Snapshot("pre-arm"),"fixture differs from original saved setup or has unrelated occupants; reload benchmark save")
 if s.kind=="formation" then assert(N.MeasureFormation(),"no measured protection advantage; do not label this a formation test") else s.valid=true end
 N.armed=true;N.limit=math.max(1,math.floor(tonumber(maxReturns) or 1));N.returns=0;N.aiTurns=0;N.seen={}
 if s.focus==1 then Players[s.ai]:AddTemporaryDominanceZone(plot(s.target):GetX(),plot(s.target):GetY());log("focus","temporary focus added while arming, after benchmark save") end
 N.pre=function(player)
  if player~=s.ai or not Players[player]:IsTurnActive() then return end
  local key=Game.GetGameTurn()..":"..player;if N.seen[key] then return end;N.seen[key]=true;N.aiTurns=N.aiTurns+1
  if s.kind=="formation" and N.aiTurns==1 then for _,rec in ipairs(s.units) do local u=current(rec)
   if u and rec.role=="ranged" then u:FinishMoves() elseif u and rec.role=="guard" then u:SetActivityType(ActivityTypes.ACTIVITY_AWAKE);u:SetMoves(s.guardMoves) end
  end end
  log("AI_START","turn="..Game.GetGameTurn().." player="..player.." observed="..N.aiTurns);N.Try("Snapshot","before-ai-update")
 end
 N.finish=function(player)if player==s.ai then log("AI_END","turn="..Game.GetGameTurn().." player="..player)end end
 N.humanReturn=function()
  if Game.GetActivePlayer()~=s.human or N.aiTurns==0 then return end
  N.returns=N.returns+1;log("HUMAN_RETURN","turn="..Game.GetGameTurn().." count="..N.returns.." aiTurns="..N.aiTurns);N.Try("Snapshot","human-return")
  if N.returns>=N.limit then N.Stop("observation_limit") end
 end
 GameEvents.PlayerPreAIUnitUpdate.Add(N.pre);GameEvents.PlayerEndTurnCompleted.Add(N.finish);Events.ActivePlayerTurnStart.Add(N.humanReturn)
 log("armed","observe at most"..N.limit.." human returns; use normal UI End Turn; no turn has been requested")
end
function N.Try(name,...)
 local fn=assert(N[name],"unknown helper method");local ok,result=pcall(fn,...)
 if not ok then log("ERROR",name..": "..tostring(result)) end
 return ok,result
end
log("loaded","Plan/Formation/Dense/Reattach/Snapshot/Arm/Stop/Cleanup; definitions only, no scenario auto-started")
