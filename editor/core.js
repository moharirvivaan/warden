'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const {TextDecoder}=require('node:util');
const object=x=>x!==null && typeof x==='object' && !Array.isArray(x);
const location=x=>object(x) && typeof x.file==='string' && Number.isSafeInteger(x.line) && x.line>0 && Number.isSafeInteger(x.column) && x.column>0;
const text=(x,...keys)=>object(x) && keys.every(k=>typeof x[k]==='string');
function validateBehavior(b){
  const bounded=a=>Array.isArray(a)&&a.length<=10000;
  const numeric=n=>Number.isInteger(n)&&n>=-2147483648&&n<=2147483647;
  const apis=['setHookPriority','setHookPriorityPre','setHookPriorityPost','setHookPriorityBefore','setHookPriorityAfter','setHookPriorityBeforePre','setHookPriorityAfterPre','setHookPriorityBeforePost','setHookPriorityAfterPost'];
  if(!object(b)||b.scope!=='source_facts_only'||!bounded(b.forwarding_calls)||!bounded(b.priority_requests)||!bounded(b.unknown))throw new Error('Invalid hook behavior in report.');
  for(const c of b.forwarding_calls)if(!object(c)||!location(c.location)||!['body','condition','conditional_branch','loop','nested_callable'].includes(c.context))throw new Error('Invalid hook behavior call.');
  for(const p of b.priority_requests){
    if(!text(p,'hook','api','status','relative_mod')||!location(p.location)||!apis.includes(p.api)||!['observed_constant','observed_relative','unknown'].includes(p.status)||![p.requested_value,p.pre_order_value].every(n=>n===null||numeric(n)))throw new Error('Invalid hook behavior priority.');
    if(p.status==='observed_constant'&&(!numeric(p.requested_value)||!numeric(p.pre_order_value)||!['setHookPriority','setHookPriorityPre','setHookPriorityPost'].includes(p.api)||p.pre_order_value!==(p.api==='setHookPriorityPost'?-p.requested_value:p.requested_value)))throw new Error('Invalid hook behavior numeric semantics.');
    if(p.status==='observed_relative'&&(!p.relative_mod||p.requested_value!==null||p.pre_order_value!==null||['setHookPriority','setHookPriorityPre','setHookPriorityPost'].includes(p.api)))throw new Error('Invalid hook behavior relative request.');
    if(p.status==='unknown'&&p.pre_order_value!==null)throw new Error('Invalid hook behavior unknown ordering.');
  }
  for(const u of b.unknown)if(!text(u,'reason')||!location(u.location))throw new Error('Invalid hook behavior unknown.');
}
function parseReport(stdout,code){
  let r;try{r=JSON.parse(stdout);}catch{throw new Error('Analyzer returned invalid JSON; see Warden Output.');}
  const arrays=['files','hooks','helpers','unknown','findings'];
  if(!object(r)||r.schema_version!==2||!text(r,'status','project_root','coverage')||!object(r.mod)||!text(r.toolchain,'sdk','target')||arrays.some(k=>!Array.isArray(r[k])||r[k].length>100000))
    throw new Error('Unsupported or malformed Warden report.');
  if(!['complete','partial','setup_error'].includes(r.status)||({complete:0,partial:1,setup_error:2})[r.status]!==code)throw new Error('Analyzer status and exit code disagree.');
  for(const method of [...r.hooks,...r.helpers])if(!text(method,'target_class','method','signature')||!location(method.location))throw new Error('Invalid method location in report.');
  for(const method of r.hooks)if(method.behavior!==undefined)validateBehavior(method.behavior);
  // Unknown/setup diagnostics may legitimately have an empty location.
  for(const u of r.unknown)if(!text(u,'reason')||!object(u.location))throw new Error('Invalid unknown record in report.');
  for(const f of r.files)if(!text(f,'file','status')||!Array.isArray(f.diagnostics)||f.diagnostics.some(d=>!text(d,'severity','message')||!object(d.location)))throw new Error('Invalid file record in report.');
  for(const f of r.findings){
    if(!text(f,'rule','severity','evidence','message','suggestion','limitations')||!location(f.location)||!Array.isArray(f.related)||f.related.some(l=>!text(l,'role')||!location(l.location)))throw new Error('Invalid finding location in report.');
    if(f.repair && (!text(f.repair,'file','sha256','expected','replacement')||!/^[a-f0-9]{64}$/.test(f.repair.sha256)||!Number.isSafeInteger(f.repair.start_byte)||!Number.isSafeInteger(f.repair.end_byte)||f.repair.start_byte<0||f.repair.end_byte<f.repair.start_byte))throw new Error('Invalid repair in report.');
  }
  return r;
}
function contained(root,file){const rel=path.relative(root,file);return rel!==''&&!rel.startsWith(`..${path.sep}`)&&rel!=='..'&&!path.isAbsolute(rel);}
async function resolveSource(root,loc){
  if(!location(loc)||loc.file.includes('\0'))throw new Error('Invalid source location.');
  root=await fs.realpath(root);const selected=path.resolve(root,loc.file);
  if(!contained(root,selected))throw new Error('Source is outside the selected mod.');
  const file=await fs.realpath(selected);
  if(!contained(root,file))throw new Error('Source symlink escapes the selected mod.');
  const content=await fs.readFile(file,'utf8'), lines=content.split(/\r?\n/);
  if(loc.line>lines.length)throw new Error('Source line no longer exists; analyze again.');
  const line=lines[loc.line-1], bytes=Buffer.from(line);
  if(loc.column>bytes.length+1)throw new Error('Source column no longer exists; analyze again.');
  let prefix;try{prefix=new TextDecoder('utf8',{fatal:true}).decode(bytes.subarray(0,loc.column-1));}catch{throw new Error('Source column splits a UTF-8 character.');}
  return {file,line:loc.line-1,column:prefix.length};
}
function prepareRepair(content,repair){
  const bytes=Buffer.from(content,'utf8');
  if(crypto.createHash('sha256').update(bytes).digest('hex')!==repair.sha256)throw new Error('Source changed since analysis. Analyze again before reviewing a repair.');
  if(!Number.isSafeInteger(repair.start_byte)||!Number.isSafeInteger(repair.end_byte)||repair.start_byte<0||repair.end_byte<repair.start_byte||repair.end_byte>bytes.length)throw new Error('Invalid repair range.');
  const decoder=new TextDecoder('utf8',{fatal:true});let before,current,after;
  try{before=decoder.decode(bytes.subarray(0,repair.start_byte));current=decoder.decode(bytes.subarray(repair.start_byte,repair.end_byte));after=decoder.decode(bytes.subarray(repair.end_byte));}catch{throw new Error('Repair splits a UTF-8 boundary.');}
  if(current!==repair.expected)throw new Error('Repair source does not match. Analyze again.');
  return {start:before.length,end:before.length+current.length,text:before+repair.replacement+after};
}
function spawnReport(executable,args,{signal,timeoutMs=300000,maxBytes=32*1024*1024}={}){
  return new Promise((resolve,reject)=>{
    if(signal?.aborted){reject(new Error('Analysis cancelled.'));return;}
    const detached=process.platform!=='win32';
    const child=spawn(executable,args,{shell:false,detached,windowsHide:true,stdio:['ignore','pipe','pipe']});
    let stdout=[],stderr=[],outSize=0,errSize=0,failure=null,killTimer;
    const stop=error=>{
      if(failure)return;failure=error;
      const kill=type=>{try{if(detached&&child.pid)process.kill(-child.pid,type);else child.kill(type);}catch{}};
      kill('SIGTERM');killTimer=setTimeout(()=>kill('SIGKILL'),500);killTimer.unref();
    };
    const abort=()=>stop(new Error('Analysis cancelled.'));
    signal?.addEventListener('abort',abort,{once:true});
    const timer=setTimeout(()=>stop(new Error('Analysis timed out. Choose a smaller configuration or increase Warden timeout.')),timeoutMs);timer.unref();
    child.stdout.on('data',data=>{outSize+=data.length;if(outSize>maxBytes)stop(new Error('Analyzer report exceeded the size limit.'));else stdout.push(data);});
    child.stderr.on('data',data=>{errSize+=data.length;if(errSize<=maxBytes)stderr.push(data);});
    child.on('error',error=>{failure=error;});
    child.on('close',(code)=>{
      clearTimeout(timer);clearTimeout(killTimer);signal?.removeEventListener('abort',abort);
      if(failure){reject(failure);return;}
      const raw=Buffer.concat(stdout).toString('utf8'),detail=Buffer.concat(stderr).toString('utf8');
      try{resolve({report:parseReport(raw,code),stderr:detail,stdout:raw,code});}catch(error){error.detail=detail;reject(error);}
    });
  });
}
module.exports={parseReport,resolveSource,prepareRepair,spawnReport,contained};
