from pathlib import Path
import sys,json,hashlib
r=Path(r'E:\Projects\Civ5StackMod');sys.path.insert(0,str(r/'work/lua-validation'))
from lupa.lua51 import LuaRuntime
payload=(r/'(1) Community Patch/Core Files/Stacking/StackingAntiCavalryProbe.lua').read_text(encoding='utf-8-sig')
lua=LuaRuntime(unpack_returned_tuples=True);lua.globals().print=lambda *args: None;lua.execute(payload) # No Game/Players/Map globals: inert-load proof.
lua.execute(r'''
checks=0
function expect(a,b,label) checks=checks+1;assert(a==b,label..": "..tostring(a).." != "..tostring(b)) end
function init()
 local plots={}
 for i=0,2 do plots[i]={i=i,GetPlotIndex=function(self)return self.i end,GetX=function(self)return self.i end,GetY=function()return 0 end} end
 Map={GetPlotByIndex=function(i)return plots[i]end}
 local now=0;Game={GetGameTurn=function()return now end,GetActivePlayer=function()return wrongActive and 1 or 0 end,GetAIAutoPlay=function()return auto and 1 or 0 end};turn=function(v)now=v;StackAINaturalTests.aiTurns=1;StackAINaturalTests.returns=1 end
 local function make(id,owner,role,where)
  local u={id=id,type=id,owner=owner,role=role,where=where,moves=(role=='guard' and60 or0),hp=100}
  function u:GetID()return self.id end;function u:GetUnitType()return self.type end;function u:GetOwner()return self.owner end
  function u:GetCurrHitPoints()return self.hp end;function u:GetPlot()return plots[self.where] end
  function u:GetMoves()return self.moves end;function u:SetMoves(m)self.moves=m end
  function u:SetXY(x,y)self.where=x;self.moves=0 end
  function u:GetStackRoleInfo()return {AntiCavalry=self.role=='guard' and not wrongGuard,Flanker=self.role=='enemy' and not wrongHorse}end
  function u:GetDanger()if self.role=='ranged' then return guard.where==0 and0 or100 end;return20 end
  function u:CanStackAtPlot(p)return not blocked end
  function u:GetStackAttackPreview(p,b)return {DefenderOwner=1,DefenderID=(guard.where==0 and not wrongPreview)and guard.id or ranged.id,DirectDamage=20}end
  return u
 end
 ranged=make(100,1,'ranged',0);guard=make(101,1,'guard',1);horse=make(102,0,'enemy',2)
 Players={[0]={IsTurnActive=function()return not inactiveHuman end,GetUnitByID=function(_,i)return i==102 and horse or nil end},[1]={GetUnitByID=function(_,i)return i==100 and ranged or i==101 and guard or nil end}}
 local s={id='fixture',kind='formation',human=0,ai=1,center=0,source=1,turn=0,units={{owner=1,id=100,type=100,initialID=100,role='ranged',initialPlot=0},{owner=1,id=101,type=101,initialID=101,role='guard',initialPlot=1},{owner=0,id=102,type=102,initialID=102,role='enemy1',initialPlot=2}}}
 for _,p in pairs(plots) do
  function p:GetNumUnits()local n=0;for _,u in ipairs({ranged,guard,horse,outsider})do if u.where==self.i then n=n+1 end end;return n end
  function p:GetUnit(i)local n=0;for _,u in ipairs({ranged,guard,horse,outsider})do if u.where==self.i then if n==i then return u end;n=n+1 end end end
 end
 StackAINaturalTests={state=s,armed=false,aiTurns=0,returns=0,Snapshot=function()return not wrongSnapshot and ranged.where==0 and guard.where==1 and guard.moves==60 and horse.where==2 end,MeasureFormation=function()return not wrongMeasure end}
 wrongGuard=false;wrongHorse=false;wrongPreview=false;blocked=false;wrongSnapshot=false;wrongMeasure=false;wrongActive=false;inactiveHuman=false;auto=false;outsider=nil
 StackAntiCavProbe.measured=nil
end
init();expect(StackAntiCavProbe.Preflight(),true,'preflight success');expect(guard.where,1,'guard position restored');expect(guard.moves,60,'guard moves restored');expect(StackAntiCavProbe.measured.alone,100,'baseline recorded');expect(StackAntiCavProbe.measured.covered,0,'covered recorded');expect(StackAntiCavProbe.measured.guardRisk,20,'guard risk recorded')
turn(1);guard.where=0;expect(StackAntiCavProbe.After(),'PROTECTED_AGAINST_CAVALRY','joined outcome')
init();wrongGuard=true;local ok=StackAntiCavProbe.Try('Preflight');expect(ok,false,'reject non anticav');expect(guard.where,1,'non anticav no move')
init();wrongHorse=true;local ok=StackAntiCavProbe.Try('Preflight');expect(ok,false,'reject non flanker');expect(guard.where,1,'non flanker no move')
init();wrongPreview=true;local ok=StackAntiCavProbe.Try('Preflight');expect(ok,false,'reject bad actual selection');expect(guard.where,1,'failed selection restores plot');expect(guard.moves,60,'failed selection restores moves');expect(StackAntiCavProbe.measured,nil,'failed selection not readiness')
init();blocked=true;local ok=StackAntiCavProbe.Try('Preflight');expect(ok,false,'reject full stack');expect(guard.where,1,'blocked position restored');expect(guard.moves,60,'blocked moves restored')
init();wrongMeasure=true;local ok=StackAntiCavProbe.Try('Preflight');expect(ok,false,'reject nondiagnostic measure');expect(guard.where,1,'nondiagnostic no move')
init();wrongSnapshot=true;local ok=StackAntiCavProbe.Try('Preflight');expect(ok,false,'reject changed original');expect(guard.where,1,'changed original no move')
init();StackAntiCavProbe.Preflight();turn(1);expect(StackAntiCavProbe.After(),'NO_QUALIFYING_PROTECTIVE_JOIN','no forced success for alternative')
init();StackAntiCavProbe.Preflight();local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject no completed turn')
init();StackAntiCavProbe.Preflight();turn(1);horse.where=1;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject moved human threat')
init();StackAntiCavProbe.Preflight();turn(1);ranged.where=1;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject moved fixed ranged')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;wrongPreview=true;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject ineffective joined protector')
init();StackAntiCavProbe.Preflight();wrongMeasure=true;local ok=StackAntiCavProbe.Try('Preflight');expect(ok,false,'reject repeated bad preflight');expect(StackAntiCavProbe.measured,nil,'bad repeat clears old readiness')
init();StackAntiCavProbe.Preflight();turn(2);guard.where=0;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject later turn')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;StackAINaturalTests.aiTurns=2;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject two observed AI turns')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;StackAINaturalTests.returns=0;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject no observed human return')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;StackAINaturalTests.armed=true;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject still armed')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;wrongActive=true;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject wrong active player')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;inactiveHuman=true;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject inactive human')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;auto=true;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject autoplay')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;guard.type=999;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject upgrade same ID')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;blocked=true;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject overcapacity')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;outsider={where=0,GetOwner=function()return 1 end,GetID=function()return 999 end};local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject unrelated protected-center occupant')
init();StackAntiCavProbe.Preflight();turn(1);guard.where=0;StackAntiCavProbe.measured.guard=999;local ok=StackAntiCavProbe.Try('After');expect(ok,false,'reject changed measured identity')

'''.replace('and60','and 60').replace('or0','or 0').replace('and0','and 0').replace('or100','or 100').replace('return20','return 20'))
result=dict(lua51_inert_load=True,checks=lua.globals().checks,failures=0,probe_sha256=hashlib.sha256((r/'(1) Community Patch/Core Files/Stacking/StackingAntiCavalryProbe.lua').read_bytes()).hexdigest().upper(),scope='Work-only Lua role/selection/restoration/outcome stubs; natural terrain selection and actual AI behavior still require live test.')
(r/'work/anti-cav-probe-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
