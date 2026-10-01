"""Prepare or run one bounded, identity-verified direct VP LTCG build.

Default is preparation only. --build is explicit; no game, deployment, toolchain,
priority or affinity changes. Polling output belongs to a fresh work/test-runs
directory. Native API handles remain tied to their original process objects.
"""
from __future__ import annotations
import argparse,ctypes as C,datetime as dt,hashlib,importlib.util,json,math,os,re,struct,subprocess,sys,time
from ctypes import wintypes as W
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def normalized(path):return os.path.normcase(os.path.abspath(path))
def resolve_run(path):
 run=path.resolve();allowed=(ROOT/'work/test-runs').resolve()
 if allowed not in run.parents:raise ValueError('Evidence must be a named directory beneath work/test-runs')
 if run.exists():raise FileExistsError('Use a fresh run directory')
 return run
def parse_temperature(data):
 if len(data)<2686:raise ValueError('Truncated Core Temp shared data')
 cores,cpus=struct.unpack_from('<II',data,1536)
 if not 1<=cores or not 1<=cpus<=128 or cores*cpus>256:raise ValueError('Invalid Core Temp core/CPU counts')
 fahrenheit,delta=data[2684]!=0,data[2685]!=0;values=[]
 for index in range(cores*cpus):
  tj=struct.unpack_from('<I',data,1024+4*(index//cores))[0]
  if not 40<=tj<=125:raise ValueError('Invalid Core Temp TjMax')
  value=struct.unpack_from('<f',data,1544+4*index)[0]
  if fahrenheit:value=value*5/9 if delta else (value-32)*5/9
  if delta:value=tj-value
  if not math.isfinite(value) or not -20<=value<=125:raise ValueError('Invalid Core Temp sensor')
  values.append(round(value,1))
 return dict(available=True,maximumC=max(values),minimumC=min(values),coreTemperaturesC=values,coreCount=cores,cpuCount=cpus)
def same_identity(actual,expected,require_live=True):
 return (actual['pid']==expected['pid'] and actual['created100ns']==expected['created100ns'] and
  normalized(actual['image'])==normalized(expected['image']) and (not require_live or actual['alive']))
def admit_tools(snapshot,owned,allowed,backend,events):
 # A stale parent PID alone is insufficient: verify its retained live handle.
 changed=True
 while changed:
  changed=False
  for item in snapshot:
   if item['pid'] in owned or item['parent'] not in owned:continue
   parent=owned[item['parent']]
   try:parent_now=backend.read(parent['handle'])
   except OSError:continue
   if not same_identity(parent_now,parent):continue
   handle=None
   try:
    handle=backend.open(item['pid']);child=backend.read(handle)
    if normalized(child['image']) not in allowed or not child['alive'] or child['created100ns']<parent['created100ns']:
     backend.close(handle);handle=None;continue
    child.update(handle=handle,parent=parent['pid'],parentCreated100ns=parent['created100ns'],depth=parent['depth']+1)
    owned[child['pid']]=child;events.append(dict(event='admitted_owned_tool',identity=public(child)));changed=True
   except OSError:
    if handle:backend.close(handle)
def public(record):return {k:v for k,v in record.items() if k!='handle'}
def stop_owned(owned,backend,root_pid,snapshot,allowed,events):
 # Stop the verified launcher first so it cannot begin a later build phase.
 # Original handles prevent PID reuse between final identity check and stop.
 order=[root_pid]+[pid for pid in sorted(owned,key=lambda p:owned[p]['depth'],reverse=True) if pid!=root_pid]
 stopped=set()
 for pid in order:
  record=owned[pid]
  try:
   current=backend.read(record['handle'])
   if not same_identity(current,record):events.append(dict(event='stop_refused_identity_or_exit',identity=public(record),actual=public(current)));continue
   backend.terminate(record['handle'],record);stopped.add(pid);events.append(dict(event='stopped_exact_owned_process',identity=public(record)))
   if pid==root_pid:
    # Capture any tool descendants that became visible immediately before stop.
    admit_tools(snapshot(),owned,allowed,backend,events)
    order.extend(p for p in sorted(owned,key=lambda p:owned[p]['depth'],reverse=True) if p not in order)
  except OSError as exc:events.append(dict(event='stop_refused_or_failed',identity=public(record),error=str(exc)))
 return stopped

class Windows:
 class ProcessEntry(C.Structure):
  _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',C.c_size_t),('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),('exe',W.WCHAR*260)]
 class Memory(C.Structure):
  _fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(name,C.c_size_t) for name in ('peakWorkingSet','workingSet','peakPaged','paged','peakNonPaged','nonPaged','pagefile','peakPagefile','private')]
 def __init__(self):
  if os.name!='nt':raise RuntimeError('Windows required')
  self.k=C.WinDLL('kernel32',use_last_error=True);self.p=C.WinDLL('psapi',use_last_error=True)
  signatures={
   'OpenProcess':(W.HANDLE,[W.DWORD,W.BOOL,W.DWORD]),'CloseHandle':(W.BOOL,[W.HANDLE]),
   'GetProcessTimes':(W.BOOL,[W.HANDLE]+[C.POINTER(C.c_ulonglong)]*4),
   'QueryFullProcessImageNameW':(W.BOOL,[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]),
   'GetProcessId':(W.DWORD,[W.HANDLE]),'TerminateProcess':(W.BOOL,[W.HANDLE,W.UINT]),
   'CreateToolhelp32Snapshot':(W.HANDLE,[W.DWORD,W.DWORD]),
   'Process32FirstW':(W.BOOL,[W.HANDLE,C.POINTER(self.ProcessEntry)]),'Process32NextW':(W.BOOL,[W.HANDLE,C.POINTER(self.ProcessEntry)]),
   'OpenFileMappingW':(W.HANDLE,[W.DWORD,W.BOOL,W.LPCWSTR]),
   'MapViewOfFile':(C.c_void_p,[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,C.c_size_t]),'UnmapViewOfFile':(W.BOOL,[C.c_void_p])}
  for name,(ret,params) in signatures.items():getattr(self.k,name).restype=ret;getattr(self.k,name).argtypes=params
  self.p.GetProcessMemoryInfo.restype=W.BOOL;self.p.GetProcessMemoryInfo.argtypes=[W.HANDLE,C.POINTER(self.Memory),W.DWORD]
 def check(self,result,name):
  if not result:raise OSError(C.get_last_error(),name)
  return result
 def open(self,pid):return self.check(self.k.OpenProcess(0x1000|0x400|0x10|0x1,False,pid),'OpenProcess')
 def close(self,handle):self.k.CloseHandle(handle)
 def read(self,handle):
  created,exited,kernel,user=[C.c_ulonglong() for _ in range(4)]
  self.check(self.k.GetProcessTimes(handle,C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)),'GetProcessTimes')
  path=C.create_unicode_buffer(32768);length=W.DWORD(len(path));self.check(self.k.QueryFullProcessImageNameW(handle,0,path,C.byref(length)),'QueryFullProcessImageName')
  result=dict(pid=int(self.k.GetProcessId(handle)),created100ns=created.value,exited100ns=exited.value,image=path.value,alive=exited.value==0,cpu100ns=kernel.value+user.value,kernel100ns=kernel.value,user100ns=user.value)
  counters=self.Memory();counters.cb=C.sizeof(counters)
  if self.p.GetProcessMemoryInfo(handle,C.byref(counters),counters.cb):result.update(privateBytes=int(counters.private),workingSetBytes=int(counters.workingSet),peakWorkingSetBytes=int(counters.peakWorkingSet),peakPagefileBytes=int(counters.peakPagefile))
  else:result['memoryError']=C.get_last_error()
  return result
 def snapshot(self):
  handle=self.k.CreateToolhelp32Snapshot(2,0)
  if handle==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'CreateToolhelp32Snapshot')
  try:
   entry=self.ProcessEntry();entry.size=C.sizeof(entry);rows=[];ok=self.k.Process32FirstW(handle,C.byref(entry))
   while ok:
    rows.append(dict(pid=int(entry.pid),parent=int(entry.parent),name=entry.exe));ok=self.k.Process32NextW(handle,C.byref(entry))
   return rows
  finally:self.close(handle)
 def terminate(self,handle,expected):
  current=self.read(handle)
  if not same_identity(current,expected):raise OSError('Final exact process verification refused')
  self.check(self.k.TerminateProcess(handle,124),'TerminateProcess exact owned build')
 def temperature(self):
  handle=self.k.OpenFileMappingW(4,False,'CoreTempMappingObjectEx')
  if not handle:return dict(available=False,reason='shared_mapping_unavailable',winError=C.get_last_error())
  view=None
  try:
   view=self.k.MapViewOfFile(handle,4,0,0,2688)
   if not view:return dict(available=False,reason='shared_mapping_read_failed',winError=C.get_last_error())
   try:return parse_temperature(C.string_at(view,2688))
   except ValueError as exc:return dict(available=False,reason=str(exc))
  finally:
   if view:self.k.UnmapViewOfFile(view)
   self.close(handle)

