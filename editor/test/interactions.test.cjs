const {test}=require('node:test');const assert=require('node:assert/strict');
const {compareReports}=require('../interactions');
function report(id){return {status:'complete',project_root:'/'+id,mod:{id,version:'v1.0.0',gd:{mac:'2.2081'}},toolchain:{sdk:'5.10.1',target:'arm64-apple-macos'},hooks:[{target_class:'LevelInfoLayer',method:'init',signature:'bool (GJGameLevel *, bool)',location:{file:'main.cpp',line:4,column:1},behavior:{scope:'source_facts_only',forwarding_calls:[{context:'condition',location:{file:'main.cpp',line:5,column:2}}],priority_requests:[],unknown:[]}}]};}
test('shared hooks are informational relationships with source-specific next actions',()=>{
 const a=report('a'),b=report('b'),r=compareReports(a,b);assert.equal(r.relationships.length,1);assert.equal(r.status,'ready');assert.equal(r.relationships[0].observations[0].evidence,'observed');assert.ok(r.relationships[0].observations[0].sources.length);assert.ok(!JSON.stringify(r).includes('conflict detected'));assert.match(r.relationships[0].observations[0].suggestion,/LevelInfoLayer/);
 b.hooks[0].signature='bool ()';assert.equal(compareReports(a,b).relationships.length,0);
});
test('missing behavior and mismatched configurations never create an order',()=>{
 const a=report('a'),b=report('b');delete b.hooks[0].behavior;b.toolchain.sdk='5.11.1';const r=compareReports(a,b);assert.equal(r.status,'blocked');assert.ok(r.reasons.length);assert.ok(r.relationships[0].observations.some(o=>o.evidence==='unknown'));
});
test('required peers cannot be disabled for the proposed test',()=>{
 const a=report('a'),b=report('b');a.mod.dependencies={b:'v1.0.0'};assert.match(JSON.stringify(compareReports(a,b)),/required dependency/i);
});
test('multiple modifications are retained and absent direct calls are not bugs',()=>{
 const a=report('a'),b=report('b');a.hooks.push({...a.hooks[0],location:{file:'other.cpp',line:1,column:1}});b.hooks[0].behavior.forwarding_calls=[];const r=compareReports(a,b);assert.equal(r.relationships[0].primary_hooks.length,2);assert.ok(r.relationships[0].observations.some(o=>o.evidence==='unknown'));assert.ok(!JSON.stringify(r).includes('forgot'));
});
module.exports={report};
