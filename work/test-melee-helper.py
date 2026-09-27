from pathlib import Path
import sys,json,hashlib
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'work/lua-validation'))
from lupa.lua51 import LuaRuntime
code=(root/'(1) Community Patch/Core Files/Stacking/StackingMeleeTests.lua').read_text(encoding='utf-8-sig');lua=LuaRuntime(unpack_returned_tuples=True);lua.execute('assert(loadstring(...))',code);lua.execute(code)
lua.execute('''
Game={GetGameTurn=function()return 0 end,GetAIAutoPlay=function()return 0 end}
ActivityTypes={ACTIVITY_AWAKE=0};MissionTypes={MISSION_MOVE_TO=9}
selected=nil;ordered=0;looked=false;busy=false;spent=false
local function defender(id)return {GetID=function()return id end,GetOwner=function()return 1 end,GetCurrHitPoints=function()return 100 end,GetX=function()return 1 end,GetY=function()return 0 end,GetMaxDefenseStrength=function()return 1000 end,GetScriptData=function()return 'STACKMELEE1|stub' end,IsCombatUnit=function()return true end,IsFighting=function()return false end,IsBusy=function()return false end}end
defenders={[11]=defender(11),[12]=defender(12)}
source={GetX=function()return 0 end,GetY=function()return 0 end}
target={GetX=function()return 1 end,GetY=function()return 0 end,GetNumUnits=function()return 2 end,GetUnit=function(self,i)return defenders[i+11]end}
attacker={GetID=function()return 10 end,GetOwner=function()return 0 end,GetCurrHitPoints=function()return 300 end,GetX=function()return 0 end,GetY=function()return 0 end,IsFighting=function()return false end,IsBusy=function()return busy end,IsOutOfAttacks=function()return spent end,SetMadeAttack=function()end,SetMoves=function()end,MaxMoves=function()return 120 end,SetActivityType=function()end,CanMoveOrAttackInto=function()return true end,GetStackAttackPreview=function()return {DefenderOwner=1,DefenderID=11,DirectDamage=10}end,GetMaxAttackStrength=function()return 1000 end,GetMeleeCombatDamage=function()return 10,5 end,PushMission=function(self,mission,x,y,a,b,c)assert(selected==attacker and looked and StackMeleeTests.state.pending,'Selection/look/pending order');assert(mission==9 and x==1 and y==0 and a==0 and b==0 and c==1,'mission arguments');ordered=ordered+1 end}
Players={[0]={IsTurnActive=function()return true end,GetUnitByID=function()return attacker end},[1]={GetUnitByID=function(self,id)return defenders[id]end}}
UI={SelectUnit=function(u)selected=u end,GetHeadSelectedUnit=function()return selected end,LookAt=function(p)assert(p==target);looked=true end}
StackMeleeTests.state={id='stub',owner=0,enemy=1,turn=0,attacker=10,source=source,target=target,expected=11,kind='protect',shots=0,guards={11,12}}
''')
lua.execute('StackMeleeTests.Fire()');assert lua.globals().ordered==1
before=lua.eval('StackMeleeTests.failed');lua.execute('StackMeleeTests.Check()');assert lua.eval('StackMeleeTests.state.pending') is not None and lua.eval('StackMeleeTests.failed')==before
lua.globals().busy=True;lua.execute('StackMeleeTests.Check()');assert lua.eval('StackMeleeTests.state.pending') is not None and lua.eval('StackMeleeTests.failed')==before
out=root/'work/melee-helper-regression';out.mkdir(exist_ok=True);result={'checks':5,'failures':0,'source_sha256':hashlib.sha256(code.encode()).hexdigest().upper(),'scope':'actual Lua Fire/Check with engine stubs: fixture selection before mission, look target, correct normal mission args, pristine/busy WAIT retains pending without false failure; no actual combat'};(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
