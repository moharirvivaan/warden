#!/usr/bin/env python3
"""Local selected-source catalog. Requires existing real SDK/build caches; no download or game change."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'build/interaction-catalog'
INPUTS = [
    ('nodeids', 'nodeids-benchmark', 'geode-sdk/NodeIDs', 'fc9b3aa12a4eee67f0d26e3f115190cba2deddf1', 'src/LevelInfoLayer.cpp'),
    ('betterinfo', 'betterinfo-original-sdk', 'Cvolton/betterinfo-geode', '04365ad20d13bd9618413f134fba6ff9ada074b7', 'src/hooks/LevelInfoLayer.cpp'),
    ('server-api', 'server-api', 'kingminer7/server-api', '924dfc7511cf754fc41530ac9432bce7a67d4223', 'src/hooks/CCHttpClient.cpp'),
]
def digest(raw): return hashlib.sha256(raw).hexdigest()
def git(directory, *args): return subprocess.check_output(['git', '-C', str(directory), *args])
def dump(path, value): path.write_text(json.dumps(value, indent=2) + '\n')
def export_source(donor, revision, destination):
    if git(donor, 'rev-parse', 'HEAD').decode().strip() != revision:
        raise RuntimeError(f'Wrong revision in {donor}; expected {revision}. Existing files preserved.')
    # Copy pinned tracked bytes, never the donor build or unrelated local work.
    files = git(donor, 'ls-tree', '-r', '--name-only', revision).decode().splitlines()
    for name in files:
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts: raise RuntimeError('Invalid tracked path')
        raw = git(donor, 'show', f'{revision}:{name}')
        original = donor / relative
        if name != 'CMakeLists.txt' and (not original.is_file() or original.read_bytes() != raw):
            raise RuntimeError(f'Modified source input: {original}; preserved')
        target = destination / relative
        if target.exists() and target.read_bytes() != raw:
            raise RuntimeError(f'Existing catalog input differs: {target}; preserved')
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists(): target.write_bytes(raw)
    return files

def prepare():
    lock=json.loads((ROOT/'docs/toolchain-lock.json').read_text())
    sdk=ROOT/'.deps/geode-5.10.1'
    for directory,revision in [(sdk,lock['additional_sdks']['5.10.1']['revision']), (ROOT/'.deps/bindings',lock['bindings']['revision'])]:
        if git(directory,'rev-parse','HEAD').decode().strip()!=revision or git(directory,'status','--porcelain').strip():
            raise RuntimeError(f'Pinned SDK/bindings input changed: {directory}')
    db=ROOT/'.deps/betterinfo-original-sdk/build/pch-510/inspect/compile_commands.json'
    entries=json.loads(db.read_text())
    template=next(e for e in entries if e['file'].endswith('/src/hooks/LevelInfoLayer.cpp'))
    template_args=template.get('arguments') or shlex.split(template['command'])
    # Expand the genuine CMake PCH's three SDK umbrella includes as textual includes.
    # A PCH from another mod contains that mod's definitions and cannot be reused.
    # This explicit selected-unit adaptation does not reproduce historical builds.
    args=[];i=0
    while i<len(template_args):
        value=template_args[i]
        if value=='-Xclang' and i+1<len(template_args) and template_args[i+1] in ('-include-pch','-include'):
            i+=4;continue
        if value=='-o':i+=2;continue
        if value in ('-c','-Winvalid-pch') or value==template['file'] or value.startswith(('-DBI_EXPORTING','-DBetterInfo_EXPORTS','-DGEODE_MOD_ID=', '-DPROJECT_NAME=')):
            i+=1;continue
        args.append(value);i+=1
    for header in ['DefaultInclude.hpp','Geode.hpp','Bindings.hpp']:
        args+=['-include',str(sdk/'loader/include/Geode'/header)]
    analyzer=ROOT/'build/warden'
    build_identity={'binary_sha256':digest(analyzer.read_bytes()),'source_diff_sha256':digest(git(ROOT,'diff','HEAD','--','src','CMakeLists.txt')),'template_database_sha256':digest(db.read_bytes())}
    build_id=digest(json.dumps(build_identity,sort_keys=True).encode())
    DEST.mkdir(parents=True,exist_ok=True)
    catalog=[];local=[]
    expected=[{'primary':'cvolton.betterinfo','peer':'geode.node-ids','reason':'Required dependency in pinned mod.json; both selected LevelInfoLayer::init implementations visible in source.'}, {'primary':'cvolton.betterinfo','peer':'km7dev.server_api','reason':'Optional dependency in pinned BetterInfo mod.json; selected CCHttpClient hook is a different family, not a globally harmless mod.'}]
    for name,cache,repo,rev,unit in INPUTS:
        project=ROOT/'.deps/interaction-catalog'/name
        files=export_source(ROOT/'.deps'/cache,rev,project)
        metadata=json.loads((project/'mod.json').read_text())
        build=project/'build';build.mkdir(exist_ok=True)
        command=[*args,f'-DGEODE_MOD_ID="{metadata["id"]}"','-c',str(project/unit)]
        if name=='server-api':command.append('-DKM7DEV_SERVER_API_EXPORTING')
        dump(build/'compile_commands.json',[{'directory':template['directory'],'file':str(project/unit),'arguments':command}])
        run=subprocess.run([str(analyzer),'inspect',str(project),'-p',str(build),'--format','json'],capture_output=True,text=True,timeout=180)
        report=json.loads(run.stdout)
        (DEST/f'{name}.stderr.txt').write_text(run.stderr)
        if run.returncode not in (0,1) or any(d['severity'] in ('error','fatal') for f in report['files'] for d in f['diagnostics']):
            dump(DEST/f'{name}.failed.json',report)
            raise RuntimeError(f'{name}: real selected source failed; see {DEST}/{name}.failed.json')
        if report['toolchain']['sdk']!='5.10.1' or not report['hooks']:raise RuntimeError(f'{name}: required real hook evidence unavailable')
        dump(DEST/f'{name}.local.json',report)
        mapping=[{'file':f,'sha256':digest((project/f).read_bytes())} for f in files if Path(f).suffix in ('.cpp','.cc','.cxx','.h','.hpp','.hh','.hxx') or f=='mod.json']
        paths={f['file'] for f in mapping}
        def loc(value):
            if value.get('file') not in paths or not value.get('line') or not value.get('column'):return {'file':'','line':0,'column':0}
            return value
        projected={'schema_version':2,'status':report['status'],'project_root':'','coverage':'Selected source units; other project files remain unexamined.', 'mod':{k:v for k,v in report['mod'].items() if k in ('id','name','version','geode','gd','dependencies','incompatibilities')},'toolchain':{k:v for k,v in report['toolchain'].items() if k!='sdk_root'},'hooks':report['hooks'],'helpers':report['helpers'],'findings':[],'unknown':[{'reason':u['reason'].replace(str(project),'<mod>').replace(str(ROOT),'<workspace>'),'location':loc(u['location'])} for u in report['unknown']], 'files':[{'file':f['file'],'status':f['status'],'kind':f['kind'],'diagnostics':[{'severity':d['severity'],'message':'Compiler diagnostic; consult local report for full context.','location':loc(d['location'])} for d in f['diagnostics']]} for f in report['files'] if f['file'] in paths]}
        raw=(json.dumps(projected,indent=2)+'\n').encode();(DEST/f'{name}.json').write_bytes(raw)
        entry={'id':name,'report_file':f'{name}.json','report_sha256':digest(raw),'repository':'https://github.com/'+repo,'revision':rev,'analyzer_revision':git(ROOT,'rev-parse','HEAD').decode().strip(),'analyzer_dirty':True,'build_id':build_id,'sdk_revision':lock['additional_sdks']['5.10.1']['revision'],'bindings_revision':lock['bindings']['revision'],'source_files':mapping,'scope':[unit],'adaptations':['Selected-unit compiler database adapted from genuine BetterInfo SDK 5.10.1 CMake settings.','PCH expanded to its real SDK umbrella headers; original C++ preserved.','Declared SDK '+metadata['geode']+'; analyzed SDK 5.10.1; historical/full-project build unverified.'],'runtime_status':'not_run','license_status':'unreviewed'}
        catalog.append(entry);local.append({'id':name,'project':str(project),'build':str(build),'command':command,'selected_source_sha256':digest((project/unit).read_bytes())})
        print(f'{name}: {len(report["hooks"])} actual registered hooks; SDK 5.10.1; selected source only',flush=True)
    dump(DEST/'manifest.json',{'schema_version':1,'created_at':datetime.now(timezone.utc).isoformat(),'entries':catalog})
    dump(DEST/'evaluation.json',{'runtime_status':'not_run','build_identity':build_identity,'build_id':build_id,'expected_relationships':expected,'local_inputs':local})
    print('Prepared local catalog. No runtime compatibility or historical reproduction established.')
if __name__=='__main__':
    try:prepare()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,StopIteration) as error:
        sys.exit(f'Catalog setup failed: {error}')
