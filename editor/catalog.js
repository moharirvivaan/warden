'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const {parseReport,contained}=require('./core');
const {compareReports,dependency}=require('./interactions');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const relative=x=>typeof x==='string'&&x.length>0&&x.length<=1024&&!/[\x00-\x1f\x7f\\%?#:]/.test(x)&&!x.split('/').some(c=>!c||c==='.'||c==='..');
const repository=x=>typeof x==='string'&&/^https:\/\/github\.com\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+$/.test(x)&&!x.endsWith('/.')&&!x.endsWith('/..');
const hex=(x,n)=>typeof x==='string'&&new RegExp(`^[a-f0-9]{${n}}$`).test(x);
async function boundedFile(root,file,max){
 if(!relative(file))throw new Error('Invalid catalog file path.');
 const resolved=await fs.realpath(path.join(root,file));if(!contained(root,resolved))throw new Error('Catalog symlink escapes its root.');
 const handle=await fs.open(resolved,'r');
 try{const stat=await handle.stat();if(!stat.isFile()||stat.size>max)throw new Error('Catalog size limit exceeded.');const bytes=Buffer.alloc(Math.min(stat.size+1,max+1));const {bytesRead}=await handle.read(bytes,0,bytes.length,0);if(bytesRead>max||bytesRead!==stat.size)throw new Error('Catalog changed while loading.');return bytes.subarray(0,bytesRead);}finally{await handle.close();}
}
function validateEntry(e){
 if(!object(e)||typeof e.id!=='string'||!/^[a-zA-Z0-9_.-]{1,128}$/.test(e.id)||!relative(e.report_file)||!hex(e.report_sha256,64)||!repository(e.repository)||!hex(e.revision,40)||!hex(e.analyzer_revision,40)||typeof e.analyzer_dirty!=='boolean'||!hex(e.build_id,64)||!hex(e.sdk_revision,40)||!hex(e.bindings_revision,40)||!Array.isArray(e.source_files)||e.source_files.length>10000||!e.source_files.length||!Array.isArray(e.scope)||!e.scope.length||e.scope.length>10000||e.scope.some(x=>!relative(x))||!Array.isArray(e.adaptations)||e.adaptations.length>100||e.adaptations.some(x=>typeof x!=='string'||x.length>2000)||e.runtime_status!=='not_run'||!['unreviewed','redistributable_with_notice','restricted'].includes(e.license_status))throw new Error('Invalid catalog provenance.');
 const paths=new Set();for(const f of e.source_files){if(!object(f)||!relative(f.file)||!hex(f.sha256,64)||paths.has(f.file))throw new Error('Invalid catalog source map.');paths.add(f.file);}
 if(e.scope.some(f=>!paths.has(f)))throw new Error('Catalog scope has no source mapping.');
}
function validateProjection(report,entry){
 if(!report.mod.id||typeof report.mod.id!=='string'||typeof report.mod.version!=='string'||report.project_root!==''||report.compilation_database||report.toolchain.sdk_root||report.findings.length)throw new Error('Catalog report contains invalid identity or local data.');
 const paths=new Set(entry.source_files.map(f=>f.file));
 const loc=l=>{if(!l.file&&(!l.line||!l.column))return;if(!relative(l.file)||!paths.has(l.file)||!Number.isSafeInteger(l.line)||l.line<1||!Number.isSafeInteger(l.column)||l.column<1)throw new Error('Catalog location is outside its source map.');};
 for(const f of report.files){if(!relative(f.file)||!paths.has(f.file)||f.arguments?.length||f.directory)throw new Error('Catalog file contains local data.');for(const d of f.diagnostics)loc(d.location);}
 for(const h of [...report.hooks,...report.helpers]){loc(h.location);if(h.behavior){for(const c of h.behavior.forwarding_calls)loc(c.location);for(const p of h.behavior.priority_requests)loc(p.location);for(const u of h.behavior.unknown)loc(u.location);}}
 for(const u of report.unknown)loc(u.location);
}
async function loadCatalog(directory){
 const root=await fs.realpath(directory),raw=await boundedFile(root,'manifest.json',1024*1024),manifest=JSON.parse(raw);
 if(!object(manifest)||manifest.schema_version!==1||typeof manifest.created_at!=='string'||!Number.isFinite(Date.parse(manifest.created_at))||!Array.isArray(manifest.entries)||manifest.entries.length>100)throw new Error('Invalid catalog manifest.');
 const entries=[],rejected=[];let total=0;
 for(const [index,entry] of manifest.entries.entries()){
   try{validateEntry(entry);const bytes=await boundedFile(root,entry.report_file,8*1024*1024);total+=bytes.length;if(total>32*1024*1024)throw new Error('Catalog aggregate size limit exceeded.');if(hash(bytes)!==entry.report_sha256)throw new Error('Catalog report hash mismatch.');const parsed=JSON.parse(bytes);const code={complete:0,partial:1,setup_error:2}[parsed?.status];const report=parseReport(bytes.toString('utf8'),code);validateProjection(report,entry);entries.push({...entry,report});}
   catch(error){rejected.push({entryId:typeof entry?.id==='string'?entry.id:`entry-${index}`,reason:error.message});}
 }
 // Conflicting duplicate identities invalidate all candidates, not whichever loads second.
 const counts=new Map(),identities=new Map();for(const e of entries){counts.set(e.id,(counts.get(e.id)||0)+1);const k=JSON.stringify([e.report.mod.id,e.report.mod.version,e.revision]);identities.set(k,(identities.get(k)||0)+1);}
 const valid=entries.filter(e=>{const duplicate=counts.get(e.id)>1||identities.get(JSON.stringify([e.report.mod.id,e.report.mod.version,e.revision]))>1;if(duplicate)rejected.push({entryId:e.id,reason:'Duplicate or conflicting catalog identity.'});return !duplicate;});
 return {id:hash(raw),createdAt:manifest.created_at,root,entries:valid,rejected};
}
function exactVersion(constraint,version){
 if(typeof constraint!=='string'||typeof version!=='string')return 'unknown';
 const literal=constraint.startsWith('=')?constraint.slice(1):constraint;
 const exact=x=>/^v?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$/.test(x);
 if(!exact(literal)||!exact(version))return 'unknown';
 if(literal.replace(/^v/,'')===version.replace(/^v/,''))return 'match';
 // The SDK interprets a bare version as >=. Do not mislabel it as exact.
 return constraint.startsWith('=')?'mismatch':'unknown';
}
function metadataRelationships(primary,peer){
 const result=[];
 for(const [owner,other,side] of [[primary,peer,'primary'],[peer,primary,'peer']]){
   const dep=dependency(owner.mod,other.mod.id);if(dep)result.push({side,kind:dep.kind,constraint:dep.constraint,versionStatus:exactVersion(dep.constraint,other.mod.version),message:`${owner.mod.id} declares ${other.mod.id} as ${dep.kind}; constraint ${dep.constraint}, catalog/source version ${other.mod.version||'unknown'}.`});
   const value=owner.mod.incompatibilities?.[other.mod.id];if(value!==undefined){const constraint=typeof value==='string'?value:value?.version;result.push({side,kind:'declared_incompatibility',constraint:constraint||'unknown',versionStatus:exactVersion(constraint,other.mod.version),message:`${owner.mod.id} declares an incompatibility with ${other.mod.id}; this is mod metadata, not a newly detected defect.`});}
 }
 return result;
}
function discoverInteractions(primary,snapshot){
 const candidates=[],checked=[],unavailable=[...snapshot.rejected],excluded=[];
 for(const entry of snapshot.entries){
   const peer=entry.report;
   if(peer.mod.id===primary.mod.id){excluded.push({entryId:entry.id,reason:'Primary mod identity; not compared to itself.'});continue;}
   if(peer.status==='setup_error'){unavailable.push({entryId:entry.id,reason:'Catalog analysis setup failed.'});continue;}
   const comparison=compareReports(primary,peer),metadata=metadataRelationships(primary,peer);
   if(metadata.some(m=>m.versionStatus!=='match')){comparison.reasons.push('Declared version constraint is mismatched or unresolved; verify the intended versions.');comparison.status='blocked';}
   checked.push({entryId:entry.id,mod:peer.mod,scope:entry.scope,status:comparison.status});
   if(comparison.status!=='ready')unavailable.push({entryId:entry.id,reason:comparison.reasons.join(' ')});
   const evidence=comparison.relationships.some(r=>[...r.primary_hooks.map(i=>primary.hooks[i]),...r.peer_hooks.map(i=>peer.hooks[i])].some(h=>h.behavior&&(h.behavior.forwarding_calls.length||h.behavior.priority_requests.length)));
   if(metadata.length||comparison.relationships.length)candidates.push({entryId:entry.id,group:metadata.length?'declared_relationship':evidence?'hook_evidence':'shared_target',metadataRelationships:metadata,comparison});
 }
 const order={declared_relationship:0,hook_evidence:1,shared_target:2};candidates.sort((a,b)=>order[a.group]-order[b.group]||a.entryId.localeCompare(b.entryId));
 return {snapshotId:snapshot.id,createdAt:snapshot.createdAt,status:checked.length?'partial':'unavailable',candidates,checked,unavailable,excluded,coverage:'Bounded catalog and selected source units; absence of a result does not establish compatibility.'};
}
function catalogSourceUrl(entry,location){
 validateEntry(entry);
 if(!location||!relative(location.file)||!Number.isSafeInteger(location.line)||location.line<1||!Number.isSafeInteger(location.column)||location.column<1||!entry.source_files.some(f=>f.file===location.file))throw new Error('Invalid catalog source location.');
 return `${entry.repository}/blob/${entry.revision}/${location.file.split('/').map(encodeURIComponent).join('/')}#L${location.line}`;
}
module.exports={loadCatalog,discoverInteractions,catalogSourceUrl};
