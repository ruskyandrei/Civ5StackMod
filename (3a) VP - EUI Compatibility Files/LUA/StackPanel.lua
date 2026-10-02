-- A tile-local order; never changes Squad membership or selects adjacent units.
include("IconSupport")
include("InstanceManager")

local settings = {}
if GameInfo.Stacking_Settings then
    for row in GameInfo.Stacking_Settings() do settings[row.Name] = tonumber(row.Value) end
end
local function setting(name, default)
    return settings[name] or default
end
local active, snapshot, source, selectedID, preview, hoverPlot, pending, inspectPlot
-- quick: the modifier key is held, so hover previews and right-click orders cover the whole stack.
local quick, reach = false, nil
local collapsed, inCityScreen = false, false
local rosterDismissed = false
local dismissedOwner, dismissedUnitID
local rowInstances, rowByID = {}, {}
local displayedRowCount = 0
local width = math.max(260, setting("UIStackRosterWidth", 360))
local rowHeight = math.max(32, setting("UIStackRosterRowHeight", 38))
local maxHeight = math.max(rowHeight, setting("UIStackRosterMaximumHeight", 430))
local moveMinimum = math.max(2, setting("UIStackMoveMinimumUnits", 2))
local modifierKey = setting("UIStackMoveModifier", 0)
local modifierName = ({ [1] = "Shift", [2] = "Ctrl" })[modifierKey] or "Alt"
local reachColors = { all = Vector4(0.2, 0.9, 0.4, 0.45), some = Vector4(1, 0.8, 0.15, 0.45) }
local destinationColors = { all = Vector4(0.2, 0.9, 0.5, 1), some = Vector4(1, 0.8, 0.15, 1), none = Vector4(1, 0.25, 0.2, 1) }
local refreshNeeded = true
local status = ""
local combatPreviewVisible, combatPreviewTop = false, 0
local lastScreenX, lastScreenY
local reasons = {
    Ready = "Ready to move", Unavailable = "No longer available", LeftSource = "Left the source tile",
    Busy = "Busy or in combat", Cargo = "Cargo uses its transport", Aircraft = "Aircraft use rebase orders",
    NoMoves = "No movement left", AlreadyHere = "Already at destination",
    Enemy = "Enemy blocks route; use an explicit attack order", TerrainOrBorders = "Terrain or borders prevent entry",
    NoPath = "No legal path", LaterTurn = "Cannot arrive this turn", Capacity = "Destination stack is full",
    Queued = "Arrives in a later turn",
    ForeignStack = "Another player occupies the combat stack"
}
local function player() return Players[Game.GetActivePlayer()] end
local function leader()
    return selectedID and player():GetUnitByID(selectedID)
end
local function modifierHeld()
    if modifierKey == 1 then return UIManager:GetShift() end
    if modifierKey == 2 then return UIManager:GetControl() end
    return UIManager:GetAlt()
end
local function reasonText(member)
    if member.CarriedBy then return "Travels with transport" end
    local text = reasons[member.Reason] or member.Reason
    local turns = tonumber(member.Turns) or -1
    if (member.Reason == "Queued" or member.Reason == "LaterTurn") and turns > 0 then
        text = text .. string.format(" (%d turn%s)", turns, turns == 1 and "" or "s")
    end
    return text
end
local function isVisible(unit, plot)
    return unit:GetOwner() == Game.GetActivePlayer() or
        (plot:IsVisible(Game.GetActiveTeam(), true) and not unit:IsInvisible(Game.GetActiveTeam(), false))
