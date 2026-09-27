from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET
r=Path(r'E:\Projects\Civ5StackMod');sys.path.insert(0,str(r/'work/lua-validation'))
from lupa.lua51 import LuaRuntime
p=r/'(3a) VP - EUI Compatibility Files/LUA/StackPanel.lua';source=p.read_text(encoding='utf-8-sig')
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
checks=0;sets=0;level=0;refreshes=0
function expect(a,b,msg)checks=checks+1;assert(a==b,msg..': '..tostring(a)..' != '..tostring(b))end
function include()end
print=function()end
function event()
 local h={};local e={}
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
Game={GetActivePlayer=function()return 0 end,GetActiveTeam=function()return 0 end,GetStackingDiagnosticsLevel=function()return level end,SetStackingDiagnosticsLevel=function(n)assert(n==0 or n==1 or n==2);sets=sets+1;level=n;return n end,GetStackingDiagnosticsStatus=function()return logError or (level==0 and 'Disabled' or 'Logging: C:/Users/Test/Documents/My Games/Civ V/Logs/StackingDiagnostics-session-1.csv')end}
Players={[0]={IsTurnActive=function()return true end}}
UI={GetHeadSelectedUnit=function()return nil end}
Mouse={eLClick=1};MouseEvents={RButtonUp=2,LButtonUp=3};KeyEvents={KeyDown=4};Keys={VK_ESCAPE=27};InterfaceModeTypes={INTERFACEMODE_SELECTION=0}
ContextPtr={SetInputHandler=function(self,f)self.input=f end,SetUpdate=function(self,f)self.update=f end,SetShutdown=function(self,f)self.shutdown=f end}
''')
lua.execute(source)
lua.execute(r'''
expect(sets,0,'load never enables logging');expect(refreshes,1,'request menu refresh once')
local entries={};LuaEvents.AdditionalInformationDropdownGatherEntries(entries)
expect(#entries,1,'available with no selected unit and roster disabled');expect(entries[1].text,'Stack diagnostics','menu label');expect(entries[1].art,'','no extra floating shortcut')
entries[1].call();expect(Controls.StackDiagnostics.hidden,false,'menu opens independent panel');expect(Controls.StackDiagnosticsState.text,'Current: Off','reads default off');expect(Controls.StackDiagnosticsOff.disabled,true,'current level disabled');expect(Controls.StackDiagnosticsSummary.disabled,false,'summary available');expect(sets,0,'opening panel read only');expect(Controls.StackDiagnosticsLog.text,'Disabled','native status shown')
expect(Controls.StackDiagnosticsRestart.text,'Reopening a game restores the XML default: Off.','default/reset notice')
Controls.StackDiagnosticsSummary.callbacks[1]();expect(level,1,'summary selection');expect(sets,1,'one native call');expect(Controls.StackDiagnosticsState.text,'Current: Summary','state refreshed');expect(Controls.StackDiagnosticsSummary.disabled,true,'current summary disabled');expect(Controls.StackDiagnosticsLog.text:find('Logging:')==1,true,'path displayed');expect(Controls.StackDiagnosticsLog.tip,Controls.StackDiagnosticsLog.text,'full status tooltip');expect(Controls.StackDiagnosticsOff.y>118,true,'buttons below dynamic status');expect(Controls.StackDiagnostics.h>Controls.StackDiagnosticsRestart.y,true,'panel contains reset notice')
Controls.StackDiagnosticsVerbose.callbacks[1]();expect(level,2,'verbose selection');expect(Controls.StackDiagnosticsVerbose.disabled,true,'current verbose disabled')
logError='Logging error: output unavailable';Controls.StackDiagnosticsSummary.callbacks[1]();expect(Controls.StackDiagnosticsLog.text,logError,'native errors remain visible');logError=nil
Controls.StackDiagnosticsOff.callbacks[1]();expect(level,0,'off selection');expect(Controls.StackDiagnosticsOff.disabled,true,'current off disabled')
local calls=sets;expect(ContextPtr.input(KeyEvents.KeyDown,Keys.VK_ESCAPE),true,'escape consumed while open');expect(Controls.StackDiagnostics.hidden,true,'escape closes');expect(sets,calls,'closing never changes level');expect(ContextPtr.input(KeyEvents.KeyDown,Keys.VK_ESCAPE),false,'escape passes through when closed')
level=2;entries[1].call();expect(Controls.StackDiagnosticsState.text,'Current: Verbose','external native change read on open')
Controls.StackDiagnosticsClose.callbacks[1]();expect(Controls.StackDiagnostics.hidden,true,'close button');entries[1].call();Events.SerialEventEnterCityScreen();expect(Controls.StackDiagnostics.hidden,true,'city screen closes panel');entries[1].call();expect(Controls.StackDiagnostics.hidden,true,'does not open over city screen');Events.SerialEventExitCityScreen();entries[1].call();expect(Controls.StackDiagnostics.hidden,false,'opens after city screen');Events.GameplaySetActivePlayer();expect(Controls.StackDiagnostics.hidden,true,'active player switch closes')
Game.GetStackingDiagnosticsStatus=nil;entries={};LuaEvents.AdditionalInformationDropdownGatherEntries(entries);expect(#entries,0,'old DLL without API has no menu entry')
Game.GetStackingDiagnosticsStatus=function()return 'Disabled'end;ContextPtr.shutdown();entries={};LuaEvents.AdditionalInformationDropdownGatherEntries(entries);expect(#entries,0,'shutdown removes menu hook')
''')
xml=r/'(3a) VP - EUI Compatibility Files/LUA/StackPanel.xml';tree=ET.parse(xml)
ids={e.attrib['ID'] for e in tree.iter() if 'ID' in e.attrib}
needed={'StackDiagnostics','StackDiagnosticsState','StackDiagnosticsLog','StackDiagnosticsRestart','StackDiagnosticsOff','StackDiagnosticsSummary','StackDiagnosticsVerbose','StackDiagnosticsClose'}
assert needed<=ids
cpp=(r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.cpp').read_text(encoding='utf-8-sig');header=(r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.h').read_text(encoding='utf-8-sig')
for name in ('GetStackingDiagnosticsLevel','GetStackingDiagnosticsStatus','SetStackingDiagnosticsLevel'):
 assert cpp.count('Method('+name+');')==1
 assert cpp.count('int CvLuaGame::l'+name+'(lua_State* L)')==1
 assert header.count('static int l'+name+'(lua_State* L);')==1
setter=cpp[cpp.index('int CvLuaGame::lSetStackingDiagnosticsLevel'):cpp.index('int CvLuaGame::lChangeActivePlayer')]
assert 'luaL_checknumber(L, 1)' in setter and 'level != 0 && level != 1 && level != 2' in setter
assert setter.index('luaL_error')<setter.index('CvStackingDiagnostics::SetLevel')
assert 'GetInstance(' not in setter and 'PushMission' not in setter and 'Rand' not in setter
files=[p,xml,r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.cpp',r/'CvGameCoreDLL_Expansion2/Lua/CvLuaGame.h']
result={'lua51_checks':lua.globals().checks,'failures':0,'xml_parse':True,'binding_declarations_and_level_guard_checked':True,'source_sha256':{str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest().upper() for x in files},'scope':'Actual full StackPanel Lua with deterministic UI/native-service stubs; checks menu/state/input/read-only behavior and source registration. No DLL compile, live UI rendering or engine logging proof.'}
(r/'work/diagnostics-ui-regression').mkdir(exist_ok=True)
(r/'work/diagnostics-ui-regression/result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
