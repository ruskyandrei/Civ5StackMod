#!/usr/bin/env python3
"""Build unchanged VP using the genuine portable MSVC 2008 SP1 x86 toolchain.

The checked-in VoxPopuli.vcxproj supplies sources, defines, include/library paths,
resource and module-definition files. Original Firaxis .lib files are linked by
Microsoft LINK 9; no clang compatibility objects or /FORCE:MULTIPLE are used.
This wrapper never rewrites commit_id.inc: root must generate it before the build.
All compiler output and logs stay below work/. --check is read-only.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
NS = {'m': 'http://schemas.microsoft.com/developer/msbuild/2003'}
MSVC_ROOT = WORK / 'toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
SDK_TOOLS = WORK / 'toolchain/sdk/admin/win32tools/Program Files/Microsoft SDKs/Windows/v7.0/Bin'
SDK_INCLUDE = WORK / 'toolchain/sdk/windows/Include'
SDK_LIB = WORK / 'toolchain/sdk/windows/Lib'
VC_INCLUDE = WORK / 'toolchain/sdk/vc9/include'
VC_LIB = WORK / 'toolchain/sdk/vc9/lib'
DEFAULT_LIBS = ['kernel32.lib','user32.lib','gdi32.lib','winspool.lib','comdlg32.lib',
                'advapi32.lib','shell32.lib','ole32.lib','oleaut32.lib','uuid.lib',
                'odbc32.lib','odbccp32.lib']


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):
            h.update(part)
    return h.hexdigest().upper()


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_project(config):
    project_dir = ROOT / 'CvGameCoreDLL_Expansion2'
    project = project_dir / 'VoxPopuli.vcxproj'
    tree = ET.parse(project)
    selected = [node for node in tree.findall('m:ItemDefinitionGroup',NS)
                if node.get('Condition') == f"'$(Configuration)|$(Platform)'=='{config}|Win32'"]
    if len(selected)!=1:
        raise RuntimeError(f'Expected one {config}|Win32 definition group')
    compile_props = selected[0].find('m:ClCompile',NS)
    link_props = selected[0].find('m:Link',NS)
    def value(parent,key,default=''):
        return parent.findtext('m:'+key,default,namespaces=NS)
    def expand(text):
        return text.replace('$(SolutionDir)',str(ROOT)+'\\').replace('$(ProjectDir)',str(project_dir)+'\\')
    def entries(parent,key):
        return [expand(item) for item in value(parent,key).split(';') if item and not item.startswith('%(')]
    sources = [project_dir/node.get('Include') for node in tree.findall('.//m:ClCompile',NS) if node.get('Include')]
    if len({p.stem.lower() for p in sources})!=len(sources):
        raise RuntimeError('Duplicate source basenames require explicit object naming')
    if value(compile_props,'RuntimeLibrary')!='MultiThreadedDLL':
        raise RuntimeError('Re-review CRT flags: project runtime setting changed')
    if value(compile_props,'DebugInformationFormat')!='ProgramDatabase':
        raise RuntimeError('Re-review debug format: expected ProgramDatabase')
    resources = [project_dir/node.get('Include') for node in tree.findall('.//m:ResourceCompile',NS) if node.get('Include')]
    defs = entries(compile_props,'PreprocessorDefinitions')
    if '_WINDLL' not in defs:
        defs.append('_WINDLL')
    # Explicitly spell out VC++ defaults from the DynamicLibrary Win32 project.
    flags = ['/nologo','/c','/MD','/W3','/Zi','/Gm-','/GS','/EHsc','/Gd','/fp:precise','/Zc:wchar_t','/Zc:forScope']
    optimization = value(compile_props,'Optimization')
    if optimization=='Full': flags.append('/Ox')
    elif optimization=='Disabled': flags.append('/Od')
    else: raise RuntimeError(f'Unsupported optimization mode: {optimization}')
    if value(compile_props,'WholeProgramOptimization')=='true': flags.append('/GL')
    flags += [a for a in value(compile_props,'AdditionalOptions').split() if not a.startswith('%(')]
    flags += ['/D'+d for d in defs]
    includes = [Path(p) for p in entries(compile_props,'AdditionalIncludeDirectories')]
    flags += ['/I'+str(p) for p in includes]
    library_dirs = [Path(p) for p in entries(link_props,'AdditionalLibraryDirectories')]+[VC_LIB,SDK_LIB]
    dependencies = entries(link_props,'AdditionalDependencies')+DEFAULT_LIBS
    libraries = []
    for dep in dependencies:
        matches=[p/dep for p in library_dirs if (p/dep).is_file()]
        if not matches: raise FileNotFoundError('Cannot locate project library '+dep)
        libraries.append(matches[0])
    link_flags=['/NOLOGO','/DLL','/MACHINE:X86','/DEBUG','/SUBSYSTEM:WINDOWS','/DYNAMICBASE','/NXCOMPAT','/MANIFEST','/INCREMENTAL:NO']
    if value(link_props,'EnableCOMDATFolding')=='true': link_flags.append('/OPT:ICF')
    if value(link_props,'OptimizeReferences')=='true': link_flags.append('/OPT:REF')
    if value(link_props,'LinkTimeCodeGeneration')=='UseLinkTimeCodeGeneration': link_flags.append('/LTCG')
    module_def = Path(expand(value(link_props,'ModuleDefinitionFile')))
    link_flags.append('/DEF:'+str(module_def))
    return {'project':project,'project_dir':project_dir,'sources':sources,'resources':resources,
            'compile_flags':flags,'link_flags':link_flags,'libraries':libraries,
            'library_dirs':library_dirs,'include_dirs':includes,'module_def':module_def,
            'pch_header':value(compile_props,'PrecompiledHeaderFile')}


def tools_and_environment():
    tools={'cl':MSVC_ROOT/'Vc7/bin/cl.exe','link':MSVC_ROOT/'Vc7/bin/link.exe',
           'rc':SDK_TOOLS/'rc.exe','mt':SDK_TOOLS/'mt.exe'}
    requirements=list(tools.values())+[
        MSVC_ROOT/'Vc7/bin/c1xx.dll',MSVC_ROOT/'Vc7/bin/c2.dll',
        MSVC_ROOT/'Common7/IDE/mspdb80.dll',MSVC_ROOT/'Common7/IDE/mspdbsrv.exe',
        SDK_TOOLS/'rcdll.dll',VC_INCLUDE/'stdio.h',VC_LIB/'msvcrt.lib',SDK_INCLUDE/'windows.h',SDK_LIB/'kernel32.lib']
    for p in requirements:
        if not p.is_file(): raise FileNotFoundError(p)
    env=os.environ.copy()
    env['PATH']=';'.join([str(MSVC_ROOT/'Vc7/bin'),str(MSVC_ROOT/'Common7/IDE'),str(SDK_TOOLS),env.get('PATH','')])
    env['INCLUDE']=';'.join(map(str,[VC_INCLUDE,SDK_INCLUDE]))
    env['LIB']=';'.join(map(str,[VC_LIB,SDK_LIB]))
    # Avoid inherited global compiler flags changing the target or runtime.
    env.pop('CL',None)
    env.pop('_CL_',None)
    env.pop('LINK',None)
    return tools,env


def write_response(path,args):
    path.write_text('\n'.join(subprocess.list2cmdline([str(a)]) for a in args)+'\n',encoding='mbcs')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',choices=['release','debug'],default='release')
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--check',action='store_true',help='Read-only prerequisite/source-list check; no compilation')
    parser.add_argument('--no-ltcg',action='store_true',help='Disable project /GL and explicit /LTCG to avoid legacy whole-program linker hangs')
    parser.add_argument('--embedded-compiler-debug',action='store_true',help='Use /Z7 object debug info; final DLL still gets /DEBUG linker PDB')
    parser.add_argument('--pch-memory',type=int,help='Explicit VC9 /Zm factor, useful for optimized non-LTCG builds')
    args=parser.parse_args()
    if os.name!='nt': raise RuntimeError('Windows is required')
    if not 1<=args.jobs<=16: raise ValueError('--jobs must be between 1 and 16')
    config=args.config.title()
    spec=parse_project(config)
    if args.no_ltcg:
        spec['compile_flags']=[f for f in spec['compile_flags'] if f!='/GL']
        spec['link_flags']=[f for f in spec['link_flags'] if f!='/LTCG']
    if args.pch_memory is not None:
        if not 100<=args.pch_memory<=2000: raise ValueError('--pch-memory must be between 100 and 2000')
        spec['compile_flags']=[f for f in spec['compile_flags'] if not f.lower().startswith('/zm')]+['/Zm'+str(args.pch_memory)]
    if args.embedded_compiler_debug:
        spec['compile_flags']=['/Z7' if f=='/Zi' else f for f in spec['compile_flags']]
    tools,env=tools_and_environment()
    version_file=ROOT/'commit_id.inc'
    if not version_file.is_file(): raise RuntimeError('Generate commit_id.inc with upstream update_commit_id.bat before building; this wrapper never writes it.')
    version_text=version_file.read_text(encoding='utf-8-sig').strip()
    all_sources=spec['sources']+spec['resources']+[spec['module_def']]
    for p in all_sources:
        if not p.is_file(): raise FileNotFoundError(p)
    pch_sources=[p for p in spec['sources'] if p.name=='_precompile.cpp']
    if len(pch_sources)!=1: raise RuntimeError('Expected _precompile.cpp PCH source')
    sources=[p for p in spec['sources'] if p not in pch_sources]
    banner=subprocess.run([str(tools['cl'])],env=env,capture_output=True,text=True,errors='replace')
    compiler_banner=banner.stdout+banner.stderr
    if '15.00.30729' not in compiler_banner:
        raise RuntimeError('Compiler is not the expected MSVC 2008 SP1: '+compiler_banner)
    preflight={'config':config,'compiler':compiler_banner.strip(),'translation_units':len(spec['sources']),
               'tools':{k:str(v) for k,v in tools.items()},'version_file':version_text,
               'libraries':[str(p) for p in spec['libraries']],
               'compile_flags':spec['compile_flags'],'link_flags':spec['link_flags'],
               'source_files_will_be_modified':False,'jobs':args.jobs,
               'no_ltcg':args.no_ltcg,'embedded_compiler_debug':args.embedded_compiler_debug}
    if args.check:
        print(json.dumps(preflight,indent=2)); return 0
    run_id=dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    build=WORK/'msvc-build'/config/run_id
    output=WORK/'msvc-output'/config/run_id
    for p in (build,output):
        if p.exists(): raise RuntimeError('Output run directory already exists: '+str(p))
        p.mkdir(parents=True)
    logs=output/'logs'; logs.mkdir()
    objects=build/'obj'; objects.mkdir()
    version_hash=sha256(version_file)
    project_hash=sha256(spec['project'])
    inputs=set(all_sources+[version_file,spec['project']]+spec['libraries'])
    for directory in spec['include_dirs']:
        inputs.update(p for p in directory.rglob('*') if p.is_file() and p.suffix.lower() in {'.h','.hpp','.inl','.inc'})
    input_hashes={str(p.resolve()):sha256(p) for p in sorted(inputs,key=str)}
    (output/'source-inputs.json').write_text(json.dumps(input_hashes,indent=2),encoding='utf-8')
    commands=[]
    started=time.monotonic()
    def run(label,command):
        log=logs/(label+'.log')
        event={'label':label,'command':[str(a) for a in command],'started_utc':timestamp(),'log':str(log)}
        commands.append(event)
        print(f'{label}: {log}',flush=True)
        with log.open('wb') as stream:
            proc=subprocess.run([str(a) for a in command],cwd=spec['project_dir'],env=env,stdout=stream,stderr=subprocess.STDOUT)
        event['returncode']=proc.returncode; event['finished_utc']=timestamp()
        (output/'commands.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
        if proc.returncode:
            print(log.read_text(encoding='mbcs',errors='replace')[-12000:])
            raise RuntimeError(f'{label} failed with {proc.returncode}; see {log}')
    dll=output/'CvGameCore_Expansion2.dll'
    pdb=output/'CvGameCore_Expansion2.pdb'
    pch=build/'CvGameCoreDLLPCH.pch'
    compiler_pdb=build/'vc90.pdb'
    metadata={'status':'building','started_utc':timestamp(),'preflight':preflight,
              'project_sha256':project_hash,'commit_id_sha256':version_hash,
              'wrapper_sha256':sha256(Path(__file__)), 'output':str(output)}
    (output/'build-result.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    try:
        common=spec['compile_flags']+['/Fp'+str(pch),'/Fd'+str(compiler_pdb)]
        pch_rsp=build/'pch.rsp'
        write_response(pch_rsp,common+['/Yc'+spec['pch_header'],'/Fo'+str(objects/'_precompile.obj'),str(pch_sources[0])])
        run('01-pch',[tools['cl'],'@'+str(pch_rsp)])
        cpp_rsp=build/'compile.rsp'
        write_response(cpp_rsp,common+['/Yu'+spec['pch_header'],f'/MP{args.jobs}','/Fo'+str(objects)+'\\']+[str(p) for p in sources])
        run('02-cpp',[tools['cl'],'@'+str(cpp_rsp)])
        resources=[]
        for n,source in enumerate(spec['resources']):
            resource=build/(source.stem+'.res')
            run(f'03-resources-{n}',[tools['rc'],'/nologo','/fo',resource,'/I',spec['project_dir'],'/I',SDK_INCLUDE,'/d','WIN32',source])
            resources.append(resource)
        manifest=build/'CvGameCore_Expansion2.dll.intermediate.manifest'
        object_files=[objects/(p.stem+'.obj') for p in spec['sources']]
        for path in object_files:
            if not path.is_file(): raise FileNotFoundError(path)
        link_rsp=build/'link.rsp'
        link_args=spec['link_flags']+['/OUT:'+str(dll),'/PDB:'+str(pdb),'/IMPLIB:'+str(output/'CvGameCore_Expansion2.lib'),'/MANIFESTFILE:'+str(manifest)]
        link_args+=['/LIBPATH:'+str(p) for p in spec['library_dirs']]
        write_response(link_rsp,link_args+[str(p) for p in object_files+resources+spec['libraries']])
        run('04-link',[tools['link'],'@'+str(link_rsp)])
        if not manifest.is_file(): raise FileNotFoundError(manifest)
        run('05-embed-manifest',[tools['mt'],'/nologo','/manifest',manifest,'/outputresource:'+str(dll)+';2'])
        if sha256(version_file)!=version_hash or sha256(spec['project'])!=project_hash:
            raise RuntimeError('Version or source project changed during build; output cannot be accepted as a fixed baseline')
        changed=[name for name,digest in input_hashes.items() if not Path(name).is_file() or sha256(Path(name))!=digest]
        if changed:
            metadata['changed_inputs']=changed
            raise RuntimeError('Build inputs changed during compilation; rebuild after edits finish: '+', '.join(changed[:8]))
        metadata['source_inputs_manifest']=str(output/'source-inputs.json')
        metadata.update({'status':'success','finished_utc':timestamp(),'elapsed_seconds':time.monotonic()-started,
                         'dll':{'path':str(dll),'sha256':sha256(dll),'bytes':dll.stat().st_size},
                         'pdb':{'path':str(pdb),'sha256':sha256(pdb),'bytes':pdb.stat().st_size}})
        (WORK/'latest-msvc-build-path.txt').write_text(str(output),encoding='utf-8')
        print(json.dumps(metadata,indent=2))
        return 0
    except Exception as exc:
        metadata.update({'status':'failed','finished_utc':timestamp(),'elapsed_seconds':time.monotonic()-started,'error':str(exc)})
        raise
    finally:
        (output/'build-result.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')


if __name__=='__main__':
    raise SystemExit(main())
