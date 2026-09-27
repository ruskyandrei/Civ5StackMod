from pathlib import Path
import sys,json,hashlib
r=Path(r'E:\Projects\Civ5StackMod');sys.path.insert(0,str(r/'work/lua-validation'));from lupa.lua51 import LuaRuntime
src=(r/'(1) Community Patch/Core Files/Stacking/StackingDispersionTests.lua').read_text(encoding='utf-8-sig');lua=LuaRuntime(unpack_returned_tuples=True);lua.globals().print=lambda *args:None;lua.execute(src)
lua.execute(r'''
checks=0;function expect(a,b,n)checks=checks+1;assert(a==b,n..' actual='..tostring(a)..' expected='..tostring(b))end
local function copy(x)local y={};for k,v in pairs(x)do y[k]=v end;return y end
local a={threatShot=true,shot=true,primary=10,primaryOwner=1,guardID=10,owner=1,spareCollateral=2,collateralCount=2,total=14,guard=10,ranged=2,spare=2,guardHP=100,rangedHP=100,spareHP=100}
local b=copy(a);b.total=12;b.spare=0;b.collateralCount=1;b.spareCollateral=0
expect(StackDispersionTests.IsBetter(a,b),true,'useful split')
for _,k in ipairs({'shot','threatShot'})do local q=copy(b);q[k]=false;expect(StackDispersionTests.IsBetter(a,q),false,'reject unavailable '..k)end
for _,change in ipairs({{'primary',11},{'primaryOwner',2},{'total',14},{'guard',11},{'ranged',3},{'spare',100}})do local q=copy(b);q[change[1]]=change[2];expect(StackDispersionTests.IsBetter(a,q),false,'reject bad '..change[1])end
local q=copy(a);q.spareCollateral=0;expect(StackDispersionTests.IsBetter(q,b),false,'actual spare collateral required');q=copy(a);q.collateralCount=1;expect(StackDispersionTests.IsBetter(q,b),false,'three-stack collateral required')
GameInfoTypes={TECH_IRON_WORKING=1,UNIT_PIKEMAN=10,UNIT_ARCHER=11,UNIT_CATAPULT=12};GameDefines={MAX_MAJOR_CIVS=2,MOVE_DENOMINATOR=60};PlotTypes={PLOT_LAND=1};ActivityTypes={ACTIVITY_SLEEP=1,ACTIVITY_AWAKE=0}
local allUnits={};local nextID=100;local plots={};local turn=0;local active=0;local iron=false;local war=false;local preCB,backCB;local throws=false;local outsider=false;local badGain=false
function reset()
 StackDispersionTests.Stop();StackDispersionTests.state=nil;allUnits={};nextID=100;turn=0;active=0;iron=false;war=false;throws=false;outsider=false;badGain=false
end
local function rows(p)local a={};for _,u in ipairs(allUnits)do if u.live and u.p==p.i then a[#a+1]=u end end;if outsider and p.i==0 then a[#a+1]={GetOwner=function()return2 end,GetID=function()return999 end}end;return a end
for i,loc in pairs({[0]={0,0},[1]={2,0},[2]={-1,0}})do local p={i=i,x=loc[1],y=loc[2]};plots[i]=p
 function p:GetPlotIndex()return self.i end;function p:GetX()return self.x end;function p:GetY()return self.y end
 function p:GetNumUnits()return #rows(self)end;function p:GetUnit(i)return rows(self)[i+1]end
 function p:IsVisible()return true end;function p:MovementCost()return60 end
 function p:GetOwner()return-1 end;function p:IsCity()return false end;function p:GetImprovementType()return-1 end;function p:GetRouteType()return-1 end;function p:GetPlotType()return1 end;function p:GetFeatureType()return-1 end;function p:IsImpassable()return false end
end
local function at(x,y)for _,p in pairs(plots)do if p.x==x and p.y==y then return p end end end
Map={GetPlotByIndex=function(i)return plots[i]end,PlotXYWithRangeCheck=function(x,y,dx,dy,n)return at(x+dx,y+dy)end,PlotDistance=function(x,y,a,b)return math.abs(x-a)+math.abs(y-b)end,GetNumPlots=function()return3 end,PlotDirection=function(x,y,d)if x==0 and y==0 and d==0 then return plots[2]end end}
Game={GetActivePlayer=function()return0 end,GetGameTurn=function()return turn end,GetAIAutoPlay=function()return0 end}
GameInfo={Stacking_Settings=function()local a={{Name='BaseCapacity',Value=2},{Name='MaximumCapacity',Value=9}};local i=0;return function()i=i+1;return a[i]end end}
local team={IsHasTech=function()return iron end,SetHasTech=function(_,id,v)iron=v end,IsAtWar=function()return war end,DeclareWar=function()war=true end,MakePeace=function()war=false end};Teams={[0]=team,[1]=team}
local function spawn(owner,kind,x,y)
 local u={id=nextID,owner=owner,kind=kind,p=at(x,y).i,live=true,moves=120,hp=100,tag=''};nextID=nextID+1;allUnits[#allUnits+1]=u
 function u:GetID()return self.id end;function u:GetOwner()return self.owner end;function u:GetUnitType()return self.kind end;function u:GetCurrHitPoints()return self.hp end;function u:GetMaxHitPoints()return100 end
 function u:GetScriptData()return self.tag end;function u:SetScriptData(t)self.tag=t;self.role=t:match('|([^|]+)$')end
 function u:GetPlot()return plots[self.p]end;function u:SetXY(x,y)self.p=at(x,y).i;self.moves=0 end;function u:GetMoves()return self.moves end;function u:SetMoves(n)self.moves=n end;function u:MaxMoves()return120 end;function u:FinishMoves()self.moves=0 end;function u:SetActivityType()end
 function u:GetFortifyTurns()return self.fortify or 0 end;function u:IsBusy()return self.busy or false end;function u:IsFighting()return false end;function u:Kill()self.live=false end
 function u:GetStackingLimit()return iron and3 or2 end;function u:CanStackAtPlot(p)local count=0;for _,v in ipairs(rows(p))do if v.owner==self.owner then count=count+1 end end;return count<self:GetStackingLimit()or(self.p==p.i and count==self:GetStackingLimit())end
 function u:GetStackRoleInfo()return{CollateralTargets=self.role=='threat' and2 or0}end
 function u:CanRangeStrikeAt(x,y)return self.moves>0 and Map.PlotDistance(self:GetPlot().x,self:GetPlot().y,x,y)<=2 end
 function u:GetDanger()if self.role=='guard'then return10 elseif self.role=='ranged'then return2 elseif self.role=='spare'then if self.p~=0 and throws then error('forecast error')end;return self.p==0 and2 or(badGain and2 or0)else return0 end end
 function u:GetStackAttackPreview()
  local d={Collateral={}};for _,v in ipairs(allUnits)do if v.live and v.p==0 then if v.role=='guard'then d.DefenderID=v.id;d.DefenderOwner=v.owner elseif v.role=='ranged'or v.role=='spare'then d.Collateral[#d.Collateral+1]={UnitID=v.id,Owner=v.owner,Damage=2}end end end;d.CollateralCount=#d.Collateral;return d
 end
 function u:GeneratePath(p,flags)local out={{X=self:GetPlot().x,Y=self:GetPlot().y,Turn=0,RemainingMovement=self.moves}};out[2]={X=p.x,Y=p.y,Turn=p.i==1 and2 or1,RemainingMovement=0};return out end
 return u
end
Players={};for i=0,1 do local id=i;Players[i]={GetTeam=function()return id end,IsAlive=function()return true end,IsHuman=function()return id==0 end,IsTurnActive=function()return active==id end,InitUnit=function(_,kind,x,y)return spawn(id,kind,x,y)end,GetUnitByID=function(_,n)for _,u in ipairs(allUnits)do if u.live and u.owner==id and u.id==n then return u end end end,AddTemporaryDominanceZone=function()end}end
GameEvents={PlayerPreAIUnitUpdate={Add=function(f)preCB=f end,Remove=function(f)if preCB==f then preCB=nil end end}}
Events={ActivePlayerTurnStart={Add=function(f)backCB=f end,Remove=function(f)if backCB==f then backCB=nil end end}}
-- Preserve actual Plan for a bounded geometry read-only check, then supply the same deterministic candidate to setup.
local originalPlan=StackDispersionTests.Plan;local planned=originalPlan();expect(planned.center,0,'natural site center');expect(#allUnits,0,'Plan spawns nothing');expect(iron,false,'Plan grants no tech')
StackDispersionTests.Plan=function()return{human=0,ai=1,center=0,target=1,alternatives={2}}end
reset();local ok=StackDispersionTests.Try('Setup',false);expect(ok,false,'explicit grant required');expect(iron,false,'rejected setup tech unchanged');expect(#allUnits,0,'rejected setup no spawn')
reset();expect(StackDispersionTests.Setup(true),true,'positive default fixture');expect(iron,true,'explicit Iron Working grant');expect(#allUnits,4,'only four new units');local s=StackDispersionTests.state;expect(s.measure.base.total,14,'baseline sum');expect(s.measure.split.total,12,'alternative sum');expect(Players[1]:GetUnitByID(s.spare.id).p,0,'measure restores position');expect(Players[1]:GetUnitByID(s.spare.id).moves,60,'measure restores moves')
throws=true;local ok=StackDispersionTests.Try('Measure');expect(ok,false,'measurement error visible');expect(Players[1]:GetUnitByID(s.spare.id).p,0,'error restores position');expect(Players[1]:GetUnitByID(s.spare.id).moves,60,'error restores moves');expect(s.ready,false,'failed measurement clears ready');expect(s.measure,nil,'failed measurement clears choice');throws=false;Players[1]:GetUnitByID(s.spare.id).fortify=1;local fortOK=StackDispersionTests.Try('Measure');expect(fortOK,false,'fortified preflight rejected');Players[1]:GetUnitByID(s.spare.id).fortify=0
StackDispersionTests.Arm();expect(StackDispersionTests.armed,true,'armed');active=1;preCB(1);preCB(1);expect(s.aiTurns,1,'duplicate callback no extra turn');expect(Players[1]:GetUnitByID(s.guard.id).moves,0,'fixed guard exhausted');expect(Players[1]:GetUnitByID(s.ranged.id).moves,0,'fixed archer exhausted');expect(Players[1]:GetUnitByID(s.spare.id).moves,60,'spare one move');Players[1]:GetUnitByID(s.spare.id):SetXY(-1,0);turn=1;active=0;backCB();expect(StackDispersionTests.armed,false,'auto observer stopped');expect(s.returns,1,'one return');expect(StackDispersionTests.Check(),true,'useful actual split');expect(Players[1]:GetUnitByID(s.spare.id).p,2,'postcheck restores actualsplit');outsider=true;local ok=StackDispersionTests.Try('Check');expect(ok,false,'reject outsider');outsider=false;turn=2;local ok=StackDispersionTests.Try('Check');expect(ok,false,'reject later turn');turn=1
Players[0]:GetUnitByID(s.threat.id).busy=true;local cleanOK=StackDispersionTests.Try('Cleanup');expect(cleanOK,false,'busy cleanup rejected');expect(Players[1]:GetUnitByID(s.guard.id)~=nil,true,'busy cleanup killed no earlier member');Players[0]:GetUnitByID(s.threat.id).busy=false;StackDispersionTests.Cleanup();expect(StackDispersionTests.state,nil,'cleanup clears state');expect(iron,false,'cleanup restores techpresence');expect(war,false,'cleanup restores warpresence');local alive=0;for _,u in ipairs(allUnits)do if u.live then alive=alive+1 end end;expect(alive,0,'cleanup only spawnedunits removed')
reset();badGain=true;expect(StackDispersionTests.Setup(true),false,'nondiagnostic returnsfalse');local ok=StackDispersionTests.Try('Arm');expect(ok,false,'nondiagnostic cannot arm');StackDispersionTests.Cleanup()
reset();StackDispersionTests.Setup(true);StackDispersionTests.Arm();active=1;preCB(1);turn=1;active=0;local savedSnapshot=StackDispersionTests.Snapshot;StackDispersionTests.Snapshot=function(label)if label=='human-return'then error('return snapshot error')end;return savedSnapshot(label)end;backCB();StackDispersionTests.Snapshot=savedSnapshot;expect(StackDispersionTests.armed,false,'snapshot error still disarms');expect(preCB,nil,'snapshot error removes AI hook');expect(backCB,nil,'snapshot error removes return hook');expect(StackDispersionTests.state.returnError,true,'return snapshot error retained');local ok=StackDispersionTests.Try('Check');expect(ok,false,'failed return cannot claim success');StackDispersionTests.Cleanup()

'''.replace('return2','return 2').replace('return999','return 999').replace('return60','return 60').replace('return1','return 1').replace('return3','return 3').replace('return0','return 0').replace('return100','return 100').replace('return120','return 120').replace('return10','return 10').replace('and3','and 3').replace('or2','or 2').replace('and2','and 2').replace('or0','or 0').replace('or1','or 1'))
result=dict(lua51_inert_load=True,checks=lua.globals().checks,failures=0,sha256=hashlib.sha256((r/'(1) Community Patch/Core Files/Stacking/StackingDispersionTests.lua').read_bytes()).hexdigest().upper(),scope='Actual work-only helper functions with deterministic unit/map/event stubs; no real danger/pathfinding/AI result implied.')
(r/'work/dispersion-helper-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
