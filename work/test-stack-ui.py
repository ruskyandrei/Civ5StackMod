"""Isolated StackPanel behavior checks; live DLL/pathfinding tests remain separate."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "lua-validation"))
from lupa.lua51 import LuaRuntime
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r"""
function include() end
function control()
    local c = {values={}}
    return setmetatable(c, {__index=function(t,k)
        return function(self,...)
            if k == "RegisterCallback" then self.callback=select(2,...)
            else self.values[k]={...} end
        end
    end})
end
Controls=setmetatable({}, {__index=function(t,k) local c=control(); rawset(t,k,c); return c end})
local function event()
    local handlers={}
    return setmetatable({Add=function(f) handlers[#handlers+1]=f end, Remove=function(f) for i=#handlers,1,-1 do if handlers[i]==f then table.remove(handlers,i) end end end},
        {__call=function(_,...) for _,f in ipairs(handlers) do f(...) end end})
end
Events=setmetatable({}, {__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
LuaEvents=setmetatable({}, {__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
GameInfo={}
GameDefines={MOVE_DENOMINATOR=60}
ActivityTypes={ACTIVITY_MISSION=1}
DomainTypes={DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2}
Mouse={eLClick=1}
MouseEvents={LButtonUp=1,RButtonUp=2,LButtonDown=3,RButtonDown=4}
KeyEvents={KeyDown=10}
Keys={VK_ESCAPE=27}
InterfaceModeTypes={INTERFACEMODE_SELECTION=0}
Game={GetActivePlayer=function() return 0 end, GetActiveTeam=function() return 0 end}
sourcePlot={units={}}
function sourcePlot:GetNumUnits() return #self.units end
function sourcePlot:GetUnit(i) return self.units[i+1] end
function sourcePlot:IsVisible() return true end
function sourcePlot:IsCity() return false end
function sourcePlot:GetX() return 1 end
function sourcePlot:GetY() return 1 end
destination={GetX=function() return 2 end,GetY=function() return 1 end}
Map={GetPlot=function() return destination end}
Players={[0]={}}
Players[0].GetUnitByID=function(self,id) return sourcePlot.units[id] end
Players[0].IsTurnActive=function() return true end
Players[0].GetPlayerColors=function() return 1,2 end
for i=1,10 do
    local u={id=i,x=1,y=1}
    function u:GetID() return self.id end
    function u:GetOwner() return 0 end
    function u:GetPlot() return sourcePlot end
    function u:GetName() return "Archer "..self.id end
    function u:GetDomainType() return 0 end
    function u:IsGarrisoned() return self.id==1 end
    function u:IsCargo() return false end
    function u:IsCombatUnit() return true end
    function u:IsRanged() return true end
    function u:GetStackRoleInfo() return {Enabled=true,Flanker=false,AntiCavalry=false,CollateralTargets=0,CityProtection=0,CountsTowardCapacity=true} end
    function u:GetStackingLimit() return 10 end
    function u:GetCurrHitPoints() return 75 end
    function u:GetMaxHitPoints() return 100 end
    function u:MovesLeft() return 90 end
    function u:GetUnitType() return 0 end
    function u:IsInvisible() return false end
    function u:IsBusy() return false end
    function u:GetActivityType() return 0 end
    function u:GetX() return self.x end
    function u:GetY() return self.y end
    function u:GetStackMovePreview(dst,src,ids)
        assert(src==sourcePlot)
        assert(#ids==10,"must snapshot all and only tile members")
        local p={Moving=7,Staying=3,ProtectorStays=true,Members={}}
        for _,id in ipairs(ids) do p.Members[#p.Members+1]={UnitID=id,CanMove=id<=7,Reason=id<=7 and "Ready" or "NoMoves",Sent=false,Uncertain=id==7} end
        return p
    end
    function u:DoStackMove(dst,src,ids)
        local p=self:GetStackMovePreview(dst,src,ids)
        for _,m in ipairs(p.Members) do
            m.Sent=m.CanMove
            if m.Sent then sourcePlot.units[m.UnitID].x=2 end
        end
        return p
    end
    sourcePlot.units[i]=u
end
UI={GetHeadSelectedUnit=function() return sourcePlot.units[3] end,
    GetMouseOverHex=function() return 2,1 end, SetInterfaceMode=function() end,
    GetUnitPortraitIcon=function() return 0,"atlas" end, GetUnitFlagIcon=function() return 0,"flagAtlas" end}
UIManager={GetScreenSizeVal=function() return 1920,1080 end}
iconHookCount=0
function IconHookup(index,size,atlas) assert(size==32 and atlas=="flagAtlas"); iconHookCount=iconHookCount+1 end
function ToHexFromGrid(v) return v end
function Vector2(x,y) return {x=x,y=y} end
function Vector4(x,y,z,w) return {x=x,y=y,z=z,w=w} end
created={}
ContextPtr={}
function ContextPtr:BuildInstanceForControl(name,instance,parent)
    for _,id in ipairs({"Row","Portrait","Name","Detail"}) do instance[id]=control() end
    created[#created+1]=instance
end
function ContextPtr:SetUpdate(f) self.update=f end
function ContextPtr:SetInputHandler(f) self.input=f end
function ContextPtr:SetShutdown(f) self.shutdown=f end
""")
src=Path(__file__).parent.parent / "(3a) VP - EUI Compatibility Files/LUA/StackPanel.lua"
lua.execute(src.read_text(encoding="utf-8-sig"))
lua.execute(r"""
ContextPtr.update(0.1)
assert(#created==10,"all 10 members have rows")
assert(Controls.StackCapacity.values.SetText[1]=="Land 10/10","capacity agrees with combat occupants")
assert(created[1].Detail.values.SetText[1]:find("75/100 HP"),"health visible")
assert(created[1].Detail.values.SetText[1]:find("1.5"),"moves use game denominator")
assert(created[3].Name.values.SetText[1]:find("COLOR_YELLOW"),"selected member indicated")
Controls.StackMove.callback()
assert(Controls.StackSummary.values.SetText[1]:find("7 move; 3 stay"),"preview split summary")
assert(Controls.StackSummary.values.SetText[1]:find("Protector stays"),"protection warning")
assert(Controls.StackSummary.values.SetText[1]:find("fog"),"uncertainty warning")
ContextPtr.update(0.1)
assert(created[10].Detail.values.SetText[1]:find("No movement left"),"per-member reason")
LuaEvents.StackMoveInput(MouseEvents.RButtonUp,0)
ContextPtr.update(0.3)
assert(Controls.StackSummary.values.SetText[1]~=nil)
ContextPtr.update(0.1)
assert(Controls.StackSummary.values.SetText[1]:find("7 arrived; 3 stayed"),"post-order split summary")
assert(iconHookCount==10,"unchanged icons are hooked only once per row")
print("PASS: 10 rows, capacity, HP/moves, selected marker, preview reasons, protector/fog warnings, snapshot and result summary")
""")


flag_source=Path(__file__).parent.parent / "(3a) VP - EUI Compatibility Files/LUA/UnitFlagManager.lua"
flag_lua=flag_source.read_text(encoding="utf-8-sig")
start=flag_lua.index("local function UpdateStackBadges(plot)")
end=flag_lua.index("local function UpdatePlotFlags( plot )",start)
lua.execute(r"""
table_insert=table.insert
GetPlotNumUnits=function(p) return p:GetNumUnits() end
GetPlotUnit=function(p,i) return p:GetUnit(i) end
g_UnitFlags={[0]={}}
for i=1,10 do
    g_UnitFlags[0][i]={StackBadge=control(),Container=control(),m_UnitID=i,
        m_IsAirCraft=false,m_IsHiddenByFog=false,m_IsInvisibleToActiveTeam=false,m_IsSelected=i==3}
end
g_UnitFlags[0][10].m_IsInvisibleToActiveTeam=true
""")
lua.execute(flag_lua[start:end] + ";TestStackBadges = UpdateStackBadges")
lua.execute(r"""
TestStackBadges(sourcePlot)
assert(g_UnitFlags[0][3].StackBadge.values.SetText[1]=="9","invisible occupant excluded")
assert(g_UnitFlags[0][3].Container.values.SetHide[1]==false,"selected flag remains visible")
assert(g_UnitFlags[0][2].Container.values.SetHide[1]==true,"overlapping flags collapse")
g_UnitFlags[0][3].m_IsInvisibleToActiveTeam=true
TestStackBadges(sourcePlot)
assert(g_UnitFlags[0][1].StackBadge.values.SetText[1]=="8","hidden representative removed from count")
assert(g_UnitFlags[0][1].Container.values.SetHide[1]==false,"remaining flag becomes representative")
GameInfo.Stacking_Settings=function()
    local done=false
    return function()
        if not done then done=true; return {Name="UIStackFlagCollapseThreshold",Value=11} end
    end
end
TestStackBadges(sourcePlot)
assert(g_UnitFlags[0][2].Container.values.SetHide[1]==false,"XML threshold disables collapse")
assert(g_UnitFlags[0][1].StackBadge.values.SetHide[1]==true,"badge follows XML threshold")
print("PASS: visible-only badges, selected representative, fog replacement and XML collapse threshold")
""")


combat_path=Path(__file__).parent.parent / "(1) Community Patch/Core Files/Overrides/EnemyUnitPanel.lua"
combat_lua=combat_path.read_text(encoding="utf-8-sig")
combat_start=combat_lua.index("local g_StackSummaryRows")
combat_end=combat_lua.index("function UpdateCombatSimulator",combat_start)
lua.execute(r"""
myRows,theirRows={},{}
function summaryManager(rows)
    return {GetInstance=function()
        local row={Text=control(),Value=control()}
        rows[#rows+1]=row
        return row
    end}
end
g_MyCombatDataIM=summaryManager(myRows)
g_TheirCombatDataIM=summaryManager(theirRows)
summaryAttacker={
    GetStackRoleInfo=function() return {Enabled=true,CollateralTargets=5} end,
    IsCanAttackRanged=function() return true end
}
summaryPreview={DefenderOwner=0,DefenderID=2,CityProtection=90,ConditionalOnAirHit=true,
    Collateral={{Owner=0,UnitID=5,Damage=6},{Owner=0,UnitID=6,Damage=3}}}
""")
lua.execute(combat_lua[combat_start:combat_end] + ";TestCombatSummary = AppendStackCombatSummary")
lua.execute(r"""
TestCombatSummary(summaryAttacker, sourcePlot.units[2], nil, summaryPreview)
assert(theirRows[1].Text.values.SetText[1]=="Stack defender: Archer 2")
assert(myRows[1].Text.values.SetText[1]=="Collateral: 2 units")
assert(myRows[1].Value.values.SetText[1]:find("9 HP"),"sum actual secondary damage")
assert(myRows[1].Text.values.SetToolTipString[1]:find("Archer 5: 6 HP collateral"))
assert(myRows[2].Text.values.SetText[1]:find("bomber reaches target"))
myRows,theirRows={},{}
g_MyCombatDataIM=summaryManager(myRows)
g_TheirCombatDataIM=summaryManager(theirRows)
TestCombatSummary(summaryAttacker, nil, {Plot=function() return sourcePlot end}, summaryPreview)
assert(theirRows[1].Text.values.SetText[1]=="City collateral protection")
assert(theirRows[1].Value.values.SetText[1]=="90%")
print("PASS: shared-defender label, actual collateral count/total, city protection and bomber condition")
""")
from luaparser import ast
ast.parse(combat_lua)
print("PASS: integrated EnemyUnitPanel syntax")


panel_lua=src.read_text(encoding="utf-8-sig")
start=panel_lua.index("local function movementCounts")
end=panel_lua.index("local function setPreview",start)
lua.execute(r"""
function player() return Players[0] end
sourcePlot.units[2].GetTransportUnit=function() return sourcePlot.units[1] end
cargoPlan={Members={
 {UnitID=1,Reason="Ready",CanMove=true,Sent=true},
 {UnitID=2,Reason="Cargo",CanMove=false,Sent=false}
}}
""")
lua.execute(panel_lua[start:end] + ";TestMovementCounts=movementCounts")
lua.execute(r"""
local moving,staying=TestMovementCounts(cargoPlan,false)
assert(moving==2 and staying==0,"passenger rides with carrier in preview")
assert(cargoPlan.Members[2].CarriedBy==1,"passenger records expected transport")
moving,staying=TestMovementCounts(cargoPlan,true)
assert(moving==2 and staying==0,"passenger rides without own Sent flag")
cargoPlan.Members[1].Sent=false
moving,staying=TestMovementCounts(cargoPlan,true)
assert(moving==0 and staying==2,"unsent carrier does not move passenger")
print("PASS: cargo counts follow actual carrier eligibility/sent status without an independent mission")
""")


lua.execute(r"""
Controls.StackMove.callback()
sourcePlot.units[11]=setmetatable({id=11,x=1,y=1},{__index=sourcePlot.units[10]})
Events.SerialEventUnitInfoDirty()
ContextPtr.update(0.1)
local outside=created[11].Detail.values.SetText[1]:find("Outside order")~=nil
print("UIREG|late arrival marked outside frozen order|"..tostring(outside))
local oldPreview=sourcePlot.units[3].GetStackMovePreview
sourcePlot.units[3].GetStackMovePreview=function(self,dst,src,ids)
 local p=oldPreview(self,dst,src,ids)
 p.Moving=6;p.Staying=4;p.Members[7].CanMove=false;p.Members[7].Reason="NoMoves"
 return p
end
Events.SerialEventUnitInfoDirty()
ContextPtr.update(0.1)
local refreshed=Controls.StackSummary.values.SetText[1]:find("6 move; 4 stay")~=nil
print("UIREG|dirty state refreshes preview under stationary cursor|"..tostring(refreshed))
assert(outside and refreshed,"stack targeting state refresh regressions")
""")


# Map-only roster dismissal uses each real current input bridge, not a synthetic
# global mouse event. Native default handlers are still called for ordinary clicks.
for relative in ("UI_bc1/Improvements/WorldView.lua", "(2) Vox Populi/Core Files/Overrides/WorldView.lua"):
    bridge=(src.parents[2]/relative).read_text(encoding="utf-8-sig")
    a=bridge.index("local stackMoveMode = false")
    b=bridge.index("ContextPtr:SetInputHandler( InputHandler );",a)+len("ContextPtr:SetInputHandler( InputHandler );")
    lua.execute(r"""
sourcePlot.units[11]=nil
sourcePlot.units[3].GetStackMovePreview=sourcePlot.units[1].GetStackMovePreview
for _,u in ipairs(sourcePlot.units) do u.x=1;u.y=1 end
local selected=sourcePlot.units[3]
UI.GetHeadSelectedUnit=function()return selected end
emptyPlot={GetX=function()return 2 end,GetY=function()return 1 end,GetNumUnits=function()return 0 end}
clickedPlot=emptyPlot
Map.GetPlot=function(x,y)return clickedPlot end
UI.GetMouseOverHex=function()return clickedPlot:GetX(),clickedPlot:GetY()end
UI.IsTouchScreenEnabled=function()return false end
inputMode=InterfaceModeTypes.INTERFACEMODE_SELECTION;UI.GetInterfaceMode=function()return inputMode end
nativeLeft=0;DefaultMessageHandler={[MouseEvents.LButtonUp]=function()nativeLeft=nativeLeft+1;return false end}
InterfaceModeMessageHandler={[InterfaceModeTypes.INTERFACEMODE_SELECTION]={},[99]={}}
PanelContext=ContextPtr;ContextPtr={SetInputHandler=function(self,f)self.input=f end}
""")
    lua.execute(bridge[a:b])
    lua.execute(r"""
bridgeInput=ContextPtr.input;ContextPtr=PanelContext
LuaEvents.StackMoveInput(KeyEvents.KeyDown,Keys.VK_ESCAPE)
LuaEvents.StackRosterOpen(0,3);ContextPtr.update(0.1)
assert(Controls.StackPanel.values.SetHide[1]==false,"explicit inspection opens")
local movedCalls=0;local nativeMove=sourcePlot.units[3].DoStackMove
sourcePlot.units[3].DoStackMove=function(self,...)movedCalls=movedCalls+1;return nativeMove(self,...)end
assert(bridgeInput(MouseEvents.LButtonUp,0,0)==false and nativeLeft==1,"empty map click keeps native handler")
assert(Controls.StackPanel.values.SetHide[1]==true,"empty map click immediately hides roster")
Events.SerialEventUnitInfoDirty();ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==true,"dirty updates cannot reopen dismissed old selection")
Events.UnitSelectionChanged(0,3,1,1,0,false);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==true,"deselection cannot reopen")
Events.UnitSelectionChanged(0,3,1,1,0,true);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==true,"redundant same-unit selected event cannot reopen")
Events.UnitSelectionChanged(0,2,1,1,0,true);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"different-unit selection reopens")
bridgeInput(MouseEvents.LButtonUp,0,0);Events.SerialEventUnitFlagSelected(0,3);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"explicit same-unit flag selection reopens")
bridgeInput(MouseEvents.LButtonUp,0,0);clickedPlot=sourcePlot;bridgeInput(MouseEvents.LButtonUp,0,0);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"explicit own-unit map reselection reopens")
clickedPlot=sourcePlot;bridgeInput(MouseEvents.LButtonUp,0,0);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"nonempty visible tile does not dismiss")
local enemy={GetOwner=function()return 1 end,GetID=function()return 42 end,IsInvisible=function()return false end}
local fogPlot={GetX=function()return 7 end,GetY=function()return 7 end,GetNumUnits=function()return 1 end,GetUnit=function()return enemy end,IsVisible=function()return false end}
clickedPlot=fogPlot;bridgeInput(MouseEvents.LButtonUp,0,0);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==true,"fog-hidden enemy behaves as visually empty; no occupancy leak")
LuaEvents.StackRosterOpen(0,3);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"explicit reopen after dismissal")
fogPlot.IsVisible=function()return true end;enemy.IsInvisible=function()return true end
bridgeInput(MouseEvents.LButtonUp,0,0);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==true,"invisible unit behaves as empty")
LuaEvents.StackRosterOpen(0,3);ContextPtr.update(0.1);enemy.IsInvisible=function()return false end
bridgeInput(MouseEvents.LButtonUp,0,0);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"visible foreign unit prevents empty-click dismissal")
clickedPlot=emptyPlot;inputMode=99;bridgeInput(MouseEvents.LButtonUp,0,0);ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"other map modes do not dismiss")
inputMode=InterfaceModeTypes.INTERFACEMODE_SELECTION
created[2].Row.callback();ContextPtr.update(0.1);assert(Controls.StackPanel.values.SetHide[1]==false,"row selection stays visible")
Controls.StackMove.callback();ContextPtr.update(0.1);local before=nativeLeft
assert(bridgeInput(MouseEvents.LButtonUp,0,0)==true,"stack-order left click remains consumed cancellation")
ContextPtr.update(0.1);assert(nativeLeft==before and movedCalls==0,"cancel issues no native selection or stack movement")
assert(Controls.StackPanel.values.SetHide[1]==false,"cancel does not masquerade as empty-map dismissal")
Controls.StackMove.callback();ContextPtr.update(0.1)
assert(bridgeInput(MouseEvents.RButtonUp,0,0)==true and movedCalls==1,"real stack-order bridge still executes once")
ContextPtr.update(0.3);ContextPtr.update(0.1)
sourcePlot.units[3].DoStackMove=nativeMove
""")
    print("PASS: real input bridge empty/fog/invisible/nonempty/other-mode dismissal, dirty persistence, reopen, row selection and stack cancel/execute:",relative)

# Exercise the actual bound-publishing function and full panel layout against scaled screen sizes.
start=panel_lua.index("local function layoutPanel")
end=panel_lua.index("-- Cargo follows",start)
lua.execute(r"""
layoutChecks=0
function verify(ok,why) layoutChecks=layoutChecks+1;assert(ok,why) end
function setting(name,default)return default end
width=360;rowHeight=40;maxHeight=430;displayedRowCount=10;collapsed=false;status=""
combatPreviewVisible=true;combatPreviewTop=420
UIManager.GetScreenSizeVal=function()return 1280,720 end
""")
lua.execute(panel_lua[start:end]+";TestLayout=layoutPanel")
lua.execute(r"""
TestLayout()
verify(Controls.StackPanel.values.SetOffsetVal[2]==428,"roster above measured preview with gap")
local h=Controls.StackPanel.values.SetSizeVal[2]
verify(h+428<=660,"roster height constrained to screen")
verify(Controls.StackScroll.values.SetSizeVal[2]<430,"long roster scrolls in remaining space")
collapsed=true;TestLayout();verify(Controls.StackScroll.values.SetHide[1],"collapsed rows hidden")
combatPreviewVisible=false;TestLayout();verify(Controls.StackPanel.values.SetOffsetVal[2]==220,"normal offset restored")
combatPreviewVisible=true;combatPreviewTop=690;TestLayout();verify(Controls.StackPanel.values.SetHide[1],"no room hides instead of overlapping")
combatPreviewTop=320;UIManager.GetScreenSizeVal=function()return 1920,1080 end;collapsed=false;TestLayout()
verify(Controls.StackPanel.values.SetOffsetVal[2]==328,"resized/scaled preview recalculates anchor")
Controls.DetailsGrid.GetOffsetVal=function()return 109,160 end
Controls.DetailsGrid.GetSizeY=function()return 240 end
Controls.RangedAttackIndicator.GetOffsetY=function()return -18 end
LuaEvents.StackCombatPreviewBounds.Add(function(hidden,x,top) published={hidden,x,top} end)
""")
start=combat_lua.index("local function PublishStackPreviewBounds")
end=combat_lua.index("function RecalculateSize",start)
lua.execute(combat_lua[start:end]+";TestPublish=PublishStackPreviewBounds")
lua.execute(r"""
TestPublish(false);verify(published[1]==false and published[2]==109 and published[3]==418,"measured bounds include combat banner overhang")
TestPublish(true);verify(published[1],"hidden preview releases reserved space")
print("PASS: preview measured bounds/layout: "..layoutChecks.." checks")
""")
