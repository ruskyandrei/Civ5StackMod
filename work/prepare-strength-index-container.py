"""Stage the reviewed chained contiguous strength-cache index; no production edits."""
from pathlib import Path
import difflib,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/strength-index-container-staged'
CONTROL='ee180b91d'
PATH='CvGameCoreDLL_Expansion2/CvStackingStrengthCache.cpp'
HEADER_PATH='CvGameCoreDLL_Expansion2/CvStackingStrengthCache.h'

def transform(source):
 candidate=source.replace('#include <unordered_map>\n#include <deque>','#include <algorithm>\n#include <vector>',1)
 old='''\t\ttypedef std::tr1::unordered_map<Key, int, Hash> Table;
\t\tTable table;
\t\t// Node references survive rehash. FIFO stores references, not duplicate keys.
\t\tstd::deque<const Key*> order;'''
 new='''\t\t// Indices survive vector growth. The ring replaces only the oldest slot;
\t\t// bucket links retain full-key equality and never depend on addresses.
\t\tstruct Node { Key key; int value, next, previous; size_t hash; };
\t\tstd::vector<Node> nodes;
\t\tstd::vector<int> buckets;
\t\tunsigned int oldest = 0;
\t\tsize_t Find(const Key& key, size_t hash)
\t\t{
\t\t\tif (buckets.empty()) return (size_t)-1;
\t\t\tfor (int i = buckets[hash & (buckets.size() - 1)]; i != -1; i = nodes[i].next)
\t\t\t\tif (nodes[i].hash == hash && nodes[i].key == key) return (size_t)i;
\t\t\treturn (size_t)-1;
\t\t}
\t\tvoid Link(unsigned int index)
\t\t{
\t\t\tNode& node = nodes[index];
\t\t\tconst size_t bucket = node.hash & (buckets.size() - 1);
\t\t\tnode.previous = -1;
\t\t\tnode.next = buckets[bucket];
\t\t\tif (node.next != -1) nodes[node.next].previous = index;
\t\t\tbuckets[bucket] = index;
\t\t}
\t\tvoid Unlink(unsigned int index)
\t\t{
\t\t\tNode& node = nodes[index];
\t\t\tif (node.previous != -1) nodes[node.previous].next = node.next;
\t\t\telse buckets[node.hash & (buckets.size() - 1)] = node.next;
\t\t\tif (node.next != -1) nodes[node.next].previous = node.previous;
\t\t}'''
 assert old in candidate;candidate=candidate.replace(old,new,1)
 candidate=candidate.replace('order.clear();\n\t\t\ttable.clear();','nodes.clear();\n\t\t\tstd::fill(buckets.begin(), buckets.end(), -1);\n\t\t\toldest = 0;',1)
 candidate=candidate.replace('stats.limit = entries > 65536 ? 65536 : entries;','''stats.limit = entries > 65536 ? 65536 : entries;
\t\tsize_t bucketCount = 1;
\t\twhile (bucketCount < stats.limit * 2) bucketCount <<= 1;
\t\ttry
\t\t{
\t\t\tbuckets.assign(bucketCount, -1);
\t\t}
\t\tcatch (...)
\t\t{
\t\t\t// A throwing constructor has no destructor. Release the claimed cache
\t\t\t// before propagating allocation failure to the existing caller.
\t\t\tstd::vector<Node>().swap(nodes);
\t\t\tstd::vector<int>().swap(buckets);
\t\t\tdepth = 0;
\t\t\tentered = false;
\t\t\tstats = Stats();
\t\t\tInterlockedExchange(&owner, 0);
\t\t\tthrow;
\t\t}''',1)
 candidate=candidate.replace('std::deque<const Key*>().swap(order);\n\t\tTable().swap(table); // Also release retained buckets in the 32-bit game.','std::vector<Node>().swap(nodes);\n\t\tstd::vector<int>().swap(buckets); // Release both retained allocations in the 32-bit game.',1)
 candidate=candidate.replace('Table::const_iterator found = table.find(key);','const size_t found = Find(key, Hash()(key));',1)
 candidate=candidate.replace('found == table.end()','found == (size_t)-1',1).replace('value = found->second;','value = nodes[found].value;',1)
 start=candidate.index('\tvoid Store(');end=candidate.index('\n\tvoid Invalidate()',start)
 candidate=candidate[:start]+'''\tvoid Store(const Key& key, long generation, int value)
\t{
\t\tlong current;
\t\t// Do not admit a result calculated across an invalidation.
\t\tif (!Context(current) || generation != current)
\t\t\treturn;
\t\tconst size_t hash = Hash()(key);
\t\tif (Find(key, hash) != (size_t)-1)
\t\t\treturn;
\t\tunsigned int index;
\t\tif (nodes.size() >= stats.limit)
\t\t{
\t\t\tindex = oldest;
\t\t\tUnlink(index);
\t\t\toldest = (oldest + 1) % stats.limit;
\t\t\t++stats.evictions;
\t\t}
\t\telse
\t\t{
\t\t\tif (nodes.size() == nodes.capacity())
\t\t\t\tnodes.reserve(std::min(stats.limit, std::max(256u, (unsigned int)nodes.size() * 2)));
\t\t\tindex = (unsigned int)nodes.size();
\t\t\tnodes.push_back(Node());
\t\t}
\t\tNode& node = nodes[index];
\t\tnode.key = key;
\t\tnode.value = value;
\t\tnode.hash = hash;
\t\tLink(index);
\t\tif (nodes.size() > stats.peakEntries)
\t\t\tstats.peakEntries = (unsigned int)nodes.size();
\t}
''' +candidate[end:]
 candidate=candidate.replace('result.entries = (unsigned int)table.size();','result.entries = (unsigned int)nodes.size();',1)
 assert 'table.' not in candidate and 'order.' not in candidate
 return candidate

def prepare():
 OUT.mkdir(exist_ok=True)
 source=subprocess.check_output(['git','show',CONTROL+':'+PATH],cwd=ROOT).decode('utf-8-sig')
 header=subprocess.check_output(['git','show',CONTROL+':'+HEADER_PATH],cwd=ROOT).decode('utf-8-sig')
 candidate=transform(source)
 (OUT/'CvStackingStrengthCache-control.cpp').write_text(source,encoding='utf-8',newline='')
 (OUT/'CvStackingStrengthCache.cpp').write_text(candidate,encoding='utf-8',newline='')
 (OUT/'CvStackingStrengthCache.h').write_text(header,encoding='utf-8',newline='')
 patch=''.join(difflib.unified_diff(source.splitlines(True),candidate.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH))
 (OUT/'strength-index.patch').write_text(patch,encoding='utf-8',newline='')
 (OUT/'staging-proof.json').write_text(json.dumps(dict(control=CONTROL,production_applied=False,source_sha256=hashlib.sha256(source.encode()).hexdigest(),candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),unchanged_header_sha256=hashlib.sha256(header.encode()).hexdigest(),key_words=22,entry_ceiling=65536,full_key_comparison=True,existing_fifo_and_statistics=True,outer_destruction_releases_both_vectors=True),indent=2)+'\n',encoding='utf-8')
 print('Staged strength index; production unchanged.')

if __name__=='__main__':prepare()