def builder_spec():
 path=ROOT/'work/build-vp-msvc.py';spec=importlib.util.spec_from_file_location('vp_build',path);builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
 project=builder.parse_project('Release');tools,_=builder.tools_and_environment();return path,project,tools
def preexisting_guard(backend,allowed):
 failures=[]
 for item in backend.snapshot():
  if item['name'].lower() in ('civilizationv.exe','civilizationv_dx11.exe','civilizationv_tablet.exe'):failures.append('Civ V is running PID'+str(item['pid']))
  if item['name'].lower() not in ('cl.exe','link.exe'):continue
  handle=None
  try:
   handle=backend.open(item['pid']);info=backend.read(handle)
   if info['alive'] and normalized(info['image']) in allowed:failures.append('Build tool already running: '+info['image']+' PID'+str(info['pid']))
  except OSError:failures.append('Cannot identify a running compiler/linker safely: PID'+str(item['pid']))
  finally:
   if handle:backend.close(handle)
 if failures:raise RuntimeError('; '.join(failures))
def log_progress(stdout,run):
 files=[stdout];last=''
 if stdout.exists():
  with stdout.open('rb') as stream:
   stream.seek(max(0,stdout.stat().st_size-16384));last=stream.read(16384).decode('utf-8',errors='replace')
 for match in re.finditer(r'^0[1-5][^\r\n]*?: (.+\.log)\r?$',last,re.M):
  path=Path(match.group(1)).resolve();base=(ROOT/'work/msvc-output').resolve()
  if base in path.parents:files.append(path)
 result=[]
 for path in files:
  try:s=path.stat();result.append([str(path),s.st_size,s.st_mtime_ns])
  except OSError:result.append([str(path),None,None])
 return result
