"""Validate the actual calibration addon against an already-built native source probe.
No DLL build or game process. The native probe contains the current DoDamageMath body.
"""
from pathlib import Path
import hashlib,json,subprocess,sys
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1];work=root/'work/air-calibration-regression'
source=(root/'CvGameCoreDLL_Expansion2/CvUnitCombat.cpp').read_text(encoding='utf-8-sig');a=source.index('int CvUnitCombat::DoDamageMath(');b=source.index('//\t---------------------------------------------------------------------------\nvoid CvUnitCombat::ResolveCombat',a);actual=source[a:b]
assert actual in (work/'damage-bound-test.cpp').read_text(encoding='utf-8-sig'),'Native probe source changed; regenerate before reusing executable'
r=subprocess.run([str(work/'damage-bound-test.exe')],cwd=work,capture_output=True,text=True);assert r.returncode==0
rows=[tuple(map(int,line.split(','))) for line in r.stdout.splitlines()]
sys.path.insert(0,str(root/'work/lua-validation'));from lupa.lua51 import LuaRuntime
lua=LuaRuntime(unpack_returned_tuples=True);lua.execute('''
negative=false;fake=false;unindexed=false
rows={{ID=1,InterceptionCombatModifier=66},{ID=2,InterceptionCombatModifier=-99,InterceptionDefenseDamageModifier=-99}}
aa={strength=100,available=true,IsHasPromotion=function(self,id)return id==1 or negative end,GetMaxAttackStrength=function(self)return self.strength*200 end,GetBaseCombatStrength=function(self)return self.strength end,SetBaseCombatStrength=function(self,n)self.strength=n end,SetDamage=function()end,CurrInterceptionProbability=function()return 130 end,GetID=function()return 1072 end}
bomber={GetID=function()return 1074 end,GetBaseRangedCombatStrength=function()return 40 end,GetCurrHitPoints=function()return 1000 end,IsHasPromotion=function(self,id)return id==2 and negative end,IsBusy=function()return false end,IsFighting=function()return false end,IsRangedSupportFire=function()return fake end,EvasionProbability=function()return 0 end,GetBestInterceptor=function()return aa.available and aa or nil end,GetStackAttackPreview=function()return {DefenderID=1070,DirectDamage=11}end}
guard={GetDanger=function()return aa.available and 3 or (unindexed and 3 or 14)end}
Players={[0]={GetUnitByID=function()return bomber end},[1]={GetUnitByID=function(self,id)if id==1072 then return aa else return guard end end}}
GameDefines={INTERCEPTION_SAME_STRENGTH_MIN_DAMAGE=2400,INTERCEPTION_SAME_STRENGTH_POSSIBLE_EXTRA_DAMAGE=1200}
GameInfo={UnitPromotions=function()local i=0;return function()i=i+1;return rows[i]end end}
StackTests={passed=0,Check=function(name,a,b)assert(a==b,name);StackTests.passed=StackTests.passed+1 end}
StackAirWaveTests={state={owner=0,enemy=1,aa=1072,guard=1070,bombers={1074},baseline=2},Fire=function()end,RearmAA=function()aa.available=true end,ExhaustAA=function()aa.available=false end,FogPerBomber=function()return 1 end}
''')
addon=(root/'work/AirWaveCalibrationAddon.lua').read_text(encoding='utf-8-sig');lua.execute(addon);checks=0
for base,defense,low,high in rows:
 lua.globals().aa.strength=base;bound=lua.eval('StackAirWaveTests.InterceptionBound(bomber)')[0]
 assert high<=bound,(base,defense,high,bound);checks+=1
lua.globals().aa.strength=100;lua.execute('StackAirWaveTests.CalibrateFirst()');selected=int(lua.globals().aa.strength);assert selected==5;checks+=1
native=[r for r in rows if r[0]==selected and r[1]==4000][0];assert native[2]>0 and native[3]<1000;checks+=2
base_bound=lua.eval('StackAirWaveTests.InterceptionBound(bomber)')[0];lua.globals().negative=True;assert lua.eval('StackAirWaveTests.InterceptionBound(bomber)')[0]==base_bound;checks+=1
lua.globals().fake=True;assert lua.eval('pcall(function() StackAirWaveTests.InterceptionBound(bomber) end)')[0] is False;checks+=1
lua.globals().fake=False;lua.globals().negative=False;lua.execute('StackAirWaveTests.ValidateFirst()');assert lua.eval('StackAirWaveTests.state.interceptionProof.id')==1074;checks+=1
assert lua.globals().aa.available is True;checks+=1
lua.execute('StackAirWaveTests.state.interceptionProof=nil');lua.globals().unindexed=True;assert lua.eval('pcall(StackAirWaveTests.ValidateFirst)')[0] is False;checks+=1
assert lua.globals().aa.available is True;checks+=1
out={'checks':checks,'failures':0,'selected_aa_base':selected,'native_actual_damage_min_max_at_observed_defense':list(native[2:]),'worst_case_damage_bound':base_bound,'damage_math_source_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'addon_sha256':hashlib.sha256(addon.encode()).hexdigest().upper(),'scope':'current actual Lua addon versus already-compiled actual native DoDamageMath across100 AA strengths/4 defense values, plus negative-modifier/support-fire/readiness controls; no DLL build/game action','live_status':'strengthened controls remain future-live-unverified'}
(work/'result-strengthened.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out))
