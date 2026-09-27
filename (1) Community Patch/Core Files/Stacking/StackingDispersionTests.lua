-- Manual natural-terrain collateral dispersion probe. Loading defines functions only.
-- Setup(true) explicitly permits a temporary AI-team Iron Working grant; no XML/terrain edits.
StackDispersionTests=StackDispersionTests or {}
local D=StackDispersionTests
local TAG="STACKDISP1|"
local function log(k,v) print("STACKDISP|"..k.."|"..tostring(v)) end
local function idx(p)return p:GetPlotIndex()end
local function xy(p)return p:GetX()..","..p:GetY()end
local function plot(i)return Map.GetPlotByIndex(i)end
local function dist(a,b)return Map.PlotDistance(a:GetX(),a:GetY(),b:GetX(),b:GetY())end
local function setting(k,default)for row in GameInfo.Stacking_Settings()do if row.Name==k then return tonumber(row.Value)end end;return default end
local function ring(p,n)
 local a,seen={},{};for dx=-n,n do for dy=-n,n do local q=Map.PlotXYWithRangeCheck(p:GetX(),p:GetY(),dx,dy,n)
  if q and not seen[idx(q)]then seen[idx(q)]=true;a[#a+1]=q end
 end end;table.sort(a,function(x,y)return idx(x)<idx(y)end);return a
end
local function unused(p)return p and p:GetOwner()==-1 and not p:IsCity() and p:GetNumUnits()==0 and p:GetImprovementType()==-1 and p:GetRouteType()==-1 end
local function clear(p,h,a)return unused(p) and p:GetPlotType()==PlotTypes.PLOT_LAND and p:GetFeatureType()==-1 and not p:IsImpassable(Players[h]:GetTeam()) and not p:IsImpassable(Players[a]:GetTeam())end
function D.Plan(startIndex)
 local human=Game.GetActivePlayer();assert(human>=0,"load a disposable game")
 local ai;for i=0,GameDefines.MAX_MAJOR_CIVS-1 do if i~=human and Players[i] and Players[i]:IsAlive() and not Players[i]:IsHuman() and Players[i]:GetTeam()~=Players[human]:GetTeam()then ai=i;break end end
 assert(ai,"need independent living AI major")
 for i=math.max(0,math.floor(startIndex or 0)),Map.GetNumPlots()-1 do local c=plot(i)
  if clear(c,human,ai)then local empty=true;for _,q in ipairs(ring(c,3))do if not unused(q)then empty=false;break end end
   if empty then for _,t in ipairs(ring(c,2))do if dist(c,t)==2 and clear(t,human,ai)then
    local alternatives={};for d=0,5 do local q=Map.PlotDirection(c:GetX(),c:GetY(),d);if clear(q,human,ai) and dist(q,t)>2 then alternatives[#alternatives+1]=idx(q)end end
    if #alternatives>0 then log("PLAN","center="..xy(c).." siege="..xy(t).." candidates="..#alternatives.." startNext="..(i+1));return {human=human,ai=ai,center=i,target=idx(t),alternatives=alternatives}end
   end end end
  end
 end
 error("No empty natural site; use another map rather than editing terrain")
end
local function get(rec)
 local u=Players[rec.owner]:GetUnitByID(rec.id)
 assert(u and u:GetCurrHitPoints()>0 and u:GetUnitType()==rec.type and u:GetScriptData()==rec.tag,"fixture unit missing/replaced")
 return u
end
local function units(s)return get(s.guard),get(s.ranged),get(s.spare),get(s.threat)end
local function outsiders(s)
 local known={};for _,r in ipairs(s.units)do known[r.owner..":"..r.id]=true end
 local count=0;for _,p in ipairs(ring(plot(s.center),3))do for i=0,p:GetNumUnits()-1 do local u=p:GetUnit(i)
  if u and not known[u:GetOwner()..":"..u:GetID()]then count=count+1;log("OUTSIDER",u:GetOwner()..":"..u:GetID().." xy="..xy(p))end
 end end;return count
end
function D.Stop()
 if D.pre then GameEvents.PlayerPreAIUnitUpdate.Remove(D.pre);D.pre=nil end
 if D.back then Events.ActivePlayerTurnStart.Remove(D.back);D.back=nil end
 D.armed=false
end
function D.Cleanup()
 D.Stop();local s=D.state;if not s then return end
 local victims={};for _,rec in ipairs(s.units)do local u=Players[rec.owner]:GetUnitByID(rec.id);if u then assert(u:GetScriptData()==rec.tag,"refuse to delete replaced unit");assert(not u:IsBusy() and not u:IsFighting(),"wait for fixture missions");victims[#victims+1]=u end end
 for _,u in ipairs(victims)do u:Kill(false,-1)end
 if s.grantedIron then Teams[Players[s.ai]:GetTeam()]:SetHasTech(s.iron,false,s.ai,false,false,true)end
 if s.startedWar then Teams[Players[s.human]:GetTeam()]:MakePeace(Players[s.ai]:GetTeam())end
 D.state=nil;log("CLEANUP","only tagged fixtures removed, tracked tech/war presence restored; era/fog/history side effects are not undone")
end
local function spawn(s,owner,kind,p,role)
 local id=assert(GameInfoTypes[kind],"missing unit "..kind);local u=assert(Players[owner]:InitUnit(id,p:GetX(),p:GetY()),"spawn failed")
 local rec={owner=owner,id=u:GetID(),type=id,tag=TAG..s.id.."|"..role,role=role,hp=u:GetCurrHitPoints(),initial=idx(p)}
 u:SetScriptData(rec.tag);s.units[#s.units+1]=rec;s[role]=rec
 assert(idx(u:GetPlot())==idx(p),"spawn relocated; cleanup tracked unit before retry")
 assert(u:CanStackAtPlot(p),"fixture exceeds legal capacity")
 return u
end
local function shot(u,p)
 local saved=u:GetMoves();u:SetMoves(u:MaxMoves());local ok,v=pcall(function()return u:CanRangeStrikeAt(p:GetX(),p:GetY(),true,false)end);u:SetMoves(saved);if not ok then error(v)end;return v
end
local function forecast(s)
 local g,r,e,t=units(s);local p=t:GetStackAttackPreview(plot(s.center),true);local spareCollateral=0
 for _,v in ipairs(p.Collateral or {})do if v.UnitID==e:GetID() and v.Owner==s.ai then spareCollateral=v.Damage end end
 local f={guard=g:GetDanger(),ranged=r:GetDanger(),spare=e:GetDanger(),guardHP=g:GetCurrHitPoints(),rangedHP=r:GetCurrHitPoints(),spareHP=e:GetCurrHitPoints(),primary=p.DefenderID,primaryOwner=p.DefenderOwner,guardID=g:GetID(),owner=s.ai,spareCollateral=spareCollateral,collateralCount=p.CollateralCount,shot=shot(r,plot(s.target)),threatShot=shot(t,plot(s.center))}
 f.total=f.guard+f.ranged+f.spare;return f
end
function D.IsBetter(a,b)
 return a.threatShot and b.threatShot and a.shot and b.shot and a.primary==a.guardID and b.primary==a.guardID and a.primaryOwner==a.owner and b.primaryOwner==a.owner and a.spareCollateral>0 and a.collateralCount>=2 and b.total<a.total and b.guard<=a.guard and b.ranged<=a.ranged and b.guard<b.guardHP and b.ranged<b.rangedHP and b.spare<b.spareHP
end
local function arrives(path,target)
 local last=path[#path];return last and last.X==target:GetX() and last.Y==target:GetY() and last.Turn-(last.RemainingMovement==0 and 1 or 0)==0
end
function D.Measure()
 local s=assert(D.state);s.ready=false;s.measure=nil;assert(not D.armed,"measure before arming")
 local g,r,e,t=units(s);local center=plot(s.center);assert(idx(g:GetPlot())==s.center and idx(r:GetPlot())==s.center and idx(e:GetPlot())==s.center and idx(t:GetPlot())==s.target,"measure original arrangement only")
 assert(outsiders(s)==0,"unrelated unit entered area")
 assert(center:IsVisible(Players[s.human]:GetTeam(),false) and plot(s.target):IsVisible(Players[s.ai]:GetTeam(),false),"normal mutual threat visibility required")
 assert(t:GetStackRoleInfo().CollateralTargets>=2,"need at least two siege collateral victims")
 local floor=setting("CollateralHPFloorPercent",50);for _,u in ipairs({g,r,e})do assert(u:GetCurrHitPoints()>math.ceil(u:GetMaxHitPoints()*floor/100),"fixture already at collateral floor")end
 local moves=e:GetMoves();assert(e:GetFortifyTurns()==0,"temporary measurement requires an unfortified spare")
 local ok,err=pcall(function()
  e:SetMoves(s.moves);local base=forecast(s)
  assert(not arrives(e:GeneratePath(plot(s.target),1),plot(s.target)),"spare has an immediate counterattack; fixture not diagnostic")
  log("BASELINE","guard="..base.guard.." ranged="..base.ranged.." spare="..base.spare.." total="..base.total.." primary="..base.primary.." spareCollateral="..base.spareCollateral)
  for _,i in ipairs(s.alternatives)do local p=plot(i);local path=e:GeneratePath(p,1)
   if #path==2 and arrives(path,p) and path[#path].RemainingMovement==0 and p:MovementCost(e,center,s.moves)==s.moves and e:CanStackAtPlot(p)then
    e:SetXY(p:GetX(),p:GetY());e:SetMoves(s.moves);local split=forecast(s)
    log("ALTERNATIVE","xy="..xy(p).." guard="..split.guard.." ranged="..split.ranged.." spare="..split.spare.." total="..split.total.." primary="..split.primary.." better="..tostring(D.IsBetter(base,split)))
    if D.IsBetter(base,split) and (not s.measure or split.total<s.measure.split.total)then s.measure={base=base,split=split,target=i};s.ready=true end
    e:SetXY(center:GetX(),center:GetY());e:SetMoves(s.moves)
   end
  end
 end)
 e:SetXY(center:GetX(),center:GetY());e:SetMoves(moves);if not ok then s.ready=false;s.measure=nil;error(err)end
 log(s.ready and "READY" or "NONDIAGNOSTIC",s.ready and ("beneficial alternative="..xy(plot(s.measure.target)).."; no turn requested")or"no measured safe alternative; do not force a positive result")
 return s.ready
end
function D.Snapshot(label)
 local s=assert(D.state);for _,rec in ipairs(s.units)do local u=get(rec);log("UNIT",label.." role="..rec.role.." owner="..rec.owner.." id="..rec.id.." xy="..xy(u:GetPlot()).." HP="..u:GetCurrHitPoints().." moves="..u:GetMoves().." danger="..u:GetDanger().." cap="..u:GetStackingLimit(u:GetPlot()));assert(u:CanStackAtPlot(u:GetPlot()),"illegal fixture capacity")end
 log("SNAPSHOT",label.." turn="..Game.GetGameTurn().." outsiders="..outsiders(s))
end
function D.Setup(allowIronGrant,startIndex)
 assert(not D.state,"cleanup existing dispersion fixture first")
 assert(not StackAINaturalTests or not StackAINaturalTests.armed,"another observer is armed")
 assert(Game.GetAIAutoPlay()==0,"keep human threat controlled")
 assert(setting("Enabled",1)==1 and setting("AIEnabled",1)==1 and setting("CollateralEnabled",1)==1 and setting("BaseCapacity",2)==2 and setting("MaximumCapacity",9)==9,"restore default XML before this test")
 local s=D.Plan(startIndex);assert(Players[s.human]:IsTurnActive() and not Players[s.ai]:IsTurnActive(),"setup during human turn")
 s.id=Game.GetGameTurn().."-"..s.center;s.turn=Game.GetGameTurn();s.moves=GameDefines.MOVE_DENOMINATOR or 60;s.units={};s.iron=assert(GameInfoTypes.TECH_IRON_WORKING);D.state=s
 local ok,err=pcall(function()
  local team=Teams[Players[s.ai]:GetTeam()];s.hadIron=team:IsHasTech(s.iron)
  if not s.hadIron then assert(allowIronGrant==true,"fresh default cap2 needs explicit Setup(true) Iron Working permission");team:SetHasTech(s.iron,true,s.ai,false,false,true);s.grantedIron=true end
  local hteam=Teams[Players[s.human]:GetTeam()];s.startedWar=not hteam:IsAtWar(Players[s.ai]:GetTeam());if s.startedWar then hteam:DeclareWar(Players[s.ai]:GetTeam(),false,s.human)end
  local g=spawn(s,s.ai,"UNIT_PIKEMAN",plot(s.center),"guard");assert(g:GetStackingLimit(plot(s.center))>=3,"Iron Working did not provide capacity3")
  local r=spawn(s,s.ai,"UNIT_ARCHER",plot(s.center),"ranged")
  local e=spawn(s,s.ai,"UNIT_PIKEMAN",plot(s.center),"spare")
  local t=spawn(s,s.human,"UNIT_CATAPULT",plot(s.target),"threat")
  g:FinishMoves();r:FinishMoves();e:SetMoves(s.moves);t:FinishMoves();t:SetActivityType(ActivityTypes.ACTIVITY_SLEEP)
  log("SETUP","AI="..s.ai.." human="..s.human.." IronWorkingGranted="..tostring(s.grantedIron==true).." center="..xy(plot(s.center)).." siege="..xy(plot(s.target)))
  D.Measure();D.Snapshot("setup")
 end)
 if not ok then D.Cleanup();error(err)end
 return s.ready
end
function D.Arm()
 local s=assert(D.state);assert(not D.armed and Game.GetGameTurn()==s.turn and Game.GetActivePlayer()==s.human,"arm original human turn only")
 assert(D.Measure(),"nondiagnostic fixture; do not arm")
 local g,r,e,t=units(s);for _,rec in ipairs(s.units)do assert(get(rec):GetCurrHitPoints()==rec.hp,"fixture HP changed")end
 s.aiTurns=0;s.returns=0;D.armed=true;Players[s.ai]:AddTemporaryDominanceZone(plot(s.target):GetX(),plot(s.target):GetY())
 D.pre=function(id)
  if id~=s.ai or not Players[id]:IsTurnActive()then return end
  if s.aiTurns>0 then return end;s.aiTurns=1
  local a,b,c=units(s);a:FinishMoves();b:FinishMoves();c:SetActivityType(ActivityTypes.ACTIVITY_AWAKE);c:SetMoves(s.moves)
  print("STACKNAT|AI_START|turn="..Game.GetGameTurn().." player="..s.ai.." observed=1 fixture=dispersion")
  D.Snapshot("before-ai")
 end
 D.back=function()
  if Game.GetActivePlayer()~=s.human or s.aiTurns~=1 then return end
  s.returns=s.returns+1;D.Stop();print("STACKNAT|HUMAN_RETURN|turn="..Game.GetGameTurn().." count="..s.returns.." aiTurns=1 fixture=dispersion")
  local ok,err=pcall(D.Snapshot,"human-return");if not ok then s.returnError=true;log("ERROR","return snapshot: "..tostring(err))end
 end
 GameEvents.PlayerPreAIUnitUpdate.Add(D.pre);Events.ActivePlayerTurnStart.Add(D.back)
 log("ARMED","observe one normal human End Turn; watcher completion marker is STACKNAT for existing external guard")
end
function D.Check()
 local s=assert(D.state);assert(not D.armed and s.aiTurns==1 and s.returns==1 and Game.GetGameTurn()==s.turn+1 and Game.GetActivePlayer()==s.human and Players[s.human]:IsTurnActive() and Game.GetAIAutoPlay()==0,"exactly one completed observed turn required")
 assert(not s.returnError,"return snapshot failed; inspect evidence before claiming a clean result")
 local g,r,e,t=units(s);D.Snapshot("check");assert(outsiders(s)==0,"unrelated entrant: record as qualified/inconclusive, not clean dispersion proof")
 for _,rec in ipairs(s.units)do assert(get(rec):GetCurrHitPoints()==rec.hp,"combat/HP change confounds dispersion-only result")end
 assert(idx(g:GetPlot())==s.center and idx(r:GetPlot())==s.center and idx(t:GetPlot())==s.target,"fixed pair or human threat moved")
 if idx(e:GetPlot())==s.center then log("OUTCOME","NO_DISPERSION; inspect actual choices without changing fixture weights/stats");return false end
 assert(e:GetFortifyTurns()==0,"fortified spare makes relocation counterfactual nondiagnostic")
 for _,rec in ipairs(s.units)do local u=get(rec);assert(not u:IsBusy() and not u:IsFighting(),"wait for all fixture missions")end
 local actual=e:GetPlot();local moves=e:GetMoves();local split=forecast(s);local packed
 -- SetXY updates LastMoveTurn; this disposable diagnostic restores plot/moves, not every hidden movement field.
 local ok,err=pcall(function()e:SetXY(plot(s.center):GetX(),plot(s.center):GetY());packed=forecast(s)end)
 e:SetXY(actual:GetX(),actual:GetY());e:SetMoves(moves);if not ok then error(err)end
 assert(e:CanStackAtPlot(actual),"final spare capacity illegal")
 local useful=D.IsBetter(packed,split)
 log("OUTCOME",(useful and "LOWER_COLLATERAL_EXPOSURE"or"MOVED_WITHOUT_PROVEN_SAFETY_GAIN").." spare="..e:GetID().." xy="..xy(actual).." splitTotal="..split.total.." same-turn-packedTotal="..packed.total.." fixedPairRetained=true")
 return useful
end
function D.Try(name,...)
 local ok,v=pcall(assert(D[name],"unknown dispersion method"),...);if not ok then log("ERROR",name..": "..tostring(v))end;return ok,v
end
