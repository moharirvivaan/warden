'use strict';
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {test}=require('node:test');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const realCore=require(path.join(root,'editor/core'));
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function host({viewDelay=0}={}){
  const commands=new Map(),messages=[],edits=[],callbacks={},layoutCalls=[];
  let viewProvider,viewResolved=false,viewFocus=0,diffOptions,recv,analyzerExists=true,selected='/A',diffGate,realpathGate,realpathEntered,panelColumn;
  const docs=Object.fromEntries(['/A','/B'].map(p=>[p,{uri:{fsPath:p+'/main.cpp'},version:1,isDirty:false,getText:()=>p==='/A'?'AAA\n':'BBB\n',positionAt:n=>({offset:n}),save:async()=>true}]));
  const uri=s=>({fsPath:s,toString:()=>s});
  const config={get:k=>({projectPath:'/A',buildPath:'/build',analyzerPath:'/warden',timeoutSeconds:600}[k]),update:async()=>{}};
  const vscode={ViewColumn:{Beside:-2,One:1,Two:2},ConfigurationTarget:{Workspace:2},Uri:{file:uri,parse:uri,joinPath:(a,...ps)=>uri(path.join(a.fsPath,...ps))},
    Position:class{constructor(line,col){this.line=line;this.character=col;}},Range:class{constructor(a,b){this.start=a;this.end=b;}},WorkspaceEdit:class{replace(u,r,t){this.edit={uri:u.fsPath,range:r,text:t};}},
    window:{registerWebviewViewProvider:(id,provider)=>{viewProvider=provider;return {dispose(){}};},tabGroups:{all:[{viewColumn:1}]},createOutputChannel:()=>({appendLine(){},show(){},dispose(){}}),createWebviewPanel:(type,title,column)=>(panelColumn=column,{webview:{cspSource:'local',asWebviewUri:x=>x.toString(),postMessage:m=>messages.push(JSON.parse(JSON.stringify(m))),onDidReceiveMessage:f=>recv=f},reveal(){},onDidDispose(){}}),showOpenDialog:async()=>[uri(selected)],showQuickPick:async()=>{},showTextDocument:async()=>{},showWarningMessage:async()=> 'Apply reviewed repair'},
    workspace:{isTrusted:true,textDocuments:[],getConfiguration:()=>config,registerTextDocumentContentProvider:()=>({dispose(){}}),onDidChangeTextDocument:f=>{callbacks.change=f;return {};},onDidSaveTextDocument:f=>{callbacks.save=f;return {};},onDidChangeConfiguration:f=>{callbacks.config=f;return {};},openTextDocument:async u=>docs[path.dirname(u.fsPath)],applyEdit:async e=>{edits.push(e.edit);return true;}},
    commands:{registerCommand:(n,f)=>{commands.set(n,f);return {};},executeCommand:async (n,args,...rest)=>{if(n==='warden.panel.focus'){viewFocus++;if(!viewResolved){viewResolved=true;const resolveView=()=>viewProvider.resolveWebviewView({webview:{cspSource:'local',asWebviewUri:x=>x.toString(),postMessage:m=>messages.push(JSON.parse(JSON.stringify(m))),onDidReceiveMessage:f=>recv=f},show(){},onDidDispose(){}});if(viewDelay)setTimeout(resolveView,viewDelay);else resolveView();}return;}if(n==='vscode.diff')diffOptions=rest[2];if(n==='vscode.getEditorLayout')return {groups:vscode.window.tabGroups.all.filter(g=>!g.agent).map(()=>({}))};if(n==='vscode.setEditorLayout'){layoutCalls.push(args);vscode.window.tabGroups.all=[{viewColumn:1},{viewColumn:2}];}if(n==='vscode.diff' && diffGate){diffGate.entered.resolve();await diffGate.done.promise;}}}};
  const fakefs={realpath:async p=>{if(realpathGate){const gate=realpathGate;realpathGate=null;realpathEntered.resolve();await gate.promise;}return p;},stat:async p=>{if(p==='/warden'&&!analyzerExists)throw new Error('missing');return {isFile:()=>true};},readFile:async p=>docs[path.dirname(p)].getText()};
  const core={...realCore,resolveSource:async project=>({file:project+'/main.cpp',line:0,column:0}),spawnReport:async(ex,args)=>{const project=args[1],text=docs[project].getText(),replacement=project==='/A'?'reviewed_A':'unreviewed_B';return {stderr:'',report:{schema_version:2,status:'complete',project_root:project,mod:{id:'review.fixture'},toolchain:{sdk:'5.11.1',target:'arm64'},coverage:'limited',files:[],hooks:[],helpers:[],unknown:[],findings:[{rule:'bounds',repair:{file:'main.cpp',sha256:crypto.createHash('sha256').update(text).digest('hex'),start_byte:0,end_byte:0,expected:'',replacement}}]}};}};
  const sandbox={require:n=>n==='vscode'?vscode:n==='node:fs/promises'?fakefs:n==='./core'?core:n==='./webview'?require('../webview'):require(n),module:{exports:{}},AbortController,setTimeout,clearTimeout};
  vm.runInNewContext(fs.readFileSync(path.join(root,'editor/extension.js'),'utf8'),sandbox);sandbox.module.exports.activate({subscriptions:[],extensionUri:uri('/extension'),extensionPath:'/extension'});
  return {commands,messages,edits,callbacks,docs,vscode,layoutCalls,get viewFocus(){return viewFocus;},get diffOptions(){return diffOptions;},get panelColumn(){return panelColumn;},send:m=>recv(m),select:p=>selected=p,
    holdDiff(){diffGate={entered:deferred(),done:deferred()};return diffGate;},
    holdNextRealpath(){realpathGate=deferred();realpathEntered=deferred();return {entered:realpathEntered,done:realpathGate};},
    missingAnalyzer:()=>analyzerExists=false,latestState:()=>messages.filter(m=>m.type==='state').at(-1)};
}
test('old project preview cannot authorize current project repair',async()=>{
  const h=host();await h.commands.get('warden.open')();await h.commands.get('warden.analyze')();
  const gate=h.holdDiff();const oldPreview=h.send({type:'preview',index:0});await gate.entered.promise;
  h.select('/B');await h.send({type:'choose'});await h.send({type:'analyze'});
  gate.done.resolve();await oldPreview;await h.send({type:'apply',index:0});
  assert.equal(h.edits.length,0,`A preview must not apply B's patch: ${JSON.stringify(h.edits)}`);
});
test('edit during final async report-root check leaves result stale',async()=>{
  const h=host();await h.commands.get('warden.open')();
  const gate=h.holdNextRealpath();const running=h.commands.get('warden.analyze')();await gate.entered.promise;
  h.docs['/A'].isDirty=true;h.docs['/A'].version++;
  h.callbacks.change({document:h.docs['/A'],contentChanges:[{text:'changed'}]});
  gate.done.resolve();await running;
  assert.equal(h.latestState().stale,true,'Changed source must not become current after an obsolete run finishes');
});

