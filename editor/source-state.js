'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const {contained}=require('./core');
async function captureSourceState(root,build){
 root=await fs.realpath(root);build=await fs.realpath(build);const hash=crypto.createHash('sha256');let total=0,count=0;
 async function add(file,label){const stat=await fs.stat(file);if(!stat.isFile()||stat.size>16*1024*1024||++count>20000||(total+=stat.size)>128*1024*1024)throw new Error('Source freshness scan exceeded its limit.');const content=await fs.readFile(file),after=await fs.stat(file);if(stat.size!==after.size||stat.mtimeMs!==after.mtimeMs||stat.ctimeMs!==after.ctimeMs)throw new Error('Source changed while checking freshness.');hash.update(JSON.stringify([label,stat.size,stat.mtimeMs,stat.ctimeMs,crypto.createHash('sha256').update(content).digest('hex')]));}
 await add(path.join(root,'mod.json'),'metadata');await add(path.join(build,'compile_commands.json'),'compiler_settings');
 async function visit(dir){
   const entries=(await fs.readdir(dir,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name));
   for(const entry of entries){const file=path.join(dir,entry.name);if(['.git','.deps','.cache','build'].includes(entry.name)||file===build)continue;
     if(entry.isSymbolicLink()){const resolved=await fs.realpath(file);if(!contained(root,resolved))throw new Error('Source symlink points outside the selected root.');throw new Error('Source symlink requires explicit review before analysis.');}
     if(entry.isDirectory())await visit(file);
     else if(entry.isFile()&&/\.(cpp|cc|cxx|h|hpp|hh|hxx)$/.test(entry.name))await add(file,path.relative(root,file));
   }
 }
 await visit(root);return hash.digest('hex');
}
module.exports={captureSourceState};
