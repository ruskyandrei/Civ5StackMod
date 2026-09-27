-- Optional bounded event logger. Loading defines functions only.
-- Start(n) observes at most n human-turn returns; it never advances a turn.
StackAITurnMonitor = StackAITurnMonitor or {}
local M=StackAITurnMonitor
local function log(event,player)
 print("STACKAI_MONITOR|"..event.."|turn="..Game.GetGameTurn().."|player="..tostring(player).."|cycles="..tostring(M.cycles or 0))
end
function M.Stop(reason)
 if M.pre then GameEvents.PlayerPreAIUnitUpdate.Remove(M.pre);M.pre=nil end
 if M.finish then GameEvents.PlayerEndTurnCompleted.Remove(M.finish);M.finish=nil end
 if M.human then Events.ActivePlayerTurnStart.Remove(M.human);M.human=nil end
 if M.running then log("STOP:"..(reason or "manual"),M.pending) end
 M.running=false;M.pending=nil
end
function M.Start(maxTurns)
 M.Stop("rearm")
 M.limit=math.max(1,math.floor(tonumber(maxTurns) or 10));M.cycles=0
 M.owner=Game.GetActivePlayer();M.seen={};M.running=true
 M.pre=function(player)
  local key=Game.GetGameTurn()..":"..player
  if M.seen[key] then return end
  M.seen[key]=true
  if M.pending then log("TRANSITION_FROM_AI",M.pending) end
  M.pending=player;log("AI_START",player)
 end
 M.finish=function(player)
  if M.pending==player then log("AI_END",player);M.pending=nil end
 end
 M.human=function()
  if Game.GetActivePlayer()~=M.owner then return end
  if M.pending then log("AI_RETURNED_TO_HUMAN",M.pending) end
  M.pending=nil;M.cycles=M.cycles+1;M.seen={}
  log("HUMAN_RETURN",M.owner)
  if M.cycles>=M.limit then M.Stop("observation_limit") end
 end
 GameEvents.PlayerPreAIUnitUpdate.Add(M.pre)
 GameEvents.PlayerEndTurnCompleted.Add(M.finish)
 Events.ActivePlayerTurnStart.Add(M.human)
 log("ARMED",M.owner)
end
function M.Status()
 print("STACKAI_MONITOR|STATUS|running="..tostring(M.running).."|pending="..tostring(M.pending).."|cycles="..tostring(M.cycles or 0))
end
print("STACKAI_MONITOR|LOADED|Start(maxTurns), Status(), Stop(); no game commands run")
