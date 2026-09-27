-- Manual read-only autoplay observer. Loading defines functions only.
-- Start(0,10): observe this loaded game until Stop/unload; details every10 turns.
-- No orders, saves, techs, stats, terrain, autoplay or game options are changed.
StackAutoplayObserver=StackAutoplayObserver or {}
local O=StackAutoplayObserver
assert(not O.running,"Stop the existing observer before reloading definitions")
local function log(k,v) print("STACKAUTO|"..k.."|"..tostring(v or "")) end
local function keys(t)local a={};for k in pairs(t)do a[#a+1]=k end;table.sort(a);return a end
local function bit(v)return v and 1 or 0 end
local function detach()
 local event,callback=O.event,O.callback;O.event=nil;O.callback=nil;O.running=false
 if event and callback then local ok,err=pcall(function()event.Remove(callback)end)
  if not ok then log("DETACH_ERROR",tostring(err))end
 end
end
function O.Stop(reason)
 local active=O.running;detach()
 if active then log("STOP","reason="..tostring(reason or "manual").." samples="..tostring(O.samples).." lastTurn="..tostring(O.lastTurn).." deadline="..tostring(O.deadline))end
end
local function ownerRecord(owner)
 return {owner=owner,units=0,hp=0,combat=0,counted=0,land=0,sea=0,air=0,cargo=0,embarked=0,other=0,busy=0,offmap=0,illegal=0,over=0,uncovered=0,hist={},groups={},records={}}
end
local function sample(turn,trigger,phase)
 log("SCAN_START","turn="..turn.." phase="..phase.." trigger="..trigger)
 local owners,rows,anomalies={}, {},{}
 for owner=0,(GameDefines.MAX_PLAYERS or 64)-1 do local player=Players[owner]
  if player and player:IsAlive()then
   local a=ownerRecord(owner);owners[#owners+1]=a
   for u in player:Units()do
    local hp=u:GetCurrHitPoints()
    if hp>0 and not u:IsDelayedDeath()then
     local p=u:GetPlot();local domain=u:GetDomainType();local role=u:GetStackRoleInfo()
     local cargo,embarked=u:IsCargo(),u:IsEmbarked();local combat=u:IsCombatUnit();local ranged=u:IsRanged()
     local counted=role.CountsTowardCapacity==true and not cargo and (domain==DomainTypes.DOMAIN_LAND or domain==DomainTypes.DOMAIN_SEA)
     a.units=a.units+1;a.hp=a.hp+hp;a.combat=a.combat+bit(combat);a.cargo=a.cargo+bit(cargo);a.embarked=a.embarked+bit(embarked)
     if domain==DomainTypes.DOMAIN_LAND then a.land=a.land+1 elseif domain==DomainTypes.DOMAIN_SEA then a.sea=a.sea+1 elseif domain==DomainTypes.DOMAIN_AIR then a.air=a.air+1 end
     if not counted and not cargo and domain~=DomainTypes.DOMAIN_AIR then a.other=a.other+1 end
     local busy=u:IsBusy() or u:IsFighting();a.busy=a.busy+bit(busy)
     local cap=p and u:GetStackingLimit(p)or -1;local legal=-1
     -- Civilian/support/air/cargo policies are not interpreted as combat-cap violations.
     if counted and p then legal=bit(u:CanStackAtPlot(p));a.counted=a.counted+1
      local kind=domain==DomainTypes.DOMAIN_LAND and "L"or "S";local key=p:GetPlotIndex()..":"..kind
      local g=a.groups[key];if not g then g={plot=p:GetPlotIndex(),kind=kind,n=0,cap=cap,ranged=0,melee=0};a.groups[key]=g end
      g.n=g.n+1;g.cap=math.min(g.cap,cap)
      if not embarked then if ranged then g.ranged=g.ranged+1 else g.melee=g.melee+1 end end
      if legal==0 then a.illegal=a.illegal+1;anomalies[#anomalies+1]="placement owner="..owner.." id="..u:GetID().." plot="..p:GetPlotIndex().." busy="..bit(busy) end
     elseif not p then a.offmap=a.offmap+1 end
     rows[#rows+1]={owner=owner,id=u:GetID(),u=u,p=p,hp=hp,domain=domain,role=role,counted=counted,cargo=cargo,embarked=embarked,ranged=ranged,combat=combat,cap=cap,legal=legal,busy=busy}
    end
   end
   for _,key in ipairs(keys(a.groups))do local g=a.groups[key];local h=g.kind..g.n;a.hist[h]=(a.hist[h]or 0)+1
    if g.ranged>0 and g.melee==0 then a.uncovered=a.uncovered+g.ranged end
    if g.n>g.cap then a.over=a.over+1;anomalies[#anomalies+1]="capacity owner="..owner.." plot="..g.plot.." domain="..g.kind.." count="..g.n.." cap="..g.cap end
   end
  end
 end
 local elapsed=turn-O.startTurn;local detail=elapsed%O.detailEvery==0 or #anomalies>0
 local output={"BEGIN|turn="..turn.." elapsed="..elapsed.." phase="..phase.." trigger="..trigger.." owners="..#owners.." units="..#rows.." detail="..tostring(detail).." anomalies="..#anomalies}
 for _,a in ipairs(owners)do local hist={};for _,h in ipairs(keys(a.hist))do hist[#hist+1]=h..":"..a.hist[h]end
  output[#output+1]="OWNER|turn="..turn.." owner="..a.owner.." units="..a.units.." hp="..a.hp.." combat="..a.combat.." counted="..a.counted.." land="..a.land.." sea="..a.sea.." air="..a.air.." cargo="..a.cargo.." embarked="..a.embarked.." other="..a.other.." busy="..a.busy.." offmap="..a.offmap.." illegalCounted="..a.illegal.." overCapStacks="..a.over.." rangedWithoutMelee="..a.uncovered.." hist="..table.concat(hist,",")
 end
 for _,v in ipairs(anomalies)do output[#output+1]="ANOMALY|turn="..turn.." "..v end
 if detail then
  table.sort(rows,function(a,b)return a.owner==b.owner and a.id<b.id or a.owner<b.owner end)
  for _,r in ipairs(rows)do local u,p=r.u,r.p
   output[#output+1]="UNIT|"..table.concat({turn,r.owner,r.id,u:GetUnitType(),r.domain,p and p:GetPlotIndex()or -1,u:GetX(),u:GetY(),r.hp,u:GetMaxHitPoints(),u:GetMoves(),r.cap,r.legal,bit(r.counted),bit(r.ranged),bit(r.role.Flanker),bit(r.role.AntiCavalry),r.role.CollateralTargets or 0,bit(r.cargo),bit(r.embarked),bit(r.busy)},",")
  end
 end
 for _,line in ipairs(output)do print("STACKAUTO|"..line)end
 log("END","turn="..turn.." units="..#rows);O.samples=O.samples+1;O.lastTurn=turn
end
local function tick(trigger,phase)
 if not O.running then return end
 local ok,err=pcall(function()
  local turn=Game.GetGameTurn()
  if turn<O.startTurn or (O.lastTurn and turn<O.lastTurn)then O.Stop("turn_rewound");return end
  if O.deadline and turn>O.deadline then O.Stop("elapsed_limit");return end
  if turn==O.lastTurn then return end
  sample(turn,trigger or -1,phase)
  if O.deadline and turn>=O.deadline then O.Stop("elapsed_limit")end
 end)
 if not ok then log("ERROR",tostring(err));O.Stop("callback_error")end
end
function O.Start(maxTurns,detailEvery)
 assert(not O.running,"Observer already running; Stop first")
 maxTurns=maxTurns or 0;detailEvery=detailEvery or 10
 assert(type(maxTurns)=="number" and maxTurns==math.floor(maxTurns) and maxTurns>=0 and maxTurns<=10000,"Use0 for unlimited, or1..10000 elapsed turns")
 assert(type(detailEvery)=="number" and detailEvery==math.floor(detailEvery) and detailEvery>=1 and detailEvery<=50,"Use1..50 detail interval")
 assert(Game and Game.GetGameTurn and Game.GetActivePlayer()>=0,"Use a loaded game")
 local event=assert(GameEvents and GameEvents.PlayerDoTurn,"PlayerDoTurn hook unavailable")
 assert(event.Add and event.Remove,"PlayerDoTurn subscription unavailable")
 O.startTurn=Game.GetGameTurn();O.deadline=maxTurns>0 and O.startTurn+maxTurns or nil;O.lastTurn=nil;O.samples=0;O.detailEvery=detailEvery;O.running=true;O.event=event
 O.generation=(O.generation or 0)+1;local generation=O.generation
 O.callback=function(player)if O.generation==generation then tick(player,"PlayerDoTurn_before_unit_AI")end end
 local ok,err=pcall(function()event.Add(O.callback)end)
 if not ok then O.Stop("subscribe_error");error(err)end
 log("START","start="..O.startTurn.." deadline="..tostring(O.deadline or "unlimited").." detailEvery="..detailEvery.." rawStructureOnly; legal=-1 for excluded domains/support/cargo; histogram counts owner/domain plots; no threat/safety inference")
 tick(Game.GetActivePlayer(),"manual_start")
 return O.running
end
function O.Status()
 log("STATUS","running="..tostring(O.running==true).." start="..tostring(O.startTurn).." deadline="..tostring(O.deadline).." lastTurn="..tostring(O.lastTurn).." samples="..tostring(O.samples or 0))
end
