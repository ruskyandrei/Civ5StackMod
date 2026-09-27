-- Manual disposable-game gifting probe. Definitions only; no automatic actions.
-- Uses natural city-state territory, tracked spawned units and a normal move.
StackGiftTests=StackGiftTests or {passed=0,failed=0}
local G=StackGiftTests
local function log(k,v) print("STACKGIFT|"..k.."|"..tostring(v)) end
local function check(k,a,e)
 local ok=a==e;G[ok and "passed" or "failed"]=G[ok and "passed" or "failed"]+1
 log(ok and "PASS" or "FAIL",k.." actual="..tostring(a).." expected="..tostring(e));return ok
end
local function at(u,p) return u and u:GetX()==p:GetX() and u:GetY()==p:GetY() end
local function unit(r) return Players[r.owner]:GetUnitByID(r.id) end
local function spawn(s,owner,p)
 local u=assert(Players[owner]:InitUnit(s.type,p:GetX(),p:GetY()));assert(at(u,p),"Spawn unexpectedly displaced")
 local r={owner=owner,id=u:GetID(),hp=u:GetCurrHitPoints()};s.units[#s.units+1]=r;return r
end
local function suitable(p,owner,recipient)
 return p and p:GetOwner()==recipient and p:GetNumUnits()==0 and not p:IsCity() and not p:IsWater() and not p:IsMountain()
  and not p:IsImpassable(Players[owner]:GetTeam()) and not p:IsImpassable(Players[recipient]:GetTeam())
end
function G.Plan(unitType)
 local owner=Game.GetActivePlayer();assert(owner>=0 and Players[owner]:IsTurnActive(),"Use active human turn")
 assert(Game.GetAIAutoPlay()==0,"Stop autoplay")
 local id=type(unitType)=="number" and unitType or GameInfoTypes[unitType or "UNIT_WARRIOR"]
 local info=id and GameInfo.Units[id];assert(info and info.Domain=="DOMAIN_LAND" and info.Combat>0,"Choose ordinary land combat")
 for i=0,Map.GetNumPlots()-1 do
  local p=Map.GetPlotByIndex(i);local recipient=p:GetOwner()
  if recipient>=0 and Players[recipient]:IsAlive() and Players[recipient]:IsMinorCiv() and
   not Teams[Players[owner]:GetTeam()]:IsAtWar(Players[recipient]:GetTeam()) and suitable(p,owner,recipient) then
   for d=0,5 do local q=Map.PlotDirection(p:GetX(),p:GetY(),d)
    if suitable(q,owner,recipient) then
     log("PLAN","donor="..owner.." recipient="..recipient.." source="..p:GetX()..","..p:GetY().." neighbor="..q:GetX()..","..q:GetY())
     return {owner=owner,recipient=recipient,source=p,neighbor=q,type=id,units={},turn=Game.GetGameTurn()}
    end
   end
  end
 end
 error("Need two adjacent empty natural land tiles owned by a peaceful city-state")
end
function G.Setup(unitType)
 assert(not G.state,"Clean up old gifting fixture first")
 local s=G.Plan(unitType);G.state=s
 s.donor=spawn(s,s.owner,s.source);local d=unit(s.donor)
 assert(d:GetStackingLimit(s.source)>=2,"Enabled stacking capacity must be at least two")
 -- Validate the positive control before adding the donor companion. This rules
 -- out danger, class caps, scout restrictions or diplomacy as refusal causes.
 assert(d:CanGift(0,1),"Single donor cannot gift here; clean up and choose a safer natural site/type")
 s.other=spawn(s,s.owner,s.source)
 check("stacked donor gift is refused",d:CanGift(0,1),false)
 local before={};for u in Players[s.recipient]:Units() do before[u:GetID()]=true end
 d:DoCommand(CommandTypes.COMMAND_GIFT,0,0)
 check("rejected donor retained",unit(s.donor)~=nil,true)
 check("rejected companion retained",unit(s.other)~=nil,true)
 local created=0;for u in Players[s.recipient]:Units() do if not before[u:GetID()] then created=created+1 end end
 check("rejected gift creates no recipient",created,0)
 check("rejected donor location unchanged",at(unit(s.donor),s.source),true)
 check("rejected companion location unchanged",at(unit(s.other),s.source),true)
end
function G.Separate()
 local s=assert(G.state);assert(Game.GetGameTurn()==s.turn,"Do not advance a turn")
 assert(s.neighbor:GetNumUnits()==0,"Destination is no longer empty")
 local other=assert(unit(s.other));other:SetMoves(other:MaxMoves())
 other:PushMission(MissionTypes.MISSION_MOVE_TO,s.neighbor:GetX(),s.neighbor:GetY(),0,0,1)
 log("MOVE","Wait for the ordinary one-tile move, then call GiftSeparated()")
end
function G.GiftSeparated()
 local s=assert(G.state);assert(at(unit(s.other),s.neighbor),"Wait for companion move")
 local d=assert(unit(s.donor));assert(at(d,s.source),"Donor moved unexpectedly")
 check("separated donor gift allowed",d:CanGift(0,1),true)
 assert(d:CanGift(0,1),"Positive control failed; do not gift")
 s.before={};for u in Players[s.recipient]:Units() do s.before[u:GetID()]=true end
 d:DoCommand(CommandTypes.COMMAND_GIFT,0,0)
 log("GIFT","Wait one frame, then call CheckGift()")
end
function G.CheckGift()
 local s=assert(G.state);assert(s.before,"No successful gift attempted")
 check("old donor removed",unit(s.donor)==nil,true)
 check("other donor remains on moved tile",at(unit(s.other),s.neighbor),true)
 local n=0
 for u in Players[s.recipient]:Units() do if not s.before[u:GetID()] then
  n=n+1;check("recipient created at original gift tile",at(u,s.source),true)
  check("recipient HP preserved",u:GetCurrHitPoints(),s.donor.hp)
  s.units[#s.units+1]={owner=s.recipient,id=u:GetID()}
 end end
 check("exactly one recipient unit created",n,1)
 log("SUMMARY",G.passed.." passed; "..G.failed.." failed")
end
function G.Cleanup()
 local s=G.state;if not s then return end
 for _,r in ipairs(s.units) do local u=unit(r);if u then u:Kill(false,-1) end end
 G.state=nil;log("CLEANUP","Tracked units removed; gift influence/history remains. Discard this disposable world without saving.")
end
