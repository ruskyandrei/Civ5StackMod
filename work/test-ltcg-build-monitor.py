"""Pure fake-backend safety/limit/Core Temp fixtures; no process launch or stop."""
from pathlib import Path
import copy,importlib.util,json,struct,types
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'work/monitor-ltcg-build.py'
spec=importlib.util.spec_from_file_location('monitor',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=0
def check(condition):
 global checks;checks+=1;assert condition
class Fake:
 def __init__(self,records):self.records=copy.deepcopy(records);self.closed=[];self.stopped=[];self.reads=[]
 def open(self,pid):
  if pid not in self.records:raise OSError('gone')
  return pid
 def close(self,h):self.closed.append(h)
 def read(self,h):
  self.reads.append(h)
  if h not in self.records:raise OSError('gone')
  return copy.deepcopy(self.records[h])
 def terminate(self,h,expected):
  actual=self.read(h)
  if not m.same_identity(actual,expected):raise OSError('exact handle refused')
  self.records[h]['alive']=False;self.stopped.append(h)
def record(pid,created,image,alive=True):return dict(pid=pid,created100ns=created,image=image,alive=alive,cpu100ns=0)
def owned_root(backend):
 r=backend.read(1);r.update(handle=1,parent=0,depth=0);return {1:r}
allowed={m.normalized('E:/tools/cl.exe'),m.normalized('E:/tools/link.exe')}
records={1:record(1,100,'C:/python/python.exe'),2:record(2,101,'E:/tools/cl.exe'),3:record(3,102,'E:/tools/cl.exe'),4:record(4,103,'E:/tools/link.exe'),5:record(5,104,'E:/tools/mspdbsrv.exe'),6:record(6,50,'E:/tools/link.exe'),7:record(7,105,'E:/other/cl.exe')}
snapshot=[dict(pid=3,parent=2),dict(pid=4,parent=1),dict(pid=2,parent=1),dict(pid=5,parent=2),dict(pid=6,parent=1),dict(pid=7,parent=1)]
b=Fake(records);owned=owned_root(b);events=[];m.admit_tools(snapshot,owned,allowed,b,events)
check(set(owned)=={1,2,3,4});check(owned[3]['depth']==2 and owned[3]['parentCreated100ns']==101);check(len(events)==3);check({5,6,7}<=set(b.closed))
stops=m.stop_owned(owned,b,1,lambda:snapshot,allowed,events);check(stops=={1,2,3,4});check(b.stopped[0]==1);check(b.stopped.index(3)<b.stopped.index(2));check(all(b.records[p]['alive'] for p in (5,6,7)))
for field,value in [('created100ns',999),('image','C:/unrelated/app.exe'),('pid',999),('alive',False)]:
 b=Fake(records);owned=owned_root(b);b.records[1][field]=value;events=[];m.admit_tools(snapshot,owned,allowed,b,events);check(set(owned)=={1});check(not events)
 m.stop_owned(owned,b,1,lambda:snapshot,allowed,events);check(not b.stopped);check(events[-1]['event']=='stop_refused_identity_or_exit')
# Reused child PID/image on the retained identity is refused at stop, including
# children after the launcher has been admitted; unowned services remain live.
b=Fake(records);owned=owned_root(b);events=[];m.admit_tools(snapshot,owned,allowed,b,events);b.records[2]['created100ns']=555
stops=m.stop_owned(owned,b,1,lambda:snapshot,allowed,events);check(2 not in stops and b.records[2]['alive']);check(3 in stops);check(5 not in b.stopped)
# A vanished handle and inconsistent snapshot cannot grant stop authority.
b=Fake(records);owned=owned_root(b);del b.records[2];events=[];m.admit_tools(snapshot,owned,allowed,b,events);check(2 not in owned and 3 not in owned);check(4 in owned)
b=Fake(records);owned=owned_root(b);events=[];m.admit_tools([dict(pid=2,parent=99)],owned,allowed,b,events);check(set(owned)=={1})
args=types.SimpleNamespace(hot_samples=3,maximum_private_gib=3.2,maximum_seconds=900,maximum_link_seconds=600,idle_seconds=120)
check(m.choose_limit(1,None,0,0,0,args) is None);check(m.choose_limit(900,None,0,0,0,args)=='maximum_build_duration');check(m.choose_limit(1,600,0,0,0,args)=='maximum_link_duration');check(m.choose_limit(1,None,120,0,0,args)=='no_log_or_cpu_progress');check(m.choose_limit(1,None,0,int(3.3*1024**3),0,args)=='owned_process_private_limit');check(m.choose_limit(1,None,0,0,3,args)=='sustained_cpu_temperature')
def temperature(cores=2,cpus=1,values=(50,60),fahrenheit=False,delta=False,tj=100):
 data=bytearray(2688);struct.pack_into('<II',data,1536,cores,cpus)
 for i in range(cpus):struct.pack_into('<I',data,1024+4*i,tj)
 for i,v in enumerate(values):struct.pack_into('<f',data,1544+4*i,v)
 data[2684]=fahrenheit;data[2685]=delta;return data
check(m.parse_temperature(temperature())['maximumC']==60);check(m.parse_temperature(temperature(values=(122,140),fahrenheit=True))['coreTemperaturesC']==[50,60]);check(m.parse_temperature(temperature(values=(50,40),delta=True))['coreTemperaturesC']==[50,60]);check(m.parse_temperature(temperature(values=(90,72),delta=True,fahrenheit=True))['coreTemperaturesC']==[50,60]);check(m.parse_temperature(temperature(cores=1,cpus=2,values=(35,40)))['coreCount']==1)
for data in [b'',temperature(cores=0),temperature(cpus=0),temperature(cores=257),temperature(cpus=129),temperature(tj=0),temperature(values=(float('nan'),1)),temperature(values=(float('inf'),1)),temperature(values=(126,1))]:
 try:m.parse_temperature(data);check(False)
 except ValueError:check(True)
out=ROOT/'work/ltcg-monitor-fixture-result.json';out.write_text(json.dumps(dict(checks=checks,failures=0,processes_launched_or_stopped=False,scope='Actual monitor discovery/identity/stop-policy and temperature/limit helpers with fake process backend; Win32 native bindings are not live-tested',source_sha256=m.sha(p)),indent=2)+'\n',encoding='utf-8')
print(str(checks)+' monitor checks passed; no native process actions.')
