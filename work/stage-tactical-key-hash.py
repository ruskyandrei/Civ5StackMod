"""Work-only variable-vector tactical hash; reverse proof limits delta to hash."""
from pathlib import Path
import difflib,hashlib,json,subprocess
root=Path(__file__).resolve().parents[1];out=root/'work/tactical-key-hash-stage';out.mkdir(exist_ok=True)
control='6f4688d81';path='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
old=subprocess.check_output(['git','show',control+':'+path],cwd=root).decode('utf-8-sig').replace('\r\n','\n')
def function(s,name):
 a=s.index(name);b=s.index('{',a)+1;depth=1
 while depth:depth+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]
before=function(old,'struct StackForecastKeyHash\n')
after='''struct StackForecastKeyHash
{
 size_t operator()(const StackForecastKey& key) const
 {
  const size_t words=key.state.size();
  // Preserve the inexpensive original recurrence for the shortest keys.
  if(words<=8)
  {
   size_t result=0;
   for(size_t i=0;i<words;++i)
    result^=(size_t)key.state[i]+0x9e3779b9+(result<<6)+(result>>2);
   return result;
  }
  // Independent full-word lanes for longer exact vectors. Length separates
  // prefixes; equality still compares every word and the vector size.
  unsigned int v1=0x9e3779b1u+0x85ebca77u;
  unsigned int v2=0x85ebca77u,v3=0u,v4=0u-0x9e3779b1u;
  size_t i=0;
  for(;i+4<=words;i+=4)
  {
   v1=(v1+(unsigned int)key.state[i])*0x9e3779b1u;v1=(v1<<13)|(v1>>19);
   v2=(v2+(unsigned int)key.state[i+1])*0x85ebca77u;v2=(v2<<17)|(v2>>15);
   v3=(v3+(unsigned int)key.state[i+2])*0xc2b2ae3du;v3=(v3<<11)|(v3>>21);
   v4=(v4+(unsigned int)key.state[i+3])*0x27d4eb2fu;v4=(v4<<19)|(v4>>13);
  }
  unsigned int result=((v1<<1)|(v1>>31))+((v2<<7)|(v2>>25))+((v3<<12)|(v3>>20))+((v4<<18)|(v4>>14));
  result+=(unsigned int)words*sizeof(int);
  for(;i<words;++i){result+=(unsigned int)key.state[i]*0xc2b2ae3du;result=((result<<17)|(result>>15))*0x27d4eb2fu;}
  result^=result>>15;result*=0x85ebca77u;result^=result>>13;result*=0xc2b2ae3du;result^=result>>16;
  return (size_t)result;
 }
}'''
assert old.count(before)==1;new=old.replace(before,after,1)
assert new.replace(after,before,1)==old,'Delta extends beyond hash'
(out/'CvTacticalAI.cpp').write_text(new,encoding='utf-8');(out/'control.cpp').write_text(old,encoding='utf-8')
(out/'hash.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path)),encoding='utf-8')
(out/'manifest.json').write_text(json.dumps(dict(control=control,source_sha256=hashlib.sha256(old.encode()).hexdigest(),candidate_sha256=hashlib.sha256(new.encode()).hexdigest(),reverse_whole_file_exact=True,production_untouched=True,scope='Only variable-length full-word hash differs. Equality, all table/FIFO/key/payload/context/math bodies byte-identical. No native ROI.'),indent=2))
print('Tactical key hash staged; whole-file reverse proof passed')
