-- Explicit disposable-game city combat. Definitions only; no automatic action.
-- Stages: SetupGarrison -> FireGarrison -> CheckGarrison (twice), then
-- SetupCapture -> FireCapture -> CheckCapture. Wait for combat between stages.
StackCityCombatTests = StackCityCombatTests or {}
local C=StackCityCombatTests
local TAG="STACKCITYCOMBAT1|"
local function log(k,v) print("STACKCITY|"..k.."|"..tostring(v)) end
local function check(name,actual,expected)
 local pass=actual==expected;log(pass and "PASS" or "FAIL",name.." actual="..tostring(actual).." expected="..tostring(expected))
 C.passed=(C.passed or 0)+(pass and 1 or 0);C.failed=(C.failed or 0)+(pass and 0 or 1);return pass
end
local function requireThat(name,actual,expected) assert(check(name,actual,expected),"precondition: "..name) end
local function unit(owner,id) return Players[owner]:GetUnitByID(id) end
local function live(owner,id)local u=unit(owner,id);return u and u:GetCurrHitPoints()>0 and u or nil end
local function at(u,p)return u and u:GetX()==p:GetX() and u:GetY()==p:GetY() or false end
local function distance(a,b)return Map.PlotDistance(a:GetX(),a:GetY(),b:GetX(),b:GetY())end
local function tagged(u,id)return u and u:GetScriptData()==TAG..id end
local function originals()
 local a={}
 for owner=0,GameDefines.MAX_MAJOR_CIVS-1 do if Players[owner] then for u in Players[owner]:Units() do
  if string.sub(u:GetScriptData()or"",1,#TAG)~=TAG then
   a[#a+1]={owner=owner,id=u:GetID(),type=u:GetUnitType(),x=u:GetX(),y=u:GetY(),hp=u:GetCurrHitPoints(),moves=u:GetMoves()}
  end
 end end end
 return a
end
local function checkOriginals(s)
 local same=true
 for _,r in ipairs(s.originals) do
  local u=unit(r.owner,r.id)
  if not u or u:GetUnitType()~=r.type or u:GetX()~=r.x or u:GetY()~=r.y or u:GetCurrHitPoints()~=r.hp or u:GetMoves()~=r.moves then
   same=false;log("ORIGINAL_CHANGED","owner="..r.owner.." id="..r.id)
  end
 end
 check("existing units unchanged",same,true)
end
local function players()
 local human=Game.GetActivePlayer();assert(human>=0 and Players[human]:IsTurnActive(),"use active human turn")
 assert(Game.GetAIAutoPlay()==0,"no autoplay during manual combat")
 for enemy=0,GameDefines.MAX_MAJOR_CIVS-1 do
  if enemy~=human and Players[enemy]:IsAlive() and Players[enemy]:GetTeam()~=Players[human]:GetTeam() and Players[enemy]:GetNumCities()>0 then return human,enemy end
 end
 error("Need another living major with an existing city, so the fixture city is not its last/capital city")
end
local function freeLand(p,team)
 if not p or p:IsWater() or p:IsMountain() or p:IsCity() or p:GetOwner()~=-1 or p:GetNumUnits()~=0 or p:GetImprovementType()~=-1 or p:GetRouteType()~=-1 or p:IsImpassable(team) then return false end
 local f=GameInfo.Features[p:GetFeatureType()]
 return not(f and (f.NaturalWonder==true or f.NaturalWonder==1))
end
local function findSite(enemy)
 local cities={};for i=0,Map.GetNumPlots()-1 do local p=Map.GetPlotByIndex(i);if p:IsCity() then cities[#cities+1]=p end end
 local team=Players[enemy]:GetTeam()
 for i=0,Map.GetNumPlots()-1 do
  local p=Map.GetPlotByIndex(i)
  if freeLand(p,team) and p:GetFeatureType()==-1 and p:GetResourceType(-1)==-1 and Players[enemy]:CanFound(p:GetX(),p:GetY()) then
   local clear=true
   for _,city in ipairs(cities)do if distance(p,city)<4 then clear=false;break end end
   if clear then for dx=-2,2 do for dy=-2,2 do
    local q=Map.PlotXYWithRangeCheck(p:GetX(),p:GetY(),dx,dy,2)
    if q and (q:GetNumUnits()>0 or q:IsCity() or q:GetOwner()~=-1 or q:GetImprovementType()~=-1)then clear=false end
   end end end
   if clear then
    local around={};for d=0,5 do local q=Map.PlotDirection(p:GetX(),p:GetY(),d);if freeLand(q,team)then around[#around+1]=q end end
    if #around>=2 then return p,around[1],around[2] end
   end
  end
 end
 error("No legal isolated natural city site; use another disposable map, never edit terrain for this test")
end
function C.CleanupUnits()
 local s=C.state;if not s then return end
 for _,r in ipairs(s.units)do local u=unit(r.owner,r.id);assert(not u or not u:IsFighting(),"combat is still resolving")end
 for _,r in ipairs(s.units)do local u=unit(r.owner,r.id);if tagged(u,s.id)and u:GetCurrHitPoints()>0 then u:Kill(false,-1)end end
 s.units={}
 log("cleanup","removed tracked tagged fixture units only; helper-created city/war remain; reload baseline for full restoration")
end
local function begin(kind)
 local owner,enemy=players();local prior=C.state;local target,source,staging
 if prior and prior.createdCity then
  local city=prior.target:GetPlotCity()
  if city and city:GetOwner()==enemy and city:GetID()==prior.cityID then
   local clear=true
   for _,p in ipairs({prior.target,prior.source,prior.staging})do for i=0,p:GetNumUnits()-1 do
    local u=p:GetUnit(i);if u and u:GetCurrHitPoints()>0 and not tagged(u,prior.id)then clear=false end
   end end
   if clear then target,source,staging=prior.target,prior.source,prior.staging end
  end
 end
 if not target then target,source,staging=findSite(enemy) end
 if prior then C.CleanupUnits() end
 C.serial=(C.serial or 0)+1;C.passed=0;C.failed=0
 local s={id=kind.."-"..Game.GetGameTurn().."-"..C.serial,kind=kind,owner=owner,enemy=enemy,target=target,source=source,staging=staging,turn=Game.GetGameTurn(),units={},guards={},originals=originals(),shots={}}
 C.state=s
 Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
 if not target:IsCity()then
  assert(Players[enemy]:CanFound(target:GetX(),target:GetY()),"normal CanFound precondition changed")
  Players[enemy]:Found(target:GetX(),target:GetY())
 end
 local city=assert(target:GetPlotCity(),"normal Found did not produce a city")
 assert(city:GetOwner()==enemy,"unexpected test-city owner")
 s.cityID=city:GetID();s.createdCity=true
 for i=0,target:GetNumUnits()-1 do local u=target:GetUnit(i);assert(not u or u:GetCurrHitPoints()<=0,"new city has an untracked occupant; preserve it and reload another fixture")end
 city:SetDamage(0)
 log("setup-city","kind="..kind.." owner="..enemy.." id="..s.cityID.." xy="..target:GetX()..","..target:GetY().." maxHP="..city:GetMaxHitPoints().." existingUnits="..#s.originals)
 return s,city
end
local function spawn(s,owner,typeName,p,role)
 local u=assert(Players[owner]:InitUnit(assert(GameInfoTypes[typeName],"unknown unit type"),p:GetX(),p:GetY()))
 u:SetScriptData(TAG..s.id);s.units[#s.units+1]={owner=owner,id=u:GetID(),role=role}
 requireThat("spawn placement "..role,at(u,p),true);return u
end
local function guard(s,typeName,strength,role,hp)
 local u=spawn(s,s.enemy,typeName,s.staging,role)
 u:SetBaseCombatStrength(strength)
 if hp then u:SetDamage(u:GetMaxHitPoints()-hp)end
 requireThat("city has free combat slot before "..role,u:CanStackAtPlot(s.target),true)
 u:SetXY(s.target:GetX(),s.target:GetY())
 requireThat("city occupancy legal "..role,u:CanStackAtPlot(s.target),true)
 s.guards[#s.guards+1]=u:GetID();return u
end
local function cityState(kind)
 local s=assert(C.state,"set up first");assert(s.kind==kind,"wrong scenario")
 assert(Game.GetGameTurn()==s.turn,"do not advance turns between combat stages")
 return s,assert(s.target:GetPlotCity(),"fixture city missing")
end
local function countEnemyCombat(s)
 local count=0
 for i=0,s.target:GetNumUnits()-1 do local u=s.target:GetUnit(i)
  if u and u:GetOwner()==s.enemy and u:GetCurrHitPoints()>0 and u:IsCombatUnit()then count=count+1 end
 end
 return count
end
local function absorptionBounds(cityDamage,cityMax,garrisonMax)
 -- R = D - floor(D*a/(C+a)) = ceil(D*C/(C+a)), a=2*garrisonMax.
 -- Lua exposes R but not the direct garrison share, so retain the exact
 -- integer interval rather than pretending a unique inverse always exists.
 if cityDamage<=0 then return 0,0 end
 local denominator=cityMax+2*garrisonMax
 local minRaw=math.floor((cityDamage-1)*denominator/cityMax)+1
 local maxRaw=math.floor(cityDamage*denominator/cityMax)
 return minRaw-cityDamage,maxRaw-cityDamage
end
local function snapshot(s,city)
 local b={cityDamage=city:GetDamage(),cityMax=city:GetMaxHitPoints(),owner=city:GetOwner(),cityID=city:GetID(),cityStrength=city:GetStrengthValue(),units={}}
 local g=city:GetGarrisonedUnit();b.garrison=g and g:GetID()or-1
 for _,id in ipairs(s.guards)do local u=live(s.enemy,id);if u then b.units[id]={hp=u:GetCurrHitPoints(),max=u:GetMaxHitPoints()}end end
 return b
end
function C.SetupGarrison(options)
 options=options or {};local s,city=begin("garrison")
 local enabled=false;for row in GameInfo.CustomModOptions()do if row.Name=="CORE_GARRISON_DAMAGE_ABSORPTION"then enabled=tonumber(row.Value)~=0 end end
 requireThat("garrison absorption enabled",enabled,true)
 local strong=guard(s,"UNIT_WARRIOR",40,"designated-one-hp",1)
 local replacement=guard(s,"UNIT_WARRIOR",20,"healthy-replacement")
 s.strong=strong:GetID();s.replacement=replacement:GetID()
 local a=spawn(s,s.owner,"UNIT_CROSSBOWMAN",s.source,"ranged-attacker")
 a:SetBaseRangedCombatStrength(options.rangedStrength or 30);s.attacker=a:GetID()
 requireThat("probe does not inflict collateral",a:GetStackRoleInfo().CollateralTargets,0)
 requireThat("strong unit designated despite1HP",city:GetGarrisonedUnit()and city:GetGarrisonedUnit():GetID()or-1,s.strong)
 requireThat("two city combat occupants",countEnemyCombat(s),2)
 checkOriginals(s)
 log("READY","FireGarrison(), wait for combat, CheckGarrison(); then repeat FireGarrison()/CheckGarrison() for replacement absorption")
end
function C.FireGarrison()
 local s,city=cityState("garrison")
 assert(#s.shots<2,"two-shot test already fired")
 if #s.shots>0 then assert(s.shots[#s.shots].checked,"check previous shot first")end
 local a=assert(live(s.owner,s.attacker));assert(not a:IsFighting(),"wait for combat")
 -- Refresh only this fixture attacker between the explicitly requested shots.
 a:SetMadeAttack(false);a:SetMoves(a:MaxMoves());a:SetActivityType(ActivityTypes.ACTIVITY_AWAKE)
 requireThat("range mission is legal",a:CanRangeStrikeAt(s.target:GetX(),s.target:GetY()),true)
 local b=snapshot(s,city);local g=assert(live(s.enemy,b.garrison),"missing designated garrison")
 local expectedID=#s.shots==0 and s.strong or s.replacement
 requireThat("shot targets expected city garrison",b.garrison,expectedID)
 local roll=a:GetRangeCombatDamage(nil,city,true)
 b.shareMin,b.shareMax=absorptionBounds(roll,b.cityMax,g:GetMaxHitPoints())
 b.rawCityDamage=roll;b.actualCityDamage=math.min(roll,b.cityMax-b.cityDamage-1)
 b.attackerHP=a:GetCurrHitPoints();b.phase=#s.shots+1
 requireThat("shot causes positive city damage",b.actualCityDamage>0,true)
 requireThat("direct garrison absorption positive",b.shareMin>0,true)
 if b.phase==1 then requireThat("direct absorption guarantees1HP garrison death",b.shareMin>=g:GetCurrHitPoints(),true)
 else requireThat("replacement survives second absorption",b.shareMax<g:GetCurrHitPoints(),true)end
 s.shots[#s.shots+1]=b
 log("FIRE_RANGE","phase="..b.phase.." cityBefore="..b.cityDamage.." cityDelta="..b.actualCityDamage.." rawCity="..roll.." garrison="..b.garrison.." shareInterval="..b.shareMin..".."..b.shareMax.." cityStrength="..b.cityStrength)
 a:PushMission(MissionTypes.MISSION_RANGE_ATTACK,s.target:GetX(),s.target:GetY(),0,0,1)
end
function C.CheckGarrison()
 local s,city=cityState("garrison");local b=assert(s.shots[#s.shots],"fire first")
 local a=assert(live(s.owner,s.attacker));assert(not a:IsFighting(),"wait for combat animation")
 local failures=C.failed
 check("city owner unchanged by ranged attack",city:GetOwner(),s.enemy)
 check("exact city damage after range shot",city:GetDamage(),b.cityDamage+b.actualCityDamage)
 check("ranged attacker stays at source",at(a,s.source),true)
 check("ranged attacker takes no combat damage",a:GetCurrHitPoints(),b.attackerHP)
 check("former garrison is dead after actual combat",live(s.enemy,s.strong)==nil,true)
 local replacement=live(s.enemy,s.replacement)
 check("replacement remains alive",replacement~=nil,true)
 local g=city:GetGarrisonedUnit()
 check("replacement designated after combat",g and g:GetID()or-1,s.replacement)
 if replacement then
  local link=replacement:GetGarrisonedCity()
  check("replacement reverse-city link",link and link:GetID()or-1,city:GetID())
  local expected=b.units[s.replacement].hp
  if b.phase==1 then
   check("non-garrison replacement takes zero first-shot damage",replacement:GetCurrHitPoints(),expected)
   check("city strength falls with weaker replacement",city:GetStrengthValue()<b.cityStrength,true)
  else
   local damage=expected-replacement:GetCurrHitPoints()
   check("replacement receives second-shot absorption",damage>=b.shareMin and damage<=b.shareMax,true)
   log("ABSORPTION_OBSERVED","replacement="..s.replacement.." damage="..damage.." independently bounded="..b.shareMin..".."..b.shareMax)
  end
 end
 check("one surviving enemy combat occupant",countEnemyCombat(s),1)
 checkOriginals(s)
 b.checked=C.failed==failures
 log("SUMMARY","phase="..b.phase.." checked="..tostring(b.checked).." passed="..C.passed.." failed="..C.failed)
 return b.checked
end
function C.SetupCapture(options)
 options=options or {};local s,city=begin("capture")
 guard(s,"UNIT_WARRIOR",20,"healthy-melee")
 guard(s,"UNIT_ARCHER",5,"healthy-ranged")
 local a=spawn(s,s.owner,"UNIT_WARRIOR",s.source,"city-capturer");a:SetBaseCombatStrength(options.attackerStrength or 60);s.attacker=a:GetID()
 city:SetDamage(city:GetMaxHitPoints()-1)
 requireThat("capture fixture has two healthy combat occupants",countEnemyCombat(s),2)
 for _,id in ipairs(s.guards)do local u=assert(live(s.enemy,id));requireThat("capture occupant full HP "..id,u:GetCurrHitPoints(),u:GetMaxHitPoints())end
 checkOriginals(s)
 log("READY","FireCapture(), wait for actual melee combat/conquest, then CheckCapture(); resolve normal conquest UI without razing/liberating test city")
end
function C.FireCapture()
 local s,city=cityState("capture");assert(not s.capture,"capture already ordered")
 local a=assert(live(s.owner,s.attacker));assert(not a:IsFighting(),"wait for combat")
 a:SetMadeAttack(false);a:SetMoves(a:MaxMoves());a:SetActivityType(ActivityTypes.ACTIVITY_AWAKE)
 requireThat("capturer is adjacent",distance(a:GetPlot(),s.target),1)
 requireThat("normal move-or-attack legal",a:CanMoveOrAttackInto(s.target,0,1),true)
 local b=snapshot(s,city);local strength=a:GetMaxAttackStrength(a:GetPlot(),s.target,nil)
 local cityHit,retaliation=a:GetMeleeCombatDamageCity(strength,city,true)
 b.rawCityDamage=cityHit;b.cityHit=math.min(cityHit,b.cityMax-b.cityDamage);b.retaliation=retaliation;b.attackerHP=a:GetCurrHitPoints()
 requireThat("melee hit reaches remaining city HP",b.cityHit,b.cityMax-b.cityDamage)
 requireThat("capturer survives predicted retaliation",retaliation<a:GetCurrHitPoints(),true)
 local g=assert(city:GetGarrisonedUnit(),"capture test requires a designated garrison")
 b.shareMin,b.shareMax=absorptionBounds(cityHit,b.cityMax,g:GetMaxHitPoints())
 requireThat("healthy garrison would survive direct absorption without capture",b.shareMax<g:GetCurrHitPoints(),true)
 s.capture=b
 log("FIRE_CAPTURE","oldCityID="..b.cityID.." owner="..b.owner.." cityHP="..(b.cityMax-b.cityDamage).." rawCity="..cityHit.." actualCityHit="..b.cityHit.." retaliation="..retaliation.." occupants="..countEnemyCombat(s).." garrisonAbsorptionMax="..b.shareMax)
 a:PushMission(MissionTypes.MISSION_MOVE_TO,s.target:GetX(),s.target:GetY(),0,0,1)
end
function C.CheckCapture()
 local s,city=cityState("capture");local b=assert(s.capture,"fire first")
 local a=live(s.owner,s.attacker);assert(not a or not a:IsFighting(),"wait for melee combat")
 check("city ownership changed by melee combat",city:GetOwner(),s.owner)
 check("capturer survives",a~=nil,true)
 if a then
  check("capturer advances into captured city",at(a,s.target),true)
  check("capturer HP matches predicted retaliation",a:GetCurrHitPoints(),b.attackerHP-b.retaliation)
  check("capturer city occupancy legal",a:CanStackAtPlot(s.target),true)
 end
 for _,id in ipairs(s.guards)do check("old city combat occupant removed "..id,live(s.enemy,id)==nil,true)end
 check("no old-owner combat survivor in city",countEnemyCombat(s),0)
 local capturePercent=assert(tonumber(GameDefines.CITY_CAPTURE_DAMAGE_PERCENT),"missing city capture damage define")
 local cap=math.floor(city:GetMaxHitPoints()*capturePercent/100);if cap>=city:GetMaxHitPoints()then cap=math.max(0,city:GetMaxHitPoints()-1)end
 check("captured-city damage matches acquisition rule",city:GetDamage(),math.min(b.cityMax,cap))
 local g=city:GetGarrisonedUnit()
 check("captured-city garrison belongs to new owner",g and g:GetOwner()or-1,s.owner)
 if g then local link=g:GetGarrisonedCity();check("captured garrison reverse-city link",link and link:GetID()or-1,city:GetID())end
 checkOriginals(s)
 log("CAPTURE_STATE","oldCityID="..b.cityID.." newCityID="..city:GetID().." owner="..city:GetOwner().." damage="..city:GetDamage().." remainingEnemyCombat="..countEnemyCombat(s))
 log("SUMMARY","passed="..C.passed.." failed="..C.failed)
 return C.failed==0
end
function C.Try(name,...)
 local fn=assert(C[name],"unknown helper function");local ok,result=pcall(fn,...)
 if not ok then log("ERROR",name..": "..tostring(result))end
 return ok,result
end
log("loaded","SetupGarrison/FireGarrison/CheckGarrison; SetupCapture/FireCapture/CheckCapture; definitions only")
