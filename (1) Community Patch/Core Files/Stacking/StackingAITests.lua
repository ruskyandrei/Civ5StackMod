-- Disposable-game AI probes. Load after include("StackingTests").
-- This file defines helpers only; it never advances a turn automatically.
assert(StackTests, "Load StackingTests first")
StackAITests = StackAITests or {}
local A, T = StackAITests, StackTests
local function mark(name, value) print("STACKAI|"..name.."|"..tostring(value)) end
local function setup()
  T.Cleanup()
  local owner, enemy = T.Players()
  Teams[Players[owner]:GetTeam()]:DeclareWar(Players[enemy]:GetTeam(),false,owner)
  local plot, adjacent = T.Plots()
  return owner, enemy, plot, adjacent
end
function A.Danger()
  local owner, enemy, plot, adjacent = setup()
  local ranged = T.Spawn(owner,"UNIT_ARCHER",plot)
  local attacker = T.Spawn(enemy,"UNIT_WARRIOR",adjacent[1])
  local alone = ranged:GetDanger()
  T.Check("AI danger detects melee threat",alone > 0,true)
  attacker:FinishMoves()
  local exhausted = ranged:GetDanger()
  mark("archer-danger-exhausted-threat",exhausted)
  T.Check("AI next-turn danger retains exhausted melee threat",exhausted,alone)
  attacker:SetMoves(attacker:MaxMoves())
  attacker:SetMadeAttack(true)
  local attacked = ranged:GetDanger()
  mark("archer-danger-spent-attack-threat",attacked)
  T.Check("AI next-turn danger retains spent melee attack",attacked,alone)
  attacker:SetMadeAttack(false)
  local protector = T.Spawn(owner,"UNIT_LONGSWORDSMAN",plot)
  local protected = ranged:GetDanger()
  mark("archer-alone-danger",alone); mark("archer-protected-danger",protected)
  T.Check("AI danger credits stack protection",protected < alone,true)
  T.Check("AI protector receives risk",protector:GetDanger() > protected,true)
  attacker:Kill(false,-1)
  attacker = T.Spawn(enemy,"UNIT_HORSEMAN",adjacent[1])
  local bypass = ranged:GetDanger()
  mark("archer-flanked-danger",bypass)
  T.Check("AI sees cavalry bypass",bypass > protected,true)
  protector:Kill(false,-1)
  protector = T.Spawn(owner,"UNIT_PIKEMAN",plot)
  local intercepted = ranged:GetDanger()
  mark("archer-anti-cavalry-danger",intercepted)
  T.Check("AI credits anti-cavalry interception",intercepted < bypass,true)
  attacker:Kill(false,-1)
  attacker = T.Spawn(enemy,"UNIT_CATAPULT",adjacent[1])
  local collateral = ranged:GetDanger()
  mark("archer-collateral-danger",collateral)
  T.Check("AI sees secondary collateral risk",collateral > 0,true)
  ranged:SetDamage(math.ceil(ranged:GetMaxHitPoints()/2))
  local atFloor = ranged:GetDanger()
  mark("archer-at-floor-danger",atFloor)
  T.Check("AI respects collateral HP floor",atFloor < collateral,true)
  T.Cleanup(); T.Summary()
end
function A.Formation()
  local owner, ai, plot, adjacent = setup()
  local ranged = T.Spawn(ai,"UNIT_ARCHER",plot)
  local protector = T.Spawn(ai,"UNIT_SPEARMAN",adjacent[4])
  local threat = T.Spawn(owner,"UNIT_WARRIOR",adjacent[1])
  A.scenario = { owner=owner, ai=ai, ranged=ranged:GetID(), protector=protector:GetID(), threat=threat:GetID(), x=plot:GetX(), y=plot:GetY(), turn=Game.GetGameTurn() }
  mark("formation-ready", "end one player turn, then call StackAITests.Snapshot()")
  A.Snapshot()
end
function A.Snapshot()
  local s = assert(A.scenario,"Call Formation first")
  local ranged = Players[s.ai]:GetUnitByID(s.ranged)
  local protector = Players[s.ai]:GetUnitByID(s.protector)
  local threat = Players[s.owner]:GetUnitByID(s.threat)
  local function describe(u)
    return u and (u:GetX()..","..u:GetY().." HP="..u:GetCurrHitPoints().." moves="..u:MovesLeft().." danger="..u:GetDanger()) or "dead"
  end
  mark("turn",Game.GetGameTurn()); mark("ranged",describe(ranged)); mark("protector",describe(protector)); mark("threat",describe(threat))
  local together = ranged and protector and ranged:GetX()==protector:GetX() and ranged:GetY()==protector:GetY()
  mark("formed-stack",together and true or false)
  -- Placement is evidence, not a forced pass: record whether the tactical log
  -- chose to protect, counterattack successfully, or found another safe move.
end
mark("loaded","Danger(), Formation(), Snapshot(); all manual")
