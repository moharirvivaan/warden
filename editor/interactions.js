'use strict';
const key=h=>JSON.stringify([h.target_class,h.method,h.signature]);
const game=r=>typeof r.mod.gd==='string'?r.mod.gd:r.mod.gd?.mac;
const concrete=x=>typeof x==='string'&&/^\d+(?:\.\d+)+$/.test(x);
function dependency(mod,id){
 const value=mod.dependencies?.[id];if(value===undefined)return null;
 if(typeof value==='string')return {kind:'required',constraint:value};
 if(value&&typeof value==='object'&&!Array.isArray(value))return {kind:value.required===false||value.importance==='suggested'||value.importance==='recommended'?'optional':'required',constraint:value.version||'unknown'};
 return {kind:'unknown',constraint:'unknown'};
}
function compareReports(primary,peer){
 const reasons=[],relationships=[];
 if(!primary||!peer||primary.status==='setup_error'||peer.status==='setup_error')return {status:'blocked',reasons:['A usable source report is unavailable.'],relationships};
 if(primary.mod.id===peer.mod.id||(primary.project_root&&primary.project_root===peer.project_root))return {status:'blocked',reasons:['Choose distinct mod identities and source roots.'],relationships};
 if(!primary.toolchain.sdk||primary.toolchain.sdk!==peer.toolchain.sdk||!primary.toolchain.target||primary.toolchain.target!==peer.toolchain.target)reasons.push('Analyzed SDK or target differs; combined order/risk conclusions are unavailable.');
 if(!concrete(game(primary))||game(primary)!==game(peer))reasons.push('A matching concrete game version is unavailable.');
 const blocked=reasons.length>0;
 if(primary.status!=='complete'||peer.status!=='complete')reasons.push('Source coverage is partial; unexamined interactions remain unknown.');
 const a=new Map(),b=new Map();
 for(const [report,map] of [[primary,a],[peer,b]])report.hooks.forEach((h,i)=>{const k=key(h);if(!map.has(k))map.set(k,[]);map.get(k).push(i);});
 for(const k of [...a.keys()].sort()) {
   if(!b.has(k))continue;
   const primary_hooks=a.get(k),peer_hooks=b.get(k),h=primary.hooks[primary_hooks[0]],observations=[];
   const target=`${h.target_class}::${h.method}`;
   for(const [side,report,indexes] of [['primary',primary,primary_hooks],['peer',peer,peer_hooks]]) {
     for(const hook of indexes){
       const record=report.hooks[hook],behavior=record.behavior;
       const sources=[{side,hook,kind:'declaration',index:0}];
       if(!behavior){observations.push({evidence:'unknown',message:`${report.mod.id}: behavior evidence is unavailable.`,sources,suggestion:`Reanalyze ${target} with behavior extraction before reasoning about its chain.`});continue;}
       if(!behavior.forwarding_calls.length)observations.push({evidence:'unknown',message:`${report.mod.id}: no supported direct forwarding call observed. Helpers or intentional replacement may explain this.`,sources,suggestion:`Inspect ${target} and its helper calls to establish the intended replacement or continuation behavior.`});
       behavior.forwarding_calls.forEach((call,index)=>observations.push({evidence:'observed',message:`${report.mod.id}: original-call source site in ${call.context.replaceAll('_',' ')}. This does not prove every path forwards.`,sources:[{side,hook,kind:'forwarding',index}],suggestion:`Exercise the ${target} screen/action and the branch around this call with the valid mod combination; inspect work before and after forwarding.`}));
       behavior.priority_requests.forEach((p,index)=>observations.push({evidence:p.status==='unknown'?'unknown':'observed',message:`${report.mod.id}: ${p.api} requests ${p.requested_value??p.relative_mod??'unresolved'}${p.pre_order_value!==null?` (pre-order value ${p.pre_order_value})`:''}. Success and runtime order are unverified.`,sources:[{side,hook,kind:'priority',index}],suggestion:`Review the ${target} priority request and verify behavior with the stated mod versions; do not change priorities solely because the target is shared.`}));
       behavior.unknown.forEach((u,index)=>observations.push({evidence:'unknown',message:`${report.mod.id}: ${u.reason}`,sources:[{side,hook,kind:'unknown',index}],suggestion:`Inspect the unresolved ${target} behavior before drawing a compatibility conclusion.`}));
     }
   }
   const required=dependency(primary.mod,peer.mod.id)?.kind==='required'||dependency(peer.mod,primary.mod.id)?.kind==='required';
   observations.push({evidence:'guidance',message:required?'A required dependency makes at least one standalone scenario unavailable.':'Verify dependency requirements before testing either mod alone.',sources:[{side:'primary',hook:primary_hooks[0],kind:'declaration',index:0},{side:'peer',hook:peer_hooks[0],kind:'declaration',index:0}],suggestion:`Test ${target} with required dependencies enabled. Record the exact versions, action and observed result; Warden has not run this test.`});
   relationships.push({target_class:h.target_class,method:h.method,signature:h.signature,primary_hooks,peer_hooks,observations});
 }
 return {status:blocked?'blocked':reasons.length?'partial':'ready',reasons,relationships};
}
module.exports={compareReports,dependency};
