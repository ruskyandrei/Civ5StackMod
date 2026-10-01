"""Stage lexical previous plot-score reuse; never edit production source."""
from pathlib import Path
import difflib,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/previous-plot-score-staged';OUT.mkdir(exist_ok=True)
CONTROL='f194cff95';PATH='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
old=subprocess.check_output(['git','show',CONTROL+':'+PATH],cwd=ROOT).decode('utf-8-sig')

def block(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]

helper=r'''// Preferred scoring holds one actor and one immutable assignment history.
// Damage-only previews borrow that same history; other histories/actors retain
// the ordinary accessor. Forecast revision/depth guards reject nested searches
// and yields which can recycle shared position slots. No pointer escapes.
struct PreviousPlotScoreQuery
{
 const int unitID;
 const vector<STacticalAssignment>* const history;
 const bool eligible;
 const unsigned long revision;
 const long scene;
 bool ready;
 int score;
 PreviousPlotScoreQuery(int actor, const CvBasePosition& position):
  unitID(actor),history(&position.getAssignments()),eligible(StackForecastContext()),
  revision(eligible ? gStackForecastRevision : 0),
  scene(eligible ? CvStackingStrengthCache::SceneEpoch() : 0),ready(false),score(0) {}
 int Get(int actor, const CvBasePosition& position)
 {
  if (!eligible || !gStackForecastsActive || gStackForecastDepth != 1 ||
   revision != gStackForecastRevision || actor != unitID || &position.getAssignments() != history ||
   scene != CvStackingStrengthCache::SceneEpoch())
   return GetPrevPlotScore(actor, position);
  if (!ready)
  {
   score = GetPrevPlotScore(actor, position);
   ready = true;
  }
  return score;
 }
private:
 PreviousPlotScoreQuery(const PreviousPlotScoreQuery&);
 PreviousPlotScoreQuery& operator=(const PreviousPlotScoreQuery&);
};

static int GetPrevPlotScore(int unitID, const CvBasePosition& position, PreviousPlotScoreQuery* previousScore)
{
 return previousScore ? previousScore->Get(unitID, position) : GetPrevPlotScore(unitID, position);
}
'''
functions=['ScorePlotForPillageMove','ScorePlotForCombatUnitMove','ScorePlotForNonFightingUnitMove','ScorePlotForRangedAttack','ScorePlotForMeleeAttack','ScorePlotForAdmiralHeal','ScorePlotForMove']
new=old
original=block(old,'static int GetPrevPlotScore(')
new=new.replace(original,original+'\n\n'+helper,1)
for name in functions:
    original=block(new,'static STacticalAssignment* '+name+'(')
    header,body=original.split('\n{',1)
    assert header.endswith(')')
    header=header[:-1]+', PreviousPlotScoreQuery* previousScore = NULL)'
    if name=='ScorePlotForMove':
        body=body.replace('evalMode, leavingProtection);','evalMode, leavingProtection, previousScore);')
        body=body.replace('evalMode);','evalMode, previousScore);')
    else:
        assert body.count('GetPrevPlotScore(unit.iUnitID, assumedPosition)')==1
        body=body.replace('GetPrevPlotScore(unit.iUnitID, assumedPosition)','GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore)')
    new=new.replace(original,header+'\n{'+body,1)

preferred=block(new,'void CvTacticalPosition::getPreferredAssignmentsForUnit(')
original_preferred=preferred
preferred=preferred.replace('\tCvTacticalPosition tempPosition;', '\tPreviousPlotScoreQuery previousScore(unit.iUnitID, *this);\n\tCvTacticalPosition tempPosition;',1)
changes={
 'it->iMovesLeft,*this);':'it->iMovesLeft,*this, &previousScore);',
 'it->iMovesLeft, *this);':'it->iMovesLeft, *this, &previousScore);',
 'enemyPlot, *this);':'enemyPlot, *this, &previousScore);',
 'tempPosition, EM_INTERMEDIATE);':'tempPosition, EM_INTERMEDIATE, NULL, &previousScore);',
 '*this, EM_INTERMEDIATE);':'*this, EM_INTERMEDIATE, NULL, &previousScore);',
 '*this, EM_INTERMEDIATE, &leavingProtection);':'*this, EM_INTERMEDIATE, &leavingProtection, &previousScore);',
 'GetPrevPlotScore(unit.iUnitID, *this));':'GetPrevPlotScore(unit.iUnitID, *this, &previousScore));',
}
for before,after in changes.items():
    assert before in preferred,before
    preferred=preferred.replace(before,after)
assert preferred.count('&previousScore')==10
new=new.replace(original_preferred,preferred,1)
(OUT/'CvTacticalAI-control.cpp').write_text(old,encoding='utf-8')
(OUT/'CvTacticalAI.cpp').write_text(new,encoding='utf-8')
patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH))
(OUT/'previous-score.patch').write_text(patch,encoding='utf-8')
(OUT/'staging-proof.json').write_text(json.dumps(dict(control=CONTROL,production_applied=False,source_sha256=hashlib.sha256(old.encode()).hexdigest(),candidate_sha256=hashlib.sha256(new.encode()).hexdigest(),scorers_with_default_null=functions,preferred_explicit_argument_count=10,no_search_bound_or_order_changes=True),indent=2)+'\n',encoding='utf-8')
print('Staged lexical previous-score proposal; production unchanged.')
