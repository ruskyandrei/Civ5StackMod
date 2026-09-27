-- Optional manual probe around the registered natural helper. Definitions only.
-- No C++/XML changes, terrain edits, turns, saves or automatic event hooks.
StackAntiCavProbe = StackAntiCavProbe or {}
local P = StackAntiCavProbe
local function log(k,v) print("STACKANTICAV|"..k.."|"..tostring(v)) end
local function unit(rec)
 local u = Players[rec.owner]:GetUnitByID(rec.id)
 assert(u and u:GetCurrHitPoints()>0 and u:GetID()==rec.initialID and u:GetUnitType()==rec.type,"missing/replaced/upgraded fixture unit")
 return u
end
local function fixture()
 local n=assert(StackAINaturalTests,"include StackingAINaturalTests first")
 local s=assert(n.state,"run natural Formation first")
 assert(s.kind=="formation","only the existing Formation fixture is accepted")
 local r,g,threats=nil,nil,{}
 for _,rec in ipairs(s.units) do
  if rec.role=="ranged" then r=unit(rec) elseif rec.role=="guard" then g=unit(rec)
  elseif string.sub(rec.role,1,5)=="enemy" then threats[#threats+1]={u=unit(rec),rec=rec} end
 end
 assert(r and g and #threats>0,"incomplete fixture")
 return n,s,r,g,threats
end
function P.Preflight()
 P.measured=nil
 local n,s,r,g,threats=fixture()
 assert(not n.armed,"preflight only before Arm")
 assert(n.Snapshot("anticav-preflight"),"fixture no longer matches original setup")
 assert(n.MeasureFormation(),"no measured survivable protection advantage; do not advance this as a positive test")
 assert(g:GetStackRoleInfo().AntiCavalry,"guard lacks configured anti-cavalry role")
 assert(r:GetPlot():GetPlotIndex()==s.center and g:GetPlot():GetPlotIndex()==s.source,"unexpected initial position")
 local center=Map.GetPlotByIndex(s.center)
 local source=Map.GetPlotByIndex(s.source)
 local moves=g:GetMoves()
 local alone=r:GetDanger()
 for _,t in ipairs(threats) do
  assert(t.u:GetStackRoleInfo().Flanker,"threat lacks configured cavalry bypass")
  local hit=t.u:GetStackAttackPreview(center,false)
  assert(hit.DefenderID==r:GetID() and hit.DefenderOwner==r:GetOwner(),"solo preview must select ranged unit")
  log("solo-preview","attacker="..t.u:GetID().." defender="..hit.DefenderID.." raw="..hit.DirectDamage)
 end
 local covered,guardRisk
 local ok,err=pcall(function()
  assert(g:CanStackAtPlot(center),"joining would exceed capacity")
  g:SetXY(center:GetX(),center:GetY())
  covered=r:GetDanger();guardRisk=g:GetDanger()
  for _,t in ipairs(threats) do
   local hit=t.u:GetStackAttackPreview(center,false)
   assert(hit.DefenderID==g:GetID() and hit.DefenderOwner==g:GetOwner(),"anti-cavalry does not intercept this attacker")
   log("covered-preview","attacker="..t.u:GetID().." defender="..hit.DefenderID.." raw="..hit.DirectDamage)
  end
 end)
 -- Always restore only the existing tagged guard, even when a preview fails.
 g:SetXY(source:GetX(),source:GetY());g:SetMoves(moves)
 if not ok then error(err) end
 assert(covered<alone and guardRisk<g:GetCurrHitPoints(),"positive-cover/survival gate failed")
 assert(n.Snapshot("anticav-preflight-restored"),"preflight did not restore exact fixture setup")
 P.measured={fixture=s.id,alone=alone,covered=covered,guardRisk=guardRisk,ranged=r:GetID(),guard=g:GetID()}
 log("READY","alone="..alone.." covered="..covered.." guardRisk="..guardRisk.."; save if desired, then Natural.Arm(1) and normal End Turn")
 return true
end
function P.After()
 local n,s,r,g,threats=fixture()
 assert(P.measured and P.measured.fixture==s.id,"record Preflight before observing the AI turn")
 assert(Game.GetGameTurn()==s.turn+1 and n.aiTurns==1 and n.returns==1 and not n.armed,"exactly one completed observed AI turn required")
 assert(Game.GetActivePlayer()==s.human and Game.GetAIAutoPlay()==0 and Players[s.human]:IsTurnActive(),"check only after the human turn returns")
 assert(r:GetID()==P.measured.ranged and g:GetID()==P.measured.guard,"measured protector/ranged identity changed")
 local known={}
 for _,rec in ipairs(s.units) do local u=unit(rec)
  assert(u:CanStackAtPlot(u:GetPlot()),"fixture occupancy is not legal")
  known[u:GetOwner()..":"..u:GetID()]=true
 end
 local center=Map.GetPlotByIndex(s.center)
 for i=0,center:GetNumUnits()-1 do local u=center:GetUnit(i)
  assert(u and known[u:GetOwner()..":"..u:GetID()],"unrelated occupant in the protected center")
 end
 for _,t in ipairs(threats) do assert(t.u:GetPlot():GetPlotIndex()==t.rec.initialPlot,"human threat moved") end
 assert(r:GetPlot():GetPlotIndex()==s.center,"ranged fixture moved; cannot claim the fixed-ranged protection test")
 local joined=g:GetPlot():GetPlotIndex()==s.center
 local danger=r:GetDanger();local safe=g:GetDanger()<g:GetCurrHitPoints()
 n.Snapshot("anticav-after")
 if joined then for _,t in ipairs(threats) do
  local hit=t.u:GetStackAttackPreview(r:GetPlot(),false)
  assert(hit.DefenderID==g:GetID() and hit.DefenderOwner==g:GetOwner(),"joined guard fails actual cavalry interception")
 end end
 local result=joined and danger<P.measured.alone and safe and "PROTECTED_AGAINST_CAVALRY" or "NO_QUALIFYING_PROTECTIVE_JOIN"
 log("OUTCOME",result.." ranged="..r:GetID().." guard="..g:GetID().." danger="..danger.." guardRisk="..g:GetDanger())
 return result
end
function P.Try(name,...)
 local ok,result=pcall(assert(P[name],"unknown probe"),...)
 if not ok then log("ERROR",name..": "..tostring(result)) end
 return ok,result
end
