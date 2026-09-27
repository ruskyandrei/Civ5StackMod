-- Manual natural-map melee tests. Loading defines functions only.
-- Setup -> Fire -> wait for combat -> Check. Advance uses Fire/Check twice.
-- No terrain, technology, city, diplomacy, turn or save changes. Use disposable games.
StackMeleeTests=StackMeleeTests or {passed=0,failed=0}
local M=StackMeleeTests
local TAG="STACKMELEE1|"
local function log(k,v) print("STACKMELEE|"..k.."|"..tostring(v)) end
local function check(k,a,e)
 local ok=a==e;M[ok and "passed" or "failed"]=M[ok and "passed" or "failed"]+1
 log(ok and "PASS" or "FAIL",k.." actual="..tostring(a).." expected="..tostring(e));return ok
end
local function requireThat(k,a,e) assert(check(k,a,e),"precondition: "..k) end
local function unit(owner,id) return Players[owner]:GetUnitByID(id) end
local function live(owner,id) local u=unit(owner,id);return u and u:GetCurrHitPoints()>0 and u or nil end
local function at(u,p) return u and u:GetX()==p:GetX() and u:GetY()==p:GetY() or false end
local function distance(a,b) return Map.PlotDistance(a:GetX(),a:GetY(),b:GetX(),b:GetY()) end
local function coords(p) return p:GetX()..","..p:GetY() end
local function tagged(u,s) return u and u:GetScriptData()==TAG..s.id end
local function ring(center,radius)
 local out,seen={},{}
 for dx=-radius,radius do for dy=-radius,radius do
  local p=Map.PlotXYWithRangeCheck(center:GetX(),center:GetY(),dx,dy,radius)
  if p and not seen[p:GetPlotIndex()] then seen[p:GetPlotIndex()]=true;out[#out+1]=p end
 end end
 return out
end
local function terrain(p)
 return table.concat({p:GetPlotType(),p:GetTerrainType(),p:GetFeatureType(),p:GetResourceType(-1),p:GetNumResource(),p:GetImprovementType(),p:GetRouteType(),p:GetOwner()},":")
end
local function originals()
 local out={}
 for owner=0,(GameDefines.MAX_PLAYERS or 64)-1 do if Players[owner] then
  for u in Players[owner]:Units() do
   out[#out+1]={owner=owner,id=u:GetID(),type=u:GetUnitType(),x=u:GetX(),y=u:GetY(),hp=u:GetCurrHitPoints(),moves=u:GetMoves()}
  end
 end end
 return out
end
local function verifyOriginals(s)
 local unchanged=true
 for _,r in ipairs(s.originals) do
  local u=unit(r.owner,r.id)
  if not u or u:GetUnitType()~=r.type or u:GetX()~=r.x or u:GetY()~=r.y or u:GetCurrHitPoints()~=r.hp or u:GetMoves()~=r.moves then
   unchanged=false;log("ORIGINAL_CHANGED","owner="..r.owner.." id="..r.id)
  end
 end
 check("unrelated units unchanged",unchanged,true)
 local natural=true
 for _,r in ipairs(s.terrain) do if terrain(Map.GetPlotByIndex(r.id))~=r.value then natural=false;log("TERRAIN_CHANGED",r.id) end end
 check("natural plot state unchanged",natural,true)
end
local function players(enemy)
 local owner=Game.GetActivePlayer();assert(owner>=0 and Players[owner]:IsTurnActive(),"Use the active human turn")
 assert(Game.GetAIAutoPlay()==0,"Stop autoplay first")
 assert(not Game.IsGameMultiPlayer(),"Use a disposable single-player game for the deterministic real-roll fixture")
 local ourTeam=Players[owner]:GetTeam()
 if enemy~=nil then
  assert(Players[enemy] and Players[enemy]:IsAlive() and Players[enemy]:GetNumCities()>0 and Teams[ourTeam]:IsAtWar(Players[enemy]:GetTeam()),"Choose an already-hostile living major with a city")
  return owner,enemy
 end
 for other=0,GameDefines.MAX_MAJOR_CIVS-1 do
  if other~=owner and Players[other]:IsAlive() and Players[other]:GetNumCities()>0 and Teams[ourTeam]:IsAtWar(Players[other]:GetTeam()) then return owner,other end
 end
 error("No existing war: use a disposable game already at war; this helper does not declare war or relocate unrelated units")
end
local function usable(p,owner,enemy)
 if not p or p:IsWater() or p:IsMountain() or p:IsCity() or p:GetOwner()~=-1 or p:GetNumUnits()>0 or p:GetImprovementType()~=-1 or p:GetRouteType()~=-1 then return false end
 if p:IsImpassable(Players[owner]:GetTeam()) or p:IsImpassable(Players[enemy]:GetTeam()) then return false end
 local f=GameInfo.Features[p:GetFeatureType()]
 return not(f and (f.NaturalWonder==true or f.NaturalWonder==1))
end
local function findSite(owner,enemy)
 for i=0,Map.GetNumPlots()-1 do
  local target=Map.GetPlotByIndex(i)
  if usable(target,owner,enemy) then
   local clear=true;local halo=ring(target,3)
   for _,p in ipairs(halo) do if p:GetNumUnits()>0 or p:IsCity() or p:GetOwner()~=-1 or p:GetImprovementType()~=-1 then clear=false;break end end
   if clear then for d=0,5 do local source=Map.PlotDirection(target:GetX(),target:GetY(),d)
    if usable(source,owner,enemy) and distance(source,target)==1 then return target,source,halo end
   end end
  end
 end
 error("No isolated natural melee site; use another map instead of editing terrain")
end
local function state()
 local s=assert(M.state,"Call Setup first")
 assert(Game.GetGameTurn()==s.turn,"Do not advance turns between fixture stages")
 assert(Players[s.owner]:IsTurnActive(),"Keep the same active human turn")
 return s
end
local function occupants(s)
 local n=0
 for i=0,s.target:GetNumUnits()-1 do
  local u=s.target:GetUnit(i)
  if u and u:GetCurrHitPoints()>0 then
   assert(tagged(u,s),"Untracked unit entered the target; preserve it and stop the fixture")
   if u:GetOwner()==s.enemy and u:IsCombatUnit() then n=n+1 end
  end
 end
 return n
end
function M.Plan(enemy)
 local owner,other=players(enemy);local target,source,halo=findSite(owner,other)
 log("PLAN","owner="..owner.." enemy="..other.." source="..coords(source).." target="..coords(target).." halo="..#halo)
 return {owner=owner,enemy=other,target=target,source=source,halo=halo}
end
function M.Cleanup()
 local s=M.state;if not s then return end
 assert(not s.pending,"Run Check after combat before cleanup")
 for _,r in ipairs(s.units) do local u=unit(r.owner,r.id);assert(not u or (not u:IsFighting() and not u:IsBusy()),"Combat/mission is still resolving") end
 for _,r in ipairs(s.units) do local u=live(r.owner,r.id);if tagged(u,s) then u:Kill(false,-1) end end
 verifyOriginals(s);M.state=nil
 log("CLEANUP","Only tagged fixture units removed; discard disposable world without saving")
end
local function spawn(s,owner,typeName,p,role,strength,hp)
 local u=assert(Players[owner]:InitUnit(assert(GameInfoTypes[typeName],"Unknown fixture type "..typeName),p:GetX(),p:GetY()))
 u:SetScriptData(TAG..s.id);s.units[#s.units+1]={owner=owner,id=u:GetID(),role=role}
 requireThat("native spawn "..role,at(u,p),true)
 -- The fixture controls unit abilities only. Class/combat-type XML roles remain.
 -- Removing promotions prevents withdrawal, capture, support-fire and kill-heal
 -- promotions from turning a simple primary-victim test into a different mechanic.
 local removed=0
 for row in GameInfo.UnitPromotions() do if u:IsHasPromotion(row.ID) then u:SetHasPromotion(row.ID,false);removed=removed+1 end end
 u:SetBaseCombatStrength(strength)
 if typeName=="UNIT_ARCHER" then u:SetBaseRangedCombatStrength(strength) end
 if owner==s.owner then u:SetMaxHitPointsBase(300) end
 u:SetDamage(hp and u:GetMaxHitPoints()-hp or 0)
 u:SetMadeAttack(false);u:SetMoves(u:MaxMoves());u:SetActivityType(ActivityTypes.ACTIVITY_AWAKE)
 requireThat("legal capacity "..role,u:CanStackAtPlot(p),true)
 requireThat("no withdrawal "..role,u:GetExtraWithdrawal(),0)
 requireThat("no ranged support fire "..role,u:IsRangedSupportFire(),false)
 log("UNIT","role="..role.." owner="..owner.." id="..u:GetID().." type="..typeName.." xy="..coords(p).." hp="..u:GetCurrHitPoints().." strength="..strength.." promotionsRemoved="..removed)
 return u
end
function M.Setup(kind,enemy)
 assert(kind=="protect" or kind=="wounded" or kind=="flank" or kind=="anticav" or kind=="advance","Use protect, wounded, flank, anticav or advance")
 M.Cleanup();local s=M.Plan(enemy)
 M.serial=(M.serial or 0)+1;s.id=kind.."-"..Game.GetGameTurn().."-"..M.serial;s.kind=kind;s.turn=Game.GetGameTurn();s.units={};s.guards={};s.shots=0;s.originals=originals();s.terrain={}
 for _,p in ipairs(s.halo) do s.terrain[#s.terrain+1]={id=p:GetPlotIndex(),value=terrain(p)} end
 M.state=s
 local mounted=kind=="flank" or kind=="anticav"
 local a=spawn(s,s.owner,mounted and "UNIT_HORSEMAN" or "UNIT_WARRIOR",s.source,"attacker",kind=="advance" and 200 or 20)
 s.attacker=a:GetID()
 requireThat("stack rules enabled",a:GetStackRoleInfo().Enabled,true)
 requireThat("attacker flanker role",a:GetStackRoleInfo().Flanker,mounted)
 requireThat("melee attacker no collateral",a:GetStackRoleInfo().CollateralTargets,0)
 local first,second
 if kind=="advance" then
  first=spawn(s,s.enemy,"UNIT_WARRIOR",s.target,"first-low-HP",1,1)
  second=spawn(s,s.enemy,"UNIT_WARRIOR",s.target,"second-low-HP",1,1)
 else
  first=spawn(s,s.enemy,kind=="anticav" and "UNIT_SPEARMAN" or "UNIT_WARRIOR",s.target,"melee",kind=="anticav" and 20 or 50,kind=="wounded" and 1 or nil)
  second=spawn(s,s.enemy,"UNIT_ARCHER",s.target,"ranged",kind=="anticav" and 50 or (kind=="wounded" and 30 or 10))
  requireThat("melee anti-cavalry role",first:GetStackRoleInfo().AntiCavalry,kind=="anticav")
  s.expected=(kind=="wounded" or kind=="flank") and second:GetID() or first:GetID()
 end
 s.guards={first:GetID(),second:GetID()}
 requireThat("two legal enemy occupants",occupants(s),2)
 requireThat("first occupant remains legal",first:CanStackAtPlot(s.target),true)
 requireThat("second occupant remains legal",second:CanStackAtPlot(s.target),true)
 requireThat("target visible",s.target:IsVisible(Players[s.owner]:GetTeam()),true)
 local preview=a:GetStackAttackPreview(s.target,false)
 if s.expected then requireThat("fixture expected preview defender",preview.DefenderID,s.expected) end
 verifyOriginals(s)
 log("READY",kind..": call Fire(), wait for normal melee combat, then Check()"..(kind=="advance" and "; repeat Fire()/Check() once for final defender" or ""))
 return true
end
function M.Fire()
 local s=state();assert(not s.pending,"Check the previous attack first")
 assert(s.shots<(s.kind=="advance" and 2 or 1),"Scenario already complete")
 local a=assert(live(s.owner,s.attacker));assert(not a:IsFighting() and not a:IsBusy(),"Wait for prior combat/mission animation")
 requireThat("attacker remains at source before attack",at(a,s.source),true)
 a:SetMadeAttack(false);a:SetMoves(a:MaxMoves());a:SetActivityType(ActivityTypes.ACTIVITY_AWAKE)
 requireThat("normal melee mission legal",a:CanMoveOrAttackInto(s.target,0,1),true)
 -- The native combat adviser confirms through Game.SelectionListMove. Its
 -- normal confirmation must refer to this fixture attacker, not another unit.
 UI.SelectUnit(a)
 local selected=UI.GetHeadSelectedUnit()
 requireThat("fixture attacker selected for adviser",selected and selected:GetOwner()==s.owner and selected:GetID()==s.attacker or false,true)
 UI.LookAt(s.target)
 local preview=a:GetStackAttackPreview(s.target,false)
 requireThat("preview defender belongs to target enemy",preview.DefenderOwner,s.enemy)
 local d=assert(live(preview.DefenderOwner,preview.DefenderID),"Preview has no live defender")
 requireThat("selected defender on target",at(d,s.target),true)
 if s.expected then requireThat("expected role selected",d:GetID(),s.expected) end
 local attack=a:GetMaxAttackStrength(s.source,s.target,d)
 local defense=d:GetMaxDefenseStrength(s.target,a,s.source,false)
 local hit,retaliation=a:GetMeleeCombatDamage(attack,defense,true,d)
 local b={primary=d:GetID(),before={},attackerHP=a:GetCurrHitPoints(),hit=hit,retaliation=retaliation,count=occupants(s),preview=preview.DirectDamage,attack=attack,defense=defense}
 for _,id in ipairs(s.guards) do local u=live(s.enemy,id);if u then b.before[id]={hp=u:GetCurrHitPoints(),x=u:GetX(),y=u:GetY()} end end
 requireThat("real melee hit positive",hit>0,true)
 requireThat("attacker survives retaliation",retaliation<a:GetCurrHitPoints(),true)
 if s.kind=="advance" then requireThat("selected defender certainly killed",hit>=d:GetCurrHitPoints(),true) end
 s.pending=b
 log("FIRE","case="..s.kind.." shot="..(s.shots+1).." attacker="..a:GetID().." primary="..b.primary.." source="..coords(s.source).." target="..coords(s.target).." combat="..attack.."/"..defense.." mean="..b.preview.." realHit="..hit.." retaliation="..retaliation.." occupants="..b.count)
 a:PushMission(MissionTypes.MISSION_MOVE_TO,s.target:GetX(),s.target:GetY(),0,0,1)
end
function M.Check()
 local s=state();local b=assert(s.pending,"Fire first")
 local a=live(s.owner,s.attacker)
 if a and (a:IsFighting() or a:IsBusy()) then log("WAIT","Attacker combat/mission still resolving; call Check again");return false end
 for _,id in ipairs(s.guards) do
  local u=live(s.enemy,id)
  if u and (u:IsFighting() or u:IsBusy()) then log("WAIT","Defender combat/mission still resolving; call Check again");return false end
 end
 local hasDamageDelta=false
 for id,r in pairs(b.before) do local u=live(s.enemy,id);if (u and u:GetCurrHitPoints() or 0)~=r.hp then hasDamageDelta=true end end
 if a and not a:IsOutOfAttacks() and not hasDamageDelta then
  log("WAIT","Mission has not spent an attack or changed HP; inspect normal combat adviser and confirm intended attacker; pending evidence retained");return false
 end
 local changed,alive=0,0
 for id,r in pairs(b.before) do
  local u=live(s.enemy,id);local hp=u and u:GetCurrHitPoints() or 0
  if hp~=r.hp then changed=changed+1 end
  local expected=id==b.primary and math.max(0,r.hp-b.hit) or r.hp
  check("exact defender HP "..id,hp,expected)
  if u then alive=alive+1;check("survivor remains on target "..id,at(u,s.target),true);check("survivor capacity legal "..id,u:CanStackAtPlot(s.target),true) end
 end
 check("only the preview-selected victim changed",changed,1)
 check("attacker survives",a~=nil,true)
 if a then
  check("attacker exact retaliation HP",a:GetCurrHitPoints(),b.attackerHP-b.retaliation)
  check("attacker capacity legal",a:CanStackAtPlot(a:GetPlot()),true)
  if alive>0 then check("surviving defender blocks advance",at(a,s.source),true)
  else check("last defender cleared allows advance",at(a,s.target),true) end
 end
 check("target live defender count",occupants(s),alive)
 if s.kind=="advance" then
  check("one defender removed this hit",alive,b.count-1)
  if s.shots==0 then check("first kill leaves exactly one defender",alive,1) else check("second kill leaves no defenders",alive,0) end
 end
 verifyOriginals(s);s.pending=nil;s.shots=s.shots+1
 log("RESULT","case="..s.kind.." shot="..s.shots.." previewVictim="..b.primary.." survivors="..alive.." attacker="..(a and coords(a:GetPlot()) or "dead"))
 M.Summary();return M.failed==0
end
function M.Summary() log("SUMMARY",M.passed.." passed; "..M.failed.." failed") end
function M.Try(name,...)
 local fn=assert(M[name],"Unknown helper function");local ok,result=pcall(fn,...)
 if not ok then log("ERROR",name..": "..tostring(result)) end
 return ok,result
end
