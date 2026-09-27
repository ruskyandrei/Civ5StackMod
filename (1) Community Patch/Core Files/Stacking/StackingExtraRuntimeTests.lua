-- Manual, disposable-game coverage. Loading this file only defines functions.
-- Requires include("StackingTests") before invoking a setup function.
-- No events, timers, turn advancement, saves or automatic scenario startup.
StackExtraTests = StackExtraTests or {}
local E = StackExtraTests
local function core()
  assert(StackTests and StackTests.Spawn, "First include('StackingTests')")
  return StackTests
end
local function say(kind, text)
  print("STACKEXTRA|" .. kind .. "|" .. tostring(text))
end
local function check(name, actual, expected)
  return core().Check("extra: " .. name, actual, expected)
end
local function requireCheck(name, actual, expected)
  assert(check(name, actual, expected), "Fixture precondition failed: " .. name)
end
local function setting(name, fallback)
  for r in GameInfo.Stacking_Settings() do
    if r.Name == name then return tonumber(r.Value) end
  end
  return fallback
end
local function unit(owner, id)
  return Players[owner]:GetUnitByID(id)
end
local function at(u, p)
  return u and u:GetX() == p:GetX() and u:GetY() == p:GetY()
end
local function empty(p, water, team)
  return p and p:IsWater() == water and not p:IsMountain()
    and not p:IsCity() and p:GetOwner() == -1 and p:GetNumUnits() == 0
    and (not water or (p:GetTerrainType() == GameInfoTypes.TERRAIN_COAST
      and p:GetFeatureType() == -1 and not p:IsImpassable(team)))
end
local function navalPlotDiagnostic(label, p, team)
  say("NAVAL_PLOT",label .. " x=" .. p:GetX() .. " y=" .. p:GetY()
    .. " terrain=" .. p:GetTerrainType() .. " feature=" .. p:GetFeatureType()
    .. " owner=" .. p:GetOwner() .. " units=" .. p:GetNumUnits()
    .. " water=" .. tostring(p:IsWater()) .. " team=" .. team
    .. " impassable=" .. tostring(p:IsImpassable(team))
    .. " visible=" .. tostring(p:IsVisible(team,false)))
