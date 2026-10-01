"""Actual-source healing fixture bound to a frozen composed AI source directory.

Executes the native formula/history, shared helper, and actual healing statements
from the new assault and Tactical callers. Does not execute the full assault AI.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
BASE='d792b4bcb3727242f6fd7607c44ab306068532f5'

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def original(name):
    return subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--emit-only',action='store_true')
    args=parser.parse_args()
    source_dir=args.source_dir.resolve()
    proof_path=source_dir/'finished-proof.json'
    composition=json.loads(proof_path.read_text(encoding='utf-8'))
    assert composition['control']==BASE[:9]
    files={}
    for name,expected in composition['candidate_hashes'].items():
        text=(source_dir/name).read_text(encoding='utf-8-sig').replace('\r\n','\n')
        assert hashlib.sha256(text.encode()).hexdigest()==expected,'Frozen composed source changed: '+name
        files[name]=text
    suite=load(ROOT/'work/test-city-healing-forecast.py','healing_formula_suite')
    method=suite.method
    city=files['CvCity.cpp'];off=files['CvStackingOffensiveAI.cpp'];tac=files['CvTacticalAI.cpp']
    control=original('CvCity.cpp')
    native_turn=method(city,'void CvCity::doTurn()')
    assert native_turn==method(control,'void CvCity::doTurn()'),'Native city turn/healing was changed'
    native_start=native_turn.index('\tbool bRunningDefenseProcess = false;')
    native_stop=native_turn.index('\n\tif (MOD_BALANCE_CORE_JFD)',native_start)
    native='void CvCity::nativeHeal(){\n'+native_turn[native_start:native_stop]+'\n}\n'
    flip=method(city,'void CvCity::flipDamageReceivedPerTurn()')
    assert flip==method(control,'void CvCity::flipDamageReceivedPerTurn()')
    helper=method(city,'int CvCity::GetAssaultHealingForecast(')
    template=(ROOT/'work/city-healing-forecast-template/CityHealingForecast.cpp').read_text().replace('\r\n','\n')
    assert helper==method(template,'int CvCity::GetAssaultHealingForecast('),'Helper differs from tested source'
    declaration='int GetAssaultHealingForecast(PlayerTypes eObserver, int iExpectedCityDamage, bool* pCompleteInformation = NULL) const;'
    assert declaration in files['CvCity.h']
    permission=method(original('CvGame.cpp'),'bool CvGame::CanOpenCityScreen(')
    getters='\n'.join(method(city,name) for name in (
        'int CvCity::getDamageTakenThisTurn() const','int CvCity::getDamageTakenLastTurn() const'))
    for name in ('int CvCity::getDamageTakenThisTurn() const','int CvCity::getDamageTakenLastTurn() const'):
        assert method(city,name)==method(control,name)
    getters=getters.replace('\n{\n','\n{\n\t++historyReads;\n')
    yield_signature='int CvCity::getYieldRateTimes100(YieldTypes eYield, bool bIgnoreTrade, bool bIgnoreProcess, bool bUseCachedValue, CvString* tooltipSink) const'
    cached_yield=method(city,yield_signature)
    assert cached_yield==method(control,yield_signature)
    assault=method(off,'AssaultPlan AssessAssault(')
    statement='const int healing=city->GetAssaultHealingForecast(owner,o.waveComplete?wave.damage:result.cityDamage,&result.healingComplete);'
    assert assault.count(statement)==1,'Actual composed assault healing statement missing or duplicated'
    # Both actual conditional branches are exercised: the unused input differs
    # by100, so a wrong branch cancels quiet healing for tiny incoming-damage cases.
    off_fn='''static int offensiveForecast(CvCity*city,PlayerTypes owner,int damage,bool*complete){
      AssaultPlan result;result.healingComplete=false;
      struct LocalObjective{bool waveComplete;}o;
      struct LocalWave{int damage;}wave;
      o.waveComplete=(damage&1)!=0;
      result.cityDamage=o.waveComplete?damage+100:damage;
      wave.damage=o.waveComplete?damage:damage+100;
    '''+statement+'\n*complete=result.healingComplete;return healing;}\n'
    execute=method(tac,'void CvTacticalAI::ExecuteCaptureCityMoves(')
    a=execute.index('\t\t\t\t\tint iCityHealRate =');b=execute.index('\n\t\t\t\t\t//assume the city heals each turn',a)
    tactical_statement=execute[a:b]
    frozen_tactical=original('CvTacticalAI.cpp')
    staged_tactical=(ROOT/'work/city-healing-forecast-staged/CvTacticalAI.cpp').read_text().replace('\r\n','\n')
    expected_execute=method(staged_tactical,'void CvTacticalAI::ExecuteCaptureCityMoves(')
    ea=expected_execute.index('\t\t\t\t\tint iCityHealRate =');eb=expected_execute.index('\n\t\t\t\t\t//assume the city heals each turn',ea)
    assert tactical_statement==expected_execute[ea:eb],'Composed Tactical healing differs from tested stage'
    unchanged_compute=method(tac,'int CvTacticalAI::ComputeTotalExpectedDamage(')
    assert unchanged_compute==method(frozen_tactical,'int CvTacticalAI::ComputeTotalExpectedDamage(')
    assert 'rtnValue += cityDamage;' in unchanged_compute
    tac_fn='static int tacticalForecast(CvCity*pCity,CvPlayer*m_pPlayer,int iExpectedDamagePerTurn){\n'+tactical_statement+'return iCityHealRate;}\n'
    prefix=suite.PREFIX.replace('struct AssaultPlan{int cityDamage;AssaultPlan():cityDamage(0){}};',
        'struct AssaultPlan{int cityDamage;bool healingComplete;AssaultPlan():cityDamage(0),healingComplete(false){}};')
    assert prefix!=suite.PREFIX,'Fixture context adaptation missing'
    actual=helper+'\n'+permission+'\n'+getters+'\n'+cached_yield+'\n'+flip+'\n'+native+off_fn+tac_fn
    fixture=prefix+actual+suite.TESTS
    out=ROOT/'work/integration-healing-regression';out.mkdir(exist_ok=True)
    cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8',newline='\n')
    report={'baseline':BASE,'source_dir':str(source_dir),'composition_proof_sha256':hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        'candidate_hashes':composition['candidate_hashes'],'fixture_sha256':hashlib.sha256(fixture.encode()).hexdigest(),
        'actual_bodies_sha256':hashlib.sha256(actual.encode()).hexdigest(),
        'native_doTurn_and_history_unchanged':True,'actual_composed_assault_healing_statement':statement,
        'conditional_wave_damage_branches_exercised':True,'garrison_split_compute_unchanged':True,
        'scope':'Actual native healing/history/permission/cached production accessor, actual shared helper and actual composed assault/Tactical healing statements. Same13785 assertions under deterministic services; full assault/search/game not executed.'}
    (out/'source-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.emit_only:
        print('Integrated healing source binding emitted; no compile/game calls.');return 0
    vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows'
    env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
    env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
    for key in ('CL','_CL_','LINK'):env.pop(key,None)
    exe=out/'test.exe'
    compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/O2','/EHsc','/MT','/GS','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
    (out/'compile.log').write_text(compiled.stdout+compiled.stderr)
    if compiled.returncode:print(compiled.stdout+compiled.stderr);return compiled.returncode
    result=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30)
    report.update(returncode=result.returncode,output=result.stdout+result.stderr)
    assert '13785 checks' in result.stdout,'Original matrix assertion count changed'
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(result.stdout+result.stderr,end='');return result.returncode

if __name__=='__main__':sys.exit(main())
