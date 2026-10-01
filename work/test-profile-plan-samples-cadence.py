"""Validate the production parser against original and current native cadence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
base=(root/'work/test-profile-plan-samples.py').read_text(encoding='utf-8')
base=base.replace('work/plan-sample-profile-fixture-result.json','work/plan-sample-profile-cadence-v1-result.json')
namespace={'__file__':str(root/'work/test-profile-plan-samples.py'),'__name__':'cadence_backward_fixture'}
exec(compile(base,'backward-compatible-v1-fixture','exec'),namespace)
profile=namespace['profile']
checks=namespace['checks']

def expect(label,condition):
    global checks
    checks+=1
    if not condition:raise AssertionError(label)

def sample(serial=1):
    record=namespace['sample'](serial=serial)
    value=record['values']
    value['phase']=(value['targetPlot']*1664525+serial*2246822519+1013904223)&4095
    strides=profile.CADENCE_STRIDES
    phases=[(value['phase']+index*97)&(stride-1) for index,stride in enumerate(strides)]
    calls=list(map(int,value['calls'].split(',')))
    selected=[(count+phase)//stride for count,phase,stride in zip(calls,phases,strides)]
    value.update(cadenceVersion=2,strides=','.join(map(str,strides)),phases=','.join(map(str,phases)),qpcReads=2*sum(selected))
    for key,values in zip(profile.ARRAYS,(calls,selected,selected,[count*500 for count in selected],[500]*13)):
        value[key]=','.join(map(str,values))
    return record

def replace(record,key,index,value):
    array=record['values'][key].split(',');array[index]=str(value);record['values'][key]=','.join(array)

def reject(label,mutate,expected):
    record=sample();mutate(record);actual,errors=profile.decode(record)
    expect(label,actual is None and any(expected in error for error in errors))

actual,errors=profile.decode(sample())
expect('v2 frozen cadence accepted',actual is not None and not errors and actual['cadenceVersion']==2)
expect('three denser part strides retained',actual['parts'][5]['stride']==256 and actual['parts'][6]['stride']==256 and actual['parts'][8]['stride']==64)
expect('dense parts stay4096',all(part['stride']==4096 for index,part in enumerate(actual['parts']) if index not in (5,6,8)))
expect('v2 selection counts denser',actual['parts'][8]['samples']==128 and actual['parts'][6]['samples']==32)
expect('v2 extrapolation still sample mean',actual['parts'][8]['estimated_total_ms']==4096)
second,_=profile.decode(sample(serial=2))
expect('same target rotates base phase',actual['phase']!=second['phase'])
expect('same target rotates each part phase',all(a!=b for a,b in zip(actual['phases'],second['phases'])))
reject('missing strides',lambda r:r['values'].pop('strides'),'strides:')
reject('missing phases',lambda r:r['values'].pop('phases'),'phases:')
reject('short strides',lambda r:r['values'].update(strides='64,256'),'array_length')
reject('short phases',lambda r:r['values'].update(phases='0,1'),'array_length')
reject('unsupported part cadence',lambda r:replace(r,'strides',8,128),'unsupported_v2')
reject('zero part cadence',lambda r:replace(r,'strides',8,0),'unsupported_v2')
reject('negative part phase',lambda r:replace(r,'phases',8,-1),'non_unsigned_integer')
reject('part phase outside stride',lambda r:replace(r,'phases',8,64),'out_of_bounds')
reject('wrong per-part phase mapping',lambda r:replace(r,'phases',8,(int(r['values']['phases'].split(',')[8])+1)&63),'disagrees_with_base')
reject('selected based on oldstride invalid',lambda r:replace(r,'selected',8,2),'stride_schedule')
reject('unsupported future cadence',lambda r:r['values'].update(cadenceVersion=3),'unsupported_cadence')
reject('v2 metadata cannot be disguised as v1',lambda r:r['values'].update(cadenceVersion=1),'unversioned_metadata')
reject('v2 metadata requiresversion',lambda r:r['values'].pop('cadenceVersion'),'unversioned_metadata')
reject('v2 original frequency checks remain',lambda r:r['values'].update(qpcFrequency=0),'frequency')
reject('v2 original truncation detection remains',lambda r:r.update(raw_message='[message truncated]'),'truncation')

# Read the actual emitted VC9 row, not a mirrored synthetic formatter.
text=(root/'work/plan-sample-cadence-regression/valid-cadence-row.txt').read_text(encoding='utf-8').strip()
record=dict(raw_tick=1020,tick=1020,turn=252,player=3,category='PLAN_SAMPLE',values=profile.wall.fields(text),origin='actual-VC9-emitted-cadence-row')
native,errors=profile.decode(record)
expect('actual native VC9 emitted row parsed',native is not None and not errors and native['cadenceVersion']==2)
expect('actual native exact QPC accounting',native['qpcReads']==2*sum(part['samples'] for part in native['parts']))
expect('actual native dense and sparse sample counts',native['parts'][8]['samples']>=156 and native['parts'][5]['samples']>=39 and native['parts'][0]['samples']>=2)
expect('actual native all13 per-part phases bounded',all(0<=part['phase']<part['stride'] for part in native['parts']))

result=profile.analyze([namespace['sample'](),sample(serial=2)])
expect('mixed v1v2 reports both',result['valid_sample_rows']==2 and {row['cadenceVersion'] for row in result['plans']}=={1,2})
expect('mixed cadence converts and aggregates unchanged estimate',result['whole_selection_parts'][8]['estimated_total_all_plans_ms']==8192)
expect('instrumentation floor warning included',any('granularity' in text for text in result['measurement_notes']))
report=dict(checks=checks,failures=0,production_parser_replaced=True,scope='All66 original v1 fixtures plus v2 fixed strides/phases, serial rotation, missing/malformed metadata, mixed aggregation and actual current VC9 emitted row; no game action.')
(root/'work/plan-sample-profile-cadence-result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
