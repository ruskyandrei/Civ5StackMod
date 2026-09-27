-- Explicit disposable-game scenarios. Defining these functions does nothing.
-- Load after StackingTests. No DLL/UI mutation, autoplay, or city creation.
assert(StackTests, "include StackingTests first")
StackAITurnTests = StackAITurnTests or {}
local A,T = StackAITurnTests,StackTests
local clock = os and os.clock
local function log(key,value) print("STACKAI_TURN|"..key.."|"..tostring(value)) end
local function id(p) return p:GetPlotIndex() end
local function xy(p) return p:GetX()..","..p:GetY() end
local function distance(a,b) return Map.PlotDistance(a:GetX(),a:GetY(),b:GetX(),b:GetY()) end
local function unit(rec) return rec and Players[rec.owner]:GetUnitByID(rec.id) end
local function alive(rec) local u=unit(rec); return u and u:GetCurrHitPoints()>0 and u or nil end
local function ring(center,radius)
 local out,seen={},{}
 for dx=-radius,radius do for dy=-radius,radius do
  local p=Map.PlotXYWithRangeCheck(center:GetX(),center:GetY(),dx,dy,radius)
  if p and not seen[id(p)] then seen[id(p)]=true;out[#out+1]=p end
 end end
 table.sort(out,function(a,b)return id(a)<id(b)end)
 return out
end
local function findPatch(radius)
 -- Prefer a land center, but allow backed-up water in the enclosure and, if
 -- necessary, an offshore center. Tiny island maps rarely have a dry radius4.
 for pass=1,2 do for i=0,Map.GetNumPlots()-1 do
  local c=Map.GetPlotByIndex(i)
  if c and (pass==2 or not c:IsWater()) and not c:IsCity() and c:GetOwner()==-1 then
   local plots=ring(c,radius+1)
   local good=#plots==1+3*(radius+1)*(radius+2)
   for _,p in ipairs(plots) do
    local feature=GameInfo.Features[p:GetFeatureType()]
    local wonder=feature and (feature.NaturalWonder==true or feature.NaturalWonder==1)
    if p:IsCity() or p:GetOwner()~=-1 or p:GetNumUnits()>0 or p:GetImprovementType()~=-1 or wonder then good=false;break end
   end
   if good then return c,ring(c,radius) end
  end
 end end
 error("No unused land/water arena: requires no cities, units, ownership, improvements or natural wonders in guard ring")
end
local function spawn(s,owner,kind,p,role)
 local u=T.Spawn(owner,kind,p)
 local rec={owner=owner,id=u:GetID(),kind=kind,role=role,x=p:GetX(),y=p:GetY(),plot=id(p)}
 s.units[#s.units+1]=rec
 return rec,u
end
local function removeHooks()
 if A.pre then GameEvents.PlayerPreAIUnitUpdate.Remove(A.pre);A.pre=nil end
 if A.finish then GameEvents.PlayerEndTurnCompleted.Remove(A.finish);A.finish=nil end
 if A.humanReturn then Events.ActivePlayerTurnStart.Remove(A.humanReturn);A.humanReturn=nil end
end
function A.Cleanup()
 removeHooks()
 local s=A.state
 if not s then return end
 for _,rec in ipairs(s.units or {}) do local u=unit(rec);if u then u:Kill(false,-1) end end
 -- Kill only this helper's units. Never delete unrelated units/cities.
 for _,b in ipairs(s.terrain or {}) do
  local p=Map.GetPlotByIndex(b.plot)
  p:SetFeatureType(-1);p:SetResourceType(-1,0)
  p:SetPlotType(b.plotType,false,true,false)
  p:SetTerrainType(b.terrain,false,true)
  p:SetFeatureType(b.feature)
  if b.resource~=-1 then p:SetResourceType(b.resource,b.resourceCount) end
  p:SetRouteType(b.route)
 end
 if s.terrain and #s.terrain>0 then Map.RecalculateAreas() end
 for _,b in ipairs(s.techs or {}) do Teams[b.team]:SetHasTech(b.tech,b.before,b.owner,false,false,true) end
 A.state=nil
 log("cleanup","scenario units removed and terrain/temporary techs restored; war/turn progression and temporary focus remain in disposable game")
end
local function begin(kind,options)
 A.Cleanup()
 local human,ai=T.Players()
 assert(Game.GetAIAutoPlay()==0,"Stop autoplay: threats must remain human controlled")
 assert(Players[human]:IsTurnActive(),"Set up during the active human turn")
 assert(not Players[ai]:IsTurnActive(),"Use sequential single-player turns for this probe")
 Teams[Players[human]:GetTeam()]:DeclareWar(Players[ai]:GetTeam(),false,human)
 local radius=kind=="dense" and 3 or 2
 local center,plots=findPatch(radius)
 local s={kind=kind,human=human,ai=ai,center=center,units={},terrain={},techs={},aiTurns=0,valid=true,options=options or {},setupTurn=Game.GetGameTurn()}
 A.state=s
 for _,p in ipairs(plots) do
  s.terrain[#s.terrain+1]={plot=id(p),plotType=p:GetPlotType(),terrain=p:GetTerrainType(),feature=p:GetFeatureType(),resource=p:GetResourceType(-1),resourceCount=p:GetNumResource(),route=p:GetRouteType()}
  p:SetFeatureType(-1);p:SetResourceType(-1,0);p:SetRouteType(-1)
  p:SetTerrainType(GameInfoTypes.TERRAIN_GRASS,false,true)
  p:SetPlotType(PlotTypes.PLOT_MOUNTAIN,false,true,false)
  p:SetTerrainType(GameInfoTypes.TERRAIN_MOUNTAIN,false,true)
  assert(p:IsImpassable(Players[human]:GetTeam()) and p:IsImpassable(Players[ai]:GetTeam()),"Arena wall is passable for a fixture team")
 end
 s.arena=plots;s.radius=radius
 log("arena-radius",radius)
 log("setup",kind.." human="..human.." ai="..ai.." center="..xy(center).." turn="..s.setupTurn)
 return s
end
local function open(p,hills)
 p:SetFeatureType(-1)
 p:SetTerrainType(GameInfoTypes.TERRAIN_GRASS,false,true)
 p:SetPlotType(hills and PlotTypes.PLOT_HILLS or PlotTypes.PLOT_LAND,false,true,false)
end
local function ensureCapacity(s,owner,probe,p,desired)
 local teamId=Players[owner]:GetTeam();local team=Teams[teamId]
 local rows={}
 for row in GameInfo.Stacking_Technologies() do rows[#rows+1]=row end
 table.sort(rows,function(a,b)return GameInfoTypes[a.TechType]<GameInfoTypes[b.TechType]end)
 for _,row in ipairs(rows) do
  if probe:GetStackingLimit(p)>=desired then break end
  local tech=GameInfoTypes[row.TechType]
  if not team:IsHasTech(tech) then
   s.techs[#s.techs+1]={team=teamId,owner=owner,tech=tech,before=false}
   team:SetHasTech(tech,true,owner,false,false,true)
  end
 end
 assert(probe:GetStackingLimit(p)>=desired,"Configured maximum is too small for this scenario")
end
local function describe(rec)
 local u=alive(rec)
 if not u then return "owner="..rec.owner.." id="..rec.id.." role="..rec.role.." DEAD" end
 return "owner="..rec.owner.." id="..rec.id.." role="..rec.role.." type="..rec.kind.." xy="..u:GetX()..","..u:GetY().." hp="..u:GetCurrHitPoints().." moves="..u:GetMoves().." danger="..u:GetDanger()
end
function A.Snapshot(label)
 local s=assert(A.state,"Set up a scenario first")
 log("snapshot",s.kind.." label="..(label or "manual").." turn="..Game.GetGameTurn().." aiTurns="..s.aiTurns)
 for _,rec in ipairs(s.units) do log("unit",describe(rec)) end
 local stationary=true
 for _,rec in ipairs(s.units) do
  local u=alive(rec)
  if rec.owner==s.human and u and (u:GetX()~=rec.x or u:GetY()~=rec.y) then stationary=false end
 end
 log("human-threats-stationary",stationary)
 if s.kind=="formation" then
  local ranged,guard=alive(s.ranged),alive(s.guard)
  local together=ranged and guard and ranged:GetX()==guard:GetX() and ranged:GetY()==guard:GetY()
  log("formation-outcome",together and "PROTECTED_STACK" or "NO_PROTECTIVE_JOIN")
  if ranged then log("ranged-stayed-on-test-tile",ranged:GetX()==s.ranged.x and ranged:GetY()==s.ranged.y) end
 elseif s.kind=="casualty" then
  local count=0
  for _,rec in ipairs(s.defenders) do if alive(rec) then count=count+1 end end
  local attacker=alive(s.attacker)
  log("surviving-defenders",count)
  log("attacker-stayed-before-survivors",attacker and attacker:GetX()==s.attacker.x and attacker:GetY()==s.attacker.y)
  if count==#s.defenders then log("casualty-result","NOT_EXERCISED: no defender killed; inspect tactical log")
  elseif count==#s.defenders-1 and attacker and attacker:GetX()==s.attacker.x and attacker:GetY()==s.attacker.y then log("casualty-result","PASS: one casualty, survivors retain tile, no advance")
  else log("casualty-result","REVIEW: unexpected casualty count or advance") end
 end
 local occupancy,valid={ },true
 for _,rec in ipairs(s.units) do
  local u=alive(rec)
  if u then
   local p=u:GetPlot();local key=rec.owner..":"..id(p)..":"..u:GetDomainType()
   occupancy[key]=(occupancy[key] or 0)+1
   if occupancy[key]>u:GetStackingLimit(p) or not u:CanStackAtPlot(p) then valid=false end
  end
 end
 log("tracked-occupancy-within-capacity",valid)
end
local function startWatch(s)
 -- An existing tactical focus area makes the remote arena relevant to the AI;
 -- it does not assign units, destinations, attacks or a protective formation.
 if s.options.focus~=false then
  Players[s.ai]:AddTemporaryDominanceZone(s.target:GetX(),s.target:GetY())
  log("focus","temporary tactical focus at arena; expires normally in disposable game")
 end
 A.pre=function(player)
  if player~=s.ai or not Players[s.ai]:IsTurnActive() then return end
  local turn=Game.GetGameTurn()
  if s.preppedTurn==turn then return end
  s.preppedTurn=turn;s.aiTurns=s.aiTurns+1
  if s.aiTurns>1 then log("INVALID","more than one AI turn elapsed");return end
  if clock then s.startClock=clock() end
  if s.kind=="formation" then
   local ranged,guard=assert(alive(s.ranged)),assert(alive(s.guard))
   ranged:SetMoves(0) -- fixed, exhausted ranged unit: it cannot choose its own retreat
   guard:SetActivityType(ActivityTypes.ACTIVITY_AWAKE)
   guard:SetMoves(s.guardMoves) -- both legal front tiles exhaust this budget
  end
  A.Snapshot("before-ai-unit-update")
 end
 A.finish=function(player)
  if player==s.ai and s.aiTurns==1 and not s.finished then
   s.finished=true
   if clock and s.startClock then log("ai-cpu-seconds",clock()-s.startClock) end
   A.Snapshot("after-ai-turn")
  end
 end
 A.humanReturn=function()
  if Game.GetActivePlayer()==s.human and s.endRequested and s.aiTurns>0 then
   A.Snapshot("human-turn-returned")
   log("one-ai-turn-observed",s.aiTurns==1)
   removeHooks()
  end
 end
 GameEvents.PlayerPreAIUnitUpdate.Add(A.pre)
 GameEvents.PlayerEndTurnCompleted.Add(A.finish)
 Events.ActivePlayerTurnStart.Add(A.humanReturn)
end
function A.Formation(options)
 local ok,err=pcall(function()
  local s=begin("formation",options)
  local r=s.center
  local p=Map.PlotDirection(r:GetX(),r:GetY(),0)
  local target=Map.PlotDirection(r:GetX(),r:GetY(),2)
  local alternate=Map.PlotDirection(r:GetX(),r:GetY(),1)
  assert(distance(p,target)==2 and distance(p,alternate)==1 and distance(target,alternate)==1,"Unexpected hex geometry")
  open(p,false);open(r,true);open(alternate,true);open(target,true);Map.RecalculateAreas()
  s.source=p;s.target=target;s.alternate=alternate
  s.ranged=spawn(s,s.ai,s.options.rangedType or "UNIT_ARCHER",r,"exhausted-ranged")
  local guard
  s.guard,guard=spawn(s,s.ai,s.options.guardType or "UNIT_PIKEMAN",p,"protector-with-two-choices")
  for i=1,(s.options.threatCount or 2) do
   local rec,u=spawn(s,s.human,s.options.threatType or "UNIT_SWORDSMAN",target,"stationary-threat-"..i)
   ensureCapacity(s,s.human,u,target,s.options.threatCount or 2)
   u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP)
  end
  ensureCapacity(s,s.ai,guard,r,2)
  s.guardMoves=s.options.guardMoves or GameDefines.MOVE_DENOMINATOR or 60
  local ranged=assert(alive(s.ranged))
  local baseline=ranged:GetDanger()
  guard:SetXY(r:GetX(),r:GetY());local protected=ranged:GetDanger();local guardRisk=guard:GetDanger()
  guard:SetXY(alternate:GetX(),alternate:GetY());local alternateDanger=ranged:GetDanger()
  guard:SetXY(p:GetX(),p:GetY());guard:SetMoves(s.guardMoves);ranged:SetMoves(0)
  log("choice-R",xy(r).." stacks with archer; hill; enemy distance1")
  log("choice-S",xy(alternate).." leaves archer alone; hill; enemy distance1")
  log("danger-baseline",baseline);log("danger-if-R",protected);log("danger-if-S",alternateDanger);log("protector-risk-if-R",guardRisk)
  s.valid=baseline>protected and alternateDanger>protected and guardRisk<guard:GetCurrHitPoints()
  log("scenario-distinguishes-protection",s.valid)
  log("expected","protector chooses R over equally close hill S; archer remains fixed; no immediate melee counterattack")
  A.Snapshot("setup-complete");startWatch(s)
 end)
 if not ok then A.Cleanup();error(err) end
end
function A.Dense(options)
 local ok,err=pcall(function()
  local s=begin("dense",options)
  local inner=ring(s.center,2)
  for _,p in ipairs(inner) do open(p,false) end
  Map.RecalculateAreas()
  local target=Map.PlotDirection(s.center:GetX(),s.center:GetY(),1)
  s.target=target
  local count=s.options.threatCount or 5
  for i=1,count do
   local rec,u=spawn(s,s.human,s.options.threatType or "UNIT_LONGSWORDSMAN",target,"dense-defender-"..i)
   ensureCapacity(s,s.human,u,target,count);u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP)
  end
  local sites={}
  for _,p in ipairs(inner) do if id(p)~=id(target) then sites[#sites+1]=p end end
  table.sort(sites,function(a,b) local da,db=distance(a,target),distance(b,target);return da==db and id(a)<id(b) or da<db end)
  local pairs=s.options.pairs or 8;assert(pairs>=1 and pairs<=#sites)
  for i=1,pairs do
   local rec,u=spawn(s,s.ai,s.options.guardType or "UNIT_PIKEMAN",sites[i],"dense-melee-"..i)
   ensureCapacity(s,s.ai,u,sites[i],2)
   spawn(s,s.ai,s.options.rangedType or "UNIT_COMPOSITE_BOWMAN",sites[i],"dense-ranged-"..i)
  end
  log("friendly-combat-count",pairs*2);log("expected","all units remain physical occupants; tactics retain13-unit/6000-position bounds; inspect log time and casualties")
  A.Snapshot("setup-complete");startWatch(s)
 end)
 if not ok then A.Cleanup();error(err) end
end
function A.Casualty(options)
 local ok,err=pcall(function()
  local s=begin("casualty",options)
  local target=s.center;local source=Map.PlotDirection(target:GetX(),target:GetY(),4)
  open(source,false);open(target,false);Map.RecalculateAreas()
  s.target=target;s.defenders={}
  for i=1,3 do
   local rec,u=spawn(s,s.human,"UNIT_WARRIOR",target,"one-hp-defender-"..i)
   ensureCapacity(s,s.human,u,target,3);u:SetDamage(u:GetMaxHitPoints()-1);u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP)
   s.defenders[#s.defenders+1]=rec
  end
  local attacker
  s.attacker,attacker=spawn(s,s.ai,s.options.attackerType or "UNIT_SWORDSMAN",source,"one-attack-melee")
  local preview=attacker:GetStackAttackPreview(target,false)
  log("primary-before-turn",preview.DefenderID)
  log("expected","one AI melee attack kills exactly one of three1HP defenders; other2 remain; attacker does not advance")
  A.Snapshot("setup-complete");startWatch(s)
 end)
 if not ok then A.Cleanup();error(err) end
end
function A.EndHumanTurn(finishOtherHumanUnits)
 local s=assert(A.state,"Set up a scenario first")
 assert(s.valid,"Setup did not produce a clear protection advantage: adjust unit types before advancing")
 assert(not s.endRequested,"Already requested one end turn: do not advance again")
 assert(Game.GetActivePlayer()==s.human and Game.GetAIAutoPlay()==0,"Keep the human player in control; no autoplay")
 if finishOtherHumanUnits then for u in Players[s.human]:Units() do u:FinishMoves() end end
 for _,rec in ipairs(s.units) do if rec.owner==s.human then local u=alive(rec);if u then u:FinishMoves();u:SetActivityType(ActivityTypes.ACTIVITY_SLEEP) end end end
 s.endRequested=true
 A.Snapshot("human-end-requested")
 local control=ControlTypes.CONTROL_ENDTURN
 if Game.CanDoControl(control) then Game.DoControl(control);log("end-turn","requested through normal game control")
 else log("end-turn","resolve research/production/dialog blockers, then click End Turn exactly once; watcher stays armed") end
end
function A.Try(name,...)
 local fn=assert(A[name],"Unknown test function "..tostring(name))
 local ok,result=pcall(fn,...)
 if not ok then log("ERROR",name..": "..tostring(result)) end
 return ok,result
end
log("loaded","Formation(), Dense(), Casualty(), EndHumanTurn(true), Snapshot(), Cleanup(); no scenario auto-started")
