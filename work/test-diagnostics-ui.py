from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET
r=Path(r'E:\Projects\Civ5StackMod');sys.path.insert(0,str(r/'work/lua-validation'))
from lupa.lua51 import LuaRuntime
p=r/'(3a) VP - EUI Compatibility Files/LUA/StackPanel.lua';source=p.read_text(encoding='utf-8-sig')
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
checks=0;sets=0;level=0;refreshes=0;autoTurns=0;observer=false;activeOwner=0
function expect(a,b,msg)checks=checks+1;assert(a==b,msg..': '..tostring(a)..' != '..tostring(b))end
function include()end
function Vector2(x,y)return{x=x,y=y}end function Vector4(x,y,z,w)return{x=x,y=y,z=z,w=w}end
print=function()end
function event()
 local h={};local e={handlers=h}
 function e.Add(f)h[#h+1]=f end
 function e.Remove(f)for i=#h,1,-1 do if h[i]==f then table.remove(h,i)end end end
 return setmetatable(e,{__call=function(_,...)for _,f in ipairs(h)do f(...)end end})
end
Events=setmetatable({},{__index=function(t,k)local e=event();rawset(t,k,e);return e end})
LuaEvents=setmetatable({},{__index=function(t,k)local e=event();rawset(t,k,e);return e end})
LuaEvents.RequestRefreshAdditionalInformationDropdownEntries.Add(function()refreshes=refreshes+1 end)
function control()
 local c={hidden=true,disabled=false,text='',callbacks={}}
 function c:RegisterCallback(k,f)self.callbacks[k]=f end
 function c:SetText(x)self.text=x end
 function c:SetToolTipString(x)self.tip=x end
 function c:SetHide(x)self.hidden=x end
 function c:SetDisabled(x)self.disabled=x end
 function c:GetSizeY()return math.max(16,math.ceil(#self.text/40)*16)end
 function c:SetOffsetVal(x,y)self.x=x;self.y=y end
 function c:SetSizeVal(x,y)self.w=x;self.h=y end
 return c
end
Controls=setmetatable({},{__index=function(t,k)local c=control();rawset(t,k,c);return c end})
GameInfo={Stacking_Settings=function()local rows={{Name='UIStackEnabled',Value=0},{Name='DiagnosticsLevel',Value=0}};local i=0;return function()i=i+1;return rows[i]end end}
Game={GetActivePlayer=function()return activeOwner end,GetAIAutoPlay=function()return autoTurns end,GetActiveTeam=function()return 0 end,GetStackingDiagnosticsLevel=function()return level end,SetStackingDiagnosticsLevel=function(n)assert(n==0 or n==1 or n==2);sets=sets+1;level=n;return n end,GetStackingDiagnosticsStatus=function()return logError or (level==0 and 'Disabled' or 'Logging: C:/Users/Test/Documents/My Games/Civ V/Logs/StackingDiagnostics-session-1.csv')end}
Players={[0]={IsTurnActive=function()return true end,IsObserver=function()return observer end}}
UIManager={GetScreenSizeVal=function()return 1920,1080 end}
UI={GetHeadSelectedUnit=function()return nil end}
Mouse={eLClick=1};MouseEvents={RButtonUp=2,LButtonUp=3};KeyEvents={KeyDown=4};Keys={VK_ESCAPE=27};InterfaceModeTypes={INTERFACEMODE_SELECTION=0}
ContextPtr={SetInputHandler=function(self,f)self.input=f end,SetUpdate=function(self,f)self.update=f end,SetShutdown=function(self,f)self.shutdown=f end}
''')
# Execute the actual installed-EUI gather consumer: it filters art="" and
# consumes the entries at its callback position, before later producers.
notification=(r/'(3a) VP - EUI Compatibility Files/LUA/NotificationPanel.lua').read_text(encoding='utf-8-sig')
a=notification.index('LuaEvents.AdditionalInformationDropdownGatherEntries.Add(')
b=notification.index('LuaEvents.RequestRefreshAdditionalInformationDropdownEntries()',a)
lua.execute(r"""
predefined={};diploButtons={};euiMade=0
local stack=control();function stack:SortChildren(f)end
local corner={BuildInstanceForControl=function(self,kind,instance,parent)euiMade=euiMade+1;instance.Button=control()end}
function LookUpControl(path)
 if path=='/InGame/WorldView/DiploCorner/DiploCornerStack' then return stack end
 if path=='/InGame/WorldView/DiploCorner' then return corner end
 return nil
end
""")
lua.execute(notification[a:b])
lua.execute(source)
lua.execute(r"""
expect(sets,0,'load never enables logging');expect(refreshes,0,'no dependency on EUI dropdown refresh')
expect(Controls.StackDiagnosticsOpen.hidden,true,'normal play hides diagnostics access')
Controls.StackDiagnosticsOpen.callbacks[1]();expect(Controls.StackDiagnostics.hidden,true,'hidden normal-play button cannot open panel');expect(sets,0,'normal play access does not change logging')
autoTurns=5;ContextPtr.update(0.1);expect(Controls.StackDiagnosticsOpen.hidden,false,'autoplay shows access without selection or enabled roster')
local ev=LuaEvents.AdditionalInformationDropdownGatherEntries;local consume=ev.handlers[1]
local function emptyArt(entries)entries[#entries+1]={text='Legacy empty-art entry',art='',call=function()end}end
local function lateEntry(entries)entries[#entries+1]={text='Legacy late entry',call=function()end}end
-- Producer first: actual EUI skips the old empty-art design.
ev.Remove(consume);ev.Add(emptyArt);ev.Add(consume);local entries={};ev(entries)
expect(#entries,1,'empty-art entry exists in hidden menu');expect(euiMade,0,'actual EUI filters empty art');expect(Controls.StackDiagnosticsOpen.hidden,false,'standalone survives empty-art filtering')
-- Consumer first: actual EUI never sees a later-added ordinary entry.
ev.Remove(emptyArt);ev.Remove(consume);ev.Add(consume);ev.Add(lateEntry);entries={};ev(entries)
expect(#entries,1,'late entry exists after event');expect(euiMade,0,'actual EUI misses producer registered later');expect(Controls.StackDiagnosticsOpen.hidden,false,'standalone survives consumer registration order');ev.Remove(lateEntry)
Controls.StackDiagnosticsOpen.callbacks[1]();expect(Controls.StackDiagnostics.hidden,false,'standalone opens independent panel');expect(Controls.StackDiagnosticsState.text,'Current: Off','reads default off');expect(Controls.StackDiagnosticsOff.disabled,true,'current level disabled');expect(Controls.StackDiagnosticsSummary.disabled,false,'summary available');expect(sets,0,'opening panel read only');expect(Controls.StackDiagnosticsLog.text,'Disabled','native status shown')
expect(Controls.StackDiagnosticsRestart.text,'Reopening a game restores the XML default: Off.','default/reset notice')
Controls.StackDiagnosticsSummary.callbacks[1]();expect(level,1,'summary selection');expect(sets,1,'one native call');expect(Controls.StackDiagnosticsState.text,'Current: Summary','state refreshed');expect(Controls.StackDiagnosticsSummary.disabled,true,'current summary disabled');expect(Controls.StackDiagnosticsLog.text:find('Logging:')==1,true,'path displayed');expect(Controls.StackDiagnosticsLog.tip,Controls.StackDiagnosticsLog.text,'full status tooltip');expect(Controls.StackDiagnosticsOff.y>118,true,'buttons below dynamic status');expect(Controls.StackDiagnostics.h>Controls.StackDiagnosticsRestart.y,true,'panel contains reset notice')
Controls.StackDiagnosticsVerbose.callbacks[1]();expect(level,2,'verbose selection');expect(Controls.StackDiagnosticsVerbose.disabled,true,'current verbose disabled')
logError='Logging error: output unavailable';Controls.StackDiagnosticsSummary.callbacks[1]();expect(Controls.StackDiagnosticsLog.text,logError,'native errors remain visible');logError=nil
Controls.StackDiagnosticsOff.callbacks[1]();expect(level,0,'off selection');expect(Controls.StackDiagnosticsOff.disabled,true,'current off disabled')
local calls=sets;expect(ContextPtr.input(KeyEvents.KeyDown,Keys.VK_ESCAPE),true,'escape consumed while open');expect(Controls.StackDiagnostics.hidden,true,'escape closes');expect(sets,calls,'closing never changes level');expect(ContextPtr.input(KeyEvents.KeyDown,Keys.VK_ESCAPE),false,'escape passes through when closed')
level=2;Controls.StackDiagnosticsOpen.callbacks[1]();expect(Controls.StackDiagnosticsState.text,'Current: Verbose','external native change read on open')
Controls.StackDiagnosticsClose.callbacks[1]();expect(Controls.StackDiagnostics.hidden,true,'close button');Controls.StackDiagnosticsOpen.callbacks[1]();Events.SerialEventEnterCityScreen();expect(Controls.StackDiagnostics.hidden,true,'city screen closes panel');expect(Controls.StackDiagnosticsOpen.hidden,true,'city screen hides access button');Controls.StackDiagnosticsOpen.callbacks[1]();expect(Controls.StackDiagnostics.hidden,true,'does not open over city screen');Events.SerialEventExitCityScreen();expect(Controls.StackDiagnosticsOpen.hidden,false,'button returns after city screen');Controls.StackDiagnosticsOpen.callbacks[1]();expect(Controls.StackDiagnostics.hidden,false,'opens after city screen');Events.GameplaySetActivePlayer();expect(Controls.StackDiagnostics.hidden,true,'active player switch closes')
Controls.StackDiagnosticsOpen.callbacks[1]();local savedSets=sets;autoTurns=0;ContextPtr.update(0.1)
expect(Controls.StackDiagnosticsOpen.hidden,true,'autoplay end hides button without turn event');expect(Controls.StackDiagnostics.hidden,true,'autoplay end closes panel');expect(sets,savedSets,'mode exit does not disable native logging');expect(level,2,'chosen logging level preserved in normal play')
Controls.StackDiagnosticsSummary.callbacks[1]();expect(sets,savedSets,'stale hidden callback cannot change level')
observer=true;ContextPtr.update(0.1);expect(Controls.StackDiagnosticsOpen.hidden,false,'actual observer visible with autoplay0')
observer=false;ContextPtr.update(0.1);expect(Controls.StackDiagnosticsOpen.hidden,true,'leaving observer hides access')
activeOwner=-1;ContextPtr.update(0.1);expect(Controls.StackDiagnosticsOpen.hidden,true,'no active player handled safely')
autoTurns=3;ContextPtr.update(0.1);expect(Controls.StackDiagnosticsOpen.hidden,false,'positive autoplay remains sufficient without active player')
activeOwner=0;autoTurns=5
Game.GetStackingDiagnosticsStatus=nil;Events.GameplaySetActivePlayer();expect(Controls.StackDiagnosticsOpen.hidden,true,'old DLL without API hides button')
ContextPtr.shutdown();expect(#ev.handlers,1,'diagnostics never registers EUI menu handler')
""")

lua.execute(r"""
Game.GetStackingDiagnosticsStatus=function()return 'Buffered diagnostics' end
activeOwner=0;autoTurns=0;observer=false;level=0;Events.GameplaySetActivePlayer();ContextPtr.update(0.1)
local before=sets
LuaEvents.StackDiagnosticsToggle();expect(Controls.StackDiagnostics.hidden,false,'manual shortcut opens normal-play controls')
expect(Controls.StackDiagnosticsOpen.hidden,true,'manual shortcut never exposes normal-play button')
expect(sets,before,'opening via shortcut has no logging side effects')
ContextPtr.update(0.1);expect(Controls.StackDiagnostics.hidden,false,'normal-play mode polling retains manually opened panel')
Controls.StackDiagnosticsSummary.callbacks[1]();expect(level,1,'manual controls enable Summary in normal play')
LuaEvents.StackDiagnosticsToggle();expect(Controls.StackDiagnostics.hidden,true,'shortcut toggles panel closed');expect(level,1,'closing retains chosen logging')
LuaEvents.StackDiagnosticsToggle();ContextPtr.input(KeyEvents.KeyDown,Keys.VK_ESCAPE);expect(Controls.StackDiagnostics.hidden,true,'escape closes manual panel')
Controls.StackDiagnosticsVerbose.callbacks[1]();expect(level,1,'closed manual panel cannot enable logging via stale callbacks')
LuaEvents.StackDiagnosticsToggle();Events.SerialEventEnterCityScreen();expect(Controls.StackDiagnostics.hidden,true,'city screen clears manual diagnostic access')
LuaEvents.StackDiagnosticsToggle();expect(Controls.StackDiagnostics.hidden,true,'city screen cannot open diagnostic panel');Events.SerialEventExitCityScreen()
LuaEvents.StackDiagnosticsToggle();Events.GameplaySetActivePlayer();expect(Controls.StackDiagnostics.hidden,true,'active-player switch clears manual access')
UI.GetInterfaceMode=function()return interfaceMode end;interfaceMode=InterfaceModeTypes.INTERFACEMODE_SELECTION
UIManager.GetControl=function()return controlDown end;UIManager.GetShift=function()return shiftDown end
Keys.D=68;InterfaceModeMessageHandler={};DefaultMessageHandler={};UI.IsTouchScreenEnabled=function()return false end
controlDown=false;shiftDown=false
""")
for relative in ['UI_bc1/Improvements/WorldView.lua','(2) Vox Populi/Core Files/Overrides/WorldView.lua']:
 bridge=(r/relative).read_text(encoding='utf-8-sig');a=bridge.index('local stackMoveMode = false');b=bridge.index('ContextPtr:SetInputHandler( InputHandler );',a)+len('ContextPtr:SetInputHandler( InputHandler );')
 lua.execute('SavedPanelContext=ContextPtr;ContextPtr={SetInputHandler=function(self,f)self.input=f end}')
 lua.execute(bridge[a:b]);lua.execute('DiagnosticBridge=ContextPtr.input;ContextPtr=SavedPanelContext')
 lua.execute(r"""
expect(DiagnosticBridge(KeyEvents.KeyDown,Keys.D,0),false,'plain D is not a diagnostics shortcut')
controlDown=true;expect(DiagnosticBridge(KeyEvents.KeyDown,Keys.D,0),false,'Ctrl+D alone is not captured')
shiftDown=true;expect(DiagnosticBridge(KeyEvents.KeyDown,Keys.D,0),true,'actual Ctrl+Shift+D bridge consumes shortcut')
expect(Controls.StackDiagnostics.hidden,false,'actual bridge opens manual panel');expect(Controls.StackDiagnosticsOpen.hidden,true,'actual bridge keeps normal button hidden')
expect(DiagnosticBridge(KeyEvents.KeyDown,Keys.D,0),true,'actual bridge toggles closed');expect(Controls.StackDiagnostics.hidden,true,'bridge closes panel')
interfaceMode=99;expect(DiagnosticBridge(KeyEvents.KeyDown,Keys.D,0),false,'non-selection mode does not intercept shortcut');interfaceMode=0
controlDown=false;shiftDown=false
""")
# Disabled XML preference must also avoid consuming the key in the real WorldView bridge.
lua.execute(r"""
GameInfo.Stacking_Settings=function()local done=false;return function()if not done then done=true;return {Name='UIStackDiagnosticsHotkeyEnabled',Value=0} end end end
controlDown=true;shiftDown=true
""")
lua.execute('SavedPanelContext=ContextPtr;ContextPtr={SetInputHandler=function(self,f)self.input=f end}')
lua.execute(bridge[a:b]);lua.execute('DiagnosticBridge=ContextPtr.input;ContextPtr=SavedPanelContext')
lua.execute("expect(DiagnosticBridge(KeyEvents.KeyDown,Keys.D,0),false,'XML disables shortcut capture')")

xml=r/'(3a) VP - EUI Compatibility Files/LUA/StackPanel.xml';tree=ET.parse(xml)
ids={e.attrib['ID'] for e in tree.iter() if 'ID' in e.attrib}
needed={'StackDiagnosticsOpen','StackDiagnostics','StackDiagnosticsState','StackDiagnosticsLog','StackDiagnosticsRestart','StackDiagnosticsOff','StackDiagnosticsSummary','StackDiagnosticsVerbose','StackDiagnosticsClose'}
assert needed<=ids
button=tree.getroot().find("GridButton[@ID='StackDiagnosticsOpen']");assert button is not None and button.attrib['Anchor']=='C,T'
diplo=ET.parse(r/'(3a) VP - EUI Compatibility Files/LUA/DiploCorner.xml');assert diplo.find(".//PullDown[@ID='MultiPull']").attrib.get('Hidden')=='1'
assert 'AdditionalInformationDropdownGatherEntries' not in source
cpp=(r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.cpp').read_text(encoding='utf-8-sig');header=(r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.h').read_text(encoding='utf-8-sig')
for name in ('GetStackingDiagnosticsLevel','GetStackingDiagnosticsStatus','SetStackingDiagnosticsLevel','FlushStackingDiagnostics'):
 assert cpp.count('Method('+name+');')==1
 assert cpp.count('int CvLuaGame::l'+name+'(lua_State* L)')==1
 assert header.count('static int l'+name+'(lua_State* L);')==1
setter=cpp[cpp.index('int CvLuaGame::lSetStackingDiagnosticsLevel'):cpp.index('int CvLuaGame::lChangeActivePlayer')]
assert 'luaL_checknumber(L, 1)' in setter and 'level != 0 && level != 1 && level != 2' in setter
assert setter.index('luaL_error')<setter.index('CvStackingDiagnostics::SetLevel')
assert 'GetInstance(' not in setter and 'PushMission' not in setter and 'Rand' not in setter
files=[p,xml,r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.cpp',r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.h']
result={'lua51_checks':lua.globals().checks,'failures':0,'xml_parse':True,'actual_eui_empty_art_and_order_regressions':True,'observer_autoplay_visibility_regressions':True,'binding_declarations_and_level_guard_checked':True,'source_sha256':{str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest().upper() for x in files},'scope':'Actual full StackPanel Lua with deterministic UI/native-service stubs; checks standalone access/state/input/read-only behavior and actual EUI consumer failure cases and source registration. No DLL compile, live UI rendering or engine logging proof.'}
(r/'work/diagnostics-ui-regression').mkdir(exist_ok=True)
(r/'work/diagnostics-ui-regression/result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
