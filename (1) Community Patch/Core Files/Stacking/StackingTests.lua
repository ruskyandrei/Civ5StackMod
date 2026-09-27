-- Manual FireTuner test harness. Never runs automatically. Use a disposable game.
-- include("StackingTests"); StackTests.Capacity(); StackTests.Defenders()
-- Results are emitted to Lua.log as STACKTEST|PASS/FAIL records.
StackTests = StackTests or { spawned = {}, passed = 0, failed = 0 }
local T = StackTests
local function log(kind, name, actual, expected)
  print("STACKTEST|" .. kind .. "|" .. name .. "|actual=" .. tostring(actual) .. "|expected=" .. tostring(expected))
end
function T.Check(name, actual, expected)
  local pass = actual == expected
  if pass then T.passed = T.passed + 1 else T.failed = T.failed + 1 end
  log(pass and "PASS" or "FAIL", name, actual, expected)
  return pass
end
function T.Summary() log("SUMMARY", "checks", T.passed .. " passed", T.failed .. " failed") end
function T.Cleanup()
  for _, v in ipairs(T.spawned) do
    local u = Players[v.owner]:GetUnitByID(v.id)
    assert(not u or (not u:IsBusy() and not u:IsFighting()), "Wait for fixture combat/missions before Cleanup")
  end
  for _, v in ipairs(T.spawned) do
    local u = Players[v.owner]:GetUnitByID(v.id)
    if u then u:Kill(false, -1) end
  end
  T.spawned = {}
  T.shot = nil
end
function T.Spawn(owner, unitType, plot)
  local id = GameInfoTypes[unitType]
  assert(id, "Unknown test unit " .. unitType)
  local u = Players[owner]:InitUnit(id, plot:GetX(), plot:GetY())
  assert(u, "Unit creation failed: " .. unitType)
  table.insert(T.spawned, { owner = owner, id = u:GetID() })
  assert(u:GetX() == plot:GetX() and u:GetY() == plot:GetY(), "Unit relocated during fixture creation: " .. unitType)
  return u
end
local function plain(p)
  local team = Players[Game.GetActivePlayer()]:GetTeam()
  return p and not p:IsWater() and not p:IsMountain() and not p:IsCity()
    and not p:IsImpassable(team) and p:GetNumUnits() == 0 and p:GetOwner() == -1
