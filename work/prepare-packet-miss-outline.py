"""Stage a cold miss-path split from frozen DLL94; never apply source."""
from pathlib import Path
import subprocess,hashlib,json,difflib
ROOT=Path(__file__).resolve().parents[1];BASE='3601cc10c71df9f6b97c3674a79059a51029c8f2';PATH='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';OUT=ROOT/'work/packet-miss-outline-staged'
def function(s,start):
    a=s.index(start);b=s.index('{',a)+1;depth=1
    while depth:depth+=(s[b]=='{')-(s[b]=='}');b+=1
    return s[a:b]
def stage():
    old=subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
    body=function(old,'static int GetCachedStackDanger(')
    marker=' PacketProbeCall packetProbeCall(unit,plot,candidates,friendlyDamage,enemyDamage,key,cacheable);'
    start=body.index(marker);tail=body[start:body.rindex('\n}')]
    signature='''static __declspec(noinline) int ResolveStackDangerForecastMiss(const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& candidates,const SUnitIDValueContainer& friendlyDamage,
 const SUnitIDValueContainer& enemyDamage,const StackForecastKey& key,bool cacheable,
 unsigned long revision,long scene,StackDangerOutcomeBatch* outcome)
'''
    helper=signature+'{\n'+tail+'\n}'
    caller=body[:start]+' return ResolveStackDangerForecastMiss(unit,plot,candidates,friendlyDamage,enemyDamage,key,cacheable,revision,scene,outcome);\n}'
    replacement=helper+'\n\n'+caller
    assert old.count(body)==1
    new=old.replace(body,replacement,1)
    assert new.replace(replacement,body,1)==old
    assert helper[helper.index('{\n')+2:helper.rindex('\n}')]==tail
    OUT.mkdir(exist_ok=True);(OUT/'control.cpp').write_text(old,encoding='utf-8',newline='\n');(OUT/'CvTacticalAI.cpp').write_text(new,encoding='utf-8',newline='\n')
    (OUT/'packet-miss-outline.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH)),encoding='utf-8',newline='\n')
    proof={'baseline':BASE,'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'candidate_sha256':hashlib.sha256(new.encode()).hexdigest(),'original_function_sha256':hashlib.sha256(body.encode()).hexdigest(),'original_miss_tail_sha256':hashlib.sha256(tail.encode()).hexdigest(),'miss_tail_byte_identical':True,'whole_reverse_exact':True,'scope':'caller keeps original key query/keySample and hit/miss gates; unchanged miss tail lives in noinline helper; /GS/EH retained'}
    (OUT/'manifest.json').write_text(json.dumps(proof,indent=2)+'\n');return old,new,proof
if __name__=='__main__':stage();print(OUT/'packet-miss-outline.patch')