test('untrusted workspace cannot run the analyzer',async()=>{
 const h=host();h.vscode.workspace.isTrusted=false;
 await assert.rejects(h.commands.get('warden.analyze')(),/Trust/);
 assert.equal(h.latestState()?.report,undefined);
});
test('applying without a current preview leaves source untouched',async()=>{
 const h=host();await h.commands.get('warden.open')();await h.commands.get('warden.analyze')();
 await h.send({type:'apply',index:0});assert.equal(h.edits.length,0);
 assert.ok(h.messages.some(m=>m.type==='error'&&/Preview/.test(m.message)));
});
test('approved current preview uses the reviewed source and replacement',async()=>{
 const h=host();await h.commands.get('warden.open')();await h.commands.get('warden.analyze')();
 await h.send({type:'preview',index:0});await h.send({type:'apply',index:0});
 assert.equal(h.edits.length,1);assert.equal(h.edits[0].uri,'/A/main.cpp');assert.equal(h.edits[0].text,'reviewed_A');
});

test('native sidebar preserves an existing multi-column editor layout',async()=>{
 const h=host();h.vscode.window.tabGroups.all=[{viewColumn:1},{viewColumn:2},{viewColumn:3}];
 await h.commands.get('warden.open')();assert.equal(h.layoutCalls.length,0);assert.equal(h.viewFocus,1);
});

test('missing analyzer is an actionable setup error rather than a phantom scan',async()=>{
 const h=host();h.missingAnalyzer();await h.commands.get('warden.open')();
 await assert.rejects(h.commands.get('warden.analyze')(),/Configure analyzer/);
 assert.equal(h.latestState().report,undefined);
});

test('repair preview passes editor options to the real diff API',async()=>{
 const h=host();await h.commands.get('warden.open')();await h.commands.get('warden.analyze')();
 await h.send({type:'preview',index:0});
 assert.equal(typeof h.diffOptions,'object','vscode.diff requires an options object, not a numeric column');
 assert.equal(h.diffOptions.viewColumn,1);
});

test('Warden opens its native sidebar without changing editor columns',async()=>{
 const h=host();await h.commands.get('warden.open')();
 assert.equal(h.viewFocus,1,'Use the registered native sidebar view');
 assert.equal(h.layoutCalls.length,0,'Do not compete with Cursor Agents editor columns');
});

test('first open waits for asynchronous native sidebar resolution',async()=>{
 const h=host({viewDelay:30});await h.commands.get('warden.open')();
 assert.equal(h.latestState().project,'/A');
});

test('cancelling repair approval never submits an edit',async()=>{
 const h=host();await h.commands.get('warden.open')();await h.commands.get('warden.analyze')();
 h.vscode.window.showWarningMessage=async()=>undefined;
 await h.send({type:'preview',index:0});await h.send({type:'apply',index:0});
 assert.equal(h.edits.length,0);
});

test('editing while repair approval is open invalidates that approval',async()=>{
 const h=host();await h.commands.get('warden.open')();await h.commands.get('warden.analyze')();
 await h.send({type:'preview',index:0});
 const entered=deferred(),approval=deferred();
 h.vscode.window.showWarningMessage=async()=>{entered.resolve();await approval.promise;return 'Apply reviewed repair';};
 const applying=h.send({type:'apply',index:0});await entered.promise;
 h.docs['/A'].version++;h.docs['/A'].isDirty=true;
 h.callbacks.change({document:h.docs['/A'],contentChanges:[{text:'changed'}]});
 approval.resolve();await applying;
 assert.equal(h.edits.length,0);
 assert.ok(h.messages.some(m=>m.type==='error'&&/Analyze|analyz|Save|changed/.test(m.message)));
});
