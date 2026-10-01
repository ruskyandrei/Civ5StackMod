"""Prepare a flags-only LTCG experiment manifest; never compile or alter tools."""
import argparse,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--jobs',type=int,default=2)
 parser.add_argument('--output',type=Path,default=ROOT/'work/ltcg-experiment-proposal.json')
 args=parser.parse_args()
 if not 1<=args.jobs<=16:raise ValueError('jobs must be1..16')
 out=args.output.resolve();work=(ROOT/'work').resolve()
 if work not in out.parents:raise ValueError('output must be beneath this workspace work directory')
 if out.exists():raise FileExistsError('Use a fresh manifest path')
 path=ROOT/'work/build-vp-msvc.py';spec=importlib.util.spec_from_file_location('vp_build',path);builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
 project=builder.parse_project('Release')
 # Match the tested PS release route before varying only the two WPO flags.
 candidate_compile=['/Z7' if f=='/Zi' else f for f in project['compile_flags'] if not f.lower().startswith('/zm')]+['/Zm400']
 candidate_link=project['link_flags']
 baseline_compile=[f for f in candidate_compile if f!='/GL'];baseline_link=[f for f in candidate_link if f!='/LTCG']
 assert candidate_compile.count('/GL')==1 and candidate_link.count('/LTCG')==1,'Project no longer selects release WPO'
 assert '/fp:precise' in candidate_compile and '/Z7' in candidate_compile and '/MD' in candidate_compile and '/INCREMENTAL:NO' in candidate_link and '/DEBUG' in candidate_link
 common=[sys.executable,'-B','-u',str(path),'--config','release','--jobs',str(args.jobs),'--embedded-compiler-debug','--pch-memory','400']
 result=dict(schema=1,kind='proposal-only-no-build',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  project_sha256=sha(project['project']),wrapper_sha256=sha(path),ps_entry_sha256=sha(ROOT/'work/build-vp.ps1'),
  baseline=dict(compile_flags=baseline_compile,link_flags=baseline_link,check_command=common+['--no-ltcg','--check'],build_command=common+['--no-ltcg']),
  candidate=dict(compile_flags=candidate_compile,link_flags=candidate_link,check_command=common+['--check'],build_command=common),
  exact_flag_delta=dict(compile=['/GL'],link=['/LTCG']),translation_units=len(project['sources']),
  ordered_libraries=[str(p) for p in project['libraries']],pch_header=project['pch_header'],
  production_or_toolchain_modified=False,build_or_game_executed=False,
  caveats=['Only /GL and /LTCG differ; PS release entry remains unchanged.',
   'PCH and every source must be freshly compiled under the same candidate flags; retain PCH/object files until link.',
   'No project/library/compiler rewrite, no /fp:fast, no arch or calling-convention change.',
   'Historical LTCG attempt used /Zi and stalled at link; /Z7 wait avoidance is an unconfirmed hypothesis.',
   'Final /DEBUG PDB must match the candidate DLL; optimized frames may differ even with matching symbols.',
   'Native behavior/FP/random-state equality and performance require a fixed-save matched comparison.',
   'Fresh run directories isolate outputs; latest-msvc-build-path changes only on successful full build.',
   'Peak link memory and elapsed time are unknown; monitor exact child link PID and use a bounded run.'])
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print('Prepared flags-only LTCG proposal: '+str(out))
if __name__=='__main__':main()
