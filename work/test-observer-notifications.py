"""Actual Lua 5.1 notification expiry block, tested against notification/event contracts.

Run with the bundled Python; pass --source-root for a prepared package.
No game access, deployment, or gameplay changes.
"""
from pathlib import Path
import argparse
import sys
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--lua-modules', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.lua_modules or args.source_root / 'work/lua-validation'))
from lupa.lua51 import LuaRuntime

panel = args.source_root / '(3a) VP - EUI Compatibility Files/LUA/NotificationPanel.lua'
source = panel.read_text(encoding='utf-8-sig')
start = source.index('-- BEGIN STACKING OBSERVER NOTIFICATION AGING')
end = source.index('-- END STACKING OBSERVER NOTIFICATION AGING')
block = source[start:end]
xml = ET.parse(args.source_root / '(1) Community Patch/Database Changes/StackingConfig.xml')
rows = [r for r in xml.findall('./Stacking_Settings/Row') if r.get('Name') == 'UIObserverNotificationLifetimeTurns']
assert len(rows) == 1 and rows[0].get('Value') == '3'
LuaRuntime().execute('assert(loadstring(...))', source)  # Entire production panel parses, including Lua local limits.
checks = 2

setup = r'''
turn=100; owner=0; auto=0; reads=0; attempts={}; removed={}; g_ActiveNotifications={}
Game={GetActivePlayer=function()return owner end,GetGameTurn=function()return turn end,GetAIAutoPlay=function()return auto end}
function event()
 local handlers={};return setmetatable({Add=function(f)handlers[#handlers+1]=f end},{__call=function(_,...)for _,f in ipairs(handlers)do f(...)end end})
end
Events=setmetatable({},{__index=function(t,k)local e=event();rawset(t,k,e);return e end})
Players={}
for i=0,1 do
 local p={observer=false,rows={}};Players[i]=p
 function p:IsObserver()return self.observer end
 function p:GetNumNotifications()reads=reads+1;return #self.rows end
 function p:GetNotificationIndex(i)return self.rows[i+1].id end
 function p:GetNotificationTurn(i)return self.rows[i+1].turn end
 function p:GetNotificationDismissed(i)return self.rows[i+1].dismissed or false end
end
function add(p,id,created,bundle,mandatory,dismissed)
 p.rows[#p.rows+1]={id=id,turn=created,mandatory=mandatory,dismissed=dismissed}
 g_ActiveNotifications[id]=bundle or id
end
UI={RemoveNotification=function(id)
 attempts[#attempts+1]=id
 for _,row in ipairs(Players[owner].rows)do
  if row.id==id and not row.mandatory then
   row.dismissed=true;g_ActiveNotifications[id]=nil;removed[#removed+1]=id
   if onRemove then onRemove(id)end
   Events.NotificationRemoved(id);break
  end
 end
end}
GameInfo={}
function config(value)
 GameInfo.Stacking_Settings=function()
  local done=false;return function()if not done then done=true;return {Name='UIObserverNotificationLifetimeTurns',Value=value}end end
 end
end
function expect(value,wanted,label)assert(value==wanted,label..': '..tostring(value)..' ~= '..tostring(wanted))end
'''

def case(before, after):
    global checks
    lua = LuaRuntime()
    lua.execute(setup)
    lua.execute(before)
    lua.execute(block)
    lua.execute(after)
    checks += after.count('expect(')

