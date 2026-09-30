-- Synthetic capture opportunity only; this future-era unit is not campaign
-- balance evidence. Mutations stay in this disposable session; do not save it.
assert(Game.GetGameTurn()==230 and Game.GetPausePlayer()==Game.GetActivePlayer())
assert(Players[Game.GetActivePlayer()]:IsObserver())
assert(GameEvents.PlayerPreAIUnitUpdate,'Pre-AI hook unavailable')
assert(not StackFollowupCaptureFixture,'Fixture already installed')
StackFollowupCaptureFixture={installed=true,triggered=false,target=514}
local function beforeUnits(owner)
 if owner~=1 then return end
 GameEvents.PlayerPreAIUnitUpdate.Remove(beforeUnits)
 local state=StackFollowupCaptureFixture
 state.triggered=true;state.turn=Game.GetGameTurn()
 local ok,err=pcall(function()
  assert(Game.GetGameTurn()==230,'Unexpected fixture turn')
  local target=Map.GetPlot(34,6);local city=target:GetPlotCity()
  assert(city and city:GetOwner()==23 and city:GetName()=='Abernethy','Target changed')
  local player=Players[1]
  assert(Teams[player:GetTeam()]:IsAtWar(Players[23]:GetTeam()),'Fixture must not declare war')
  local spawn=nil
  for direction=0,5 do
   local p=Map.PlotDirection(34,6,direction)
   if p and not p:IsWater() and not p:IsCity() and not p:IsImpassable() and p:GetNumUnits()==0 then spawn=p;break end
  end
  assert(spawn,'No empty legal adjacent land plot')
  local armor=GameInfo.Units['UNIT_MODERN_ARMOR'];local role=GameInfo.UnitAIInfos['UNITAI_ATTACK']
  assert(armor and role,'Expected unit/role unavailable')
  local unit=player:InitUnit(armor.ID,spawn:GetX(),spawn:GetY(),role.ID)
  assert(unit,'Fixture unit creation failed')
  state.unit=unit:GetID();state.spawn=spawn:GetPlotIndex();state.ownerBefore=city:GetOwner()
  state.unitType=unit:GetUnitType();state.unitTypeName=GameInfo.Units[state.unitType].Type
  state.unitName=unit:GetName();state.baseCombat=unit:GetBaseCombatStrength()
  assert(state.unitType==armor.ID,'Fixture unit type changed during creation')
  assert(unit:GetX()==spawn:GetX() and unit:GetY()==spawn:GetY(),'Fixture unit relocated during creation')
  unit:SetDamage(0);unit:SetMoves(unit:MaxMoves());unit:SetMadeAttack(false)
  unit:SetActivityType(ActivityTypes.ACTIVITY_AWAKE)
  assert(not unit:IsNoCapture() and not unit:IsEmbarked() and not unit:IsOutOfAttacks())
  assert(unit:IsCanAttackWithMoveNow(),'Fixture melee attack unavailable')
  assert(unit:CanStackAtPlot(spawn),'Fixture placement exceeds native capacity')
  assert(unit:CanMoveOrAttackInto(target,0,1),'Final attack entry illegal')
  assert(target:IsVisible(player:GetTeam()),'Fixture target not tactically visible')
  city:SetDamage(city:GetMaxHitPoints()-1)
  local strength=unit:GetMaxAttackStrength(spawn,target,nil)
  local damage,retaliation=unit:GetMeleeCombatDamageCity(strength,city,false)
  state.damage=damage;state.retaliation=retaliation;state.hp=unit:GetMaxHitPoints()
  state.attackStrength=strength;state.cityStrength=city:GetStrengthValue()
  state.currentHP=unit:GetCurrHitPoints();state.cityHP=city:GetMaxHitPoints()-city:GetDamage()
  state.retaliationLimit=20
  assert(damage>=1 and retaliation<state.currentHP,'Fixture capture not survivable')
  assert(retaliation<=state.retaliationLimit,'Fixture incoming damage exceeds low-risk limit')
  state.prepared=true
  print('FOLLOWUP_CAPTURE_FIXTURE',state.turn,state.unit,state.unitTypeName,state.unitName,state.spawn,
   state.baseCombat,state.attackStrength,state.cityStrength,damage,retaliation)
 end)
 if not ok then state.error=tostring(err);print('FOLLOWUP_CAPTURE_FIXTURE_ERROR',state.error) end
end
GameEvents.PlayerPreAIUnitUpdate.Add(beforeUnits)
return StackFollowupCaptureFixture
