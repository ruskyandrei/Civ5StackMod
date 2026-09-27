from pathlib import Path
import sys,json,hashlib
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'work/lua-validation'))
from lupa.lua51 import LuaRuntime
d=r/'work/production-resume-030606'
names=['01-check-queue.lua','02-check-units.lua','02b-check-blocked-turn.lua','03-open-slot.lua','04-check-open.lua','05-check-complete.lua'];blocks=[(d/n).read_text(encoding='utf-8') for n in names]
stub="""
logs={};print=function(...)logs[#logs+1]={...}end
turn=2;order={{0,83,3,true,false},{1,25,-1,false,false}};bank=64;things=0;opened=false;mutations=0;missions=0;handler=nil
Game={GetActivePlayer=function()return 0 end,GetGameTurn=function()return turn end};ActivityTypes={ACTIVITY_AWAKE=0,ACTIVITY_SLEEP=1};MissionTypes={MISSION_MOVE_TO=1}
units={};function unit(id,x,y)local u={id=id,x=x,y=y,hp=100,moves=0};function u:GetID()return self.id end;function u:GetX()return self.x end;function u:GetY()return self.y end;function u:GetUnitType()return 83 end;function u:GetCurrHitPoints()return self.hp end;function u:GetPlot()return self end;function u:CanStackAtPlot()return true end;function u:IsBusy()return false end;function u:IsFighting()return false end;function u:GetMoves()return self.moves end;function u:CanMoveOrAttackInto(p,a,b)assert(a==0 and b==1);return true end;function u:SetActivityType(n)assert(type(n)=='number');mutations=mutations+1 end;function u:PushMission(m,x,y,f,a,b)assert(m==1 and f==0 and a==0 and b==1 and self.moves>0);missions=missions+1;mutations=mutations+1;self.x=x;self.y=y;self.moves=0;opened=true end;function u:GetExperienceTimes100()return 0 end;units[id]=u;return u end
for _,v in ipairs({{1094,16,1},{1095,16,1},{1096,15,1},{1097,15,1},{1098,16,2},{1099,16,2}})do unit(unpack(v))end
c={};function c:GetOrderQueueLength()return #order end;function c:GetOrderFromQueue(i)return unpack(order[i+1])end;function c:GetProductionTimes100()return bank*100 end;function c:GetUnitProduction(i)assert(i==83);return bank end;function c:GetNumThingsProduced()return things end;function c:CanPlaceUnitHere(i)assert(i==83);return opened end;function c:GetTotalOverflowProductionTimes100()return 1200 end
p={};Players={[0]=p};function p:IsTurnActive()return true end;function p:GetCityByID(id)assert(id==1087);return c end;function p:GetUnitByID(id)return units[id]end;function p:GetUnitClassMaking(i)assert(i==2);return 1 end;function p:Units()local key=nil;return function()local v;key,v=next(units,key);return v end end
Map={GetPlot=function(x,y)assert(x==15 and y==2);return {GetNumUnits=function()return 0 end}end}
GameEvents={CityTrained={Add=function(f)assert(not handler);handler=f end,Remove=function(f)assert(handler==f);handler=nil end}}
function blockedTurn()assert(turn==2 and not opened);turn=3;bank=68;for _,u in pairs(units)do u.moves=120 end end
function complete()assert(turn==3 and opened);turn=4;bank=0;things=1;order={{1,25,-1,false,false},{0,83,3,true,false}};unit(1108,15,1);assert(handler);handler(0,1087,1108,false,false)end
"""
def fresh():
 l=LuaRuntime();l.execute(stub);return l
def must_reject(l,body,label):
 try:l.execute(body)
 except Exception:return label
 raise AssertionError('Failed to reject '+label)
l=fresh();l.execute(blocks[0]);l.execute(blocks[1]);assert l.globals().mutations==0 and l.globals().handler is None
neg=[must_reject(l,blocks[3],'move before normal blocked turn')]
l.execute('blockedTurn()');l.execute(blocks[2]);assert l.globals().mutations==0
l.execute(blocks[3]);assert l.globals().missions==1;l.execute(blocks[4]);l.execute('complete()');l.execute(blocks[5]);assert l.globals().handler is None
for label,patch,index in [('changed saved production','bank=63',0),('changed repeat flag','order[1][4]=false',0),('wrong saved position','units[1096].x=14',1),('wrong saved HP','units[1098].hp=99',1)]:
 t=fresh()
 if index:t.execute(blocks[0])
 t.execute(patch);neg.append(must_reject(t,blocks[index],label))
t=fresh();t.execute(blocks[0]);t.execute(blocks[1]);t.execute('blockedTurn();bank=64');neg.append(must_reject(t,blocks[2],'missing postload accumulated production'))
result={'actual_command_blocks_executed':6,'all_checks_passed':True,'rejected_mismatches':neg,'saved_move_points':0,'move_grant_method_absent_from_stubs':True,'initial_check_world_mutations':0,'mission_submissions':1,'observer_removed_after_completion':True,'scope':'Actual manual command text against deterministic Lua5.1 stubs. Engine continuation remains unverified until parent performs normal menu load, two normal turns and one move.','hashes':{n:hashlib.sha256((d/n).read_bytes()).hexdigest().upper() for n in names}}
(d/'stub-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
