'use strict';
const vscode=require('vscode');
const path=require('node:path');
const fs=require('node:fs/promises');
const crypto=require('node:crypto');
const {panelHtml}=require('./webview');
const {loadCatalog,discoverInteractions,catalogSourceUrl}=require('./catalog');
const {compareReports}=require('./interactions');
const {captureSourceState}=require('./source-state');
const {spawnReport,resolveSource,prepareRepair,contained}=require('./core');

function activate(context){
  const output=vscode.window.createOutputChannel('Warden');
  let panel,project,build,report,controller,epoch=0,saveTimer,stale=false;
  let catalog,discovery={status:'unavailable',reason:'Analyze your project to load the interaction catalog.'},catalogEpoch=0,catalogLoading=false,sourceFingerprint,scanFingerprint,peer;
  let sourceWatchers=[],catalogWatchers=[],peerWatchers=[];
  const disposeAll=items=>{for(const item of items)item.dispose?.();};
  const catalogDirectory=()=>config().get('catalogPath')||path.join(context.extensionPath,'..','build','interaction-catalog');
  const previews=new Map();
  const virtual=new Map();
  const viewWaiters=new Set();
  const config=()=>vscode.workspace.getConfiguration('warden');
  const provider=vscode.workspace.registerTextDocumentContentProvider('warden-preview',{provideTextDocumentContent:uri=>virtual.get(uri.toString())||''});
  const send=()=>panel?.webview.postMessage({type:'state',project,build,report,stale,running:!!controller,error:null,discovery,catalogLoading,generation:epoch,catalogGeneration:catalogEpoch,peer:peer?{report:peer.report,comparison:peer.comparison,error:peer.error,stale:peer.stale}:null,catalogEntries:catalog?.entries.map(e=>({id:e.id,mod:e.report.mod,revision:e.revision,scope:e.scope,adaptations:e.adaptations,license_status:e.license_status}))||[]});
  const notice=error=>panel?.webview.postMessage({type:'error',message:error.message||String(error)});
  function clearPeer(){disposeAll(peerWatchers);peerWatchers=[];peer=undefined;}
  function cancel(){epoch++;controller?.abort();controller=undefined;catalogLoading=false;send();}
  function invalidatePeer(){if(peer){peer.stale=true;peer.error='Peer source changed. Compare again.';}if(controller)cancel();send();}
  function invalidate(){cancel();stale=true;discovery={status:'unavailable',reason:'Source changed. Analyze again for current interactions.'};if(peer)peer.stale=true;previews.clear();send();}
  function watch(pattern,onChange){
    if(!vscode.workspace.createFileSystemWatcher||!vscode.RelativePattern)return [];
    const watcher=vscode.workspace.createFileSystemWatcher(pattern);watcher.onDidChange(onChange);watcher.onDidCreate(onChange);watcher.onDidDelete(onChange);return [watcher];
  }
  async function checkSavedSource(){
    const run=epoch,root=project,settings=build;if(!root||!settings)return;
    try{
      const saved=await captureSourceState(root,settings);
      if(run!==epoch||root!==project||settings!==build)return;
      const expected=controller?scanFingerprint:sourceFingerprint;
      if(!expected||saved!==expected)invalidate();
    }catch(error){if(run===epoch&&root===project&&settings===build){invalidate();output.appendLine('Source freshness: '+error.message);}}
  }
  function watchSource(){
    disposeAll(sourceWatchers);sourceWatchers=[];
    if(!project||!build||!vscode.RelativePattern)return;
    const changed=uri=>{const relative=path.relative(project,uri.fsPath);if(relative.split(path.sep).some(c=>['.git','.deps','.cache','build'].includes(c))||contained(build,uri.fsPath))return;if(relative==='mod.json'||/\.(cpp|cc|cxx|h|hpp|hh|hxx)$/.test(relative))return checkSavedSource();};
    sourceWatchers.push(...watch(new vscode.RelativePattern(project,'**/*'),changed));
    sourceWatchers.push(...watch(new vscode.RelativePattern(build,'compile_commands.json'),checkSavedSource));
  }
  function watchCatalog(){
    disposeAll(catalogWatchers);catalogWatchers=[];
    if(!vscode.RelativePattern)return;
    catalogWatchers=watch(new vscode.RelativePattern(catalogDirectory(),'*.json'),()=>{catalogEpoch++;catalogLoading=false;discovery={status:'unavailable',reason:'Catalog changed. Analyze again to use the new snapshot.'};send();});
  }
  async function refreshDiscovery(run=epoch){
    const version=catalogEpoch;catalogLoading=true;discovery={status:'unavailable',reason:'Loading the current catalog snapshot…'};send();
    try{const selected=await loadCatalog(catalogDirectory());if(run!==epoch||version!==catalogEpoch)return;catalog=selected;discovery=discoverInteractions(report,selected);}
    catch(error){if(run!==epoch||version!==catalogEpoch)return;catalog=undefined;discovery={status:'unavailable',reason:'Interaction catalog unavailable: '+error.message};output.appendLine(discovery.reason);}
    finally{if(run===epoch&&version===catalogEpoch){catalogLoading=false;send();}}
  }
  async function chooseCatalog(){
    const uris=await vscode.window.showOpenDialog({title:'Choose the prepared Warden catalog folder',canSelectFolders:true,canSelectFiles:false,canSelectMany:false});if(!uris?.[0])return;
    await config().update('catalogPath',uris[0].fsPath,vscode.ConfigurationTarget.Workspace);
  }
  function interactionLocation(report,source){
    if(!source||!Number.isInteger(source.hook)||source.hook<0||!Number.isInteger(source.index)||source.index<0)return;
    const h=report.hooks[source.hook];if(!h)return;
    if(source.kind==='declaration')return h.location;
    const fields={forwarding:'forwarding_calls',priority:'priority_requests',unknown:'unknown'};
    return h.behavior?.[fields[source.kind]]?.[source.index]?.location;
  }
  async function openPeerSource(message){
    current();const run=epoch,selected=peer;
    if(!selected?.report||selected.stale||message.generation!==run)throw new Error('Manual comparison is stale. Compare again.');
    for(const key of ['relationship','observation','source'])if(!Number.isInteger(message[key])||message[key]<0)throw new Error('Invalid manual source selection.');
    const source=selected.comparison.relationships[message.relationship]?.observations[message.observation]?.sources[message.source];
    if(!source||!['primary','peer'].includes(source.side))throw new Error('Invalid manual source.');
    if(sourceFingerprint!==await captureSourceState(project,build)||selected.fingerprint!==await captureSourceState(selected.root,selected.build))throw new Error('Source changed. Analyze and compare again.');
    if(run!==epoch||peer!==selected||selected.stale)throw new Error('Comparison changed.');
    if(source.side==='primary')return openLocation(interactionLocation(report,source));
    const resolved=await resolveSource(selected.root,interactionLocation(selected.report,source));
    const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(resolved.file));
    if(run!==epoch||peer!==selected||selected.stale||doc.isDirty)throw new Error('Peer source changed. Compare again.');
    const pos=new vscode.Position(resolved.line,resolved.column);
    await vscode.window.showTextDocument(doc,{viewColumn:vscode.ViewColumn.One,selection:new vscode.Range(pos,pos)});panel?.show(true);
  }
  async function openInteraction(message){
    current();const run=epoch,version=catalogEpoch;
    if(message.generation!==run||message.catalogGeneration!==version)throw new Error('Interaction selection is stale. Analyze again.');
    const candidate=discovery.candidates?.find(c=>c.entryId===message.entryId);
    if(!candidate||!Number.isInteger(message.relationship)||message.relationship<0||!Number.isInteger(message.observation)||message.observation<0||!Number.isInteger(message.source)||message.source<0)throw new Error('Invalid interaction selection.');
    const observation=candidate.comparison.relationships[message.relationship]?.observations[message.observation];
    const source=observation?.sources[message.source];if(!source)throw new Error('Invalid interaction source.');
    if(await captureSourceState(project,build)!==sourceFingerprint){invalidate();throw new Error('Saved source changed. Analyze again.');}
    if(run!==epoch||version!==catalogEpoch)throw new Error('Interaction changed. Analyze again.');
    if(source.side==='primary')return openLocation(interactionLocation(report,source));
    if(source.side!=='peer')throw new Error('Invalid interaction side.');
    const selected=await loadCatalog(catalogDirectory());
    const entry=selected.entries.find(e=>e.id===candidate.entryId);
    if(run!==epoch||version!==catalogEpoch||selected.id!==catalog?.id||!entry)throw new Error('Catalog evidence changed. Analyze again.');
    const url=catalogSourceUrl(entry,interactionLocation(entry.report,source));
    await vscode.env.openExternal(vscode.Uri.parse(url));
  }
  async function compareLocal(){
    if(!vscode.workspace.isTrusted)throw new Error('Trust this workspace before analyzing another source project.');
    current();clearPeer();send();const run=epoch;
    const previousRoot=config().get('peerProjectPath');
    const roots=previousRoot?[vscode.Uri.file(previousRoot)]:await vscode.window.showOpenDialog({title:'Advanced: choose another mod source folder',canSelectFolders:true,canSelectFiles:false,canSelectMany:false});if(!roots?.[0])return;
    const root=await fs.realpath(roots[0].fsPath);if(root===project)throw new Error('Choose a different mod source root.');
    const previousBuild=config().get('peerBuildPath');
    const databases=previousBuild?[vscode.Uri.file(path.join(previousBuild,'compile_commands.json'))]:await vscode.window.showOpenDialog({title:'Choose the other mod compile_commands.json',canSelectFiles:true,canSelectMany:false,filters:{'Compiler settings':['json']}});if(!databases?.[0])return;
    const peerBuild=await fs.realpath(path.dirname(databases[0].fsPath));
    if(run!==epoch)return;
    if(vscode.workspace.textDocuments.some(d=>d.isDirty&&contained(root,d.uri.fsPath)))throw new Error('Save the other mod before comparison.');
    const before=await captureSourceState(root,peerBuild);if(run!==epoch)return;
    await config().update('peerProjectPath',root,vscode.ConfigurationTarget.Workspace);await config().update('peerBuildPath',peerBuild,vscode.ConfigurationTarget.Workspace);if(run!==epoch)return;
    controller=new AbortController();send();
    try{
      const result=await spawnReport(config().get('analyzerPath')||path.join(context.extensionPath,'..','build','warden'),['inspect',root,'-p',peerBuild,'--format','json'],{signal:controller.signal,timeoutMs:config().get('timeoutSeconds',600)*1000});
      if(run!==epoch)return;
      if(await fs.realpath(result.report.project_root)!==root||before!==await captureSourceState(root,peerBuild)||sourceFingerprint!==await captureSourceState(project,build))throw new Error('Source changed during manual comparison. Analyze again.');
      if(run!==epoch)return;
      if(vscode.workspace.textDocuments.some(d=>d.isDirty&&contained(root,d.uri.fsPath)))throw new Error('Peer source has unsaved changes. Save and compare again.');
      peer={root,build:peerBuild,fingerprint:before,report:result.report,comparison:compareReports(report,result.report),stale:false};
      if(vscode.RelativePattern){const selected=peer;const changed=()=>{if(peer===selected&&run===epoch)invalidatePeer();};peerWatchers.push(...watch(new vscode.RelativePattern(root,'**/*'),changed),...watch(new vscode.RelativePattern(peerBuild,'compile_commands.json'),changed));}
    }catch(error){if(run===epoch)peer={error:error.message};}
    finally{if(run===epoch){controller=undefined;send();}}
  }
  async function createPanel(){
    // The focus command returns before VS Code resolves a fresh webview view.
    let timer,resolveView;
    const ready=panel?Promise.resolve():new Promise((resolve,reject)=>{
      resolveView=resolve;viewWaiters.add(resolve);
      timer=setTimeout(()=>reject(new Error('Warden sidebar could not open. Reload the editor window and try again.')),15000);
    });
    try{await vscode.commands.executeCommand('warden.panel.focus');await ready;}
    finally{clearTimeout(timer);viewWaiters.delete(resolveView);}
  }
  function attachView(view){
    const attached=view;
    panel=attached;
    view.webview.options={enableScripts:true,localResourceRoots:[vscode.Uri.joinPath(context.extensionUri,'media')]};
    const nonce=crypto.randomBytes(16).toString('hex');
    panel.webview.html=panelHtml(panel.webview,context.extensionUri,vscode,nonce);
    view.onDidDispose(()=>{if(panel===attached){panel=undefined;cancel();previews.clear();virtual.clear();}});
    panel.webview.onDidReceiveMessage(async message=>{
      if(!message||typeof message.type!=='string')return;
      try{
        switch(message.type){
          case 'ready':send();panel.webview.postMessage({type:'settings',autosave:config().get('analyzeOnSave')});break;
          case 'choose':await chooseProject(true);break;
          case 'configure':await chooseBuild(true);break;
          case 'analyzer':await chooseAnalyzer();break;
          case 'catalog':await chooseCatalog();break;
          case 'interactionSource':await openInteraction(message);break;
          case 'peerSource':await openPeerSource(message);break;
          case 'compare':await compareLocal();break;
          case 'removePeer':cancel();clearPeer();await config().update('peerProjectPath',undefined,vscode.ConfigurationTarget.Workspace);await config().update('peerBuildPath',undefined,vscode.ConfigurationTarget.Workspace);send();break;
          case 'analyze':await analyze();break;
          case 'cancel':cancel();break;
          case 'autosave':if(typeof message.enabled==='boolean')await config().update('analyzeOnSave',message.enabled,vscode.ConfigurationTarget.Workspace);break;
          case 'source':await openSource(message.kind,message.index,message.related);break;
          case 'preview':await previewRepair(message.index);break;
          case 'apply':await applyRepair(message.index);break;
          case 'output':output.show();break;
        }
      }catch(error){notice(error);output.appendLine(error.stack||String(error));}
    },undefined,context.subscriptions);
  }
  async function exists(file){try{return (await fs.stat(file)).isFile();}catch{return false;}}
  async function chooseProject(browse=false){
    let selected=!browse && config().get('projectPath');
    if(!selected&&!browse){
      const options=[];
      for(const folder of vscode.workspace.workspaceFolders||[])if(await exists(path.join(folder.uri.fsPath,'mod.json')))options.push(folder.uri.fsPath);
      if(options.length===1)selected=options[0];
      else if(options.length>1)selected=await vscode.window.showQuickPick(options,{title:'Choose the mod to analyze'});
    }
    if(!selected){const uris=await vscode.window.showOpenDialog({title:'Choose a Geode mod folder',canSelectFolders:true,canSelectFiles:false,canSelectMany:false});selected=uris?.[0]?.fsPath;}
    if(!selected)return false;
    selected=await fs.realpath(selected);
    if(!await exists(path.join(selected,'mod.json')))throw new Error('Choose the mod folder containing mod.json.');
    invalidate();project=selected;build=undefined;report=undefined;stale=false;send();
    await chooseBuild(false);return true;
  }
  async function chooseBuild(browse=false){
    if(!project)if(!await chooseProject(false))return false;
    let selected=!browse && config().get('buildPath');
    if(!selected&&!browse && await exists(path.join(project,'build','compile_commands.json')))selected=path.join(project,'build');
    if(!selected){const uris=await vscode.window.showOpenDialog({title:'Choose compile_commands.json from your configured build',canSelectFolders:false,canSelectMany:false,filters:{'Compiler settings':['json']}});if(uris?.[0])selected=path.dirname(uris[0].fsPath);}
    if(!selected)return false;
    selected=await fs.realpath(selected);
    if(!await exists(path.join(selected,'compile_commands.json')))throw new Error('This folder has no compile_commands.json. Configure the mod build with CMAKE_EXPORT_COMPILE_COMMANDS=ON, then choose its compiler settings.');
    invalidate();build=selected;report=undefined;stale=false;watchSource();watchCatalog();send();return true;
  }
  async function chooseAnalyzer(){
    const uris=await vscode.window.showOpenDialog({title:'Select the compiled warden analyzer executable',canSelectFiles:true,canSelectFolders:false,canSelectMany:false});
    if(!uris?.[0])return;
    const selected=await fs.realpath(uris[0].fsPath);
    if(!await exists(selected))throw new Error('Choose the compiled warden executable, not its folder.');
    await config().update('analyzerPath',selected,vscode.ConfigurationTarget.Workspace);
    send();
  }
  async function analyze(){
    await createPanel();
    if(!vscode.workspace.isTrusted)throw new Error('Trust this workspace before Warden can execute the local analyzer.');
    if(!project && !await chooseProject(false))return;
    if(!build && !await chooseBuild(false))return;
    if(vscode.workspace.textDocuments.some(d=>d.isDirty&&contained(project,d.uri.fsPath)))throw new Error('Save your mod changes before analysis. Warden reads files on disk.');
    const executable=config().get('analyzerPath')||path.join(context.extensionPath,'..','build','warden');
    if(!await exists(executable))throw new Error('Configure analyzer: select your compiled warden executable under Project setup. This extension requires the native analyzer and LLVM 21.');
    cancel();clearPeer();scanFingerprint=undefined;const run=epoch;controller=new AbortController();stale=true;previews.clear();send();
    output.appendLine(`Analyzing ${project}\nCompiler settings: ${build}`);
    try{
      const before=await captureSourceState(project,build);if(run!==epoch)return;scanFingerprint=before;
      const result=await spawnReport(executable,['inspect',project,'-p',build,'--format','json'],{signal:controller.signal,timeoutMs:config().get('timeoutSeconds',600)*1000});
      if(run!==epoch)return;
      const reportRoot=await fs.realpath(result.report.project_root);
      const after=await captureSourceState(project,build);
      if(run!==epoch)return;
      if(reportRoot!==project)throw new Error('Analyzer returned a report for a different project.');
      if(before!==after)throw new Error('Saved source changed during analysis. Analyze again.');
      sourceFingerprint=after;
      output.appendLine(result.stderr);report=result.report;stale=false;controller=undefined;
      // Open real source on the first scan. The sidebar remains independent
      // of Cursor's code and Agents editor groups.
      const active=vscode.window.activeTextEditor;
      const initial=report.findings[0]?.location||report.hooks[0]?.location||
        (report.files?.find(f=>f.kind==='translation_unit') ? {file:report.files.find(f=>f.kind==='translation_unit').file,line:1,column:1}:undefined);
      if(initial && (!active || !contained(project,active.document.uri.fsPath))) {
        try{await openLocation(initial);}catch(error){output.appendLine('Source preview: '+error.message);}
      }
      if(run!==epoch)return;
      panel?.show(true);send();await refreshDiscovery(run);return report;
    }catch(error){if(run===epoch){controller=undefined;notice(error);send();output.appendLine(error.detail||error.stack||String(error));}throw error;}
  }
  function current(){if(!report||stale||controller)throw new Error('Analyze saved source again before using this result.');}
  function sourceFor(kind,index,related){
    if(!Number.isInteger(index)||index<0)return;
    if(kind==='finding'){const f=report.findings[index];return related===undefined?f?.location:Number.isInteger(related)&&related>=0?f?.related[related]?.location:undefined;}
    if(kind==='hook')return report.hooks[index]?.location;
    if(kind==='helper')return report.helpers[index]?.location;
    if(kind==='unknown')return report.unknown[index]?.location;
    if(kind==='diagnostic'){const records=report.files.flatMap(f=>f.diagnostics);return records[index]?.location;}
  }
  async function openSource(kind,index,related){
    return openLocation(sourceFor(kind,index,related));
  }
  async function openLocation(loc){
    current();const run=epoch;const resolved=await resolveSource(project,loc);
    const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(resolved.file));
    current();if(run!==epoch)throw new Error('Selection changed during navigation. Analyze again.');
    if(doc.isDirty)throw new Error('Source has unsaved changes. Save and analyze again.');
    const position=new vscode.Position(resolved.line,resolved.column);
    const editor=await vscode.window.showTextDocument(doc,{viewColumn:vscode.ViewColumn.One,selection:new vscode.Range(position,position),preserveFocus:false});
    if(run===epoch)panel?.show(true);
    return editor;
  }
  async function repairInput(index){
    current();if(!Number.isInteger(index)||index<0)throw new Error('Invalid repair selection.');
    const run=epoch,selectedReport=report,selectedProject=project;
    const f=report.findings[index],repair=f?.repair;if(!repair)throw new Error('This finding has a suggestion, not a supported automatic patch.');
    const resolved=await resolveSource(selectedProject,{file:repair.file,line:1,column:1});
    const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(resolved.file));
    if(doc.isDirty)throw new Error('Save your source and analyze again before reviewing this repair.');
    const disk=await fs.readFile(resolved.file,'utf8');
    current();if(run!==epoch||selectedReport!==report||selectedProject!==project)throw new Error('Source or selection changed during repair review. Analyze and preview again.');
    if(disk!==doc.getText())throw new Error('Editor and disk differ. Reload the source and analyze again.');
    return {doc,patch:prepareRepair(disk,repair),repair,f,run,selectedReport,selectedProject};
  }
  async function previewRepair(index){
    const input=await repairInput(index),{doc,patch,f,run,selectedReport,selectedProject}=input;const id=crypto.randomBytes(8).toString('hex');
    const before=vscode.Uri.parse(`warden-preview:/${id}/before.cpp`),after=vscode.Uri.parse(`warden-preview:/${id}/after.cpp`);
    virtual.set(before.toString(),doc.getText());virtual.set(after.toString(),patch.text);
    await vscode.commands.executeCommand('vscode.diff',before,after,'Warden · Proposed bounds guard · Review before applying',{viewColumn:vscode.ViewColumn.One});
    current();if(run!==epoch||selectedReport!==report||selectedProject!==project)throw new Error('Source or selection changed while the preview opened. Analyze and preview again.');
    previews.set(index,{epoch:run,version:doc.version,report:selectedReport,project:selectedProject,file:doc.uri.fsPath,repair:input.repair});
    panel?.webview.postMessage({type:'previewed',index,message:'Review the inserted guard and intended fallback. Existing null handling stays intact. Apply requires your approval; Cmd/Ctrl+Z undoes the edit.'});
    output.appendLine(`Repair preview: ${f.rule}. No source changed.`);
  }
  async function applyRepair(index){
    if(!vscode.workspace.isTrusted)throw new Error('Workspace trust is required to apply a repair.');
    const preview=previews.get(index);if(!preview||preview.epoch!==epoch||preview.report!==report||preview.project!==project||preview.repair!==report.findings[index]?.repair)throw new Error('Preview this repair first.');
    let input=await repairInput(index);if(input.doc.version!==preview.version)throw new Error('Source changed since the preview. Analyze and preview again.');
    const approved=await vscode.window.showWarningMessage('Apply the reviewed bounds guard? Verify pagination and empty-array behavior afterward. Undo is available in the source editor.',{modal:true},'Apply reviewed repair');
    if(approved!=='Apply reviewed repair')return;
    current();input=await repairInput(index);if(input.doc.version!==preview.version||preview.epoch!==epoch||preview.report!==report||preview.file!==input.doc.uri.fsPath)throw new Error('Source or selection changed during approval. Analyze and preview again.');
    const edit=new vscode.WorkspaceEdit();edit.replace(input.doc.uri,new vscode.Range(input.doc.positionAt(input.patch.start),input.doc.positionAt(input.patch.end)),input.repair.replacement);
    if(!await vscode.workspace.applyEdit(edit))throw new Error('The editor could not apply this repair.');
    await vscode.window.showTextDocument(input.doc,{viewColumn:vscode.ViewColumn.One});
    if(!await input.doc.save())throw new Error('Repair is in the editor but could not be saved. Save manually; Cmd/Ctrl+Z undoes it.');
    await analyze();
    panel?.webview.postMessage({type:'repairApplied',message:'Repair applied and source reanalyzed. Build and test the intended behavior before release. Undo remains available in the source editor.'});
  }
  const sidebar=vscode.window.registerWebviewViewProvider('warden.panel',{resolveWebviewView(view){attachView(view);send();for(const resolve of viewWaiters)resolve();viewWaiters.clear();}},{webviewOptions:{retainContextWhenHidden:true}});
  context.subscriptions.push(output,provider,sidebar,
    vscode.commands.registerCommand('warden.open',async()=>{await createPanel();try{if(!project)await chooseProject(false);send();}catch(error){notice(error);output.appendLine(error.stack||String(error));}}),
    vscode.commands.registerCommand('warden.analyze',analyze),
    vscode.commands.registerCommand('warden.cancel',cancel),
    vscode.commands.registerCommand('warden.compare',compareLocal),
    vscode.commands.registerCommand('warden.interactions',async()=>{await createPanel();panel?.webview.postMessage({type:'tab',tab:'interactions'});return discovery;}),
    vscode.workspace.onDidChangeTextDocument(e=>{if(!e.contentChanges.length)return;if(project&&contained(project,e.document.uri.fsPath))invalidate();else if(peer?.root&&contained(peer.root,e.document.uri.fsPath))invalidatePeer();}),
    vscode.workspace.onDidSaveTextDocument(doc=>{if(peer?.root&&contained(peer.root,doc.uri.fsPath))invalidatePeer();if(project&&contained(project,doc.uri.fsPath)){invalidate();if(config().get('analyzeOnSave')&&/\.(cpp|cc|cxx|h|hpp)$/.test(doc.uri.fsPath)){clearTimeout(saveTimer);saveTimer=setTimeout(()=>analyze().catch(notice),700);}}}),
    vscode.workspace.onDidChangeConfiguration(e=>{if(e.affectsConfiguration('warden')){if(['peerProjectPath','peerBuildPath'].some(k=>e.affectsConfiguration('warden.'+k))&&!['projectPath','buildPath','analyzerPath','catalogPath'].some(k=>e.affectsConfiguration('warden.'+k))){if(peer?.root&&(config().get('peerProjectPath')!==peer.root||config().get('peerBuildPath')!==peer.build))invalidatePeer();return;}if(e.affectsConfiguration('warden.catalogPath')&&!['projectPath','buildPath','analyzerPath'].some(k=>e.affectsConfiguration('warden.'+k))){catalogEpoch++;watchCatalog();if(report&&!stale)refreshDiscovery().catch(notice);return;}invalidate();if(e.affectsConfiguration('warden.projectPath')||e.affectsConfiguration('warden.buildPath')){project=undefined;build=undefined;report=undefined;send();}panel?.webview.postMessage({type:'settings',autosave:config().get('analyzeOnSave')});}}),
    {dispose(){clearTimeout(saveTimer);cancel();disposeAll(sourceWatchers);disposeAll(catalogWatchers);clearPeer();previews.clear();virtual.clear();}}
  );
}
module.exports={activate};
