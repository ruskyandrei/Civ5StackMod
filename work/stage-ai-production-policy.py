"""Work-only role-aware production stage, pinned to the resumed DLL96 baseline."""
from pathlib import Path
import difflib,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='d792b4bcb3727242f6fd7607c44ab306068532f5'
OUT=ROOT/'work/ai-production-policy-staged'
NAMES=('CvStackingOffensiveAI.cpp','CvStackingOffensiveAI.h','CvUnitProductionAI.cpp','CvCity.cpp')

def function(source,signature):
    a=source.index(signature);b=source.index('{',a)+1;depth=1
    while depth:depth+=(source[b]=='{')-(source[b]=='}');b+=1
    return source[a:b]

def generate():
    old={n:subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+n],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n') for n in NAMES}
    new=dict(old);changes=[]
    def once(name,before,after):
        assert new[name].count(before)==1,(name,before[:70],new[name].count(before))
        new[name]=new[name].replace(before,after,1);changes.append((name,before,after))
    api=(ROOT/'work/ai-production-policy-api.h').read_text(encoding='utf-8-sig')
    budget=(ROOT/'work/ai-production-policy-budget.cpp').read_text(encoding='utf-8-sig')
    choice=(ROOT/'work/ai-production-policy-choice.cpp').read_text(encoding='utf-8-sig')
    public=(ROOT/'work/ai-production-policy-public.cpp').read_text(encoding='utf-8-sig')
    once('CvStackingOffensiveAI.h','    int ProductionBonus(const CvCity* city, UnitTypes unit);',api+'\n    int ProductionBonus(const CvCity* city, UnitTypes unit);')
    once('CvStackingOffensiveAI.cpp','        int staffTurn, staffUnits, staffSiege, staffRanged, staffCapture;',
         '        int staffTurn, staffUnits, staffSiege, staffRanged, staffCapture;\n        int productionTurn,productionUnits,productionSiege,productionRanged,productionCapture,productionQueued;\n        unsigned long productionGeneration;\n        std::vector<int> productionCaptureQueues;')
    once('CvStackingOffensiveAI.cpp','staffCapture(0),lastUsefulTurn(-1)',
         'staffCapture(0),productionTurn(-1),productionUnits(0),productionSiege(0),productionRanged(0),productionCapture(0),productionQueued(0),productionGeneration(0),lastUsefulTurn(-1)')
    original_choice=function(new['CvStackingOffensiveAI.cpp'],'    int ProductionChoice(')
    once('CvStackingOffensiveAI.cpp',original_choice,budget+'\n'+choice.rstrip())
    bonus=function(new['CvStackingOffensiveAI.cpp'],'    int ProductionBonus(')
    replacement='''    int ProductionBonus(const CvCity* city,UnitTypes unit)
    {
        ProductionIntent intent;GetProductionIntent(city,unit,intent);return intent.bonus;
    }'''
    once('CvStackingOffensiveAI.cpp',bonus,public+'\n'+replacement)
    # Queue heads and support claims are separate ownership facts. During Sync,
    # each claim insertion must invalidate the next factory's cached totals.
    recorded='claim.goal=chosen; claim.unit=unit; claim.started=claim.progress=currentTurn; claim.turns=city->getProductionTurnsLeft();'
    once('CvStackingOffensiveAI.cpp',recorded,recorded+'\n        AdvanceProductionGeneration(city->getOwner());')
    completed='production.erase(claim); // completion must replace its pending credit exactly once'
    once('CvStackingOffensiveAI.cpp',completed,completed+'\n        AdvanceProductionGeneration(city->getOwner());')
    born='''        if(!city || !Usable(unit) || !Enabled(city->getOwner())) return;
        const Key key(city->getOwner(),city->GetID());'''
    once('CvStackingOffensiveAI.cpp',born,born.replace('        const Key','        InvalidateProductionOwner(city->getOwner());\n        const Key',1))
    # Keep Reset/Refresh/RecordTransfer/Handoff/Review owned by root. Required
    # seam notes accompany the stage instead of editing their complete bodies.
    for sig in ('    void Reset()','    void RecordTransfer(','    void Handoff(','    void ReviewObjectives('):
        assert function(new['CvStackingOffensiveAI.cpp'],sig)==function(old['CvStackingOffensiveAI.cpp'],sig)

    unit='CvUnitProductionAI.cpp'
    marker='\tif (bNeedsSupply)\n\t{\n\t\tif (pkUnitEntry->GetDomainType() == DOMAIN_LAND'
    preparation='''\tCvStackingOffensiveAI::ProductionIntent stackingIntent;
    if(bCombat&&!bFree&&!kPlayer.isMinorCiv())
        CvStackingOffensiveAI::GetProductionIntent(m_pCity,eUnit,stackingIntent,!bForPurchase);
    const bool stackingQuota=stackingIntent.quotaEligible&&!bFree&&!bForPurchase;

'''
    assert new[unit].count(marker)==1
    once(unit,marker,preparation+marker)
    land='''\t\tif (pkUnitEntry->GetDomainType() == DOMAIN_LAND && pkUnitEntry->GetDefaultUnitAIType() != UNITAI_EXPLORE && iNumLandUnits >= kPlayer.GetMilitaryAI()->GetRecommendLandArmySize())
\t\t\treturn SR_UNITSUPPLY;'''
    newland='''\t\tif (pkUnitEntry->GetDomainType() == DOMAIN_LAND && pkUnitEntry->GetDefaultUnitAIType() != UNITAI_EXPLORE && iNumLandUnits >= kPlayer.GetMilitaryAI()->GetRecommendLandArmySize())
        {
            if(!stackingQuota||(long long)iNumLandUnits>=(long long)kPlayer.GetMilitaryAI()->GetRecommendLandArmySize()+stackingIntent.quotaUnits)
            {CvStackingOffensiveAI::RecordProductionRejection(m_pCity,eUnit,stackingIntent,CvStackingOffensiveAI::PRODUCTION_DOMAIN_QUOTA);return SR_UNITSUPPLY;}
        }'''
    once(unit,land,newland)
    sea='''\t\telse if (pkUnitEntry->GetDomainType() == DOMAIN_SEA && iNumSeaUnits >= kPlayer.GetMilitaryAI()->GetRecommendNavySize())
\t\t\treturn SR_UNITSUPPLY;'''
    newsea='''\t\telse if (pkUnitEntry->GetDomainType() == DOMAIN_SEA && iNumSeaUnits >= kPlayer.GetMilitaryAI()->GetRecommendNavySize())
        {
            if(!stackingQuota||(long long)iNumSeaUnits>=(long long)kPlayer.GetMilitaryAI()->GetRecommendNavySize()+stackingIntent.quotaUnits)
            {CvStackingOffensiveAI::RecordProductionRejection(m_pCity,eUnit,stackingIntent,CvStackingOffensiveAI::PRODUCTION_DOMAIN_QUOTA);return SR_UNITSUPPLY;}
        }'''
    once(unit,sea,newsea)
    once(unit,'const int iStackingOffensiveBonus=bCombat?CvStackingOffensiveAI::ProductionBonus(m_pCity,eUnit):0;',
         'const int iStackingOffensiveBonus=bCombat&&!bFree&&!kPlayer.isMinorCiv()?stackingIntent.bonus:0;')

    # Queue state is updated before callback-driven production selection.
    city='CvCity.cpp'
    for sig,anchor in (
        ('void CvCity::pushOrder(', '\n\tif (eOrder == ORDER_MAINTAIN && (ProcessTypes)iData1 != NO_PROCESS)'),
        ('void CvCity::popOrder(', '\n\tif ((getTeam() == GC.getGame().getActiveTeam()) || GC.getGame().isDebugMode())'),
        ('void CvCity::swapOrder(', '\n\tif ((getTeam() == GC.getGame().getActiveTeam()) || GC.getGame().isDebugMode())')):
        body=function(new[city],sig);assert anchor in body
        hook='\n\tCvStackingOffensiveAI::ProductionQueueChanged(this);\n'
        if sig=='void CvCity::popOrder(':hook+='\tif(bFinish&&(eConstructBuilding!=NO_BUILDING||eCreateProject!=NO_PROJECT))\n\t\tCvStackingOffensiveAI::ProductionEconomyChanged(getOwner());\n'
        once(city,body,body.replace(anchor,hook+anchor,1))
    op='\t\t\t\t\t\t\tm_unitBeingBuiltForOperation = thisOperationSlot;'
    once(city,op,op+'\n\t\t\t\t\t\t\tCvStackingOffensiveAI::ProductionQueueChanged(this);')
    purchase='\t\t\t\t\t\t\t\t\tm_unitBeingBuiltForOperation.Invalidate();'
    once(city,purchase,purchase+'\n\t\t\t\t\t\t\t\t\tCvStackingOffensiveAI::ProductionQueueChanged(this);\n\t\t\t\t\t\t\t\t\tCvStackingOffensiveAI::InvalidateProductionOwner(getOwner());')
    # clearOrderQueue routes every mutation through the now-hooked popOrder.
    assert function(new[city],'void CvCity::clearOrderQueue()')==function(old[city],'void CvCity::clearOrderQueue()')

    restored=dict(new)
    for name,before,after in reversed(changes):
        assert restored[name].count(after)==1;restored[name]=restored[name].replace(after,before,1)
    assert restored==old
    proof=dict(control=BASE,whole_reverse_exact=True,source_sha256={n:hashlib.sha256(t.encode()).hexdigest() for n,t in new.items()},
               pending_source_calls=['Reset -> ResetProductionPolicy','RecordTransfer/Handoff/real-unit contribution -> InvalidateProductionStaff(owner,target,domain)','City create/acquire/remove -> ProductionCitiesChanged(old/new owner)','Refresh/other support claim erasure -> AdvanceProductionGeneration(owner)'],
               settings=[dict(name='AIOffensiveProductionRoleRepairUnits',default=2,min=0,max=8),dict(name='AIOffensiveProductionRecommendationSlack',default=2,min=0,max=8)],
               production_untouched=True,scope='Role-aware affordable/supplied recommendation exception, cached queued credit, native queue hooks, no scrapping/direct queue override; pending root lifecycle seams and validation')
    return old,new,proof

if __name__=='__main__':
    old,new,proof=generate();OUT.mkdir(exist_ok=True)
    diff=[]
    for name,text in new.items():
        (OUT/name).write_text(text,encoding='utf-8')
        diff.append(''.join(difflib.unified_diff(old[name].splitlines(True),text.splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+name,tofile='b/CvGameCoreDLL_Expansion2/'+name)))
    (OUT/'production-policy.patch').write_text(''.join(diff),encoding='utf-8')
    (OUT/'stage-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof))