end
local function neighbors(p)
  local a = {}
  for d = 0, 5 do
    local n = Map.PlotDirection(p:GetX(), p:GetY(), d)
    if n then a[#a+1] = n end
  end
  return a
end
local function cities()
  local a = {}
  for i = 0, Map.GetNumPlots()-1 do
    local p = Map.GetPlotByIndex(i)
    if p:IsCity() then a[#a+1] = p end
  end
  return a
end
local function isolated(p, allCities)
  for _, c in ipairs(allCities) do
    if Map.PlotDistance(p:GetX(),p:GetY(),c:GetX(),c:GetY()) < 4 then return false end
  end
  return true
end
local function grantStackTechs(owner)
  local teamID = Players[owner]:GetTeam()
  local team = Teams[teamID]
  E.savedTechs = E.savedTechs or {}
  E.savedTechs[teamID] = E.savedTechs[teamID] or { owner=owner, values={} }
  local saved = E.savedTechs[teamID].values
  for r in GameInfo.Stacking_Technologies() do
    local id = assert(GameInfoTypes[r.TechType], "Unknown stacking technology " .. r.TechType)
    if saved[id] == nil then saved[id] = team:IsHasTech(id) end
    team:SetHasTech(id, true, owner, false, false, true)
  end
end
function E.Cleanup()
  -- Only units tracked by the existing StackTests fixture are removed.
  -- Cities, diplomacy and other tech-grant side effects remain in this disposable world.
  core().Cleanup()
  for teamID, saved in pairs(E.savedTechs or {}) do
    for id, had in pairs(saved.values) do
      Teams[teamID]:SetHasTech(id, had, saved.owner, false, false, true)
    end
  end
  E.savedTechs = nil
  E.state = nil
end
local function begin()
  E.Cleanup()
  local owner, enemy = core().Players()
  grantStackTechs(owner)
  grantStackTechs(enemy)
  Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
  return owner, enemy
end
local function spawn(owner, name, plot)
  local u = core().Spawn(owner, name, plot)
  requireCheck(name .. " spawned on intended plot", at(u,plot), true)
  return u
end
local function snapshot(s)
  s.before = {}
  for _, id in ipairs(s.victims) do
    local u = assert(unit(s.enemy,id))
    s.before[id] = { hp=u:GetCurrHitPoints(), max=u:GetMaxHitPoints() }
  end
end
local function ready(kind)
  say("READY", kind .. "; use the next documented command after a game frame")
end

-- ground: frigate in a friendly two-ship stack fires at a land stack.
-- sea: negative control under the default DOMAIN_SEA collateral exclusion.
function E.SetupNaval(targetDomain)
  targetDomain = targetDomain or "ground"
  assert(targetDomain == "ground" or targetDomain == "sea", "Use 'ground' or 'sea'")
  local owner, enemy = begin()
  local team = Players[owner]:GetTeam()
  if targetDomain == "sea" then
    local enabled = false
    for r in GameInfo.Stacking_CollateralDomains() do
      if r.DomainType == "DOMAIN_SEA" then enabled = tonumber(r.Enabled) ~= 0 end
    end
    requireCheck("sea negative-control configuration", enabled, false)
  end
  local target, source, scoutPlot
  for i = 0, Map.GetNumPlots()-1 do
    local p = Map.GetPlotByIndex(i)
    if empty(p,targetDomain == "sea",team) then
      for _, n in ipairs(neighbors(p)) do
        if empty(n,true,team) then source=n; break end
      end
      if targetDomain == "sea" then
        if source then target=p; break end
      else
        for _, n in ipairs(neighbors(p)) do
          if empty(n,false) then scoutPlot=n; break end
        end
        if source and scoutPlot then target=p; break end
      end
      source=nil; scoutPlot=nil
    end
  end
  assert(target,"Need an empty coast/sea patch for this scenario")
  local attacker = spawn(owner,"UNIT_FRIGATE",source)
  attacker:SetBaseRangedCombatStrength(30)
  local escort = spawn(owner,"UNIT_CARAVEL",source)
  if scoutPlot then spawn(owner,"UNIT_SCOUT",scoutPlot) end
  local kind = targetDomain == "sea" and "UNIT_CARAVEL" or "UNIT_WARRIOR"
  local first = spawn(enemy,kind,target)
  local capacity = first:GetStackingLimit(target)
  local limit = attacker:GetStackRoleInfo().CollateralTargets
  requireCheck("naval collateral role enabled",limit > 0,true)
  requireCheck("naval arena can test cap plus unhit survivor",capacity >= limit+2,true)
  local s = { kind="naval", owner=owner, enemy=enemy, attacker=attacker:GetID(),
    escort=escort:GetID(), escortHP=escort:GetCurrHitPoints(), source=source,
    target=target, targetDomain=targetDomain, victims={ first:GetID() } }
  for i = 2, math.min(capacity,limit+4) do
    s.victims[#s.victims+1] = spawn(enemy,kind,target):GetID()
  end
  -- Keep enough healthy victims to exercise the cap; use any surplus for floor checks.
  if #s.victims >= limit+3 then
    local floorUnit = assert(unit(enemy,s.victims[#s.victims]))
    floorUnit:SetDamage(math.ceil(floorUnit:GetMaxHitPoints()/2))
  end
  requireCheck("naval source legal with friendly escort",attacker:CanStackAtPlot(source),true)
  E.state=s
  ready("naval " .. targetDomain .. ": StackExtraTests.FireNaval(), then CheckNaval() after combat")
end
function E.FireNaval()
  local s=assert(E.state); assert(s.kind == "naval" and not s.fired)
  local a=assert(unit(s.owner,s.attacker))
  local team=Players[s.owner]:GetTeam()
  navalPlotDiagnostic("source",a:GetPlot(),team)
  navalPlotDiagnostic("target",s.target,team)
  say("NAVAL_ATTACKER","id=" .. s.attacker .. " moves=" .. a:GetMoves()
    .. " targetDomain=" .. s.targetDomain .. " atSource=" .. tostring(at(a,s.source)))
  requireCheck("naval can range-strike",a:CanRangeStrikeAt(s.target:GetX(),s.target:GetY()),true)
  local preview=a:GetStackAttackPreview(s.target,true)
  s.primary=preview.DefenderID
  requireCheck("naval primary belongs to arena",unit(s.enemy,s.primary) ~= nil,true)
  snapshot(s)
  local primary=assert(unit(s.enemy,s.primary))
  s.raw=a:GetRangeCombatDamage(primary,nil,true)
  requireCheck("naval positive primary damage",s.raw > 0,true)
  local amount=math.floor(s.raw*setting("CollateralPercent",20)/100)
  if amount > 0 then amount=math.max(amount,setting("CollateralMinimumDamage",1)) end
  local candidates={}
  s.expected={}
  for id,b in pairs(s.before) do
    if id ~= s.primary and s.targetDomain == "ground" then
      local damage=math.min(amount,math.max(0,b.hp-math.ceil(b.max*setting("CollateralHPFloorPercent",50)/100)))
      if damage > 0 then candidates[#candidates+1]={id=id,damage=damage} end
    end
  end
  table.sort(candidates,function(a,b) if a.damage == b.damage then return a.id < b.id end return a.damage > b.damage end)
  local cap=a:GetStackRoleInfo().CollateralTargets
  for i,c in ipairs(candidates) do if i <= cap then s.expected[c.id]=c.damage end end
  requireCheck("naval preview secondary count",preview.CollateralCount,math.min(cap,#candidates))
  say("ROLL","naval raw=" .. s.raw .. ", secondaryAmount=" .. amount)
  s.fired=true
  a:PushMission(MissionTypes.MISSION_RANGE_ATTACK,s.target:GetX(),s.target:GetY(),0,0,1)
end
function E.CheckNaval()
  local s=assert(E.state); assert(s.kind == "naval" and s.fired)
  local a=assert(unit(s.owner,s.attacker))
  assert(not a:IsFighting(),"Wait for combat animation, then call CheckNaval again")
  local changed=0
  for id,b in pairs(s.before) do
    local u=unit(s.enemy,id)
    local hp=u and u:GetCurrHitPoints() or 0
    local expected=id == s.primary and math.max(0,b.hp-s.raw) or b.hp-(s.expected[id] or 0)
    check("naval exact HP " .. id,hp,expected)
    if id ~= s.primary then
      check("naval secondary survives " .. id,u ~= nil,true)
      if hp < b.hp then changed=changed+1 end
    end
  end
  local expectedCount=0
  for _ in pairs(s.expected) do expectedCount=expectedCount+1 end
  check("naval actual secondary count",changed,expectedCount)
  if s.targetDomain == "ground" then check("naval secondary damage occurred",changed > 0,true) end
  check("naval fired from friendly stack",at(a,s.source) and at(unit(s.owner,s.escort),s.source),true)
  check("naval friendly escort unharmed",unit(s.owner,s.escort):GetCurrHitPoints(),s.escortHP)
  core().Summary()
end

-- Guaranteed interception, including a surviving bomber: attack must abort before
-- primary/city/garrison/collateral damage. Use separate setup/fire/check frames.
function E.SetupInterception(cityTarget)
  begin()
  local T=core()
  if cityTarget then T.SetupCityCollateral(false,"UNIT_BOMBER")
  else T.SetupCollateral("UNIT_BOMBER") end
  local old=assert(T.shot)
  local s={kind="interception",owner=old.owner,enemy=old.enemy,attacker=old.attacker,
    target=old.target,victims={},cityTarget=not not cityTarget}
  for id in pairs(old.before) do s.victims[#s.victims+1]=id end
  local bomber=assert(unit(s.owner,s.attacker))
  local capacityProbe=assert(unit(s.enemy,s.victims[1]))
  requireCheck("bombing arena capacity",capacityProbe:GetStackingLimit(s.target) >= #s.victims,true)
  for _,id in ipairs(s.victims) do
    requireCheck("bombing victim remains on intended tile " .. id,at(unit(s.enemy,id),s.target),true)
  end
  bomber:SetMaxHitPointsBase(1000)
  bomber:SetDamage(0)
  for p in GameInfo.UnitPromotions() do
    if tonumber(p.EvasionChange or 0) ~= 0 and bomber:IsHasPromotion(p.ID) then
      bomber:SetHasPromotion(p.ID,false)
    end
  end
  local aaPlot
  for _,p in ipairs(neighbors(s.target)) do
    if not p:IsWater() and not p:IsMountain() and not p:IsCity() and p:GetNumUnits()==0 then aaPlot=p; break end
  end
  assert(aaPlot,"Need a vacant land tile beside the bombing target")
  local aa=spawn(s.enemy,"UNIT_ANTI_AIRCRAFT_GUN",aaPlot)
  for _,name in ipairs({"PROMOTION_INTERCEPTION_1","PROMOTION_INTERCEPTION_2","PROMOTION_INTERCEPTION_3"}) do
    aa:SetHasPromotion(assert(GameInfoTypes[name],"Missing " .. name),true)
  end
  aa:SetDamage(0)
  aa:SetMadeInterception(false)
  s.interceptor=aa:GetID()
  E.state=s
  ready("interception: StackExtraTests.FireInterception(), then CheckInterception() after combat")
end
function E.FireInterception()
  local s=assert(E.state); assert(s.kind == "interception" and not s.fired)
  local bomber=assert(unit(s.owner,s.attacker))
  local aa=assert(unit(s.enemy,s.interceptor))
  requireCheck("bomber evasion zero",bomber:EvasionProbability(),0)
  requireCheck("interception at least 100 percent",aa:CurrInterceptionProbability() >= 100,true)
  requireCheck("AA can intercept now",aa:isOutOfInterceptions(),false)
  -- GetBestInterceptor's second argument is the incoming bomber, as in actual combat.
  local selected=bomber:GetBestInterceptor(s.target,bomber,false,false)
  requireCheck("expected interceptor selected",selected and selected:GetID() or -1,s.interceptor)
  requireCheck("bomber can strike target",bomber:CanRangeStrikeAt(s.target:GetX(),s.target:GetY()),true)
  local preview=bomber:GetStackAttackPreview(s.target,true)
  requireCheck("air preview is conditional",preview.ConditionalOnAirHit,true)
  requireCheck("unintercepted strike would have collateral",preview.CollateralCount > 0,true)
  snapshot(s)
  s.bomberHP=bomber:GetCurrHitPoints()
  local city=s.target:GetPlotCity()
  if s.cityTarget then
    requireCheck("target city ownership intact",city and city:GetOwner() or -1,s.enemy)
    s.cityDamage=city:GetDamage()
  end
  s.fired=true
  bomber:PushMission(MissionTypes.MISSION_RANGE_ATTACK,s.target:GetX(),s.target:GetY(),0,0,1)
end
function E.CheckInterception()
  local s=assert(E.state); assert(s.kind == "interception" and s.fired)
  local bomber=unit(s.owner,s.attacker)
  assert(not bomber or not bomber:IsFighting(),"Wait for combat animation, then retry")
  check("intercepted bomber survives",bomber ~= nil,true)
  check("interception actually damaged bomber",bomber and bomber:GetCurrHitPoints() < s.bomberHP or false,true)
  for id,b in pairs(s.before) do
    local u=unit(s.enemy,id)
    check("aborted bombing leaves target alive " .. id,u ~= nil,true)
    check("aborted bombing leaves HP unchanged " .. id,u and u:GetCurrHitPoints() or 0,b.hp)
  end
  if s.cityTarget then
    local city=s.target:GetPlotCity()
    check("aborted bombing leaves city damage unchanged",city and city:GetDamage() or -1,s.cityDamage)
    check("aborted bombing leaves ownership unchanged",city and city:GetOwner() or -1,s.enemy)
  end
  core().Summary()
end

-- Garrison bookkeeping after an actual Kill and after relocation. This does not
-- assert a combat casualty occurred; combat-caused garrison death remains a separate test.
function E.SetupGarrison()
  local owner,enemy=begin()
  local target,around
  local existing=cities()
  for i=0,Map.GetNumPlots()-1 do
    local p=Map.GetPlotByIndex(i)
    if empty(p,false) and isolated(p,existing) then
      local a={}
      for _,n in ipairs(neighbors(p)) do if empty(n,false) then a[#a+1]=n end end
      if #a == 6 then target=p; around=a; break end
    end
  end
  assert(target,"Need an isolated empty land city site")
  local city=assert(Players[owner]:InitCity(target:GetX(),target:GetY()))
  local s={kind="garrison",owner=owner,enemy=enemy,target=target,around=around,cityID=city:GetID(),guards={}}
  for i=1,3 do
    local u=spawn(owner,"UNIT_WARRIOR",around[1])
    u:SetBaseCombatStrength(i*20)
    u:SetXY(target:GetX(),target:GetY())
    requireCheck("garrison unit placed " .. i,at(u,target),true)
    s.guards[i]=u:GetID()
  end
  local probe=assert(unit(owner,s.guards[1]))
  requireCheck("three garrison candidates are legal",probe:GetStackingLimit(target) >= 3,true)
  E.state=s
  ready("garrison: CheckGarrison('initial'), KillGarrison(), CheckGarrison('death'), MoveGarrison(), CheckGarrison('move'), EmptyGarrison(), CheckGarrison('empty'), ReturnGarrison(), CheckGarrison('return'); separate commands")
end
local function garrisonState()
  local s=assert(E.state); assert(s.kind == "garrison")
  local city=assert(Players[s.owner]:GetCityByID(s.cityID),"Test city missing")
  return s,city
end
function E.CheckGarrison(stage)
  local s,city=garrisonState()
  local expected={initial=s.guards[3],death=s.guards[2],move=s.guards[1],empty=-1,["return"]=s.guards[2]}
  assert(expected[stage] ~= nil,"Unknown garrison stage")
  local g=city:GetGarrisonedUnit()
  check("garrison " .. stage .. " selects expected unit",g and g:GetID() or -1,expected[stage])
  if g then
    check("garrison " .. stage .. " physically in city",at(g,s.target),true)
    local link=g:GetGarrisonedCity()
    check("garrison " .. stage .. " reverse city link",link and link:GetID() or -1,s.cityID)
  end
  if stage ~= "initial" then check("dead former garrison remains absent",unit(s.owner,s.guards[3]) == nil,true) end
  say("CITY_STRENGTH",stage .. "=" .. city:GetStrengthValue())
  core().Summary()
end
function E.KillGarrison()
  local s,city=garrisonState()
  requireCheck("kill intended strongest garrison",city:GetGarrisonedUnit():GetID(),s.guards[3])
  assert(unit(s.owner,s.guards[3])):Kill(false,-1)
end
function E.MoveGarrison()
  local s,city=garrisonState()
  requireCheck("move intended replacement garrison",city:GetGarrisonedUnit():GetID(),s.guards[2])
  assert(unit(s.owner,s.guards[2])):SetXY(s.around[1]:GetX(),s.around[1]:GetY())
end
function E.EmptyGarrison()
  local s,city=garrisonState()
  requireCheck("move final garrison",city:GetGarrisonedUnit():GetID(),s.guards[1])
  assert(unit(s.owner,s.guards[1])):SetXY(s.around[2]:GetX(),s.around[2]:GetY())
end
function E.ReturnGarrison()
  local s=garrisonState()
  assert(unit(s.owner,s.guards[2])):SetXY(s.target:GetX(),s.target:GetY())
end