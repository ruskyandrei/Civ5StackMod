"""Stage DLL82 PATH-only stride128/row-cap revision; no production edits."""
from pathlib import Path
import difflib,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1];CONTROL='6f4688d81';OUT=ROOT/'work/path-query-profile-bounded-staged';OUT.mkdir(exist_ok=True)
names=('CvStackingDiagnostics.h','CvStackingDiagnostics.cpp','CvAStar.cpp')
old={n:subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/'+n],cwd=ROOT).decode('utf-8-sig') for n in names};new=dict(old)
text=old['CvStackingDiagnostics.cpp']
text=text.replace('PATH_QUERY_STRIDE=8, PATH_CALL_STRIDE=16','PATH_QUERY_STRIDE=128, PATH_ROW_LIMIT=128, PATH_CALL_STRIDE=16')
needle='    static __declspec(thread) long pathProfileDisabledEpoch=-1;\n'
addition='''    // Shared under Lock: earliest completed selected queries, across threads.
    static int pathProfileRowTurn=-1,pathProfilePreviousCapTurn=-1;
    static unsigned int pathProfileRows=0;
    static unsigned __int64 pathProfileCappedSelected=0,pathProfilePreviousCappedSelected=0;
'''
assert text.count(needle)==1;text=text.replace(needle,needle+addition)
needle='        tacticalSamplingOverride=-1; // PLAN_SAMPLE_DIAGNOSTIC_ONLY\n'
addition='        pathProfileRowTurn=pathProfilePreviousCapTurn=-1;pathProfileRows=0;pathProfileCappedSelected=pathProfilePreviousCappedSelected=0; // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n'
assert text.count(needle)==1;text=text.replace(needle,needle+addition)
needle='        if((serial+phase)&(PATH_QUERY_STRIDE-1))return;\n'
addition='''        const int turn=GC.getGame().getGameTurn();
        if(pathProfileRowTurn!=turn)
        {
            pathProfilePreviousCapTurn=pathProfileRowTurn;pathProfilePreviousCappedSelected=pathProfileCappedSelected;
            pathProfileRowTurn=turn;pathProfileRows=0;pathProfileCappedSelected=0;
        }
        if(pathProfileRows>=PATH_ROW_LIMIT) { ++pathProfileCappedSelected;return; }
'''
assert text.count(needle)==1;text=text.replace(needle,needle+addition)
needle='            !categoryEnabledUnlocked(1,pathProfile.actor,"PATH_SAMPLE"))return;\n'
addition='''        // Recheck at completion: concurrent selected queries share one cap.
        if(pathProfileRowTurn!=pathProfile.turn)return;
        if(pathProfileRows>=PATH_ROW_LIMIT) { ++pathProfileCappedSelected;return; }
        ++pathProfileRows;
'''
assert text.count(needle)==1;text=text.replace(needle,needle+addition)
text=text.replace('queryStride=%u queryPhase=%lu callStride=', 'queryStride=%u queryPhase=%lu turnRowLimit=%u turnRowOrdinal=%u capAfterThisRow=%d previousCapTurn=%d previousCappedSelectedQueries=%I64u rowCoverage=earliest_completed_selected_queries_after_cap_later_unknown callStride=')
text=text.replace('PATH_QUERY_STRIDE,pathProfile.queryPhase,PATH_CALL_STRIDE,','PATH_QUERY_STRIDE,pathProfile.queryPhase,PATH_ROW_LIMIT,pathProfileRows,pathProfileRows==PATH_ROW_LIMIT?1:0,pathProfilePreviousCapTurn,pathProfilePreviousCappedSelected,PATH_CALL_STRIDE,')
text=text.replace('subset of systematic sampled queries; no raw-result reuse;', 'subset of systematic sampled queries; bounded early cap biases coverage; later selected queries unknown until a following turn row; no raw-result reuse;')
new['CvStackingDiagnostics.cpp']=text
for name,body in new.items():(OUT/name).write_text(body,encoding='utf-8')
patch=''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+n,tofile='b/CvGameCoreDLL_Expansion2/'+n)) for n in names)
(OUT/'bounded-path-profile.patch').write_text(patch,encoding='utf-8')
# Reuse the actual complete Find/Verify fixture and pinned79 reverse-strip oracle.
# The new generator uses82 as the strict patch base; original path bodies stay79.
fixture=(ROOT/'work/test-path-query-profile.py').read_text(encoding='utf-8-sig')
fixture=fixture.replace("STAGE=ROOT/'work/path-query-profile-staged'","STAGE=ROOT/'work/path-query-profile-bounded-staged'").replace("OUT=ROOT/'work/path-query-profile-regression'","OUT=ROOT/'work/path-query-profile-bounded-regression'")
fixture=fixture.replace('pathProfileSerial=7;','pathProfileSerial=79;')
fixture=fixture.replace('pathProfileDisabledEpoch=-1;tacticalSamplingOverride=1;','pathProfileDisabledEpoch=-1;pathProfileRowTurn=pathProfilePreviousCapTurn=-1;pathProfileRows=0;pathProfileCappedSelected=pathProfilePreviousCappedSelected=0;tacticalSamplingOverride=1;')
extra=r'''
 Clean();for(int i=0;i<512;++i){pathProfileSerial=(unsigned long)i*128+79;PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}
 Expect("strict whole-turn128 rows",recordCalls==128&&pathProfileRows==128&&pathProfileCappedSelected==384);
 Expect("last row explicitly marks early cap",rowsSeen.back().find("turnRowOrdinal=128 capAfterThisRow=1")!=std::string::npos);
 {LONG clocks=qpcCalls,frequency=qpfCalls;unsigned long reads=metadataReads;pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);PathProfileScope raw(PATH_RAW_DANGER,&actor,&dangerPlot);}Expect("capped selected query no hot clocks or getters",qpcCalls==clocks&&qpfCalls==frequency&&metadataReads==reads);}
 SetTacticalSamplingEnabled(false);SetTacticalSamplingEnabled(true);pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("toggle does not reopen same-turn cap",recordCalls==128&&pathProfileRows==128);
 testTurn=253;pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}
 Expect("next turn opens bounded budget",recordCalls==129&&pathProfileRows==1);
 Expect("following-turn row reports prior selected censor",rowsSeen.back().find("previousCapTurn=252 previousCappedSelectedQueries=386")!=std::string::npos);
 Reset();tacticalSamplingOverride=1;level=1;pathProfileSerial=79;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("load reset clears cap and prior-turn proof",pathProfileRows==1&&pathProfilePreviousCapTurn==-1&&pathProfilePreviousCappedSelected==0);
 Clean();pathProfileRows=127;pathProfileRowTurn=252;{PathProfileSession session(3,1,0,1,4,0,0,1,0,false);pathProfileRows=128;}Expect("completion rechecks concurrent cap",recordCalls==0&&pathProfileCappedSelected==1);
 Clean();for(int serialValue=1;serialValue<=128;++serialValue){pathProfileSerial=serialValue-1;PathProfileSession session(3,1,0,1,4,0,0,1,0,false);}Expect("one rotated selection per128 queries",recordCalls==1);
'''
needle=' printf("actual path query profile:';assert fixture.count(needle)==1;fixture=fixture.replace(needle,extra+needle)
(ROOT/'work/test-bounded-path-query-profile.py').write_text(fixture,encoding='utf-8')
for name in ('profile-turn-phases.py','profile-phase-cpu.py'):(OUT/name).write_text((ROOT/'work'/name).read_text(encoding='utf-8-sig'),encoding='utf-8')
parser=(ROOT/'work/profile-path-queries.py').read_text(encoding='utf-8-sig')
parser=parser.replace("METADATA=('unit'", "METADATA=('turnRowLimit','turnRowOrdinal','capAfterThisRow','previousCapTurn','previousCappedSelectedQueries','rowCoverage','unit'")
parser=parser.replace("for key,expected in (('queryStride',8),('callStride',16)","if value.get('queryStride') not in (8,128):errors.append('queryStride:unsupported')\n for key,expected in (('callStride',16)")
parser=parser.replace("(('queryPhase',8),('callPhase',16)","(('queryPhase',value.get('queryStride',0) if type(value.get('queryStride')) is int else 0),('callPhase',16)")
needle=" if value.get('queryAvailable') not in (0,1)"
extra=""" if value.get('queryStride')==128:
  for key,bound in (('turnRowLimit',128),):
   if value.get(key)!=bound:errors.append(key+':invalid')
  if type(value.get('turnRowOrdinal')) is not int or not 1<=value['turnRowOrdinal']<=128:errors.append('turnRowOrdinal:invalid')
  if type(value.get('capAfterThisRow')) is not int or value['capAfterThisRow']!=int(value.get('turnRowOrdinal')==128):errors.append('capAfterThisRow:invalid')
  if type(value.get('previousCapTurn')) is not int or not -(1<<31)<=value['previousCapTurn']<(1<<31):errors.append('previousCapTurn:invalid')
  if type(value.get('previousCappedSelectedQueries')) is not int or not 0<=value['previousCappedSelectedQueries']<=U64:errors.append('previousCappedSelectedQueries:invalid')
  if value.get('rowCoverage')!='earliest_completed_selected_queries_after_cap_later_unknown':errors.append('rowCoverage:unsupported')
"""
assert parser.count(needle)==1;parser=parser.replace(needle,extra+needle)
parser=parser.replace("return dict(turn=row['turn']", "return dict(query_stride=value['queryStride'],row_cap={k:value[k] for k in ('turnRowLimit','turnRowOrdinal','capAfterThisRow','previousCapTurn','previousCappedSelectedQueries','rowCoverage') if k in value},turn=row['turn']")
parser=parser.replace("NOTES=[", "NOTES=[\n 'Stride128 rows are capped at128 earliest completed selected queries per native-run turn across threads. Reaching the cap biases coverage toward earlier work. Later selected query counts remain unknown until a following-turn row reports previousCappedSelectedQueries; no query timings are extrapolated past the cap.',")
needle=" return dict(schema='native_PATH_SAMPLE_v1'"
addition=""" caps=[]
 for turn in sorted({r['turn'] for r in decoded}):
  rows=[r for r in decoded if r['turn']==turn and r['row_cap']]
  if not rows:continue
  previous=defaultdict(set)
  for r in rows:previous[r['row_cap']['previousCapTurn']].add(r['row_cap']['previousCappedSelectedQueries'])
  caps.append(dict(turn=turn,maximum_retained_ordinal=max(r['row_cap']['turnRowOrdinal'] for r in rows),cap_reached=any(r['row_cap']['capAfterThisRow'] for r in rows),later_selected_query_count='unknown_until_following_turn_report',previous_turn_selected_censor_reports=[dict(turn=t,counts=sorted(c),consistent=len(c)==1) for t,c in sorted(previous.items()) if t!=-1]))
"""
assert parser.count(needle)==1;parser=parser.replace(needle,addition+needle).replace("return dict(schema='native_PATH_SAMPLE_v1',archive_quality=", "return dict(schema='native_PATH_SAMPLE_v1',row_cap_coverage=caps,archive_quality=")
(OUT/'profile-path-queries.py').write_text(parser,encoding='utf-8')
fixture=(ROOT/'work/test-profile-path-queries.py').read_text(encoding='utf-8-sig')
fixture=fixture.replace("p=module('pathprof',ROOT/'work/profile-path-queries.py');checks=0", "STAGE=ROOT/'work/path-query-profile-bounded-staged';parser_source=ROOT/'work/profile-path-queries.py' if options.production else STAGE/'profile-path-queries.py';assert parser_source.read_text(encoding='utf-8-sig')==(STAGE/'profile-path-queries.py').read_text(encoding='utf-8-sig'),'Whole production parser differs from reviewed stage';p=module('pathprof',parser_source);checks=0")
fixture=fixture.replace("stage=ROOT/'work/path-query-profile-staged'", "stage=STAGE").replace("str(ROOT/'work/profile-path-queries.py')", "str(parser_source)").replace("'work/path-query-parser-fixture-result.json'", "'work/path-query-bounded-parser-fixture-result.json'").replace("hashlib.sha256((ROOT/'work/profile-path-queries.py').read_bytes())", "hashlib.sha256(parser_source.read_bytes())")
extra="""
current=row();current['values'].update(queryStride=128,queryPhase=127,serial=1,turnRowLimit=128,turnRowOrdinal=1,capAfterThisRow=0,previousCapTurn=-1,previousCappedSelectedQueries=0,rowCoverage='earliest_completed_selected_queries_after_cap_later_unknown')
parsed,errors=p.decode(current);check(not errors and parsed['query_stride']==128 and parsed['row_cap']['turnRowOrdinal']==1)
current['values'].update(turnRowOrdinal=128,capAfterThisRow=1,previousCapTurn=251,previousCappedSelectedQueries=386)
check(not p.decode(current)[1]);report=p.analyze([current]);check(report['row_cap_coverage'][0]['cap_reached'] and report['row_cap_coverage'][0]['previous_turn_selected_censor_reports'][0]['counts']==[386])
for key,value in [('queryPhase',128),('turnRowOrdinal',0),('turnRowOrdinal',129),('turnRowOrdinal',True),('turnRowLimit',129),('capAfterThisRow',0),('capAfterThisRow',True),('previousCapTurn',True),('previousCappedSelectedQueries',-1),('rowCoverage','complete'),('queryStride',16)]:
 broken=dict(current);broken['values']=dict(current['values']);broken['values'][key]=value;check(bool(p.decode(broken)[1]))
broken=dict(current);broken['values']=dict(current['values']);del broken['values']['turnRowLimit'];check(bool(p.decode(broken)[1]))
broken=dict(current);broken['raw_message']='turnRowOrdinal=128 turnRowOrdinal=2';check(bool(p.decode(broken)[1]))
check(p.decode(row())[0]['row_cap']=={})
"""
needle="# Anchor patch shared";assert fixture.count(needle)==1;fixture=fixture.replace(needle,extra+needle)
(ROOT/'work/test-profile-bounded-path-queries.py').write_text(fixture,encoding='utf-8')
proof={n:{'control_sha256':hashlib.sha256(old[n].encode()).hexdigest(),'stage_sha256':hashlib.sha256(new[n].encode()).hexdigest()} for n in names}
(OUT/'proof.json').write_text(json.dumps(dict(control=CONTROL,production_applied=False,query_stride=128,row_limit=128,files=proof),indent=2)+'\n')
print('Prepared bounded PATH stride128/cap128 stage; production unchanged.')
