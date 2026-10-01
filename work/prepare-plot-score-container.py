"""Stage a sorted plot-score representation; never apply production changes."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'work/plot-score-container-staged';out.mkdir(exist_ok=True)
control='490ee12c4'
files=['CvTacticalAI.h','CvTacticalAI.cpp']
original={name:subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/'+name],cwd=root).decode('utf-8-sig') for name in files}
wrapper='''// Plot scores are small, frequently copied and only mutated through operator[].
// Integer key order and default-zero short values match the former map. Element
// references/iterators can move on insertion; callers do not retain them across
// insertion. The container object itself remains stable for CoW borrowing.
class STacticalPlotScores
{
public:
    typedef std::pair<int, short> value_type;
    typedef std::vector<value_type>::const_iterator const_iterator;
    short& operator[](int key)
    {
        std::vector<value_type>::iterator it = std::lower_bound(values.begin(), values.end(), key, KeyLess());
        if (it == values.end() || it->first != key)
            it = values.insert(it, value_type(key, 0));
        return it->second;
    }
    const_iterator begin() const { return values.begin(); }
    const_iterator end() const { return values.end(); }
    size_t size() const { return values.size(); }
    bool empty() const { return values.empty(); }
    void clear() { values.clear(); }
    void swap(STacticalPlotScores& other) { values.swap(other.values); }
private:
    struct KeyLess
    {
        bool operator()(const value_type& value, int key) const { return value.first < key; }
    };
    std::vector<value_type> values;
};

'''
header=original[files[0]]
needle='//copy-on-write for often reused seldom updated fields in tactical positions\n'
assert header.count(needle)==1
assert header.count('SCoWField<map<int, short>> plotScores;')==1
header=header.replace(needle,wrapper+needle,1).replace('SCoWField<map<int, short>> plotScores;','SCoWField<STacticalPlotScores> plotScores;')
cpp=original[files[1]]
assert cpp.count('map<int, short>')==4
cpp=cpp.replace('map<int, short>','STacticalPlotScores')
staged=dict(zip(files,(header,cpp)))
patch=''.join(''.join(difflib.unified_diff(original[name].splitlines(keepends=True),staged[name].splitlines(keepends=True),
    fromfile='a/CvGameCoreDLL_Expansion2/'+name,tofile='b/CvGameCoreDLL_Expansion2/'+name)) for name in files)
(out/'container.patch').write_text(patch,encoding='utf-8',newline='\n')
for name,text in staged.items():(out/name).write_text(text,encoding='utf-8',newline='\n')
proof=dict(control=control,production_applied=False,files={name:dict(original_sha256=hashlib.sha256(original[name].encode()).hexdigest(),staged_sha256=hashlib.sha256(staged[name].encode()).hexdigest()) for name in files},
    cpp_original_after_type_restoration=cpp.replace('STacticalPlotScores','map<int, short>')==original[files[1]],
    header_original_after_wrapper_and_type_restoration=header.replace(wrapper,'',1).replace('SCoWField<STacticalPlotScores> plotScores;','SCoWField<map<int, short>> plotScores;')==original[files[0]],
    changed_cpp_type_occurrences=4,no_actor_cap=True,no_search_policy_changes=True,reference_audit='operator[] refs used only within assignment/+= expressions. UpdateScore iterates either borrowed parent or local scores; an in-loop write only updates an existing key, insertion occurs after loop. Finish iterates scores after all insertions. CoW borrows container object, not elements.')
(out/'staging-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(staged=str(out),production_applied=False)))
