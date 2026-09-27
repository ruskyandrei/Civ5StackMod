-- XML-variation manual fixtures. Definitions only at load. Disposable new game only.
-- Requires imported StackingTests; use work/xml-variation/main as the matching profile.
StackXMLTests = StackXMLTests or {}
local V=StackXMLTests
local function T() return assert(StackTests,"include('StackingTests') first") end
local function check(n,a,e) return T().Check("XML: "..n,a,e) end
local function must(n,a,e) assert(check(n,a,e),"Fixture precondition: "..n) end
local function scalar(name)
 for r in GameInfo.Stacking_Settings() do if r.Name==name then return tonumber(r.Value) end end
end
local function setTechs(owner,value)
 V.saved=V.saved or {}
 local teamID=Players[owner]:GetTeam(); local team=Teams[teamID]
 V.saved[teamID]=V.saved[teamID] or {owner=owner,values={}}
 for r in GameInfo.Stacking_Technologies() do
  local id=assert(GameInfoTypes[r.TechType])
  if V.saved[teamID].values[id]==nil then V.saved[teamID].values[id]=team:IsHasTech(id) end
  team:SetHasTech(id,value,owner,false,false,true)
 end
end
function V.Cleanup()
 T().Cleanup()
 for teamID,s in pairs(V.saved or {}) do
  for id,had in pairs(s.values) do Teams[teamID]:SetHasTech(id,had,s.owner,false,false,true) end
 end
 V.saved=nil; V.state=nil
end
local function begin(grant)
 V.Cleanup()
 local owner,enemy=T().Players()
 setTechs(owner,grant); setTechs(enemy,grant)
 Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
 return owner,enemy
end
local function at(u,p) return u and u:GetX()==p:GetX() and u:GetY()==p:GetY() end
local function spawn(owner,name,p)
 local u=T().Spawn(owner,name,p); must(name.." placement",at(u,p),true); return u
