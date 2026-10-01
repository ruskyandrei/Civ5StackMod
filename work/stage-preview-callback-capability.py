"""WORK ONLY: callback-free preview proof preserving stock cache paths.

Pinned DLL82. No core edit, game call, compiler run, table/budget/math/save change.
The provider inspects current native fields under the core lock; no UnitInfo-only
assumption or SceneEpoch-only lifetime. Unsupported previews run original math.
"""
from pathlib import Path
import difflib,hashlib,importlib.util,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('narrow',ROOT/'work/stage-air-loading-callback-guards.py')
narrow=importlib.util.module_from_spec(spec);spec.loader.exec_module(narrow)
BASE='24b0428c48d22b0bcc86fd424be0668100d1ae70';once=narrow.once;function=narrow.function
NAMES=('CvTacticalAI.cpp','CvUnit.cpp','CvDangerPlots.cpp','CvStackingStrengthCache.h','CvStackingStrengthCache.cpp')
OUT=ROOT/'work/preview-callback-capability-staged'

provider=r'''// Pure current-world capability proof. These bits are intentionally
// conservative: unsupported/custom AIR loading graphs disable reuse for the
// segment. Standard ranged aircraft with zero melee base preserve all caches.
static bool StackPreviewCallbackCapabilities(unsigned int& flags,bool scan)
{
 flags = 0;
 if (!gDLL->HasGameCoreLock() || MOD_EVENTS_CAN_MOVE_INTO || MOD_EVENTS_AIRLIFT ||
  MOD_EVENTS_SEALIFT || MOD_EVENTS_UNIT_RANGEATTACK || MOD_EVENTS_CITY_BOMBARD || MOD_EVENTS_REBASE || MOD_EVENTS_UNIT_ACTIONS)
  return false;
 if (!scan) return true; // Cheap live lock/options validation, no world reads.
 for (int i=0;i<MAX_PLAYERS;++i)
 {
  const CvPlayer& player=GET_PLAYER((PlayerTypes)i);
  int cursor=0;
  for (const CvUnit* unit=player.firstUnit(&cursor);unit;unit=player.nextUnit(&cursor))
   if (!unit->IsDead() && !unit->isDelayedDeath() && unit->getDomainType()==DOMAIN_AIR)
   {
    // Base strength and ranged readiness can be changed by Lua/native setters.
    if (unit->GetBaseCombatStrength()!=0) flags|=CvStackingStrengthCache::CALLBACK_AIR_BLOCKADER;
   }
  const vector<pair<int,int> >& interceptors=player.GetPossibleInterceptors();
  for (size_t j=0;j<interceptors.size();++j)
  {
   const CvUnit* unit=player.getUnit(interceptors[j].first);
   if (unit && !unit->IsDead() && !unit->isDelayedDeath() && unit->getDomainType()!=DOMAIN_AIR &&
    (unit->IsCanHeavyCharge() || unit->GetMoraleBreakChance()!=0))
    flags|=CvStackingStrengthCache::CALLBACK_AIR_ESCAPE;
  }
 }
 return true;
}
static bool StackPreviewInputsSupported(const vector<CvUnit*>& units)
{
 if (!gDLL->HasGameCoreLock() || MOD_EVENTS_CAN_MOVE_INTO || MOD_EVENTS_AIRLIFT ||
  MOD_EVENTS_SEALIFT || MOD_EVENTS_UNIT_RANGEATTACK || MOD_EVENTS_CITY_BOMBARD || MOD_EVENTS_REBASE || MOD_EVENTS_UNIT_ACTIONS)
  return false;
 for (size_t i=0;i<units.size();++i)
  if (units[i] && units[i]->getDomainType()==DOMAIN_AIR) return false;
 return true;
}

'''

