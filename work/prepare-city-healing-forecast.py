"""Emit a work-only city-healing forecast stage; never modifies core files."""
from pathlib import Path
import difflib, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'd792b4bcb3727242f6fd7607c44ab306068532f5'
OUT = ROOT / 'work/city-healing-forecast-staged'
PATHS = tuple('CvGameCoreDLL_Expansion2/' + name for name in (
    'CvCity.cpp', 'CvCity.h', 'CvStackingOffensiveAI.cpp', 'CvTacticalAI.cpp'))

def original(path):
    return subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT).decode('utf-8-sig').replace('\r\n', '\n')

def once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)

def stage():
    before = {path: original(path) for path in PATHS}
    after = dict(before)
    template = (ROOT / 'work/city-healing-forecast-template/CityHealingForecast.cpp').read_text().replace('\r\n', '\n')
    city, header, off, tac = PATHS
    after[city] = once(before[city], 'void CvCity::doTurn()\n', template + '\n\nvoid CvCity::doTurn()\n')
    declaration = '\t// Current-state next-owner-turn estimate; false completeness means hidden inputs were omitted.\n\tint GetAssaultHealingForecast(PlayerTypes eObserver, int iExpectedCityDamage, bool* pCompleteInformation = NULL) const;\n'
    after[header] = once(before[header], '\tvoid doTurn();\n', '\tvoid doTurn();\n' + declaration)
    oldoff = '''        int healing=0;
        if(!city->IsBlockadedWaterAndLand())
        {
            healing=GD_INT_GET(CITY_HIT_POINTS_HEALED_PER_TURN);
            if(MOD_BALANCE_VP) healing+=city->getPopulation();
        }
'''
    newoff = '''        bool healingComplete=false;
        const int healing=city->GetAssaultHealingForecast(owner,result.cityDamage,&healingComplete);
'''
    after[off] = once(before[off], oldoff, newoff)
    oldtac = '''\t\t\t\t\tint iCityHealRate = 0;
\t\t\t\t\tif (!pCity->IsBlockadedWaterAndLand())
\t\t\t\t\t{
\t\t\t\t\t\tiCityHealRate = /*20 in CP, 8 in VP*/ GD_INT_GET(CITY_HIT_POINTS_HEALED_PER_TURN);
\t\t\t\t\t\tif (MOD_BALANCE_VP)
\t\t\t\t\t\t\tiCityHealRate += pCity->getPopulation();
\t\t\t\t\t}
'''
    newtac = '''\t\t\t\t\tint iCityHealRate = 0;
\t\t\t\t\tif (CvStackingOffensiveAI::Enabled(m_pPlayer->GetID()))
\t\t\t\t\t\tiCityHealRate = pCity->GetAssaultHealingForecast(m_pPlayer->GetID(), iExpectedDamagePerTurn);
\t\t\t\t\telse if (!pCity->IsBlockadedWaterAndLand())
\t\t\t\t\t{
\t\t\t\t\t\tiCityHealRate = /*20 in CP, 8 in VP*/ GD_INT_GET(CITY_HIT_POINTS_HEALED_PER_TURN);
\t\t\t\t\t\tif (MOD_BALANCE_VP)
\t\t\t\t\t\t\tiCityHealRate += pCity->getPopulation();
\t\t\t\t\t}
'''
    after[tac] = once(before[tac], oldtac, newtac)
    assert once(after[city], template + '\n\n', '') == before[city]
    assert once(after[header], declaration, '') == before[header]
    assert once(after[off], newoff, oldoff) == before[off]
    assert once(after[tac], newtac, oldtac) == before[tac]
    OUT.mkdir(exist_ok=True)
    patch = ''
    individual = {}
    for path in PATHS:
        (OUT / Path(path).name).write_text(after[path], encoding='utf-8', newline='\n')
        individual[path] = ''.join(difflib.unified_diff(before[path].splitlines(True), after[path].splitlines(True), fromfile='a/' + path, tofile='b/' + path))
        patch += individual[path]
    (OUT / 'healing.patch').write_text(patch, encoding='utf-8', newline='\n')
    (OUT / 'healing-city.patch').write_text(individual[city] + individual[header], encoding='utf-8', newline='\n')
    (OUT / 'healing-tactical.patch').write_text(individual[tac], encoding='utf-8', newline='\n')
    (OUT / 'healing-offensive-fragment.patch').write_text(individual[off], encoding='utf-8', newline='\n')
    proof = {'baseline': BASE, 'reverse_whole_files_exact': True,
             'scope': 'Pure healing forecast helper and two healing-only caller substitutions. Actual city healing/history unchanged. Offensive body fragment must be composed with forecaster stage, not overwritten.',
             'files': {p: {'baseline_sha256': hashlib.sha256(before[p].encode()).hexdigest(), 'candidate_sha256': hashlib.sha256(after[p].encode()).hexdigest()} for p in PATHS}}
    (OUT / 'stage-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return before, after

if __name__ == '__main__':
    stage()
    print(OUT / 'healing.patch')
