"""Compare read-only STACKWORLD snapshots before normal save and after reload."""
from pathlib import Path
import argparse, hashlib, json
ROOT=Path(__file__).resolve().parents[1]
UNIT_FIELDS=('owner','id','type','x','y','hp','max_hp','moves','capacity','legal')
CITY_FIELDS=('owner','id','x','y','population','damage','max_hp','garrison_owner','garrison_id')
def parse(text, marker='STACKWORLD', fields=UNIT_FIELDS, kind='UNIT'):
    current=None;latest=None
    for number,line in enumerate(text.splitlines(),1):
        pos=line.find(marker+'|')
        if pos<0: continue
        parts=line[pos:].split('|')
        if parts[1]=='BEGIN':
            if current is not None: raise ValueError('New BEGIN before prior END')
            expected_header=6 if marker=='STACKWORLD' else 5
            if len(parts)!=expected_header: raise ValueError('Unexpected header length')
            vals=list(map(int,parts[2:]));current={'turn':vals[0],'active_player':vals[1],'count':vals[2],'records':[],'begin_line':number}
            if len(vals)>3:current['living_players']=vals[3]
        elif parts[1]==kind:
            if len(parts)!=3: raise ValueError('Unexpected record pipe count')
            if current is None: raise ValueError('Record outside snapshot')
            values=list(map(int,parts[2].split(',')))
            if len(values)!=len(fields):raise ValueError('Wrong record field count')
            current['records'].append(dict(zip(fields,values)))
        elif parts[1]=='END':
            if len(parts)!=3: raise ValueError('Unexpected END pipe count')
            if current is None:raise ValueError('END without BEGIN')
            if int(parts[2])!=current['count'] or len(current['records'])!=current['count']:raise ValueError('Snapshot truncated/count mismatch')
            keys=[(x['owner'],x['id']) for x in current['records']]
            if len(keys)!=len(set(keys)):raise ValueError('Duplicate owner/id')
            if keys!=sorted(keys):raise ValueError('Snapshot is not numerically sorted')
            current['end_line']=number;latest=current;current=None
        else:raise ValueError('Unknown snapshot marker subtype: '+parts[1])
    if current is not None:raise ValueError('Latest snapshot incomplete; do not reuse older block')
    if latest is None:raise ValueError('No complete '+marker+' snapshot')
    return latest

def compare(a,b,fields):
    first={(x['owner'],x['id']):x for x in a['records']};second={(x['owner'],x['id']):x for x in b['records']}
    header={k:{'before':a.get(k),'after':b.get(k)} for k in ('turn','active_player','count','living_players') if a.get(k)!=b.get(k)}
    removed=[first[k] for k in sorted(first.keys()-second.keys())];added=[second[k] for k in sorted(second.keys()-first.keys())]
    changed=[]
    for k in sorted(first.keys() & second.keys()):
        delta={f:{'before':first[k][f],'after':second[k][f]} for f in fields if first[k][f]!=second[k][f]}
        if delta:changed.append({'owner':k[0],'id':k[1],'fields':delta})
    return {'matches':not(header or removed or added or changed),'before_count':len(first),'after_count':len(second),'header_changes':header,'removed':removed,'added':added,'changed':changed}

def self_test():
    def block(records,turn=3):
        return '\n'.join(['[1.0] InGame: STACKWORLD|BEGIN|%s|0|%s|3'%(turn,len(records))]+['[1.0] InGame: STACKWORLD|UNIT|'+','.join(map(str,x)) for x in records]+['[1.0] InGame: STACKWORLD|END|'+str(len(records))])
    original=[[0,9,4,1,2,90,100,0,2,1],[63,9,8,4,5,100,100,120,2,1]]
    checks=0
    a=parse(block(original));assert compare(a,parse(block(original)),UNIT_FIELDS)['matches'];checks+=1
    change=[x[:] for x in original];change[1][7]=0;assert not compare(a,parse(block(change)),UNIT_FIELDS)['matches'];checks+=1
    assert not compare(a,parse(block(original[:1])),UNIT_FIELDS)['matches'];checks+=1
    assert not compare(a,parse(block(original,4)),UNIT_FIELDS)['matches'];checks+=1
    assert parse(block(original)+'\n'+block(original[:1]))['count']==1;checks+=1
    for bad in [block(original).replace('END|2','END|3'),block([original[0],original[0]]),block(list(reversed(original))),block(original)+'\nSTACKWORLD|BEGIN|3|0|1|3',block(original).replace('100,100,120,2,1','100,100,120,2,1|garbage'),block(original)+'|garbage',block(original)+'\nSTACKWORLD|BEG']:
        try:parse(bad)
        except ValueError:checks+=1
        else:raise AssertionError('Invalid snapshot accepted')
    empty=parse(block([]));assert compare(empty,empty,UNIT_FIELDS)['matches'];checks+=1
    assert len({(x['owner'],x['id']) for x in a['records']})==2;checks+=1
    c=parse('STACKCITYWORLD|BEGIN|3|0|1\nSTACKCITYWORLD|CITY|0,7,1,2,3,4,200,0,9\nSTACKCITYWORLD|END|1','STACKCITYWORLD',CITY_FIELDS,'CITY');assert compare(c,c,CITY_FIELDS)['matches'];checks+=1
    print(json.dumps({'self_test_checks':checks,'failures':0,'game_actions':False}));return

def main():
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path);p.add_argument('--after',type=Path);p.add_argument('--out',type=Path);p.add_argument('--cities',action='store_true');p.add_argument('--self-test',action='store_true');args=p.parse_args()
    if args.self_test:return self_test()
    if not(args.before and args.after and args.out):p.error('--before --after --out required')
    out=args.out.resolve();out.relative_to((ROOT/'work').resolve())
    texts=[x.read_text(encoding='utf-8-sig',errors='replace') for x in (args.before,args.after)]
    snapshots=[parse(t) for t in texts];result={'units':compare(*snapshots,UNIT_FIELDS),'unit_fields':UNIT_FIELDS,'unit_snapshot_headers':[{k:v for k,v in t.items() if k!='records'} for t in snapshots],'units_reporting_legal_false':{'before':[x for x in snapshots[0]['records'] if x['legal']==0],'after':[x for x in snapshots[1]['records'] if x['legal']==0]},'inputs':[{'path':str(x.resolve()),'sha256':hashlib.sha256(x.read_bytes()).hexdigest().upper()} for x in (args.before,args.after)],'fixed_initial_unit_count_required':False}
    if args.cities:result['cities']=compare(*(parse(t,'STACKCITYWORLD',CITY_FIELDS,'CITY') for t in texts),CITY_FIELDS)
    result['matches']=result['units']['matches'] and (not args.cities or result['cities']['matches']);result['scope']='Exact persistence of captured fields, not broad game-state equivalence or proof that all reported legal flags are true.'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'matches':result['matches'],'units':result['units']['before_count'],'after_units':result['units']['after_count'],'legal_false_after':len(result['units_reporting_legal_false']['after']),'out':str(out)}))
    if not result['matches']:raise SystemExit(1)
if __name__=='__main__':main()