def choose_limit(elapsed,link_elapsed,idle_elapsed,private,temp_hot,args):
 if temp_hot>=args.hot_samples:return 'sustained_cpu_temperature'
 if private>=args.maximum_private_gib*1024**3:return 'owned_process_private_limit'
 if elapsed>=args.maximum_seconds:return 'maximum_build_duration'
 if link_elapsed is not None and link_elapsed>=args.maximum_link_seconds:return 'maximum_link_duration'
 if idle_elapsed>=args.idle_seconds:return 'no_log_or_cpu_progress'
 return None
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--run-dir',required=True,type=Path);parser.add_argument('--jobs',type=int,default=2)
 parser.add_argument('--mode',choices=('ltcg','baseline'),default='ltcg');parser.add_argument('--build',action='store_true')
 parser.add_argument('--maximum-seconds',type=float,default=900);parser.add_argument('--maximum-link-seconds',type=float,default=600)
 parser.add_argument('--idle-seconds',type=float,default=120);parser.add_argument('--sample-seconds',type=float,default=2)
 parser.add_argument('--maximum-private-gib',type=float,default=3.2);parser.add_argument('--temperature-limit',type=float,default=95);parser.add_argument('--hot-samples',type=int,default=3)
 args=parser.parse_args()
 if not 1<=args.jobs<=16 or not 1<=args.sample_seconds<=30 or not 10<=args.idle_seconds<=3600 or not 10<=args.maximum_seconds<=3600 or not 10<=args.maximum_link_seconds<=3600 or not 1<=args.maximum_private_gib<=3.8 or not 85<=args.temperature_limit<=100 or not 2<=args.hot_samples<=10:raise ValueError('Invalid bounded monitor setting')
 run=resolve_run(args.run_dir);builder,project,tools=builder_spec();allowed={normalized(p) for p in tools.values()};backend=Windows()
 preexisting_guard(backend,allowed)
 command=[sys.executable,'-B','-u',str(builder),'--config','release','--jobs',str(args.jobs),'--embedded-compiler-debug','--pch-memory','400']
 if args.mode=='baseline':command.append('--no-ltcg')
 compile_flags=['/Z7' if f=='/Zi' else f for f in project['compile_flags'] if not f.lower().startswith('/zm')]+['/Zm400'];link_flags=list(project['link_flags'])
 if compile_flags.count('/GL')!=1 or link_flags.count('/LTCG')!=1:raise ValueError('Release project no longer matches the reviewed GL/LTCG flags')
 if args.mode=='baseline':compile_flags.remove('/GL');link_flags.remove('/LTCG')
 plan=dict(schema=1,createdUtc=utc(),buildRequested=args.build,mode=args.mode,command=command,compileFlags=compile_flags,linkFlags=link_flags,limits=vars(args)|{'run_dir':str(run)},builderSha256=sha(builder),projectSha256=sha(project['project']),monitorSha256=sha(Path(__file__)),toolPaths={k:str(v) for k,v in tools.items()},toolSha256={k:sha(v) for k,v in tools.items()},temperature=backend.temperature(),priorityOrAffinityChanged=False,toolchainOrProductionChanged=False)
 run.mkdir(parents=True);(run/'monitor-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
 if not args.build:print('Prepared only; no build launched: '+str(run));return 0
 # Recheck immediately before spawning; shared services are never admitted/stopped.
 preexisting_guard(backend,allowed)
 log=(run/'build-monitor.jsonl').open('w',encoding='utf-8');stdout_path=run/'builder-output.log';stream=stdout_path.open('wb');owned={};proc=None;start=time.monotonic();last_progress=start;progress=None;last_cpu={};hot=0;link_started=None;reason=None;events=[]
 def record(event):event['utc']=utc();event['elapsedSeconds']=time.monotonic()-start;event['monitorCpuSeconds']=time.process_time();log.write(json.dumps(event,separators=(',',':'))+'\n');log.flush()
 try:
  proc=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  handle=backend.open(proc.pid);root=backend.read(handle)
  if not root['alive'] or normalized(root['image'])!=normalized(sys.executable):backend.close(handle);raise RuntimeError('New launcher identity unavailable; no process-stop authority')
  root.update(handle=handle,parent=os.getpid(),depth=0);owned[root['pid']]=root;record(dict(event='armed',launcher=public(root)))
  while True:
   now=time.monotonic();admit_tools(backend.snapshot(),owned,allowed,backend,events)
   for event in events:record(event)
   events.clear();samples=[];cpu_progress=False;maximum_private=0
   for pid,bound in owned.items():
    try:
     current=backend.read(bound['handle'])
     if not same_identity(current,bound,False):record(dict(event='sample_refused_identity',identity=public(bound),actual=current));continue
     before=last_cpu.get(pid,current['cpu100ns']);delta=max(0,current['cpu100ns']-before);last_cpu[pid]=current['cpu100ns'];current['cpuDelta100ns']=delta;samples.append(current)
     if current['alive']:maximum_private=max(maximum_private,current.get('privateBytes',0));cpu_progress=cpu_progress or delta>=500000
     if current['alive'] and normalized(current['image'])==normalized(tools['link']) and link_started is None:link_started=now
    except OSError as exc:record(dict(event='sample_unavailable',pid=pid,error=str(exc)))
   token=log_progress(stdout_path,run)
   if token!=progress or cpu_progress:last_progress=now;progress=token
   temperature=backend.temperature();hot=hot+1 if temperature.get('available') and temperature['maximumC']>=args.temperature_limit else 0
   record(dict(event='sample',processes=samples,temperature=temperature,hotSamples=hot,logProgress=token,idleSeconds=now-last_progress,linkSecondsSinceFirstObservation=None if link_started is None else now-link_started))
   code=proc.poll()
   if code is not None:record(dict(event='builder_exited',returncode=code));break
   reason=choose_limit(now-start,None if link_started is None else now-link_started,now-last_progress,maximum_private,hot,args)
   if reason:
    record(dict(event='limit_reached',reason=reason));stop_owned(owned,backend,root['pid'],backend.snapshot,allowed,events)
    for event in events:record(event)
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:record(dict(event='launcher_still_unavailable_after_verified_stop'))
    code=124;break
   time.sleep(min(args.sample_seconds,max(0.01,args.maximum_seconds-(time.monotonic()-start))))
  result=dict(status='bounded-stop' if reason else 'builder-exited',reason=reason,returncode=code,elapsedSeconds=time.monotonic()-start,launcher=public(root),ownedProcesses=[public(v) for v in owned.values()],finalTemperature=temperature,buildOutputLog=str(stdout_path),normalBuilderResultStillRequired=True)
  (run/'monitor-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2));return code
 except BaseException as exc:
  record(dict(event='monitor_error',error=str(exc)))
  if owned and proc and proc.poll() is None:
   stop_owned(owned,backend,proc.pid,backend.snapshot,allowed,events)
   for event in events:record(event)
  (run/'monitor-result.json').write_text(json.dumps(dict(status='monitor-error',error=str(exc),buildStarted=proc is not None),indent=2)+'\n',encoding='utf-8');raise
 finally:
  for item in owned.values():backend.close(item['handle'])
  stream.close();log.close()
if __name__=='__main__':raise SystemExit(main())