case('add(Players[0],17,1)', '''
expect(#attempts,0,'normal play untouched');expect(reads,0,'normal play avoids ring scans')
Events.SerialEventGameDataDirty();expect(reads,0,'normal dirty event is inert')
Players[0].observer=true;Events.SerialEventGameDataDirty();expect(removed[1],17,'enter observer same turn')
''')
case('Players[0].observer=true;add(Players[0],9,98);add(Players[0],9001,97)', '''
expect(#removed,1,'age-three boundary');expect(removed[1],9001,'sparse lookup id, not slot')
expect(g_ActiveNotifications[9],9,'age two remains')
Events.SerialEventGameDataDirty();Events.AIProcessingStartedForPlayer(3);expect(reads,1,'one sweep per global turn')
turn=101;Events.AIProcessingStartedForPlayer(4);expect(removed[2],9,'next turn expires age two')
''')
case("Players[0].observer=true;add(Players[0],4,90,'Bundle');add(Players[0],8,99,'Bundle')", '''
expect(removed[1],4,'old bundle member removed');expect(#removed,1,'new bundle member retained')
expect(g_ActiveNotifications[8],'Bundle','bundle remains available')
''')
case('Players[0].observer=true;config(0);add(Players[0],1,1)', '''
expect(#removed,0,'zero disables');expect(reads,0,'disabled avoids scans')
''')
case('auto=10;config(2);add(Players[0],1,98);add(Players[0],2,99)', '''
expect(#removed,1,'custom lifetime during autoplay');expect(removed[1],1,'autoplay uses exact age')
auto=0;turn=101;Events.SerialEventGameDataDirty();expect(#removed,1,'leaving autoplay stops cleanup')
auto=1;Events.SerialEventGameDataDirty();expect(removed[2],2,'reenter same turn is not throttled')
''')
case('Players[0].observer=true;add(Players[0],1,-1);add(Players[0],2,101);add(Players[0],3,1,nil,false,true);add(Players[0],4,1);g_ActiveNotifications[4]=nil', '''
expect(#removed,0,'invalid/future/dismissed/undisplayed notifications skipped')
''')
case('Players[0].observer=true;add(Players[0],111,95,nil,true);add(Players[0],222,95)', '''
expect(#attempts,2,'uses ordinary UI removal for each id');expect(#removed,1,'mandatory choice protected by engine')
expect(removed[1],222,'ordinary entry removed');expect(g_ActiveNotifications[111],111,'mandatory still displayed')
''')
case('Players[0].observer=true;turn=200;add(Players[0],12345,190)', '''
expect(removed[1],12345,'saved original age used at load')
add(Players[0],12346,190);Events.NotificationAdded(12346);expect(removed[2],12346,'late rebroadcast keeps original age')
''')
case('Players[0].observer=true;Players[1].observer=true;add(Players[0],1,1);add(Players[1],91,99)', '''
expect(removed[1],1,'first player');owner=1;Events.GameplaySetActivePlayer(1,0)
expect(#removed,1,'second player newer entry not affected by first player id')
turn=102;Events.ActivePlayerTurnStart();expect(removed[2],91,'second player eligible at own timestamp')
''')
case('Players[0].observer=true;add(Players[0],1,1);add(Players[0],2,1);onRemove=function()Events.NotificationAdded(77);Events.SerialEventGameDataDirty()end', '''
expect(#attempts,2,'nested events do not duplicate removal');expect(#removed,2,'both snapshot ids removed')
''')
case('Players[0].observer=true;add(Players[0],1,1);add(Players[0],2,1);onRemove=function()owner=1;Events.GameplaySetActivePlayer(1,0)end', '''
expect(#removed,1,'nested owner change stops old-player removal');expect(g_ActiveNotifications[2],2,'old remaining notification untouched')
''')
case('Players[0].observer=true;add(Players[0],1,1);add(Players[0],2,1);onRemove=function()Players[0].observer=false end', '''
expect(#removed,1,'nested observer exit stops sweep');expect(g_ActiveNotifications[2],2,'normal view notification retained')
''')
case('Players[0].observer=true;config(-2);add(Players[0],1,1)', "expect(#removed,0,'negative clamped to disabled')")
case('Players[0].observer=true;config(10001);turn=20000;add(Players[0],1,10000)', "expect(removed[1],1,'upper bound clamped')")
case("Players[0].observer=true;config('bad');add(Players[0],1,97)", "expect(removed[1],1,'invalid setting uses default')")
assert source.index('Events.GameplaySetActivePlayer.Add( OnSetActivePlayer )') < start
assert source.index('Events.NotificationAdded.Add(') < start
checks += 2
print(f'PASS: {checks} observer-notification checks (actual Lua 5.1 block, full-panel syntax and XML).')
