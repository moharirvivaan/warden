const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const core=require('../core');

const report=()=>({schema_version:2,status:'complete',project_root:'/mod',mod:{id:'example.mod'},toolchain:{sdk:'5.11.1',target:'arm64'},coverage:'limited',files:[],hooks:[],helpers:[],unknown:[],findings:[]});
test('rejects malformed reports instead of showing an empty successful scan',()=>{
  assert.throws(()=>core.parseReport('{}',0),/report/i);
  const partial=report();partial.status='partial';
  assert.throws(()=>core.parseReport(JSON.stringify(partial),0),/exit|status/i);
  const valid=core.parseReport(JSON.stringify(partial),1);assert.equal(valid.status,'partial');
  const invalid=report();invalid.findings=[{rule:'x',location:{file:'x.cpp',line:0,column:1}}];
  assert.throws(()=>core.parseReport(JSON.stringify(invalid),0),/report|location/i);
});
test('navigation rejects traversal, symlink escape and invalid positions',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'warden-path-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const outside=await fs.mkdtemp(path.join(os.tmpdir(),'warden-outside-'));t.after(()=>fs.rm(outside,{recursive:true,force:true}));
  await fs.writeFile(path.join(outside,'out.cpp'),'outside source\n');
  await fs.writeFile(path.join(root,'main.cpp'),'one\ntwo\n');
  await fs.symlink(outside,path.join(root,'escape'),process.platform==='win32'?'junction':'dir');
  const good=await core.resolveSource(root,{file:'main.cpp',line:2,column:1});assert.equal(good.file,await fs.realpath(path.join(root,'main.cpp')));
  await assert.rejects(core.resolveSource(root,{file:'escape/out.cpp',line:1,column:1}),/symlink escapes/);
  for(const location of [{file:'../else.cpp',line:1,column:1},{file:'main.cpp',line:0,column:1},{file:'main.cpp',line:20,column:1},{file:'main.cpp',line:1,column:99}])
    await assert.rejects(core.resolveSource(root,location));
});
test('repair rejects stale files and converts byte offsets after unicode correctly',()=>{
  const text='// 🟦\nold\n', bytes=Buffer.from(text), start=bytes.indexOf('old');
  const repair={file:'main.cpp',sha256:crypto.createHash('sha256').update(bytes).digest('hex'),start_byte:start,end_byte:start+3,expected:'old',replacement:'new'};
  const patch=core.prepareRepair(text,repair);assert.equal(patch.text,'// 🟦\nnew\n');assert.equal(patch.start,6);
  assert.throws(()=>core.prepareRepair(text+'changed',repair),/changed|stale/i);
  assert.throws(()=>core.prepareRepair(text,{...repair,expected:'wrong'}),/match/i);
  assert.throws(()=>core.prepareRepair(text,{...repair,start_byte:4}),/UTF|boundary/i);
});
test('process transport preserves partial reports and captures process errors',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'warden-process-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const script=path.join(root,'analyzer.js');const r=report();r.status='partial';
  await fs.writeFile(script,`process.stdout.write(${JSON.stringify(JSON.stringify(r))});process.stderr.write('compiler detail');process.exitCode=1;`);
  const result=await core.spawnReport(process.execPath,[script],{timeoutMs:1000});assert.equal(result.report.status,'partial');assert.equal(result.stderr,'compiler detail');
  await assert.rejects(core.spawnReport(path.join(root,'missing'),[],{}),/ENOENT/);
  await fs.writeFile(script,"process.stdout.write('not json');");
  await assert.rejects(core.spawnReport(process.execPath,[script],{}),/JSON|report/i);
});
test('cancellation and timeout stop a running analyzer',async t=>{
  const controller=new AbortController();
  const running=core.spawnReport(process.execPath,['-e','setInterval(()=>{},1000)'],{signal:controller.signal,timeoutMs:10000});
  setTimeout(()=>controller.abort(),30);await assert.rejects(running,/cancel/i);
  await assert.rejects(core.spawnReport(process.execPath,['-e','setInterval(()=>{},1000)'],{timeoutMs:30}),/timed out/i);
});
test('oversized analyzer output is rejected before becoming a report',async()=>{
  await assert.rejects(core.spawnReport(process.execPath,['-e',"process.stdout.write('x'.repeat(4096));"],{maxBytes:128}),/size limit/);
});
test('an already cancelled request never attempts to launch the analyzer',async()=>{
  const controller=new AbortController();controller.abort();
  await assert.rejects(core.spawnReport('/missing-analyzer',[],{signal:controller.signal}),/cancel/i);
});
