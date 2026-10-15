const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {captureSourceState}=require('../source-state');
test('saved edits additions deletions and compiler settings change the source identity',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'warden-state-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));const build=path.join(root,'build');await fs.mkdir(build);await fs.writeFile(path.join(root,'mod.json'),'{}');await fs.writeFile(path.join(build,'compile_commands.json'),'[]');await fs.writeFile(path.join(root,'main.cpp'),'one');
 const a=await captureSourceState(root,build);await fs.writeFile(path.join(root,'main.cpp'),'two');const b=await captureSourceState(root,build);assert.notEqual(a,b);await fs.writeFile(path.join(root,'shared.hpp'),'header');const c=await captureSourceState(root,build);assert.notEqual(b,c);await fs.unlink(path.join(root,'shared.hpp'));assert.equal(await captureSourceState(root,build),b);await fs.writeFile(path.join(build,'compile_commands.json'),'[{}]');assert.notEqual(await captureSourceState(root,build),b);
});
test('outside-root source symlinks are rejected before file reads',async t=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'warden-state-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));await fs.mkdir(path.join(root,'build'));await fs.writeFile(path.join(root,'mod.json'),'{}');await fs.writeFile(path.join(root,'build/compile_commands.json'),'[]');await fs.symlink('/etc/hosts',path.join(root,'escape.cpp'));await assert.rejects(captureSourceState(root,path.join(root,'build')),/symlink|outside/);
});
