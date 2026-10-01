"""Work-only full-word strength-cache hash stages; production is never edited."""
from pathlib import Path
import argparse,difflib,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
CONTROL='cf8f842e2733841255a1d5bc741e4d95a387299b'
PATH='CvGameCoreDLL_Expansion2/CvStackingStrengthCache.cpp'
HEADER='CvGameCoreDLL_Expansion2/CvStackingStrengthCache.h'
OUT=ROOT/'work/strength-hash-experiment'

def function(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]

def transform(source,variant):
 old=function(source,'size_t operator()(const Key& key) const')
 round2='''v1 += (unsigned int)key.values[i] * 0x85ebca77u;
					v1 = ((v1 << 13) | (v1 >> 19)) * 0x9e3779b1u;
					v2 += (unsigned int)key.values[i+1] * 0x85ebca77u;
					v2 = ((v2 << 13) | (v2 >> 19)) * 0x9e3779b1u;
					v3 += (unsigned int)key.values[i+2] * 0x85ebca77u;
					v3 = ((v3 << 13) | (v3 >> 19)) * 0x9e3779b1u;
					v4 += (unsigned int)key.values[i+3] * 0x85ebca77u;
					v4 = ((v4 << 13) | (v4 >> 19)) * 0x9e3779b1u;'''
 round1='''v1 = (v1 + (unsigned int)key.values[i]) * 0x9e3779b1u;
					v1 = (v1 << 13) | (v1 >> 19);
					v2 = (v2 + (unsigned int)key.values[i+1]) * 0x85ebca77u;
					v2 = (v2 << 17) | (v2 >> 15);
					v3 = (v3 + (unsigned int)key.values[i+2]) * 0xc2b2ae3du;
					v3 = (v3 << 11) | (v3 >> 21);
					v4 = (v4 + (unsigned int)key.values[i+3]) * 0x27d4eb2fu;
					v4 = (v4 << 19) | (v4 >> 13);'''
 assert variant in ('multiply2','multiply1')
 new='''size_t operator()(const Key& key) const
			{
				// Four independent full-word lanes shorten the serial dependency
				// chain. Every input bit is mixed; full-key equality is unchanged.
				unsigned int v1 = 0x9e3779b1u + 0x85ebca77u;
				unsigned int v2 = 0x85ebca77u, v3 = 0u, v4 = 0u - 0x9e3779b1u;
				const size_t words = sizeof(key.values) / sizeof(key.values[0]);
				size_t i = 0;
				for (; i + 4 <= words; i += 4)
				{
					ROUND
				}
				unsigned int result = ((v1 << 1) | (v1 >> 31)) + ((v2 << 7) | (v2 >> 25))
					+ ((v3 << 12) | (v3 >> 20)) + ((v4 << 18) | (v4 >> 14));
				result += (unsigned int)sizeof(key.values);
				for (; i < words; ++i)
				{
					result += (unsigned int)key.values[i] * 0xc2b2ae3du;
					result = ((result << 17) | (result >> 15)) * 0x27d4eb2fu;
				}
				result ^= result >> 15;
				result *= 0x85ebca77u;
				result ^= result >> 13;
				result *= 0xc2b2ae3du;
				result ^= result >> 16;
				return (size_t)result;
			}'''.replace('ROUND',round2 if variant=='multiply2' else round1)
 assert source.count(old)==1
 candidate=source.replace(old,new,1)
 assert candidate.replace(new,old,1)==source
 return candidate

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--variant',choices=('multiply2','multiply1'),default='multiply2');args=p.parse_args()
 source=subprocess.check_output(['git','show',CONTROL+':'+PATH],cwd=ROOT).decode('utf-8-sig')
 header=subprocess.check_output(['git','show',CONTROL+':'+HEADER],cwd=ROOT).decode('utf-8-sig')
 assert 'int values[22];' in header and (ROOT/HEADER).read_text(encoding='utf-8-sig')==header
 candidate=transform(source,args.variant);out=OUT/args.variant;out.mkdir(parents=True,exist_ok=True)
 (out/'control.cpp').write_text(source,encoding='utf-8',newline='');(out/'CvStackingStrengthCache.cpp').write_text(candidate,encoding='utf-8',newline='')
 (out/'hash.patch').write_text(''.join(difflib.unified_diff(source.splitlines(keepends=True),candidate.splitlines(keepends=True),fromfile='a/'+PATH,tofile='b/'+PATH)),encoding='utf-8',newline='')
 proof={'control':CONTROL,'variant':args.variant,'production_applied':False,'hash_only_reverse_byte_exact':True,
  'header_unchanged':True,'context_ring_equality_budgets_stats_unchanged':True,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
  'candidate_sha256':hashlib.sha256(candidate.encode()).hexdigest(),'header_sha256':hashlib.sha256(header.encode()).hexdigest(),
  'scope':'Only full-word integer hash operator changes; bucket distribution may change, complete88-byte equality and deterministic ring FIFO remain.'}
 (out/'staging-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
if __name__=='__main__':main()
