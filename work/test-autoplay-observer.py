from pathlib import Path
import sys,json,hashlib
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'work/lua-validation'))
from lupa.lua51 import LuaRuntime
p=r/'work/StackingAutoplayObserver.lua';source=p.read_text(encoding='utf-8-sig');lua=LuaRuntime();lua.execute('logs={};print=function(...)local a={...};for i,v in ipairs(a)do a[i]=tostring(v)end;logs[#logs+1]=table.concat(a," ")end');lua.execute(source);assert len(lua.globals().logs)==0
lua.execute(r"""
checks=0;function C(v,n)checks=checks+1;assert(v,n)end
function contains(s)for _,x in ipairs(logs)do if string.find(x,s,1,true)then return true end end return false end
function count(s)local n=0;for _,x in ipairs(logs)do if string.find(x,s,1,true)then n=n+1 end end return n end
turn=10;mutations=0;addFails=false;roleFails=false;removeFails=false
DomainTypes={DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2};GameDefines={MAX_PLAYERS=64};Game={GetGameTurn=function()return turn end,GetActivePlayer=function()return 0 end}
function forbidden()mutations=mutations+1;error('world mutation attempted')end
Game.SetAIAutoPlay=forbidden;Game.DoTurn=forbidden;Game.SaveGame=forbidden
hooks={};GameEvents={PlayerDoTurn={}}
function GameEvents.PlayerDoTurn.Add(f)if addFails then error('subscribe error')end;hooks[#hooks+1]=f end
function GameEvents.PlayerDoTurn.Remove(f)if removeFails then error('remove error')end;for i=#hooks,1,-1 do if hooks[i]==f then table.remove(hooks,i)end end end
function fire(o)local a={};for _,f in ipairs(hooks)do a[#a+1]=f end;for _,f in ipairs(a)do f(o)end end
function unit(id,plot,extra)
 local u={id=id,plot=plot,hp=100,moves=120,domain=0,counted=true,ranged=false,cap=2,legal=true,combat=true};for k,v in pairs(extra or{})do u[k]=v end
 function u:GetCurrHitPoints()return self.hp end;function u:IsDelayedDeath()return self.delayed or false end
 function u:GetPlot()if not self.plot then return nil end;local n=self.plot;return{GetPlotIndex=function()return n end}end
 function u:GetDomainType()return self.domain end
 function u:GetStackRoleInfo()if roleFails or self.bad then error('role error')end;return{Enabled=true,CountsTowardCapacity=self.counted,Flanker=false,AntiCavalry=false,CollateralTargets=0}end
 function u:IsCargo()return self.cargo or false end;function u:IsEmbarked()return self.embarked or false end
 function u:IsCombatUnit()return self.combat end;function u:IsRanged()return self.ranged end
 function u:IsBusy()return false end;function u:IsFighting()return false end
 function u:GetStackingLimit(p)assert(p:GetPlotIndex()==self.plot);return self.cap end
 function u:CanStackAtPlot(p)assert(self.counted and not self.cargo and self.domain~=2,'excluded unit legality queried');assert(p:GetPlotIndex()==self.plot);return self.legal end
 function u:GetID()return self.id end;function u:GetUnitType()return 80+self.id end
 function u:GetX()return self.plot or -1 end;function u:GetY()return 0 end
 function u:GetMaxHitPoints()return 100 end;function u:GetMoves()return self.moves end
 u.SetMoves=forbidden;u.SetXY=forbidden;u.PushMission=forbidden;u.Kill=forbidden;u.SetDamage=forbidden
 return u
end
all={unit(1,1),unit(2,1,{ranged=true}),unit(3,1,{counted=false,combat=false}),unit(4,1,{counted=false}),unit(5,1,{counted=false,domain=2,combat=false}),unit(6,1,{counted=false,cargo=true}),unit(7,2,{embarked=true,ranged=true}),unit(8,1,{delayed=true,bad=true}),unit(9,1,{hp=0,bad=true})}
function player(alive,units)local p={};function p:IsAlive()return alive end;function p:Units()local i=0;return function()i=i+1;return units[i]end end;p.InitUnit=forbidden;return p end
Players={[0]=player(true,all),[1]=player(true,{unit(1,3,{ranged=true})}),[2]=player(false,{unit(90,1,{bad=true})}),[63]=player(true,{unit(20,4)})}
function fingerprint()local a={};for _,u in ipairs(all)do a[#a+1]=table.concat({u.id,u.plot,u.hp,u.moves,u.cap,tostring(u.legal),tostring(u.counted)},',')end;return table.concat(a,';')end
local before=fingerprint();local O=StackAutoplayObserver
C(O.Start(50,5)==true,'starts');C(#hooks==1,'one subscription');C(O.samples==1,'one initial sample');C(contains('owners=3 units=9 detail=true anomalies=0'),'live/dead/domain aggregate');C(contains('counted=3 land=6 sea=0 air=1 cargo=1 embarked=1 other=2'),'excluded categories correct');C(contains('rangedWithoutMelee=0 hist=L1:1,L2:1'),'embarked not false uncovered');C(contains('owner=1 units=1'),'second owner');C(contains('owner=63 units=1'),'barb included');C(count('STACKAUTO|UNIT|')==9,'initial nine details')
fire(0);fire(1);fire(63);C(O.samples==1,'same game-turn dedup')
for n=11,59 do turn=n;fire(0);fire(1);fire(63)end
C(O.running and O.samples==50,'still running before deadline');turn=60;fire(0);C(not O.running and O.samples==51 and #hooks==0,'50elapsed turns plus initial then detached');C(count('STACKAUTO|UNIT|')==99,'details only11 scheduled samples');turn=61;fire(0);C(O.samples==51,'no callback after limit');C(fingerprint()==before and mutations==0,'read-only world state')
logs={};turn=100;C(O.Start(50,5),'restart');local ok=pcall(O.Start,1,1);C(not ok and #hooks==1,'double start rejected without duplicate');turn=101;all[2].legal=false;fire(0);C(contains('ANOMALY|turn=101 placement'),'placement anomaly');C(count('STACKAUTO|UNIT|')==18,'anomaly forces details offcycle');all[2].legal=true
all[#all+1]=unit(10,1);turn=102;fire(1);C(contains('capacity owner=0 plot=1 domain=L count=3 cap=2'),'owner-domain count overflow');O.Stop();C(not O.running and #hooks==0,'manual stop');all[#all]=nil
logs={};turn=200;C(O.Start(2,5),'small bound');turn=204;fire(0);C(not O.running and O.samples==1 and #hooks==0,'jump past deadline detaches without late sample')
turn=300;O.Start(2,5);turn=299;fire(0);C(not O.running and #hooks==0,'rewind detaches')
logs={};turn=400;O.Start(2,5);roleFails=true;turn=401;ok=pcall(fire,0);C(ok and not O.running and #hooks==0,'callback error protected/detached');C(contains('STACKAUTO|ERROR|role error') or contains('role error'),'error logged');C(not contains('BEGIN|turn=401'),'failed collection emits no misleading sample');roleFails=false
addFails=true;ok=pcall(O.Start,2,5);C(not ok and not O.running and #hooks==0,'subscription error detaches');addFails=false
for _,n in ipairs({10001,1.5,-1})do ok=pcall(O.Start,n,5);C(not ok and #hooks==0,'invalid bound rejected')end
logs={};turn=500;C(O.Start()==true and O.deadline==nil and O.detailEvery==10,'default whole-game observer');C(contains('deadline=unlimited'),'unlimited labeled');turn=550;fire(1);turn=1000;fire(0);C(O.running and O.samples==3,'continues beyond fifty turns');C(count('STACKAUTO|SCAN_START|')==3 and count('STACKAUTO|END|')==3,'cost markers pair every sample');O.Stop();C(#hooks==0,'unlimited manual stop')
turn=1100;O.Start(0,10);local orphan=O.callback;removeFails=true;O.Stop();C(not O.running and #hooks==1,'remove error leaves inert orphan');removeFails=false;O.Start(0,10);local samples=O.samples;turn=1101;orphan(0);C(O.samples==samples,'old generation cannot revive after restart');fire(0);C(O.samples==samples+1,'current callback samples once');O.Stop();GameEvents.PlayerDoTurn.Remove(orphan);C(#hooks==0,'test orphan cleanup')
C(mutations==0 and fingerprint()==before,'zero world mutations across all paths');O.Status();C(contains('STATUS|running=false'),'status works stopped')
""")
result={'lua51_inert_load':True,'checks':lua.globals().checks,'failures':0,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest().upper(),'world_mutations':lua.globals().mutations,'scope':'Actual standalone observer with deterministic read-only unit/player/event stubs. No game, installation, config or autoplay operation. Real event delivery/log volume remains a runtime observation.'}
(r/'work/autoplay-observer-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