end
local function members(plot, ownOnly)
    local result = {}
    if not plot then return result end
    for i = 0, plot:GetNumUnits() - 1 do
        local unit = plot:GetUnit(i)
        if unit and isVisible(unit, plot) and (not ownOnly or unit:GetOwner() == Game.GetActivePlayer()) then
            result[#result + 1] = unit
        end
    end
    table.sort(result, function(a, b)
        if a:GetOwner() ~= b:GetOwner() then return a:GetOwner() < b:GetOwner() end
        return a:GetID() < b:GetID()
    end)
    return result
end
local function setMode(value)
    active = value
    LuaEvents.StackMoveModeChanged(value)
    Events.ClearHexHighlights()
    if value then
        UI.SetInterfaceMode(InterfaceModeTypes.INTERFACEMODE_SELECTION)
        Controls.StackMoveLabel:SetText("Cancel")
    else
        Controls.StackMoveLabel:SetText("Move Stack")
    end
    refreshNeeded = true
end
local function clearHighlights()
    Events.ClearHexHighlights()
end
local function stopMode()
    setMode(false)
    snapshot, source, preview, hoverPlot, reach = nil, nil, nil, nil, nil
end
local function stopQuick()
    if not quick then return end
    quick = false
    LuaEvents.StackQuickModeChanged(false)
    snapshot, source, preview, hoverPlot, reach = nil, nil, nil, nil, nil
    clearHighlights()
    if not pending then status = "" end
    refreshNeeded = true
end
local function roleText(unit)
    local parts = {}
    local role = unit:GetStackRoleInfo()
    if unit:IsGarrisoned() then parts[#parts + 1] = "City garrison" end
    if unit:IsCargo() then parts[#parts + 1] = "Cargo"
    elseif unit:GetDomainType() == DomainTypes.DOMAIN_AIR then parts[#parts + 1] = "Aircraft"
    elseif not unit:IsCombatUnit() then parts[#parts + 1] = "Civilian / support"
    elseif unit:IsRanged() then parts[#parts + 1] = "Ranged"
    else parts[#parts + 1] = "Melee" end
    if role.Flanker then parts[#parts + 1] = "Flanking" end
    if role.AntiCavalry then parts[#parts + 1] = "Anti-cavalry" end
    if role.CollateralTargets > 0 then parts[#parts + 1] = "Collateral " .. role.CollateralTargets end
    return table.concat(parts, ", ")
end
-- Measure the wrapped labels rather than relying on a fixed footer allowance.
-- Top anchoring avoids multiline labels extending below the panel's bottom edge.
local function layoutPanel()
    Controls.StackSummary:SetWrapWidth(width - 34)
    Controls.StackCapacity:SetWrapWidth(width - 34)
    local capacityHeight = Controls.StackCapacity:GetSizeY() or 18
    local summaryHeight = status ~= "" and (Controls.StackSummary:GetSizeY() or 36) or 0
    local scrollY = 44 + capacityHeight + 8
    local footerSpace = summaryHeight > 0 and summaryHeight + 22 or 16
    local screenX, screenY = UIManager:GetScreenSizeVal()
    local offsetY = setting("UIStackRosterOffsetY", 220)
    if combatPreviewVisible then offsetY = math.max(offsetY, combatPreviewTop + math.max(0, math.min(100, setting("UIStackCombatPreviewGap", 8)))) end
    -- An unusually tall preview can consume all remaining screen space. Hide the
    -- roster until it closes rather than overlap either panel's labels.
    if combatPreviewVisible and offsetY + scrollY + footerSpace + 60 > screenY then
        Controls.StackPanel:SetHide(true)
        return
    end
    offsetY = math.min(offsetY, math.max(0, screenY - scrollY - footerSpace - 60))
    local available = math.max(0, screenY - offsetY - scrollY - footerSpace - 60)
    local height = collapsed and 0 or math.min(displayedRowCount * (rowHeight + 2), maxHeight, available)
    Controls.StackScroll:SetOffsetVal(12, scrollY)
    Controls.StackScroll:SetSizeVal(width - 24, height)
    Controls.StackScroll:CalculateInternalSize()
    Controls.StackScroll:SetHide(collapsed)
    Controls.StackSummary:SetHide(status == "")
    Controls.StackSummary:SetOffsetVal(16, scrollY + height + 8)
    Controls.StackPanel:SetSizeVal(width, scrollY + height + footerSpace)
    Controls.StackPanel:SetOffsetVal(math.min(setting("UIStackRosterOffsetX", 110), math.max(0, screenX - width)), offsetY)
    Controls.StackToggle:SetSizeX(width - 140)
end

-- Cargo follows its normal transport. It receives no independent move mission,
-- but it must not be described as staying when its carrier is moving.
local function movementCounts(plan, sentOnly)
    local byID, moving, staying = {}, 0, 0
    for _, member in ipairs(plan.Members) do byID[member.UnitID] = member end
    for _, member in ipairs(plan.Members) do
        member.CarriedBy = nil
        local unit = player():GetUnitByID(member.UnitID)
        if member.Reason == "Cargo" and unit then
            local carrier = unit:GetTransportUnit()
            local carrierMove = carrier and carrier:GetOwner() == Game.GetActivePlayer() and byID[carrier:GetID()]
            if carrierMove and ((sentOnly and carrierMove.Sent) or (not sentOnly and carrierMove.CanMove)) then
                member.CarriedBy = carrier:GetID()
            end
        end
        local goes = (sentOnly and member.Sent) or (not sentOnly and member.CanMove) or member.CarriedBy
        if goes then moving = moving + 1 else staying = staying + 1 end
    end
    return moving, staying, byID
end
local function setPreview(nextPreview)
    preview = nextPreview
    local moving, staying, byID = movementCounts(preview, false)
    local details, uncertain, queued = {}, false, 0
    for _, member in ipairs(preview.Members) do
        local unit = player():GetUnitByID(member.UnitID)
        local reason = member.CarriedBy and "Travels with transport; no independent move order" or reasonText(member)
        if member.Uncertain then reason = reason .. "; fog may interrupt movement"; uncertain = true end
        if member.CanMove and member.Reason == "Queued" then queued = queued + 1 end
        details[#details + 1] = (unit and unit:GetName() or "Unit") .. ": " .. reason
    end
    local outside = 0
    for id in pairs(rowByID) do if not byID[id] then outside = outside + 1 end end
    if queued > 0 then
        status = string.format("%d arrive now; %d later; %d stay", moving - queued, queued, staying)
    else
        status = string.format("%d move; %d stay", moving, staying)
    end
    if outside > 0 then status = status .. " (" .. outside .. " outside order)" end
    if preview.ProtectorStays then status = status .. " [COLOR_WARNING_TEXT]Protector stays![ENDCOLOR]" end
    if uncertain then status = status .. " (fog may stop units)" end
    if quick then
        status = status .. "[NEWLINE]" .. modifierName .. "+right-click moves the stack."
    else
        status = status .. "[NEWLINE]Right-click destination; left-click or Esc cancels."
    end
    Controls.StackSummary:SetToolTipString(table.concat(details, "[NEWLINE]"))
    for id, instance in pairs(rowByID) do
        local member = byID[id]
        if member then
            local unit = player():GetUnitByID(id)
            local base = unit and roleText(unit) or ""
            local reason = reasonText(member)
            local verdict = "[COLOR_WARNING_TEXT]Stay"
            if member.CanMove and member.Reason == "Queued" then verdict = "[COLOR_YELLOW]Later"
            elseif member.CanMove or member.CarriedBy then verdict = "[COLOR_POSITIVE_TEXT]Move" end
            instance.Detail:SetText(verdict .. "[ENDCOLOR] - " .. reason)
            instance.Row:SetToolTipString(base .. "[NEWLINE]" .. reason ..
                (member.Uncertain and "[NEWLINE]Fog may interrupt this path." or ""))
        else
            instance.Detail:SetText("[COLOR_GREY]Outside order[ENDCOLOR] - new arrival")
            instance.Row:SetToolTipString("This unit joined the tile after Move Stack was selected. Start a new order to include it.")
        end
    end
    Controls.StackSummary:SetText(status)
    layoutPanel()
end
local cannotMoveThisTurn = { NoMoves = true, Cargo = true, Aircraft = true, Busy = true, LeftSource = true, Unavailable = true }
-- Green: every member that can still move this turn arrives. Yellow: only some do,
-- or (with the modifier) the rest are ordered to arrive in later turns. Red: none move.
local function destinationColor(plan)
    local now, eligible = 0, 0
    for _, member in ipairs(plan.Members) do
        if member.CanMove and member.Reason ~= "Queued" then now = now + 1 end
        if not cannotMoveThisTurn[member.Reason] then eligible = eligible + 1 end
    end
    if reach then eligible = reach.Eligible end
    if now > 0 and now >= eligible then return destinationColors.all end
    if plan.Moving > 0 then return destinationColors.some end
    return destinationColors.none
end
local function drawHighlights(destination, color)
    clearHighlights()
    if reach then
        for _, plot in ipairs(reach.Plots) do
            Events.SerialEventHexHighlight(ToHexFromGrid(Vector2(plot.X, plot.Y)), true,
                plot.Arriving >= reach.Eligible and reachColors.all or reachColors.some)
        end
    end
    if destination then
        Events.SerialEventHexHighlight(ToHexFromGrid(Vector2(destination:GetX(), destination:GetY())), true, color)
    end
end
local function updateHover()
    if not active and not quick then return end
    local unit = leader()
    if not unit or not source then
        if active then stopMode() else stopQuick() end
        return
    end
    local x, y = UI.GetMouseOverHex()
    local plot = Map.GetPlot(x, y) or hoverPlot
    if not plot then return end
    hoverPlot = plot
    -- Both order paths queue members that cannot arrive this turn.
    setPreview(unit:GetStackMovePreview(plot, source, snapshot, true))
    drawHighlights(plot, destinationColor(preview))
end
local function takeSnapshot(unit)
    source, selectedID = unit:GetPlot(), unit:GetID()
    snapshot = {}
    for _, member in ipairs(members(source, true)) do snapshot[#snapshot + 1] = member:GetID() end
end
-- One reach search per member, refreshed with the roster rather than on every hover.
local function computeReach()
    local unit = leader()
    reach = unit and unit.GetStackMoveReach and unit:GetStackMoveReach(source, snapshot) or nil
end
local function quickLeader()
    if active or inCityScreen or setting("UIStackEnabled", 1) == 0 or not modifierHeld() then return nil end
    local mode = UI.GetInterfaceMode()
    if mode ~= InterfaceModeTypes.INTERFACEMODE_SELECTION and mode ~= InterfaceModeTypes.INTERFACEMODE_MOVE_TO then return nil end
    local unit = UI.GetHeadSelectedUnit()
    if not unit or unit:GetOwner() ~= Game.GetActivePlayer() or not unit.GetStackMoveReach or not player():IsTurnActive() then
        return nil
    end
    if #members(unit:GetPlot(), true) < moveMinimum then return nil end
    return unit
end
local function startQuick(unit)
    takeSnapshot(unit)
    computeReach()
    quick = true
    LuaEvents.StackQuickModeChanged(true)
    refreshNeeded = true
    updateHover()
end
local function buildRows()
    local screenWidth = UIManager:GetScreenSizeVal()
    width = math.min(math.max(260, setting("UIStackRosterWidth", 360)), math.max(260, screenWidth - 20))
    if inCityScreen or rosterDismissed then Controls.StackPanel:SetHide(true); return end
    local selected = UI.GetHeadSelectedUnit()
    if not selected and inspectPlot then
        for _, visibleUnit in ipairs(members(inspectPlot, false)) do selected = visibleUnit; break end
    end
    if not selected or not selected.GetStackMovePreview or not selected:GetStackRoleInfo().Enabled or setting("UIStackEnabled", 1) == 0 then
        Controls.StackPanel:SetHide(true)
        if active then stopMode() end
        return
    end
    local plot = active and source or inspectPlot or selected:GetPlot()
    local list = members(plot, false)
    if #list < 2 and not active and not pending then Controls.StackPanel:SetHide(true); return end
    Controls.StackPanel:SetHide(false)
    local own = members(plot, true)
    local land, sea, support, landCap, seaCap = 0, 0, 0, nil, nil
    for _, unit in ipairs(own) do
        if unit:GetStackRoleInfo().CountsTowardCapacity and unit:GetDomainType() == DomainTypes.DOMAIN_LAND then
            land = land + 1; landCap = unit:GetStackingLimit(plot)
        elseif unit:GetStackRoleInfo().CountsTowardCapacity and unit:GetDomainType() == DomainTypes.DOMAIN_SEA then
            sea = sea + 1; seaCap = unit:GetStackingLimit(plot)
        else support = support + 1 end
    end
    local capacity = {}
    if landCap then capacity[#capacity + 1] = "Land " .. land .. "/" .. landCap end
    if seaCap then capacity[#capacity + 1] = "Sea " .. sea .. "/" .. seaCap end
    if support > 0 then capacity[#capacity + 1] = "Other " .. support end
    local cityProtection = (#own > 0 and own[1]:GetStackRoleInfo().CityProtection) or 0
    if plot:IsCity() and cityProtection > 0 then capacity[#capacity + 1] = cityProtection .. "% collateral protection" end
    Controls.StackCapacity:SetText(table.concat(capacity, "  |  "))
    Controls.StackTitle:SetText((collapsed and "[ICON_PLUS] " or "[ICON_MINUS] ") .. "Stack: " .. #list .. " units")
    Controls.StackMove:SetHide(#own < moveMinimum or plot ~= selected:GetPlot())
    Controls.StackMove:SetDisabled(not player():IsTurnActive())
    Controls.StackMove:SetToolTipString("Move the members of this tile to a destination. Green tiles take every member that can still move this turn; yellow tiles only some. Members that cannot arrive this turn, including exhausted ones, continue in later turns. Each keeps its own movement allowance. Selected unit gets destination capacity first. Linked movement is released; Squad memberships are preserved.[NEWLINE][NEWLINE]Shortcut: hold " .. modifierName .. " and right-click a tile.")
    for _, instance in ipairs(rowInstances) do instance.Row:ChangeParent(Controls.StackScrap) end
    rowByID = {}
    for i, unit in ipairs(list) do
        local instance = rowInstances[i]
        if not instance then
            instance = {}
            ContextPtr:BuildInstanceForControl("StackMember", instance, Controls.StackRows)
            rowInstances[i] = instance
        else instance.Row:ChangeParent(Controls.StackRows) end
        instance.Row:SetSizeVal(width - 42, rowHeight)
        instance.Name:SetTruncateWidth(width - 95)
        instance.Detail:SetTruncateWidth(width - 95)
        local hp = unit:GetCurrHitPoints()
        local moves = unit:MovesLeft() / GameDefines.MOVE_DENOMINATOR
        local isSelected = unit:GetOwner() == selected:GetOwner() and unit:GetID() == selected:GetID()
        instance.Name:SetText((isSelected and "[COLOR_YELLOW]" or "") .. unit:GetName() ..
            (isSelected and "[ENDCOLOR]" or ""))
        instance.Detail:SetText(string.format("%d/%d HP  %s[ICON_MOVES]  %s", hp, unit:GetMaxHitPoints(),
            string.format("%.1f", moves), roleText(unit)))
        local nameHeight = instance.Name:GetSizeY() or 20
        local detailHeight = instance.Detail:GetSizeY() or 18
        instance.Detail:SetOffsetVal(42, 4 + nameHeight + 2)
        -- The XML row-height setting is a minimum; never clip either rendered line.
        rowHeight = math.max(rowHeight, 4 + nameHeight + 2 + detailHeight + 6, 32 + 8)
        instance.Row:SetToolTipString(unit:GetName() .. "[NEWLINE]" .. roleText(unit) .. "[NEWLINE]" ..
            hp .. "/" .. unit:GetMaxHitPoints() .. " HP; " .. string.format("%.1f", moves) .. " movement remaining")
        local unitID, ownerID = unit:GetID(), unit:GetOwner()
        instance.Row:SetDisabled(ownerID ~= Game.GetActivePlayer())
        instance.Row:RegisterCallback(Mouse.eLClick, function()
            if active then stopMode() end
            inspectPlot = nil
            rosterDismissed = false
            Events.SerialEventUnitFlagSelected(ownerID, unitID)
            status = ""
            refreshNeeded = true
        end)
        -- Unit portrait atlases do not necessarily contain a 32px sheet. Flag atlases
        -- do, and use the same icons as the map flags. Cache the hookup per row.
        local flagIndex, flagAtlas = UI.GetUnitFlagIcon(unit)
        local iconKey = tostring(flagIndex) .. ":" .. tostring(flagAtlas) .. ":" .. ownerID
        if instance.StackIconKey ~= iconKey then
            IconHookup(flagIndex, 32, flagAtlas, instance.Portrait)
            local iconColor = Players[ownerID]:GetPlayerColors()
            instance.Portrait:SetColor(iconColor)
            instance.StackIconKey = iconKey
        end
        if ownerID == Game.GetActivePlayer() then rowByID[unitID] = instance end
    end
    displayedRowCount = #list
    for i = 1, displayedRowCount do rowInstances[i].Row:SetSizeVal(width - 42, rowHeight) end
    Controls.StackRows:CalculateSize()
    Controls.StackRows:ReprocessAnchoring()
    Controls.StackSummary:SetText(status)
    layoutPanel()
    if active then updateHover() end
end
-- Diagnostics is independent of the selected stack and starts no Lua observer.
-- A standalone control avoids hidden EUI dropdowns and listener-order dependencies.
local diagnosticsVisible = false
local diagnosticsManualAccess = false
local diagnosticNames = { [0] = "Off", [1] = "Summary", [2] = "Verbose" }
local function diagnosticsAvailable()
    return Game.GetStackingDiagnosticsLevel and Game.SetStackingDiagnosticsLevel and Game.GetStackingDiagnosticsStatus
end
local diagnosticsAccess
local function diagnosticsModeAllowed()
    local current = Players[Game.GetActivePlayer()]
    return (Game.GetAIAutoPlay and Game.GetAIAutoPlay() > 0) or
        (current and current.IsObserver and current:IsObserver()) or false
end
local function updateDiagnosticsAccess()
    local allowed = not inCityScreen and diagnosticsAvailable() and diagnosticsModeAllowed() or false
    if allowed ~= diagnosticsAccess then
        diagnosticsAccess = allowed
        Controls.StackDiagnosticsOpen:SetHide(not allowed)
    end
    if not allowed and not (diagnosticsManualAccess and not inCityScreen and diagnosticsAvailable()) and diagnosticsVisible then
        diagnosticsVisible = false
        Controls.StackDiagnostics:SetHide(true)
    end
end
local function refreshDiagnostics()
    if not diagnosticsAvailable() then
        diagnosticsVisible = false
        Controls.StackDiagnostics:SetHide(true)
        return
    end
    local level = Game.GetStackingDiagnosticsLevel()
    Controls.StackDiagnosticsState:SetText("Current: " .. (diagnosticNames[level] or tostring(level)))
    Controls.StackDiagnosticsOff:SetDisabled(level == 0)
    Controls.StackDiagnosticsSummary:SetDisabled(level == 1)
    Controls.StackDiagnosticsVerbose:SetDisabled(level == 2)
    local message = Game.GetStackingDiagnosticsStatus()
    Controls.StackDiagnosticsLog:SetText(message)
    Controls.StackDiagnosticsLog:SetToolTipString(message)
    Controls.StackDiagnosticsRestart:SetText("Reopening a game restores the XML default: " .. (diagnosticNames[setting("DiagnosticsLevel", 0)] or "Off") .. ".")
    local buttonsY = 118 + (Controls.StackDiagnosticsLog:GetSizeY() or 36) + 12
    Controls.StackDiagnosticsOff:SetOffsetVal(16, buttonsY)
    Controls.StackDiagnosticsSummary:SetOffsetVal(122, buttonsY)
    Controls.StackDiagnosticsVerbose:SetOffsetVal(228, buttonsY)
    Controls.StackDiagnosticsRestart:SetOffsetVal(16, buttonsY + 40)
    Controls.StackDiagnostics:SetSizeVal(342, buttonsY + 40 + (Controls.StackDiagnosticsRestart:GetSizeY() or 32) + 16)
end
local function closeDiagnostics()
    diagnosticsManualAccess = false
    diagnosticsVisible = false
    Controls.StackDiagnostics:SetHide(true)
end
local function openDiagnostics(manual)
    if manual and not inCityScreen and diagnosticsAvailable() then diagnosticsManualAccess = true end
    updateDiagnosticsAccess()
    if not diagnosticsAccess and not diagnosticsManualAccess then return end
    if active then stopMode(); status = "" end
    diagnosticsVisible = true
    refreshDiagnostics()
    Controls.StackDiagnostics:SetHide(false)
end
local function setDiagnostics(level)
    updateDiagnosticsAccess()
    if not diagnosticsAccess and not diagnosticsManualAccess then return end
    Game.SetStackingDiagnosticsLevel(level)
    refreshDiagnostics()
end
Controls.StackDiagnosticsOff:RegisterCallback(Mouse.eLClick, function() setDiagnostics(0) end)
Controls.StackDiagnosticsSummary:RegisterCallback(Mouse.eLClick, function() setDiagnostics(1) end)
Controls.StackDiagnosticsVerbose:RegisterCallback(Mouse.eLClick, function() setDiagnostics(2) end)
Controls.StackDiagnosticsClose:RegisterCallback(Mouse.eLClick, closeDiagnostics)
Controls.StackDiagnosticsOpen:RegisterCallback(Mouse.eLClick, function() openDiagnostics(false) end)
LuaEvents.StackDiagnosticsToggle.Add(function()
    if setting("UIStackDiagnosticsHotkeyEnabled", 1) == 0 or inCityScreen or not diagnosticsAvailable() then return end
    if diagnosticsVisible then closeDiagnostics() else openDiagnostics(true) end
end)
updateDiagnosticsAccess()
ContextPtr:SetInputHandler(function(uiMsg, wParam)
    if diagnosticsVisible and uiMsg == KeyEvents.KeyDown and wParam == Keys.VK_ESCAPE then
        closeDiagnostics()
        return true
    end
    return false
end)

local function beginMove()
    if active then stopMode(); status = ""; return end
    local unit = UI.GetHeadSelectedUnit()
    if not unit or unit:GetOwner() ~= Game.GetActivePlayer() then return end
    stopQuick()
    takeSnapshot(unit)
    if #snapshot < moveMinimum then return end
    computeReach()
    rosterDismissed = false
    status = "Choose destination. Right-click to move; left-click or Esc cancels."
    pending = nil
    setMode(true)
    updateHover()
end
Controls.StackMove:RegisterCallback(Mouse.eLClick, beginMove)
Controls.StackToggle:RegisterCallback(Mouse.eLClick, function() collapsed = not collapsed; refreshNeeded = true end)
-- Shared by the Move Stack button and the modifier shortcut.
local function orderStack(unit, plot)
    local result = unit:DoStackMove(plot, source, snapshot, true)
    local moving, staying = movementCounts(result, true)
    local queued = 0
    for _, member in ipairs(result.Members) do
        if member.Sent and member.Reason == "Queued" then queued = queued + 1 end
    end
    pending = { members = result.Members, x = plot:GetX(), y = plot:GetY(), elapsed = 0 }
    if queued > 0 then
        status = string.format("Ordered %d to move (%d over later turns); %d stay.", moving, queued, staying)
    else
        status = string.format("Ordered %d to move; %d stay.", moving, staying)
    end
end
LuaEvents.StackMoveInput.Add(function(uiMsg, wParam)
    if not active then return end
    if uiMsg == MouseEvents.RButtonUp then
        local unit = leader()
        if unit and hoverPlot then orderStack(unit, hoverPlot) end
        stopMode()
    elseif uiMsg == MouseEvents.LButtonUp or (uiMsg == KeyEvents.KeyDown and wParam == Keys.VK_ESCAPE) then
        stopMode(); status = ""
    end
end)
-- WorldView asks before its own right-click handling; leaving order.handled unset keeps the
-- native single-unit order (attacks included).
LuaEvents.StackQuickMoveInput.Add(function(x, y, order)
    if not quick or active or not modifierHeld() then return end
    local unit, plot = leader(), Map.GetPlot(x, y)
    if not unit or not plot or not source or plot == source then return end
    if unit:GetStackMovePreview(plot, source, snapshot, true).Moving == 0 then return end
    orderStack(unit, plot)
    order.handled = true
    -- The poll restarts the overlay from the new tile while the key stays held.
    stopQuick()
end)
-- Only WorldView forwards map clicks; button/row clicks do not reach this bridge.
-- Treat invisible units like an empty tile so dismissal reveals no hidden occupants.
LuaEvents.StackRosterMapLeftClick.Add(function(x, y)
    if active or inCityScreen then return end
    local plot = Map.GetPlot(x, y)
    if not plot then return end
    local visible = members(plot, false)
    if #visible == 0 then
        local selected = UI.GetHeadSelectedUnit()
        dismissedOwner = selected and selected:GetOwner()
        dismissedUnitID = selected and selected:GetID()
        inspectPlot = nil
        rosterDismissed = true
        status = ""
        Controls.StackPanel:SetHide(true)
        refreshNeeded = true
    else
        -- Clicking our visible units is an explicit selection gesture, including
        -- selecting the same unit again after an empty-map dismissal.
        for _, unit in ipairs(visible) do
            if unit:GetOwner() == Game.GetActivePlayer() then
                rosterDismissed = false
                refreshNeeded = true
                break
            end
        end
    end
end)
Events.SerialEventUnitFlagSelected.Add(function()
    rosterDismissed = false
    refreshNeeded = true
end)
LuaEvents.StackRosterOpen.Add(function(ownerID, unitID)
    local unit = Players[ownerID]:GetUnitByID(unitID)
    if unit and isVisible(unit, unit:GetPlot()) then
        if active then stopMode() end
        if ownerID == Game.GetActivePlayer() then Events.SerialEventUnitFlagSelected(ownerID, unitID) end
        inspectPlot = unit:GetPlot()
        rosterDismissed = false
        collapsed = false
        refreshNeeded = true
    end
end)
LuaEvents.StackCombatPreviewBounds.Add(function(hidden, x, top)
    combatPreviewVisible = not hidden
    combatPreviewTop = math.max(0, tonumber(top) or 0)
    refreshNeeded = true
end)
Events.SerialEventMouseOverHex.Add(updateHover)
Events.SerialEventUnitInfoDirty.Add(function() refreshNeeded = true end)
Events.UnitVisibilityChanged.Add(function() refreshNeeded = true end)
Events.UnitStateChangeDetected.Add(function() refreshNeeded = true end)
Events.HexFOWStateChanged.Add(function() refreshNeeded = true end)
Events.SerialEventEnterCityScreen.Add(function() inCityScreen = true; closeDiagnostics(); updateDiagnosticsAccess(); stopMode(); stopQuick(); refreshNeeded = true end)
Events.SerialEventExitCityScreen.Add(function() inCityScreen = false; updateDiagnosticsAccess(); refreshNeeded = true end)
Events.UnitSelectionChanged.Add(function(ownerID, unitID, x, y, z, isSelected)
    if isSelected and (not rosterDismissed or ownerID ~= dismissedOwner or unitID ~= dismissedUnitID) then
        rosterDismissed = false
    end
    if active and isSelected and (ownerID ~= Game.GetActivePlayer() or unitID ~= selectedID) then
        stopMode(); status = ""
    end
    if not active then inspectPlot = nil end
    refreshNeeded = true
end)
Events.InterfaceModeChanged.Add(function(oldMode, newMode)
    if active and newMode ~= InterfaceModeTypes.INTERFACEMODE_SELECTION then stopMode(); status = "" end
end)
Events.UnitMoveQueueChanged.Add(function() refreshNeeded = true end)
Events.GameplaySetActivePlayer.Add(function() closeDiagnostics(); updateDiagnosticsAccess(); stopMode(); stopQuick(); rosterDismissed = false; pending = nil; status = ""; refreshNeeded = true end)
Events.ActivePlayerTurnEnd.Add(function() stopMode(); stopQuick(); pending = nil; status = "" end)
ContextPtr:SetUpdate(function(delta)
    -- Mode can change during autoplay without a selection/turn event. Poll only
    -- these cheap mode flags; native diagnostic sampling remains in the DLL.
    updateDiagnosticsAccess()
    local sx, sy = UIManager:GetScreenSizeVal()
    if sx ~= lastScreenX or sy ~= lastScreenY then
        lastScreenX, lastScreenY, refreshNeeded = sx, sy, true
    end
    -- Only polled while the key is held; otherwise this is one modifier check per frame.
    local quickUnit = quickLeader()
    if quick and (not quickUnit or quickUnit:GetID() ~= selectedID) then stopQuick() end
    if quickUnit and not quick then startQuick(quickUnit) end
    if refreshNeeded then
        refreshNeeded = false
        if quick then
            local unit = leader()
            if unit then takeSnapshot(unit); computeReach() end
        elseif active then computeReach() end
        buildRows()
        -- Also when the roster itself is hidden or dismissed.
        if quick then updateHover() end
    end
    if pending then
        pending.elapsed = pending.elapsed + delta
        if pending.elapsed >= setting("UIStackResultDelayMilliseconds", 250) / 1000 then
            local busy, arrived, stopped, stayed, onTheWay = false, 0, 0, 0, 0
            local byID = {}
            for _, member in ipairs(pending.members) do byID[member.UnitID] = member end
            for _, member in ipairs(pending.members) do
                local unit = player():GetUnitByID(member.UnitID)
                local carrier = member.CarriedBy and byID[member.CarriedBy]
                -- Later-turn orders keep their mission after this turn's steps end.
                local later = member.Reason == "Queued" or (carrier and carrier.Reason == "Queued")
                if member.Sent or member.CarriedBy then
                    if unit and (unit:IsBusy() or (not later and unit:GetActivityType() == ActivityTypes.ACTIVITY_MISSION)) then busy = true end
                    if unit and unit:GetX() == pending.x and unit:GetY() == pending.y then arrived = arrived + 1
                    elseif later then onTheWay = onTheWay + 1
                    else stopped = stopped + 1 end
                else stayed = stayed + 1 end
            end
            if not busy then
                status = string.format("%d arrived; %d stayed", arrived, stayed)
                if onTheWay > 0 then status = status .. string.format("; %d on the way", onTheWay) end
                if stopped > 0 then status = status .. string.format("; %d stopped en route.", stopped) end
                Events.GameplayAlertMessage("Stack move: " .. status)
                pending = nil
                refreshNeeded = true
            end
        end
    end
end)
print("Stack roster and tile-local movement UI loaded")

ContextPtr:SetShutdown(function()
    if active then LuaEvents.StackMoveModeChanged(false) end
    if quick then LuaEvents.StackQuickModeChanged(false) end
end)