end
local function coastalSite(owner)
 local team=Players[owner]:GetTeam(); local cities={}
 for i=0,Map.GetNumPlots()-1 do local p=Map.GetPlotByIndex(i); if p:IsCity() then cities[#cities+1]=p end end
 local function empty(p)
  return p and not p:IsCity() and not p:IsMountain() and p:GetNumUnits()==0 and p:GetOwner()==-1 and not p:IsImpassable(team)
 end
 for i=0,Map.GetNumPlots()-1 do
  local p=Map.GetPlotByIndex(i)
  if empty(p) and not p:IsWater() then
   local isolated=true
   for _,c in ipairs(cities) do if Map.PlotDistance(p:GetX(),p:GetY(),c:GetX(),c:GetY())<4 then isolated=false; break end end
   if isolated then
    local land,sea={},{}
    for d=0,5 do
     local n=Map.PlotDirection(p:GetX(),p:GetY(),d)
     if empty(n) then
      if not n:IsWater() then land[#land+1]=n
      elseif n:GetTerrainType()==GameInfoTypes.TERRAIN_COAST and n:GetFeatureType()==-1 then sea[#sea+1]=n end
     end
    end
    if #land>=3 and #sea>=2 then return p,land,sea end
   end
  end
 end
 error("Need isolated coast site with three empty land and two clear coast neighbors")
end
function V.Data(profile)
 profile=profile or "main"
 local expected={Enabled=1,DefenderSelectionEnabled=1,FlankingEnabled=1,CollateralEnabled=1,AIEnabled=1,
  BaseCapacity=3,MaximumCapacity=10,LandCapacityBonus=0,SeaCapacityBonus=1,CityCapacityBonus=1,
  MinorCapacityBonus=1,BarbarianCapacityBonus=2,CollateralPercent=30,CollateralHPFloorPercent=60,
  CollateralMinimumDamage=3,CityProtectionMaximumPercent=65}
 local toggles={["no-flanking"]="FlankingEnabled",["no-collateral"]="CollateralEnabled",["no-stacking"]="Enabled",["no-ai"]="AIEnabled"}
 if toggles[profile] then expected[toggles[profile]]=0 end
 for name,value in pairs(expected) do check("database "..name,scalar(name),value) end
 local techs={TECH_IRON_WORKING=2,TECH_GUNPOWDER=1,TECH_MILITARY_SCIENCE=3,TECH_ROBOTICS=1}; local count=0
 for row in GameInfo.Stacking_Technologies() do count=count+1; check("tech row "..row.TechType,tonumber(row.CapacityBonus),techs[row.TechType]) end
 check("technology row count",count,4)
 for row in GameInfo.Stacking_CollateralDomains() do
  local enabled=(row.DomainType=="DOMAIN_LAND" or (profile=="sea-enabled" and row.DomainType=="DOMAIN_SEA")) and 1 or 0
  check("domain row "..row.DomainType,tonumber(row.Enabled),enabled)
 end
 local found=false
 for row in GameInfo.UnitPromotions_Domains() do
  if row.PromotionType=="PROMOTION_SIEGE_INACCURACY" and row.DomainType=="DOMAIN_LAND" then
   found=true; check("siege XML land-attack modifier",tonumber(row.Attack),-20)
  end
 end
 check("siege modifier row exists",found,true)
 T().Summary()
end
function V.CapacityDomains(fillTen)
 local owner,enemy=begin(false)
 local p,land,sea=coastalSite(owner)
 local city=assert(Players[owner]:InitCity(p:GetX(),p:GetY()))
 local warrior=spawn(owner,"UNIT_WARRIOR",land[1]); local ship=spawn(owner,"UNIT_CARAVEL",sea[1])
 local other=spawn(enemy,"UNIT_WARRIOR",land[2])
 local function values(label,bonus)
  check(label.." land",warrior:GetStackingLimit(land[3]),math.min(10,3+bonus))
  check(label.." sea",ship:GetStackingLimit(sea[2]),math.min(10,4+bonus))
  check(label.." city land",warrior:GetStackingLimit(p),math.min(10,4+bonus))
  check(label.." city sea",ship:GetStackingLimit(p),math.min(10,5+bonus))
  check(label.." foreign city uses moving owner's technology",other:GetStackingLimit(p),4)
 end
 values("base",0)
 local total=0
 for _,r in ipairs({{"TECH_IRON_WORKING",2},{"TECH_GUNPOWDER",1},{"TECH_MILITARY_SCIENCE",3},{"TECH_ROBOTICS",1}}) do
  Teams[Players[owner]:GetTeam()]:SetHasTech(GameInfoTypes[r[1]],true,owner,false,false,true)
  total=total+r[2]; values(r[1],total)
 end
 if fillTen then
  for i=1,10 do
   local a=spawn(owner,"UNIT_WARRIOR",land[3]); check("field land occupant legal "..i,a:CanStackAtPlot(land[3]),true)
   local b=spawn(owner,"UNIT_CARAVEL",sea[2]); check("field sea occupant legal "..i,b:CanStackAtPlot(sea[2]),true)
   local c=spawn(owner,"UNIT_WARRIOR",p); check("city land occupant legal "..i,c:CanStackAtPlot(p),true)
   local d=spawn(owner,"UNIT_CARAVEL",p); check("city sea occupant legal "..i,d:CanStackAtPlot(p),true)
  end
  check("field rejects eleventh land unit",warrior:CanStackAtPlot(land[3]),false)
  check("field rejects eleventh sea unit",ship:CanStackAtPlot(sea[2]),false)
  check("city rejects eleventh land unit",warrior:CanStackAtPlot(p),false)
  check("city rejects eleventh sea unit",ship:CanStackAtPlot(p),false)
  local worker=spawn(owner,"UNIT_WORKER",p); check("civilian remains separate",worker:CanStackAtPlot(p),true)
 end
 V.state={owner=owner,enemy=enemy,city=city:GetID(),plot=p}
 T().Summary()
 print("STACKXML|READY|Capacity arena retained for inspection; Cleanup restores tech presence and removes tracked units")
end
function V.Roles()
 local owner,enemy=begin(true)
 local p,land,sea=coastalSite(owner)
 Players[owner]:InitCity(p:GetX(),p:GetY())
 local function probe(name,field,value)
  local row=GameInfo.Units[GameInfoTypes[name]]
  local where=row.Domain=="DOMAIN_AIR" and p or (row.Domain=="DOMAIN_SEA" and sea[1] or land[1])
  local u=spawn(owner,name,where)
  if field=="CollateralTargets" then u:SetHasPromotion(GameInfoTypes.PROMOTION_DRILL_1,false) end
  check(name.." "..field,u:GetStackRoleInfo()[field],value)
  return u
 end
 probe("UNIT_HORSEMAN","Flanker",false):Kill(false,-1)
 probe("UNIT_WARRIOR","Flanker",true):Kill(false,-1)
 probe("UNIT_KNIGHT","Flanker",true):Kill(false,-1)
 local drill=assert(GameInfoTypes.PROMOTION_DRILL_1)
 local catapult=probe("UNIT_CATAPULT","CollateralTargets",3)
 catapult:SetHasPromotion(drill,true); check("explicit unit 3 overrides promotion 5",catapult:GetStackRoleInfo().CollateralTargets,3)
 catapult:Kill(false,-1)
 local trebuchet=probe("UNIT_TREBUCHET","CollateralTargets",1)
 trebuchet:SetHasPromotion(drill,true); check("promotion grants 5 over inherited 1",trebuchet:GetStackRoleInfo().CollateralTargets,5)
 trebuchet:SetHasPromotion(drill,false); check("promotion removal restores inherited 1",trebuchet:GetStackRoleInfo().CollateralTargets,1)
 trebuchet:Kill(false,-1)
 probe("UNIT_FRIGATE","CollateralTargets",2):Kill(false,-1)
 probe("UNIT_BOMBER","CollateralTargets",6):Kill(false,-1)
 local spear=spawn(owner,"UNIT_SPEARMAN",land[1])
 for r in GameInfo.Stacking_PromotionRoles() do if r.Role=="ANTI_CAVALRY" then spear:SetHasPromotion(GameInfoTypes[r.PromotionType],false) end end
 check("class zero disables spear anti-cavalry",spear:GetStackRoleInfo().AntiCavalry,false)
 spear:SetHasPromotion(GameInfoTypes.PROMOTION_FORMATION_1,true)
 check("promotion restores spear anti-cavalry",spear:GetStackRoleInfo().AntiCavalry,true)
 spear:Kill(false,-1)
 local artillery=probe("UNIT_ARTILLERY","CollateralTargets",2)
 local promotion=assert(GameInfoTypes.PROMOTION_SIEGE_INACCURACY)
 artillery:SetHasPromotion(promotion,false); local without=artillery:DomainAttackPercent(DomainTypes.DOMAIN_LAND)
 artillery:SetHasPromotion(promotion,true)
 check("live siege promotion contribution",artillery:DomainAttackPercent(DomainTypes.DOMAIN_LAND)-without,-20)
 artillery:Kill(false,-1)
 local knight=spawn(owner,"UNIT_KNIGHT",land[1]); knight:SetBaseCombatStrength(40)
 local melee=spawn(enemy,"UNIT_LONGSWORDSMAN",land[2]); melee:SetBaseCombatStrength(100)
 local archer=spawn(enemy,"UNIT_ARCHER",land[2]); archer:SetBaseCombatStrength(1); archer:SetBaseRangedCombatStrength(1)
 check("archer FLANK_TARGET zero prevents cavalry bypass",knight:GetStackAttackPreview(land[2],false).DefenderID,melee:GetID())
 T().Summary()
end
function V.SetupFloor()
 begin(true)
 T().SetupCollateral("UNIT_ARTILLERY")
 local s=T().shot; local ids={}
 for id in pairs(s.before) do ids[#ids+1]=id end
 table.sort(ids)
 for _,id in ipairs(ids) do
  local u=Players[s.enemy]:GetUnitByID(id); u:SetDamage(u:GetMaxHitPoints()-math.ceil(u:GetMaxHitPoints()*0.60))
 end
 local strong=Players[s.enemy]:GetUnitByID(ids[1]); strong:SetBaseCombatStrength(100); strong:SetDamage(0)
 local near=Players[s.enemy]:GetUnitByID(ids[2]); near:SetDamage(near:GetMaxHitPoints()-63)
 local odd=Players[s.enemy]:GetUnitByID(ids[#ids]); odd:SetMaxHitPointsBase(101); odd:SetDamage(38)
 local attacker=Players[s.owner]:GetUnitByID(s.attacker); attacker:SetHasPromotion(GameInfoTypes.PROMOTION_DRILL_1,false); attacker:SetBaseRangedCombatStrength(80)
 s.before={}
 for _,id in ipairs(ids) do local u=Players[s.enemy]:GetUnitByID(id); s.before[id]={hp=u:GetCurrHitPoints(),max=u:GetMaxHitPoints()} end
 s.preview=attacker:GetStackAttackPreview(s.target,true); s.primary=s.preview.DefenderID
 must("floor test protects strongest primary",s.primary,strong:GetID())
 must("two floor-limited secondary victims",s.preview.CollateralCount,2)
 print("STACKXML|READY|Call StackTests.Fire(), then StackTests.CheckShot() after combat; expected floors60 and ceil101*.6=61")
end
function V.SetupCity()
 begin(true)
 T().SetupCityCollateral(false,"UNIT_ARTILLERY")
 local s=T().shot; local city=assert(s.target:GetPlotCity())
 Players[s.owner]:GetUnitByID(s.attacker):SetHasPromotion(GameInfoTypes.PROMOTION_DRILL_1,false)
 local probe=Players[s.enemy]:GetUnitByID(next(s.before))
 local total=0
 for _,r in ipairs({{"BUILDING_WALLS",11},{"BUILDING_CASTLE",13},{"BUILDING_ARSENAL",17},{"BUILDING_MILITARY_BASE",19},{"BUILDING_BOMB_SHELTER",31}}) do
  city:SetNumRealBuilding(GameInfoTypes[r[1]],1); total=total+r[2]
  check("protection after "..r[1],probe:GetStackRoleInfo().CityProtection,math.min(65,total))
 end
 city:SetNumRealBuilding(GameInfoTypes.BUILDING_BOMB_SHELTER,0)
 check("removal below protection cap",probe:GetStackRoleInfo().CityProtection,60)
 city:SetNumRealBuilding(GameInfoTypes.BUILDING_WALLS,0)
 check("specific building override removed once",probe:GetStackRoleInfo().CityProtection,49)
 city:SetNumRealBuilding(GameInfoTypes.BUILDING_WALLS,1)
 city:SetNumRealBuilding(GameInfoTypes.BUILDING_BOMB_SHELTER,1)
 s.preview=Players[s.owner]:GetUnitByID(s.attacker):GetStackAttackPreview(s.target,true)
 check("restored protection cap",s.preview.CityProtection,65)
 print("STACKXML|READY|Call StackTests.Fire(), then StackTests.CheckShot() after combat; percentage/floor/minimum/protection read from variation DB")
end
function V.SetupSeaCollateral()
 local enabled=0
 for r in GameInfo.Stacking_CollateralDomains() do if r.DomainType=="DOMAIN_SEA" then enabled=tonumber(r.Enabled) end end
 must("sea-enabled profile loaded",enabled,1)
 local owner,enemy=begin(true); local _,_,sea=coastalSite(owner)
 local attacker=spawn(owner,"UNIT_FRIGATE",sea[1]); attacker:SetHasPromotion(GameInfoTypes.PROMOTION_DRILL_1,false); attacker:SetBaseRangedCombatStrength(30)
 local before={}
 for i=1,6 do local u=spawn(enemy,"UNIT_CARAVEL",sea[2]); before[u:GetID()]={hp=u:GetCurrHitPoints(),max=u:GetMaxHitPoints()} end
 must("sea fixture legal range strike",attacker:CanRangeStrikeAt(sea[2]:GetX(),sea[2]:GetY()),true)
 local preview=attacker:GetStackAttackPreview(sea[2],true)
 must("sea collateral preview follows enabled XML domain",preview.CollateralCount,2)
 T().shot={owner=owner,enemy=enemy,attacker=attacker:GetID(),target=sea[2],before=before,primary=preview.DefenderID,preview=preview}
 print("STACKXML|READY|Call StackTests.Fire(), then StackTests.CheckShot() after combat. Requires removal of redundant naval-water early return before freezing comparison DLL.")
end