def generate():
    old={n:subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+n],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n') for n in NAMES};candidate=dict(old)
    # Strict mechanical rebase:84 restored the82 Tactical hash; its diagnostic
    # changes are outside these five files and must remain untouched.
    old82=narrow.get_source('CvTacticalAI.cpp')
    assert old82==old['CvTacticalAI.cpp'],'84 Tactical is not the reviewed restored82 control'
    for name in NAMES[1:]:assert old[name]==narrow.get_source(name),'Unexpected84 source drift: '+name
    h=candidate['CvStackingStrengthCache.h']
    h=once(h,'\tclass Scope\n',
        '''\tenum CallbackCapability { CALLBACK_AIR_BLOCKADER=1, CALLBACK_AIR_ESCAPE=2 };
\t// Provider must inspect current native fields without callbacks/writes.
\ttypedef bool (*CallbackCapabilityProvider)(unsigned int& flags,bool scan);
\tclass PreviewSuspension
\t{
\tpublic:
\t\texplicit PreviewSuspension(bool active=true);
\t\t~PreviewSuspension();
\tprivate:
\t\tbool active;
\t\tPreviewSuspension(const PreviewSuspension&);
\t\tPreviewSuspension& operator=(const PreviewSuspension&);
\t};
\tbool IsPreviewSuspended();
\tclass Scope
''')
    h=once(h,'explicit Scope(unsigned int entries);','explicit Scope(unsigned int entries, CallbackCapabilityProvider provider=NULL);')
    h=once(h,'\t\tunsigned long evictions, invalidations;',
        '\t\tunsigned long evictions, invalidations;\n\t\tunsigned long capabilityScans, capabilityFlags, capabilityValidationBypasses, capabilitySuspensions;')
    candidate['CvStackingStrengthCache.h']=h
    cpp=candidate['CvStackingStrengthCache.cpp']
    cpp=once(cpp,'\t\tStats stats = {};',
        '''\t\tStats stats = {};
\t\tCallbackCapabilityProvider capabilityProvider = NULL;
\t\tbool capabilitiesReady=false, capabilitiesSupported=false, validationSupported=false, capabilitiesBuilding=false;
\t\tunsigned int capabilities=0;
\t\t// Every loading/rebuild suspension is local to the invoking thread;
\t\t// atomic epoch invalidation also cancels an owning foreign computation.
\t\tstatic __declspec(thread) unsigned int previewSuspensionDepth=0;''')
    cpp=once(cpp,'\t\tvoid Clear()\n\t\t{',
        '\t\tvoid Clear()\n\t\t{\n\t\t\tcapabilitiesReady=false;\n\t\t\tvalidationSupported=false;')
    cpp=once(cpp,'\tScope::Scope(unsigned int entries) : entered(false)',
        '\tScope::Scope(unsigned int entries, CallbackCapabilityProvider provider) : entered(false)')
    cpp=once(cpp,'\t\tdepth = 1;\n\t\tClear();',
        '\t\tdepth = 1;\n\t\tcapabilityProvider=provider;\n\t\tClear();')
    cpp=once(cpp,'\t\t\tdepth = 0;\n\t\t\tentered = false;',
        '\t\t\tdepth = 0;\n\t\t\tcapabilityProvider=NULL;\n\t\t\tcapabilitiesReady=false;\n\t\t\tentered = false;')
    cpp=once(cpp,'\t\tstd::vector<int>().swap(buckets); // Release both retained allocations in the 32-bit game.',
        '\t\tstd::vector<int>().swap(buckets); // Release both retained allocations in the 32-bit game.\n\t\tcapabilityProvider=NULL;\n\t\tcapabilitiesReady=false;')
    cpp=once(cpp,'\t\tif (!IsOwner() || depth != 1 || !stats.limit)',
        '\t\tif (!IsOwner() || depth != 1 || !stats.limit || previewSuspensionDepth || capabilitiesBuilding)')
    cpp=once(cpp,'\t\treturn true;\n\t}\n\n\tbool Lookup(',
        '''\t\tif (!capabilityProvider) return false;
\t\tunsigned int liveFlags=0;
\t\tif (!capabilityProvider(liveFlags,false))
\t\t{
\t\t\t++stats.capabilityValidationBypasses;
\t\t\t// An unsupported transition must not revive retained values or proof
\t\t\t// if lock/options later return without any unrelated scene signal.
\t\t\tif (validationSupported || capabilitiesReady || !nodes.empty())
\t\t\t{ Invalidate(); Clear(); cachedEpoch=Read(epoch); }
\t\t\treturn false;
\t\t}
\t\tvalidationSupported=true;
\t\tif (!capabilitiesReady)
\t\t{
\t\t\tstruct BuildingGuard
\t\t\t{
\t\t\t\tbool& flag;BuildingGuard(bool& value):flag(value){flag=true;}
\t\t\t\t~BuildingGuard(){flag=false;}
\t\t\t} building(capabilitiesBuilding);
\t\t\tunsigned int flags=0;
\t\t\t++stats.capabilityScans;
\t\t\tconst bool supported=capabilityProvider(flags,true);
\t\t\t// A provider is a pure native scan, but validate the complete owner/
\t\t\t// epoch/lifecycle again before publishing its bounded proof.
\t\t\tif (!IsOwner() || depth!=1 || previewSuspensionDepth || Read(epoch)!=generation)
\t\t\t\treturn false;
\t\t\tif (!capabilityProvider(liveFlags,false))
\t\t\t{ ++stats.capabilityValidationBypasses; Invalidate(); Clear(); cachedEpoch=Read(epoch); return false; }
\t\t\tstats.capabilityFlags|=flags;
\t\t\tcapabilities=flags;capabilitiesSupported=supported;capabilitiesReady=true;
\t\t}
\t\treturn capabilitiesSupported && capabilities==0;
\t}

\tPreviewSuspension::PreviewSuspension(bool value):active(value)
\t{
\t\tif (active) { ++previewSuspensionDepth; Invalidate(); if(IsOwner())++stats.capabilitySuspensions; }
\t}
\tPreviewSuspension::~PreviewSuspension()
\t{
\t\tif (active) { --previewSuspensionDepth; Invalidate(); }
\t}
\tbool IsPreviewSuspended() { return previewSuspensionDepth!=0; }

\tbool Lookup(''')
    candidate['CvStackingStrengthCache.cpp']=cpp
    danger=candidate['CvDangerPlots.cpp']
    danger=once(danger,'void CvDangerPlots::UpdateDanger()\n{',
        'void CvDangerPlots::UpdateDanger()\n{\n\t// Rebuild may call movement/loading hooks while the map is partial.\n\tCvStackingStrengthCache::PreviewSuspension callbackSuspension;')
    candidate['CvDangerPlots.cpp']=danger
    unit=candidate['CvUnit.cpp']
    _,guard=narrow.generate()
    # Only the precise direct AIR-escape bypass is needed. The provider proves
    # stock city blockade safe; do not introduce broad city or AIR exclusions.
    unit=guard['CvUnit.cpp']
    fallback=function(unit,'int CvUnit::GetNumFallBackPlotsAvailable(')
    replacement=once(fallback,'\tVALIDATE_OBJECT();',
        '\tVALIDATE_OBJECT();\n\t// AIR retreat legality can invoke modern or legacy CanLoadAt callbacks.\n\tCvStackingStrengthCache::PreviewSuspension callbackSuspension(getDomainType()==DOMAIN_AIR);')
    candidate['CvUnit.cpp']=once(unit,fallback,replacement)
    tact=candidate['CvTacticalAI.cpp']
    tact=once(tact,'static bool StackForecastContext()\n{',
        '''static bool StackForecastContext()
{
 if (CvStackingStrengthCache::IsPreviewSuspended()) return false;
 long callbackGeneration;
 if (!CvStackingStrengthCache::Context(callbackGeneration)) return false;''')
    # Context ownership must be checked before the new strength provider or any
    # engine getter: retain foreign bypass in front of the added proof checks.
    bad=''' if (CvStackingStrengthCache::IsPreviewSuspended()) return false;
 long callbackGeneration;
 if (!CvStackingStrengthCache::Context(callbackGeneration)) return false;
 if (!IsStackForecastOwner() || !gStackForecastsActive || gStackForecastDepth != 1)
  return false;'''
    good=''' if (!IsStackForecastOwner() || !gStackForecastsActive || gStackForecastDepth != 1)
  return false;
 if (CvStackingStrengthCache::IsPreviewSuspended()) return false;
 long callbackGeneration;
 if (!CvStackingStrengthCache::Context(callbackGeneration)) return false;'''
    tact=once(tact,bad,good)
    tact=once(tact,'struct StackForecastScope\n{',provider+'struct StackForecastScope\n{')
    tact=once(tact,' StackForecastScope():owned(false)',' StackForecastScope(bool supported=false):owned(false)')
    # Constructor count/cleanup semantics stay the same. Unsupported input
    # disables all contexts via its empty strength Scope, without refactoring
    # the old scalar/table or nested-owner implementation.
    old_calls='''\tStackForecastScope stackForecastScope;
\tCvStackingStrengthCache::Scope strengthCacheScope(CvStacking::IsEnabled() && gDLL->HasGameCoreLock() ? CvStacking::GetInt("AITacticalStrengthCacheEntries", 16384) : 0);'''
    new_calls='''\tconst bool callbackFreeInputs=StackPreviewInputsSupported(vUnits);
\tStackForecastScope stackForecastScope(callbackFreeInputs);
\tCvStackingStrengthCache::Scope strengthCacheScope(callbackFreeInputs && CvStacking::IsEnabled() ? CvStacking::GetInt("AITacticalStrengthCacheEntries", 16384) : 0,
\t\tcallbackFreeInputs ? StackPreviewCallbackCapabilities : NULL);'''
    tact=once(tact,old_calls,new_calls)
    tact=once(tact,'packetBypasses=%lu; phase tick timing is coarse',
        'packetBypasses=%lu callbackProofScans=%lu callbackProofFlags=%lu callbackValidationBypasses=%lu callbackSuspensions=%lu; phase tick timing is coarse')
    tact=once(tact,'\t\t\tgStackPacketHits,gStackPacketBuilds,gStackPacketBypasses);',
        '\t\t\tgStackPacketHits,gStackPacketBuilds,gStackPacketBypasses,\n\t\t\tstrength.capabilityScans,strength.capabilityFlags,strength.capabilityValidationBypasses,strength.capabilitySuspensions);')
    # The bool must have an explicit effect before a strength scope from another
    # outer caller could accidentally make unsupported inputs look admissible.
    tact=once(tact,'  ++gStackForecastDepth;\n  gStackForecastsActive = gStackForecastDepth == 1;',
        '  ++gStackForecastDepth;\n  gStackForecastsActive = gStackForecastDepth == 1;\n  if (gStackForecastDepth==1 && !supported) gStackForecastsActive=false;')
    scope_body=function(tact,'struct StackForecastScope\n')
    scope_fixed=once(scope_body,'  if (!gStackForecastsActive)',
        '  if (gStackForecastDepth != 1)')
    # An unsupported outer group must still reset its per-search counters and
    # limits. It is not a nested search and must not expose stale diagnostics.
    tact=once(tact,scope_body,scope_fixed)
    # No new per-hit AIR source iteration. Existing guard remains conservative;
    # all-source capability proof is obtained once per uninterrupted generation.
    candidate['CvTacticalAI.cpp']=tact
    for sig in ('int CvUnit::GetMaxAttackStrengthUncached(', 'int CvUnit::GetMaxDefenseStrengthUncached(',
        'int CvUnit::GetGenericMeleeStrengthModifierUncached(', 'int CvUnit::GetMaxRangedCombatStrengthUncached('):
        assert function(old['CvUnit.cpp'],sig)==function(candidate['CvUnit.cpp'],sig),sig
    for sig in ('int CvDangerPlotContents::GetStackDanger(', 'void CvDangerPlotContents::GetStackDangerOutcome(',
        'void CvDangerPlots::Serialize(', 'void CvDangerPlots::Read(', 'void CvDangerPlots::Write('):
        assert function(old['CvDangerPlots.cpp'],sig)==function(candidate['CvDangerPlots.cpp'],sig),sig
    for sig in ('static int GetCachedStackDanger(', 'struct StackDangerOutcomeBatch\n',
        'static void StoreStackDangerForecast(', 'static void StoreStackDangerPacketForecast('):
        assert function(old['CvTacticalAI.cpp'],sig)==function(candidate['CvTacticalAI.cpp'],sig),sig
    return old,candidate

if __name__=='__main__':
    old,candidate=generate();OUT.mkdir(exist_ok=True);patch=[]
    for name in NAMES:
        live=(ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig').replace('\r\n','\n')
        assert live==old[name],'Pinned82 production changed: '+name
        (OUT/('control-'+name)).write_text(old[name],encoding='utf-8')
        (OUT/name).write_text(candidate[name],encoding='utf-8')
        patch.append(''.join(difflib.unified_diff(old[name].splitlines(True),candidate[name].splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+name,tofile='b/CvGameCoreDLL_Expansion2/'+name)))
    (OUT/'preview-callback-capability.patch').write_text(''.join(patch),encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps(dict(control=BASE,production_untouched=True,
        original_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in old.items()},
        candidate_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in candidate.items()},
        source_math_and_storage_preserved=True,new_result_tables=0,save_format_unchanged=True,
        caveats=['No native ROI claim; explicit-provider fixtures required before adoption.','Default entry budget unchanged; disabling strength cache yields conservative unknown-proof fallback.','Work-only independent code/lifecycle review still required.']),indent=2),encoding='utf-8')
    print('Narrow owned-preview callback proof staged; production untouched')
