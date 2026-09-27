-- Natural-terrain air-wave regression. Definitions only; no automatic game actions.
-- Requires StackTests and an existing active-player city in a disposable game.
StackAirWaveTests=StackAirWaveTests or {}
local W=StackAirWaveTests
local function T() return assert(StackTests,"include('StackingTests') first") end
local function check(n,a,e) return T().Check("air-wave: "..n,a,e) end
local function must(n,a,e) assert(check(n,a,e),"Fixture precondition: "..n) end
local function u(owner,id) return Players[owner]:GetUnitByID(id) end
local function setting(name,fallback)
 for r in GameInfo.Stacking_Settings() do if r.Name==name then return tonumber(r.Value) end end
 return fallback
end
local function plain(p)
 return p and not p:IsWater() and not p:IsMountain() and not p:IsCity() and p:GetNumUnits()==0
end
local function oneAttempt(aa)
 aa:SetMadeInterception(false)
 local limit
 for i=1,100 do
  aa:SetMadeInterception(true)
  if aa:isOutOfInterceptions() then limit=i;break end
 end
 assert(limit,"Fixture interceptor count exceeds safe probe bound")
 aa:SetMadeInterception(false)
 for i=1,limit-1 do aa:SetMadeInterception(true) end
 must("exactly one live attempt available",aa:isOutOfInterceptions(),false)
 return limit
end
function W.Setup()
 T().Cleanup()
 local owner,enemy=T().Players()
 local city=Players[owner]:GetCapitalCity()
 assert(city,"Found a normal city first; fixture never creates a city or edits terrain")
 local target,aaPlot
 for i=0,Map.GetNumPlots()-1 do
  local p=Map.GetPlotByIndex(i)
  if plain(p) and p:GetOwner()==-1 and Map.PlotDistance(p:GetX(),p:GetY(),city:GetX(),city:GetY())==2 then
   for d=0,5 do
    local n=Map.PlotDirection(p:GetX(),p:GetY(),d)
    if plain(n) and n:GetOwner()==-1 then target=p;aaPlot=n;break end
   end
  end
  if target then break end
 end
 assert(target,"Need empty natural land two hexes from the existing capital")
 Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
 local guard=T().Spawn(enemy,"UNIT_LONGSWORDSMAN",target);guard:SetBaseCombatStrength(80)
 local archer=T().Spawn(enemy,"UNIT_ARCHER",target);archer:SetBaseCombatStrength(5);archer:SetBaseRangedCombatStrength(5)
 must("two field defenders fit",guard:CanStackAtPlot(target),true)
 local aa=T().Spawn(enemy,"UNIT_ANTI_AIRCRAFT_GUN",aaPlot)
 for _,name in ipairs({"PROMOTION_INTERCEPTION_1","PROMOTION_INTERCEPTION_2","PROMOTION_INTERCEPTION_3"}) do aa:SetHasPromotion(GameInfoTypes[name],true) end
 aa:SetDamage(0);aa:SetBaseCombatStrength(100)
 local limit=oneAttempt(aa)
 must("guaranteed intercept probability",aa:CurrInterceptionProbability()>=100,true)
 W.state={owner=owner,enemy=enemy,base=city:Plot(),target=target,guard=guard:GetID(),archer=archer:GetID(),aa=aa:GetID(),maxAttempts=limit,bombers={}}
 print("STACKAIR|READY|Query('baseline'); AddBomber(); CalibrateFirst(); next frame ValidateFirst(); Query('one'); AddBomber(); Query('wave'); use separate frames")
