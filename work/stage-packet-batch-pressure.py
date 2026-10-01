"""Stage two local-batch-first packet variants from frozen DLL79, without applying.

No numerical body, entry/payload ceiling or table/FIFO policy is changed.
"""
from pathlib import Path
import difflib,hashlib,json,subprocess
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/packet-batch-pressure-candidate';out.mkdir(exist_ok=True)
control='e0d85052b'
old=subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig').replace('\r\n','\n')
def once(text,before,after):
 assert text.count(before)==1,before[:80];return text.replace(before,after,1)
def function(text,start):
 a=text.index(start);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
ready=once(old,' StackDangerPacketQuery packetQuery(cacheable);',
 ' const bool tryPacket = cacheable && (!outcome || !outcome->ready);\n StackDangerPacketQuery packetQuery(tryPacket);')
ready=once(ready,'const bool packetResolved = cacheable && ResolveStackDangerPacket(',
 'const bool packetResolved = tryPacket && ResolveStackDangerPacket(')
before='''  if(computed&&outcome->ready){finalDamage=&outcome->finalDamage;cityCanFall=outcome->cityCanFall;}
  else if(computed)
  {
   // A computed local ledger was released on invalidation/budget failure.
   // Retain this one query value; never replay the original callbacks/math.
   query.scalarValid=ValidateStackDangerPacket(query,unit,plot,revision,scene);++gStackPacketBypasses;return true;
  }'''
after='''  if(computed)
  {
   // The lexical batch already supplies subsequent member queries. Retain
   // this one value and its queried scalar entry without seeding a packet.
   // Released/invalidated builds must never replay their original math.
   query.scalarValid=ValidateStackDangerPacket(query,unit,plot,revision,scene);
   if(!outcome->ready||!query.scalarValid)++gStackPacketBypasses;
   return true;
  }'''
no_seed=once(ready,before,after)
names={'ready-only':ready,'ready-and-local-no-seed':no_seed}
original_wrapper=function(old,'static int GetCachedStackDanger(')
for name,text in names.items():
 for signature in ['struct StackForecastKey\n','struct StackForecastKeyHash\n','struct StackForecastQuery\n',
  'struct StackDangerOutcomeBatch\n','static void AppendStackCandidates(',
  'static void AppendStackDamageProjected(','static void StoreStackDangerForecast(',
  'static void StoreStackDangerPacketForecast(','static bool PrepareStackDangerPacket(',
  'static bool ValidateStackDangerPacket(']:
  assert function(old,signature)==function(text,signature),'Original dependency changed: '+signature
 prefix=lambda s:s[:s.index(' const unsigned long revision = cacheable ?')]
 # Entire first scalar lookup and key loan remain unchanged, through hit and
 # misses/probe. Only the original packet-query construction is gated later.
 marker=' int result = 0;'
 assert original_wrapper[:original_wrapper.index(marker)]==function(text,'static int GetCachedStackDanger(').split(marker)[0]
 (out/(name+'.cpp')).write_text(text,encoding='utf-8')
 patch=''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/CvTacticalAI.cpp',tofile='b/CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'))
 (out/(name+'.patch')).write_text(patch,encoding='utf-8')
(out/'manifest.json').write_text(json.dumps(dict(control=control,production_untouched=True,
 original_sha256=hashlib.sha256(old.encode()).hexdigest(),
 candidate_sha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in names.items()},
 policies=dict(ready_only='Original scalar-hit prefix; ready supplied batch uses original TryGet/StoreScalar pipeline.',
 ready_and_local_no_seed='Ready policy plus no packet seed after a cold batch computes; queried scalar admission and already-existing global packet lookup retained.'),
 unchanged_math_and_budgets=True,native_ROI_unproven=True),indent=2))
print('Local-batch pressure variants staged from79; production untouched')