end
function T.Plots(cityLocation)
  -- City initialization does not enforce founding distance. Check it before mutation.
  local cities = {}
  if cityLocation then
    for i = 0, Map.GetNumPlots() - 1 do
      local p = Map.GetPlotByIndex(i)
      if p:IsCity() then cities[#cities+1] = p end
    end
  end
  local function isolated(p)
    for _, c in ipairs(cities) do
      if Map.PlotDistance(p:GetX(),p:GetY(),c:GetX(),c:GetY()) < 4 then return false end
    end
    return true
  end
  for i = 0, Map.GetNumPlots() - 1 do
    local p = Map.GetPlotByIndex(i)
    if plain(p) then
      local around = {}
      for d = 0, 5 do
        local n = Map.PlotDirection(p:GetX(), p:GetY(), d)
        if plain(n) then table.insert(around, n) end
      end
      if #around == 6 then
        if cityLocation == "source" then
          for j, n in ipairs(around) do
            if isolated(n) then around[1],around[j]=around[j],around[1]; return p,around end
          end
        elseif not cityLocation or isolated(p) then return p,around end
      end
    end
  end
  error("No empty passable land patch with the required city spacing exists")
end
function T.Players()
  local active = Game.GetActivePlayer()
  assert(active >= 0, "Run tests inside a loaded game")
  for p = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
    if p ~= active and Players[p]:IsAlive() and Players[p]:GetTeam() ~= Players[active]:GetTeam() then return active, p end
  end
  error("Need two living independent major civilizations")
end
local function setting(name, fallback)
  for r in GameInfo.Stacking_Settings() do if r.Name == name then return r.Value end end
  return fallback
end
function T.Capacity()
  T.Cleanup()
  local owner, other = T.Players()
  local target, adjacent = T.Plots()
  local team = Teams[Players[owner]:GetTeam()]
  local probe = T.Spawn(owner, "UNIT_WARRIOR", adjacent[1])
  local otherProbe = T.Spawn(other, "UNIT_WARRIOR", adjacent[4])
  local otherBefore = otherProbe:GetStackingLimit(target)
  local techs, saved = {}, {}
  for r in GameInfo.Stacking_Technologies() do
    table.insert(techs, { id = GameInfoTypes[r.TechType], name = r.TechType, bonus = r.CapacityBonus })
  end
  table.sort(techs, function(a,b) return a.id < b.id end)
  for _,t in ipairs(techs) do
    saved[t.id] = team:IsHasTech(t.id)
    team:SetHasTech(t.id, false, owner, false, false, true)
  end
  local base = setting("BaseCapacity",2) + setting("LandCapacityBonus",0)
  local maximum = setting("MaximumCapacity",9)
  local expected = math.min(maximum,math.max(1,base))
  T.Check("base capacity", probe:GetStackingLimit(target), expected)
  -- Test capacity as actual occupants arrive, including the full-stack boundary.
  local occupants = {}
  for i = 1, expected do
    T.Check("slot available before occupant " .. i, probe:CanStackAtPlot(target), true)
    table.insert(occupants,T.Spawn(owner,"UNIT_WARRIOR",target))
  end
  T.Check("full stack rejects new combat unit", probe:CanStackAtPlot(target), false)
  for i,u in ipairs(occupants) do T.Check("existing full-stack unit remains legal " .. i,u:CanStackAtPlot(target),true) end
  local civilian = T.Spawn(owner,"UNIT_WORKER",target)
  T.Check("civilian separate from combat capacity",civilian:CanStackAtPlot(target),true)
  local cumulative = base
  for _,t in ipairs(techs) do
    team:SetHasTech(t.id,true,owner,false,false,true)
    cumulative = cumulative + t.bonus
    T.Check("unlock " .. t.name,probe:GetStackingLimit(target),math.min(maximum,math.max(1,cumulative)))
    T.Check("other team unaffected " .. t.name,otherProbe:GetStackingLimit(target),otherBefore)
    team:SetHasTech(t.id,true,owner,false,false,true)
    T.Check("repeated tech grant " .. t.name,probe:GetStackingLimit(target),math.min(maximum,math.max(1,cumulative)))
  end
  for _,t in ipairs(techs) do team:SetHasTech(t.id,false,owner,false,false,true) end
  cumulative = base
  for i = #techs,1,-1 do
    local t = techs[i]
    team:SetHasTech(t.id,true,owner,false,false,true)
    cumulative = cumulative + t.bonus
    T.Check("reverse-order unlock " .. t.name,probe:GetStackingLimit(target),math.min(maximum,math.max(1,cumulative)))
  end
  for _,t in ipairs(techs) do team:SetHasTech(t.id,saved[t.id],owner,false,false,true) end
  T.Cleanup()
  T.Summary()
end
function T.Defenders()
  T.Cleanup()
  local owner, enemy = T.Players()
  Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
  local target, adjacent = T.Plots()
  local cavalry = T.Spawn(owner,"UNIT_HORSEMAN",adjacent[1])
  local melee = T.Spawn(enemy,"UNIT_WARRIOR",target)
  local ranged = T.Spawn(enemy,"UNIT_ARCHER",target)
  local preview = cavalry:GetStackAttackPreview(target,false)
  T.Check("cavalry bypass chooses ranged",preview.DefenderID,ranged:GetID())
  local interceptor = T.Spawn(enemy,"UNIT_SPEARMAN",target)
  preview = cavalry:GetStackAttackPreview(target,false)
  T.Check("anti-cavalry blocks bypass",preview.DefenderID,interceptor:GetID())
  interceptor:Kill(false,-1)
  local infantry = T.Spawn(owner,"UNIT_WARRIOR",adjacent[2])
  melee:SetDamage(melee:GetMaxHitPoints()-1)
  preview = infantry:GetStackAttackPreview(target,false)
  T.Check("healthy ranged before nearly dead melee",preview.DefenderID,ranged:GetID())
  T.Cleanup()
  T.Summary()
end
function T.SetupCollateral(unitType)
  T.Cleanup()
  local owner, enemy = T.Players()
  Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
  local isAir = GameInfo.Units[GameInfoTypes[unitType or "UNIT_CATAPULT"]].Domain == "DOMAIN_AIR"
  local target, adjacent = T.Plots(isAir and "source" or nil)
  if isAir then
    local city = Players[owner]:InitCity(adjacent[1]:GetX(),adjacent[1]:GetY())
    assert(city and adjacent[1]:GetPlotCity() and adjacent[1]:GetPlotCity():GetOwner()==owner, "Unable to create valid spaced airbase")
  end
  local attacker = T.Spawn(owner,unitType or "UNIT_CATAPULT",adjacent[1])
  local protector = T.Spawn(owner,"UNIT_WARRIOR",adjacent[1])
  local victims = {}
  for i = 1,6 do table.insert(victims,T.Spawn(enemy,"UNIT_WARRIOR",target)) end
  victims[4]:SetDamage(math.floor(victims[4]:GetMaxHitPoints()/2))
  victims[5]:SetDamage(victims[5]:GetMaxHitPoints()-3)
  victims[6]:SetMaxHitPointsBase(101)
  victims[6]:SetDamage(48)
  local preview = attacker:GetStackAttackPreview(target,true)
  assert(T.Check("stacked ranged unit can fire",attacker:CanRangeStrikeAt(target:GetX(),target:GetY()),true), "Fixture has no legal ranged shot")
  T.Check("collateral victim cap",preview.CollateralCount <= attacker:GetStackRoleInfo().CollateralTargets,true)
  T.Check("collateral produces secondary damage",preview.CollateralCount > 0,true)
  local before = {}
  for _,u in ipairs(victims) do before[u:GetID()] = { hp=u:GetCurrHitPoints(), max=u:GetMaxHitPoints() } end
  for _,v in ipairs(preview.Collateral) do
    T.Check("primary excluded " .. v.UnitID,v.UnitID ~= preview.DefenderID,true)
    T.Check("floor preview " .. v.UnitID,v.HPAfter >= math.ceil(v.MaxHP*setting("CollateralHPFloorPercent",50)/100),true)
  end
  T.shot = { owner=owner, enemy=enemy, attacker=attacker:GetID(), target=target, before=before, primary=preview.DefenderID, preview=preview }
  print("STACKTEST|READY|collateral scenario|call StackTests.Fire(), then StackTests.CheckShot() after animations")
  T.Summary()
end
function T.Fire()
  local s = assert(T.shot,"Set up a collateral scenario first")
  local u = assert(Players[s.owner]:GetUnitByID(s.attacker))
  u:PushMission(MissionTypes.MISSION_RANGE_ATTACK,s.target:GetX(),s.target:GetY(),0,0,1)
end
function T.CheckShot()
  local s = assert(T.shot)
  local changed = 0
  for id,b in pairs(s.before) do
    if id ~= s.primary then
      local u = Players[s.enemy]:GetUnitByID(id)
      T.Check("secondary survives " .. id,u ~= nil,true)
      if u then
        if u:GetCurrHitPoints() < b.hp then changed = changed + 1 end
        T.Check("secondary HP floor " .. id,u:GetCurrHitPoints() >= math.min(b.hp,math.ceil(b.max*setting("CollateralHPFloorPercent",50)/100)),true)
        log("DAMAGE","secondary " .. id,b.hp-u:GetCurrHitPoints(),"limited collateral")
      end
    end
  end
  local u = Players[s.owner]:GetUnitByID(s.attacker)
  T.Check("actual secondary hit count bounded",changed <= u:GetStackRoleInfo().CollateralTargets,true)
  T.Check("actual secondary damage occurred",changed > 0,true)
  T.Summary()
end
print("StackTests loaded. Manual disposable-game tests only; no scenario started.")
-- Additional runtime checks; these calculate expected collateral independently
-- from the shared preview, using the deterministic real attack roll.
function T.RecordShotRoll()
  local s = assert(T.shot)
  local attacker = assert(Players[s.owner]:GetUnitByID(s.attacker))
  local primary = s.primary >= 0 and Players[s.enemy]:GetUnitByID(s.primary) or nil
  local city = s.target:GetPlotCity()
  s.rawDamage = attacker:GetRangeCombatDamage(primary,city,true)
  s.city = city
  s.garrison = city and city:GetGarrisonedUnit() and city:GetGarrisonedUnit():GetID() or -1
  local base = math.floor(s.rawDamage * setting("CollateralPercent",20)/100)
  local protected = attacker:GetStackAttackPreview(s.target,true).CityProtection
  local amount = math.floor(base*(100-protected)/100)
  if base > 0 and protected < 100 then amount = math.max(amount,setting("CollateralMinimumDamage",1)) end
  local eligible = {}
  for id,b in pairs(s.before) do
    if id ~= s.primary and id ~= s.garrison then
      local damage = math.min(amount,math.max(0,b.hp-math.ceil(b.max*setting("CollateralHPFloorPercent",50)/100)))
      if damage > 0 then table.insert(eligible,{id=id,damage=damage}) end
    end
  end
  table.sort(eligible,function(a,b) if a.damage == b.damage then return a.id < b.id end return a.damage > b.damage end)
  s.expectedDamage = {}
  for i,v in ipairs(eligible) do
    if i <= attacker:GetStackRoleInfo().CollateralTargets then s.expectedDamage[v.id] = v.damage end
  end
  print("STACKTEST|ROLL|primary raw damage|actual=" .. s.rawDamage .. "|cityProtection=" .. protected)
end
local previousFire = T.Fire
function T.Fire()
  local s = assert(T.shot,"Set up a collateral scenario first")
  assert(not s.fired,"This shot has already been requested; CheckShot before another setup")
  local attacker = assert(Players[s.owner]:GetUnitByID(s.attacker))
  assert(not attacker:IsBusy() and not attacker:IsFighting(),"Wait for prior combat/mission animation")
  assert(attacker:CanRangeStrikeAt(s.target:GetX(),s.target:GetY()),"Fixture has no legal ranged shot")
  T.RecordShotRoll()
  s.cityDamageBefore = s.city and s.city:GetDamage() or nil
  s.fired = true
  previousFire()
end
local previousCheck = T.CheckShot
function T.CheckShot()
  local s = assert(T.shot)
  assert(s.fired,"Fire before checking a shot")
  if s.checked then return T.failed == 0 end
  local attacker = Players[s.owner]:GetUnitByID(s.attacker)
  if attacker and (attacker:IsBusy() or attacker:IsFighting()) then
    print("STACKTEST|WAIT|Attacker combat/mission still resolving; call CheckShot again"); return false
  end
  local changed = s.city and s.city:GetDamage() ~= s.cityDamageBefore or false
  for id,b in pairs(s.before) do
    local u = Players[s.enemy]:GetUnitByID(id)
    if u and (u:IsBusy() or u:IsFighting()) then
      print("STACKTEST|WAIT|Defender combat/mission still resolving; call CheckShot again"); return false
    end
    if (u and u:GetCurrHitPoints() or 0) ~= b.hp then changed = true end
  end
  if attacker and not attacker:IsOutOfAttacks() and not changed then
    print("STACKTEST|WAIT|Mission has not spent an attack or changed HP; pending evidence retained"); return false
  end
  if not s.city then previousCheck() end
  local citySecondaryHits = 0
  for id,b in pairs(s.before) do
    local unit = Players[s.enemy]:GetUnitByID(id)
    if id == s.primary then
      T.Check("primary resolves predicted roll " .. id,unit and unit:GetCurrHitPoints() or 0,math.max(0,b.hp-s.rawDamage))
    elseif id ~= s.garrison then
      T.Check("secondary survives exact test " .. id,unit ~= nil,true)
      if unit then
        if not s.city then
          T.Check("exact collateral " .. id,b.hp-unit:GetCurrHitPoints(),s.expectedDamage[id] or 0)
        else
          -- Garrison absorption may consume one victim slot; validate every
          -- affected nongarrison target against its own independent formula.
          local actual = b.hp-unit:GetCurrHitPoints()
          T.Check("city secondary floor " .. id,unit:GetCurrHitPoints() >= math.min(b.hp,math.ceil(b.max*setting("CollateralHPFloorPercent",50)/100)),true)
          if actual > 0 then
            citySecondaryHits = citySecondaryHits + 1
            local base = math.floor(s.rawDamage*setting("CollateralPercent",20)/100)
            local amount = math.floor(base*(100-s.preview.CityProtection)/100)
            if base > 0 and s.preview.CityProtection < 100 then amount = math.max(amount,setting("CollateralMinimumDamage",1)) end
            local expected = math.min(amount,math.max(0,b.hp-math.ceil(b.max*setting("CollateralHPFloorPercent",50)/100)))
            T.Check("exact city collateral " .. id,actual,expected)
          end
          log("CITY_DAMAGE","secondary " .. id,actual,"fortification-mitigated")
        end
      end
    else
      log("GARRISON","HP after absorption and collateral",unit and unit:GetCurrHitPoints() or 0,"direct damage remains separate")
    end
  end
  if s.city then
    T.Check("city secondary damage occurred",citySecondaryHits > 0,true)
    local attacker=Players[s.owner]:GetUnitByID(s.attacker)
    T.Check("city secondary hit count bounded",citySecondaryHits <= attacker:GetStackRoleInfo().CollateralTargets,true)
  end
  s.checked = true
  T.Summary()
  return T.failed == 0
end
local originalSetup = T.SetupCollateral
function T.SetupCollateral(unitType)
  originalSetup(unitType)
  local s=T.shot
  local u=Players[s.owner]:GetUnitByID(s.attacker)
  if u:GetDomainType() == DomainTypes.DOMAIN_AIR and not u:GetPlot():IsCity() then
    Players[s.owner]:InitCity(u:GetX(),u:GetY())
    s.preview=u:GetStackAttackPreview(s.target,true)
    s.primary=s.preview.DefenderID
  end
end
function T.SetupCityCollateral(protected,unitType)
  T.Cleanup()
  local owner,enemy=T.Players()
  local target,adjacent=T.Plots("target")
  local city=Players[enemy]:InitCity(target:GetX(),target:GetY())
  assert(city,"Unable to create target test city")
  Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
  local typeName=unitType or "UNIT_ARTILLERY"
  local source = adjacent[1]
  if GameInfo.Units[GameInfoTypes[typeName]].Domain == "DOMAIN_AIR" then
    source = nil
    for i=0,Map.GetNumPlots()-1 do
      local candidate=Map.GetPlotByIndex(i)
      if plain(candidate) and Map.PlotDistance(candidate:GetX(),candidate:GetY(),target:GetX(),target:GetY()) == 4 then
        local clear=true
        for j=0,Map.GetNumPlots()-1 do
          local other=Map.GetPlotByIndex(j)
          if other:IsCity() and Map.PlotDistance(candidate:GetX(),candidate:GetY(),other:GetX(),other:GetY()) < 4 then clear=false; break end
        end
        if clear then source=candidate; break end
      end
    end
    assert(source,"Need an isolated airbase four hexes from the target")
    Players[owner]:InitCity(source:GetX(),source:GetY())
    T.Spawn(owner,"UNIT_SCOUT",adjacent[1])
  end
  assert(target:GetPlotCity() and target:GetPlotCity():GetOwner()==enemy,"Target city was invalidated by scenario setup")
  local attacker=T.Spawn(owner,typeName,source)
  attacker:SetBaseRangedCombatStrength(30)
  local victims={}
  for i=1,6 do table.insert(victims,T.Spawn(enemy,"UNIT_WARRIOR",target)) end
  local fortifications={{"BUILDING_WALLS",10},{"BUILDING_CASTLE",15},{"BUILDING_ARSENAL",20},{"BUILDING_MILITARY_BASE",25},{"BUILDING_BOMB_SHELTER",30}}
  local total=0
  for _,b in ipairs(fortifications) do city:SetNumRealBuilding(GameInfoTypes[b[1]],0) end
  T.Check("unfortified city protection",victims[1]:GetStackRoleInfo().CityProtection,0)
  if protected then
    for _,b in ipairs(fortifications) do
      city:SetNumRealBuilding(GameInfoTypes[b[1]],1)
      total=total+b[2]
      T.Check("add protection " .. b[1],victims[1]:GetStackRoleInfo().CityProtection,math.min(setting("CityProtectionMaximumPercent",90),total))
    end
    city:SetNumRealBuilding(GameInfoTypes.BUILDING_BOMB_SHELTER,0)
    T.Check("remove fortification updates protection",victims[1]:GetStackRoleInfo().CityProtection,70)
    city:SetNumRealBuilding(GameInfoTypes.BUILDING_BOMB_SHELTER,1)
  end
  victims[5]:SetDamage(50)
  victims[6]:SetMaxHitPointsBase(101)
  victims[6]:SetDamage(48)
  local preview=attacker:GetStackAttackPreview(target,true)
  local before={}
  for _,u in ipairs(victims) do before[u:GetID()]={hp=u:GetCurrHitPoints(),max=u:GetMaxHitPoints()} end
  T.shot={owner=owner,enemy=enemy,attacker=attacker:GetID(),target=target,before=before,primary=-1,preview=preview}
  assert(T.Check("city attack can be made",attacker:CanRangeStrikeAt(target:GetX(),target:GetY()),true), "Fixture has no legal city shot")
  T.Check("city collateral has targets",preview.CollateralCount>0,true)
  T.Summary()
end
