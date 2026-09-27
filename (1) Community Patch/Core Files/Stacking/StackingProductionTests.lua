-- Manual disposable-game production probes. Loading defines functions only.
-- No terrain, city, technology, production queue, save or turn edits.
-- Setup explicitly spawns tracked units and may declare war. Discard the world.
StackProductionTests = StackProductionTests or {passed=0,failed=0}
local P=StackProductionTests
local function log(k,v) print("STACKPROD|"..k.."|"..tostring(v)) end
local function check(k,a,e)
 local ok=a==e;P[ok and "passed" or "failed"]=P[ok and "passed" or "failed"]+1
 log(ok and "PASS" or "FAIL",k.." actual="..tostring(a).." expected="..tostring(e));return ok
end
local function at(u,p) return u and u:GetX()==p:GetX() and u:GetY()==p:GetY() end
local function get(r) return Players[r.owner]:GetUnitByID(r.id) end
local function city(s) return assert(Players[s.owner]:GetCityByID(s.city),"Fixture city is gone") end
local function spawn(s,owner,p)
 local u=assert(Players[owner]:InitUnit(s.unitType,p:GetX(),p:GetY()),"InitUnit failed")
 assert(at(u,p),"Fixture spawn moved unexpectedly")
 local r={owner=owner,id=u:GetID(),x=u:GetX(),y=u:GetY(),hp=u:GetCurrHitPoints()}
 s.units[#s.units+1]=r;return u,r
end
function P.Plan(cityID,unitType)
 local owner=Game.GetActivePlayer();assert(owner>=0,"Load a disposable game")
 local player=Players[owner];assert(player:IsTurnActive() and Game.GetAIAutoPlay()==0,"Use active human turn; stop autoplay")
 local c=cityID and player:GetCityByID(cityID) or player:GetCapitalCity();assert(c,"Need an existing city")
 local id=type(unitType)=="number" and unitType or GameInfoTypes[unitType or "UNIT_WARRIOR"]
 local info=id and GameInfo.Units[id];assert(info and info.Domain=="DOMAIN_LAND" and info.Combat>0,"Choose an ordinary land combat type")
 local enemy
 for i=0,GameDefines.MAX_MAJOR_CIVS-1 do
  if i~=owner and Players[i]:IsAlive() and Players[i]:GetTeam()~=player:GetTeam() then enemy=i;break end
 end
 assert(enemy,"Need another independent living major")
 local plots,seen={},{}
 for d=-1,5 do
  local p=d==-1 and c:Plot() or Map.PlotDirection(c:GetX(),c:GetY(),d)
  if p and not seen[p:GetPlotIndex()] then
   seen[p:GetPlotIndex()]=true
   assert(p:GetNumUnits()==0,"City and all adjacent plots must have no existing units")
   if not p:IsWater() and not p:IsImpassable(player:GetTeam()) then
    assert(p:GetOwner()==owner or p:GetOwner()==-1,"Fixture ring must be own or unowned")
    assert(not p:IsImpassable(Players[enemy]:GetTeam()),"Enemy cannot use a legal production plot")
    plots[#plots+1]=p
   end
  end
 end
 assert(#plots>=2 and plots[1]:GetPlotIndex()==c:Plot():GetPlotIndex(),"Need an empty usable city and land neighbor")
 log("PLAN","city="..c:GetID().." owner="..owner.." enemy="..enemy.." eligiblePlots="..#plots.." unit="..id)
 return {owner=owner,enemy=enemy,city=c:GetID(),unitType=id,plots=plots,units={},turn=Game.GetGameTurn()}
end
function P.Setup(cityID,unitType)
 assert(not P.state,"Clean up the previous fixture first")
 local s=P.Plan(cityID,unitType);P.state=s
 local ourTeam=Players[s.owner]:GetTeam();local theirTeam=Players[s.enemy]:GetTeam()
 s.wasWar=Teams[ourTeam]:IsAtWar(theirTeam)
 if not s.wasWar then Teams[ourTeam]:DeclareWar(theirTeam) end
 local c=city(s);local first=spawn(s,s.owner,c:Plot());s.cap=first:GetStackingLimit(c:Plot())
 assert(s.cap>=2 and s.cap<=10,"Use enabled stacking profile with capacity2..10")
 for i=2,s.cap do spawn(s,s.owner,c:Plot()) end
 s.enemies={}
 for i=2,#s.plots do local u,r=spawn(s,s.enemy,s.plots[i]);s.enemies[#s.enemies+1]=r end
 check("hostile ring offers no production slot",c:CanPlaceUnitHere(s.unitType),false)
 log("SETUP","city full; each eligible adjacent plot has exactly one hostile combat unit")
end
function P.OpenFriendlySlot()
 local s=assert(P.state);assert(not s.open,"Slot already opened")
 assert(Game.GetGameTurn()==s.turn,"Do not advance the fixture turn")
 local r=s.enemies[1];local e=assert(get(r));local p=Map.GetPlot(e:GetX(),e:GetY())
 e:Kill(false,-1);r.removed=true
 local u=spawn(s,s.owner,p);local cap=u:GetStackingLimit(p)
 assert(cap>=2 and cap<=10,"Expected ordinary land capacity2..10")
 for i=2,cap-1 do spawn(s,s.owner,p) end
 s.open=p;s.openCap=cap
 check("one friendly slot becomes available",city(s):CanPlaceUnitHere(s.unitType),true)
end
function P.PurchaseOne()
 local s=assert(P.state);assert(s.open and not s.purchased,"Open exactly one friendly slot first")
 local c=city(s);local player=Players[s.owner];local gold=YieldTypes.YIELD_GOLD
 assert(Game.GetGameTurn()==s.turn,"Do not advance the fixture turn")
 assert(c:IsCanPurchase(true,true,s.unitType,-1,-1,gold),"Unit unavailable/unaffordable: choose a trainable unit and sufficient gold before setup")
 local before={};for u in player:Units() do before[u:GetID()]=true end
 c:Purchase(s.unitType,-1,-1,gold);s.purchased=true
 local count=0
 for u in player:Units() do if not before[u:GetID()] then
  count=count+1;s.units[#s.units+1]={owner=s.owner,id=u:GetID()}
  check("purchased unit stays on sole friendly plot",at(u,s.open),true)
 end end
 check("one actual unit purchased",count,1)
 check("filled friendly plot closes production slot",c:CanPlaceUnitHere(s.unitType),false)
 for _,r in ipairs(s.enemies) do if not r.removed then
  local u=get(r);check("enemy survives "..r.id,u~=nil,true)
  if u then
   check("enemy x unchanged "..r.id,u:GetX(),r.x);check("enemy y unchanged "..r.id,u:GetY(),r.y)
   check("enemy HP unchanged "..r.id,u:GetCurrHitPoints(),r.hp)
  end
 end end
 P.Summary()
end
function P.Summary() log("SUMMARY",P.passed.." passed; "..P.failed.." failed") end
function P.Cleanup()
 local s=P.state;if not s then return end
 for _,r in ipairs(s.units) do local u=get(r);if u then u:Kill(false,-1) end end
 P.state=nil
 log("CLEANUP","Tracked units removed. Purchase/diplomacy effects remain; discard this disposable world without saving.")
end