end
function W.AddBomber()
 local s=assert(W.state);assert(#s.bombers<2)
 local bomber=T().Spawn(s.owner,"UNIT_BOMBER",s.base)
 bomber:SetBaseRangedCombatStrength(40);bomber:SetMaxHitPointsBase(1000);bomber:SetDamage(0)
 for p in GameInfo.UnitPromotions() do if tonumber(p.EvasionChange or 0)~=0 and bomber:IsHasPromotion(p.ID) then bomber:SetHasPromotion(p.ID,false) end end
 s.bombers[#s.bombers+1]=bomber:GetID()
 local interceptor=bomber:GetBestInterceptor(s.target,bomber,false,false)
 local aa=assert(u(s.enemy,s.aa))
 if #s.bombers==2 and s.shot and s.shot.index==1 and aa:isOutOfInterceptions() then
  must("second bomber sees exhausted AA",interceptor==nil,true)
 else must("intended AA is selected",interceptor and interceptor:GetID() or -1,s.aa) end
 must("bomber zero evasion",bomber:EvasionProbability(),0)
 must("bomber can strike",bomber:CanRangeStrikeAt(s.target:GetX(),s.target:GetY()),true)
 print("STACKAIR|ADDED|bomber="..bomber:GetID().."; query next frame")
end
function W.FogPerBomber()
 local s=assert(W.state);local seen={};local n=0
 if s.base:IsWater()~=s.target:IsWater() then return 0 end
 for dx=-2,2 do for dy=-2,2 do
  local p=Map.PlotXYWithRangeCheck(s.base:GetX(),s.base:GetY(),dx,dy,2)
  if p and not seen[p:GetPlotIndex()] then
   seen[p:GetPlotIndex()]=true
   if not p:IsVisible(Players[s.enemy]:GetTeam()) and not p:IsImpassable(Players[s.owner]:GetTeam()) and Map.PlotDistance(p:GetX(),p:GetY(),s.target:GetX(),s.target:GetY())<=2 then n=n+1 end
  end
 end end
 return n
end
function W.Query(stage)
 local s=assert(W.state);local per=W.FogPerBomber()
 assert(not s.fogPerBomber or s.fogPerBomber==per,'Fog contribution changed; reset fixture instead of comparing different visibility')
 s.fogPerBomber=per
 local danger=assert(Players[s.enemy]:GetUnitByID(s.guard)):GetDanger()
 local fog=#s.bombers*per;local combat=danger-fog
 print('STACKAIR|DANGER|'..stage..' raw='..danger..' addedFog='..fog..' combat='..combat..' fogPerBomber='..per)
 if stage=='baseline' then assert(#s.bombers==0);s.baseline=danger
 elseif stage=='one' then assert(#s.bombers==1 and s.baseline);s.one=danger;check('one bomber blocked after measured fog adjustment',combat,s.baseline)
 elseif stage=='wave' then assert(#s.bombers==2 and s.one);s.wave=danger;check('second bomber outlasts single interceptor after fog adjustment',combat>s.one-per,true)
 elseif stage=='exhausted' then assert(#s.bombers==2);s.exhausted=danger;check('spent AA cannot reduce combat wave danger',combat>=assert(s.wave)-2*per,true)
 elseif stage=='partial' then assert(#s.bombers==2);check('partial interception cannot be certain after fog adjustment',combat>=assert(s.wave)-2*per,true);check('partial no worse than zero protection after fog adjustment',combat<=assert(s.exhausted)-2*per,true)
 else error('Use baseline/one/wave/exhausted/partial') end
 StackTests.Summary()
end
function W.RecheckFog()
 local s=assert(W.state);local per=W.FogPerBomber()
 assert(s.baseline and s.one,'Need recorded baseline and one-bomber values')
 assert(not s.fogPerBomber or s.fogPerBomber==per,'Fog contribution changed')
 s.fogPerBomber=per
 print('STACKAIR|FOG_RECHECK|perBomber='..per..' originalBaseline='..s.baseline..' originalOne='..s.one..'; original FAIL evidence retained')
 check('recorded blocked bomber adds fog only',s.one-per,s.baseline)
 if s.wave then check('recorded second bomber causes combat damage',s.wave-2*per>s.one-per,true) end
 StackTests.Summary()
end
function W.ExhaustAA()
 local s=assert(W.state);local aa=assert(u(s.enemy,s.aa));aa:SetMadeInterception(true)
 must("AA live attempt exhausted",aa:isOutOfInterceptions(),true)
end
function W.RearmAA(partial)
 local s=assert(W.state);local aa=assert(u(s.enemy,s.aa));oneAttempt(aa);aa:SetDamage(0)
 if partial then
  local hp=math.max(1,math.floor(50*aa:GetMaxHitPoints()/aa:MaxInterceptionProbability()))
  aa:SetDamage(aa:GetMaxHitPoints()-hp)
  must("partial chance between zero and100",aa:CurrInterceptionProbability()>0 and aa:CurrInterceptionProbability()<100,true)
 end
 print("STACKAIR|AA|chance="..aa:CurrInterceptionProbability().."; query next frame")
end
function W.InterceptionBound(b)
 local s=assert(W.state);local aa=assert(Players[s.enemy]:GetUnitByID(s.aa));local im,dm=0,0
 assert(not b:IsRangedSupportFire(),"Unsupported fake ranged unit")
 for p in GameInfo.UnitPromotions() do
  if aa:IsHasPromotion(p.ID) then im=im+math.max(0,tonumber(p.InterceptionCombatModifier or 0)) end
  if b:IsHasPromotion(p.ID) then dm=dm+math.max(0,tonumber(p.InterceptionDefenseDamageModifier or 0)) end
 end
 assert(dm>-100 and im>-100,'Interception damage disabled by modifier')
 local attack=math.floor(aa:GetMaxAttackStrength(nil,nil,b)*(100+im)/100)
 local defense=math.max(1,b:GetBaseRangedCombatStrength()*10)
 local ratio=math.max(attack,defense)/math.max(1,math.min(attack,defense))
 ratio=math.min(1000,(((ratio+3)/4)^4+1)/2);if defense>attack then ratio=1/ratio end
 local base=assert(tonumber(GameDefines.INTERCEPTION_SAME_STRENGTH_MIN_DAMAGE))
 local extra=assert(tonumber(GameDefines.INTERCEPTION_SAME_STRENGTH_POSSIBLE_EXTRA_DAMAGE))
 local bound=math.floor(math.floor(math.floor((base+math.max(0,extra-1))*ratio)*(100+dm)/100)/100)
 return bound,attack,defense,im,dm
end
function W.CalibrateFirst()
 local s=assert(W.state);local alive={}
 for _,id in ipairs(s.bombers) do local b=Players[s.owner]:GetUnitByID(id);if b and b:GetCurrHitPoints()>0 then alive[#alive+1]=id end end
 assert(#alive==1,'Need one surviving bomber')
 s.bombers=alive;s.shot=nil;local b=Players[s.owner]:GetUnitByID(alive[1]);local aa=Players[s.enemy]:GetUnitByID(s.aa)
 assert(not b:IsBusy() and not b:IsFighting(),'Wait for combat')
 aa:SetDamage(0);local limit=math.max(1,math.min(100,aa:GetBaseCombatStrength()));local best=0
 for strength=1,limit do aa:SetBaseCombatStrength(strength);if W.InterceptionBound(b)<b:GetCurrHitPoints()/4 then best=strength end end
 assert(best>0,'No nonlethal AA strength found');aa:SetBaseCombatStrength(best);W.RearmAA(false)
 s.interceptionProof=nil
 print('STACKAIR|CALIBRATED|bomber='..alive[1]..' aaBase='..best..' maxDamageBound='..W.InterceptionBound(b)..'; next frame call ValidateFirst()')
end
function W.ValidateFirst()
 local s=assert(W.state);assert(#s.bombers==1 and s.baseline,'Need one bomber and baseline')
 local b=Players[s.owner]:GetUnitByID(s.bombers[1]);local aa=Players[s.enemy]:GetUnitByID(s.aa);local g=Players[s.enemy]:GetUnitByID(s.guard)
 assert(aa:CurrInterceptionProbability()>=100 and b:EvasionProbability()==0,'Need certain interception')
 assert(b:GetBestInterceptor(s.target,b,false,false):GetID()==s.aa,'Wrong interceptor')
 local preview=b:GetStackAttackPreview(s.target,true)
 assert(preview.DefenderID==s.guard and preview.DirectDamage>0,'Need positive unblocked damage to guard')
 local protected=g:GetDanger();assert(protected==s.baseline+W.FogPerBomber(),'Protected damage mismatch')
 W.ExhaustAA();local ok,spent=pcall(function()return g:GetDanger()end);W.RearmAA(false)
 assert(ok and spent>protected and g:GetDanger()==protected,'Interception control failed')
 local bound=W.InterceptionBound(b);assert(bound>0 and bound<b:GetCurrHitPoints(),'Nonlethal bound failed')
 s.interceptionProof={id=b:GetID(),aaBase=aa:GetBaseCombatStrength()}
 StackTests.Check('air-wave: calibrated certain abort forecast',true,true)
 StackTests.Check('air-wave: conservative max interception is nonlethal',bound<b:GetCurrHitPoints(),true)
 print('STACKAIR|INTERCEPTION_PROOF|bomber='..b:GetID()..' maxDamageBound='..bound..' HP='..b:GetCurrHitPoints())
end
function W.Fire(index)
 local s=assert(W.state);assert(index==1 or index==2)
 local bomber=assert(u(s.owner,s.bombers[index]));local aa=assert(u(s.enemy,s.aa))
 local best=bomber:GetBestInterceptor(s.target,bomber,false,false)
 if index==1 then
  must("first strike guaranteed AA",best and best:GetID()==s.aa and aa:CurrInterceptionProbability()>=100,true)
  local proof=s.interceptionProof
  assert(proof and proof.id==bomber:GetID() and proof.aaBase==aa:GetBaseCombatStrength(),"CalibrateFirst/ValidateFirst before adding second bomber")
  must("calibrated interception is nonlethal",W.InterceptionBound(bomber)<bomber:GetCurrHitPoints(),true)
 else must("second strike has no remaining interceptor",best==nil,true) end
 must("actual bombing legal",bomber:CanRangeStrikeAt(s.target:GetX(),s.target:GetY()),true)
 local preview=bomber:GetStackAttackPreview(s.target,true)
 local before={}
 for _,id in ipairs({s.guard,s.archer}) do local v=assert(u(s.enemy,id));before[id]={hp=v:GetCurrHitPoints(),max=v:GetMaxHitPoints()} end
 local primary=assert(u(s.enemy,preview.DefenderID))
 s.shot={index=index,before=before,bomberHP=bomber:GetCurrHitPoints(),primary=primary:GetID(),raw=bomber:GetRangeCombatDamage(primary,nil,true)}
 bomber:PushMission(MissionTypes.MISSION_RANGE_ATTACK,s.target:GetX(),s.target:GetY(),0,0,1)
 print("STACKAIR|FIRED|"..index.."; call CheckShot() after animation")
end
function W.CheckShot()
 local s=assert(W.state);local shot=assert(s.shot);local bomber=u(s.owner,s.bombers[shot.index])
 assert(not bomber or not bomber:IsFighting(),"Wait for combat animation")
 check("bomber survives",bomber~=nil,true)
 if shot.index==1 then
  check("interception caused actual bomber damage",bomber and bomber:GetCurrHitPoints()<shot.bomberHP or false,true)
  check("first attack consumed remaining AA use",u(s.enemy,s.aa):isOutOfInterceptions(),true)
 end
 local base=math.floor(shot.raw*setting("CollateralPercent",20)/100)
 local amount=base>0 and math.max(base,setting("CollateralMinimumDamage",1)) or 0
 for id,b in pairs(shot.before) do
  local actual=u(s.enemy,id);local expected=b.hp
  if shot.index==2 then
   if id==shot.primary then expected=math.max(0,b.hp-shot.raw)
   else expected=b.hp-math.min(amount,math.max(0,b.hp-math.ceil(b.max*setting("CollateralHPFloorPercent",50)/100))) end
  end
  check("actual wave HP "..id,actual and actual:GetCurrHitPoints() or 0,expected)
 end
 T().Summary()
end