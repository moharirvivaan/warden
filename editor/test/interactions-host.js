
'use strict';
const vscode=require('vscode'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
async function run(){
 const root=path.resolve(__dirname,'../..'),out=path.join(root,'build/interaction-work');let result={passed:false};
 try{
   const extension=vscode.extensions.getExtension('warden-local.warden-geode');assert.ok(extension);await extension.activate();const config=vscode.workspace.getConfiguration('warden');
   for(const [key,value] of Object.entries({analyzerPath:path.join(root,'build/warden'),projectPath:path.join(root,'.deps/interaction-catalog/betterinfo'),buildPath:path.join(root,'.deps/interaction-catalog/betterinfo/build'),catalogPath:path.join(root,'build/interaction-catalog')}))await config.update(key,value,vscode.ConfigurationTarget.Workspace);
   const report=await vscode.commands.executeCommand('warden.analyze');assert.equal(report.mod.id,'cvolton.betterinfo');
   const d=await vscode.commands.executeCommand('warden.interactions');assert.equal(d.checked.length,2);assert.equal(d.excluded.length,1);assert.ok(d.candidates.some(c=>c.entryId==='nodeids'&&c.comparison.relationships.some(r=>r.method==='init')));
   assert.ok(d.candidates.some(c=>c.entryId==='server-api'&&c.metadataRelationships.some(m=>m.kind==='optional')));
   assert.equal(d.status,'partial');
   const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(root,'.deps/interaction-catalog/betterinfo/src/hooks/LevelInfoLayer.cpp')));
   const original=doc.getText();await vscode.window.showTextDocument(doc,vscode.ViewColumn.One);
   const edit=new vscode.WorkspaceEdit();edit.insert(doc.uri,doc.positionAt(original.length),'\n// Warden temporary editor freshness check\n');assert.ok(await vscode.workspace.applyEdit(edit));await doc.save();
   assert.equal((await vscode.commands.executeCommand('warden.interactions')).status,'unavailable');
   await vscode.window.showTextDocument(doc,{viewColumn:vscode.ViewColumn.One,preserveFocus:false});
   await vscode.commands.executeCommand('undo');assert.equal(doc.getText(),original);await doc.save();
   await vscode.commands.executeCommand('warden.analyze');assert.ok((await vscode.commands.executeCommand('warden.interactions')).candidates.some(c=>c.entryId==='nodeids'));
   result={passed:true,extensionPath:extension.extensionPath,editor:vscode.version,project:report.mod.id,source_hooks:report.hooks.length,discovery:d,game_run:false,source_edit_and_undo_verified:true,ui_clicks_verified:false};
 }catch(error){result={passed:false,error:error.stack||String(error)};throw error;}finally{await fs.writeFile(path.join(out,'actual-host.json'),JSON.stringify(result,null,2));}
}
module.exports={run};
