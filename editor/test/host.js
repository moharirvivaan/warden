'use strict';
const vscode=require('vscode');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');

async function run(){
  const root=path.resolve(__dirname,'../..'),dir=path.join(root,'build','editor-host');
  await fs.mkdir(dir,{recursive:true});let result={passed:false};
  try{
    const extension=vscode.extensions.getExtension('warden-local.warden-geode');assert.ok(extension,'Warden extension is loaded');await extension.activate();
    const config=vscode.workspace.getConfiguration('warden');
    await config.update('analyzerPath',path.join(root,'build','warden'),vscode.ConfigurationTarget.Workspace);
    const data=JSON.parse(await fs.readFile(path.join(root,'.deps','example-mod','build','compile_commands.json'),'utf8'));
    const entry=data.find(e=>e.file.endsWith('src/main.cpp'));
    // CMake generated commands are shell syntax; use Python shlex in test setup,
    // never in the extension's analyzer execution.
    const {execFileSync}=require('node:child_process');
    const base=entry.arguments||JSON.parse(execFileSync('python3',['-c','import shlex,json,sys;print(json.dumps(shlex.split(sys.argv[1])))',entry.command],{encoding:'utf8'}));
    const prefix='#include <Geode/Geode.hpp>\n#include <Geode/modify/MenuLayer.hpp>\nusing namespace geode::prelude;\n';
    async function fixture(name,source){
      const project=path.join(dir,name),build=path.join(project,'build'),file=path.join(project,'main.cpp');await fs.mkdir(build,{recursive:true});
      await fs.writeFile(file,prefix+source);await fs.writeFile(path.join(project,'mod.json'),JSON.stringify({id:'warden.host-test',name:'Warden SDK-backed editor test',geode:'5.11.1'}));
      await fs.writeFile(path.join(build,'compile_commands.json'),JSON.stringify([{directory:entry.directory,file,arguments:base.map(a=>a===entry.file?file:a)}]));return {project,build,file};
    }
    const first=await fixture('mod',`struct $modify(EditorTest,MenuLayer){bool init(){return MenuLayer::init();}};
void queued(){auto node=CCNode::create();Loader::get()->queueInMainThread([node](){node->setTag(42);});}
void paging(CCArray* data,unsigned i){
    auto object=data->objectAtIndex(i);
    if(i>=data->count() || object==nullptr) return;
}
`);
    await config.update('projectPath',first.project,vscode.ConfigurationTarget.Workspace);await config.update('buildPath',first.build,vscode.ConfigurationTarget.Workspace);
    const editorLayoutBefore=await vscode.commands.executeCommand('vscode.getEditorLayout');
    const report=await vscode.commands.executeCommand('warden.analyze');
    assert.equal(report.toolchain.sdk,'5.11.1');assert.deepEqual(report.hooks.map(h=>h.method),['init']);
    assert.deepEqual(report.findings.map(f=>f.rule).sort(),['geode.deferred-cocos-ownership','geode.late-array-bounds-check']);
    assert.ok(report.findings.find(f=>f.repair),'Real repair candidate is available');
    const doc=await vscode.workspace.openTextDocument(vscode.Uri.file(first.file));await vscode.window.showTextDocument(doc,vscode.ViewColumn.One);
    const editorLayoutAfter=await vscode.commands.executeCommand('vscode.getEditorLayout');
    assert.deepEqual(editorLayoutAfter,editorLayoutBefore,'The native sidebar must preserve code/Agents editor groups');
    const original=doc.getText(),edit=new vscode.WorkspaceEdit();edit.insert(doc.uri,doc.positionAt(original.length),'// unsaved edit\n');assert.ok(await vscode.workspace.applyEdit(edit));
    await assert.rejects(vscode.commands.executeCommand('warden.analyze'),/Save/);
    const restore=new vscode.WorkspaceEdit();restore.replace(doc.uri,new vscode.Range(doc.positionAt(0),doc.positionAt(doc.getText().length)),original);await vscode.workspace.applyEdit(restore);await doc.save();
    const broken=await fixture('broken','struct $modify(Broken,MenuLayer){bool init(){return missing_name;}};\n');
    await config.update('projectPath',broken.project,vscode.ConfigurationTarget.Workspace);await config.update('buildPath',broken.build,vscode.ConfigurationTarget.Workspace);
    const partial=await vscode.commands.executeCommand('warden.analyze');
    assert.equal(partial.project_root,await fs.realpath(broken.project));assert.equal(partial.status,'partial');assert.ok(partial.files.some(f=>f.diagnostics.some(d=>d.severity==='error')));
    // Return to the working demo for the manual visual/navigation/repair check.
    await config.update('projectPath',first.project,vscode.ConfigurationTarget.Workspace);await config.update('buildPath',first.build,vscode.ConfigurationTarget.Workspace);
    await vscode.commands.executeCommand('warden.analyze');
    result={passed:true,editor:vscode.version,sdk:report.toolchain.sdk,hooks:report.hooks.length,findings:report.findings.map(f=>f.rule),partial_error_verified:true,unsaved_change_rejected:true,native_sidebar_verified:true,editor_layout_preserved:true};
  }catch(error){result={passed:false,error:error.stack||String(error)};throw error;}
  finally{await fs.writeFile(path.join(dir,'result.json'),JSON.stringify(result,null,2));}
}
module.exports={run};
