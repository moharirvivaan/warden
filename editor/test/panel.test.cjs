const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Node {constructor(text=''){this.text=text;this.children=[];}append(...children){this.children.push(...children);}allText(){return [this.text,...this.children.map(c=>c.allText())].join(' ');}}
test('manual comparison remains visible when automatic catalog is unavailable',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../media/panel.js'),'utf8');const start=source.indexOf('function renderInteractions('),end=source.indexOf('for (const [id, type]',start);
 const sandbox={state:{discovery:{status:'unavailable',reason:'Catalog unavailable'},peer:{report:{mod:{id:'peer.mod'}},comparison:{reasons:[],relationships:[]}}},card:(title)=>new Node(title),element:(tag,text)=>new Node(text),button:(label)=>new Node(label),post(){}};
 vm.runInNewContext(source.slice(start,end),sandbox);const results=new Node();sandbox.renderInteractions(results);assert.match(results.allText(),/Advanced local comparison/);assert.match(results.allText(),/peer.mod/);
});
test('unexamined files are grouped coverage limits rather than investigation cards',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../media/panel.js'),'utf8');
 const start=source.indexOf('function renderCoverage(');assert.ok(start>=0,'Coverage renderer must group analysis limitations');const end=source.indexOf('for (const [id, type]',start);
 const sandbox={card:title=>new Node(title),element:(tag,text)=>{const node=new Node(text);node.tag=tag;return node;},source(){}};vm.runInNewContext(source.slice(start,end),sandbox);
 const report={coverage:'Selected source only',toolchain:{sdk:'5.10.1',target:'arm64'},files:[],unknown:[...Array.from({length:86},(_,i)=>({reason:'Source file has no command in the selected compilation database.',location:{file:`src/${i}.cpp`}})),...Array.from({length:52},(_,i)=>({reason:'Header was not included by the selected translation units.',location:{file:`src/${i}.hpp`}})),{reason:'Unsupported member template/lifecycle declaration: onModify',location:{file:'main.cpp',line:2,column:1}}]};
 const results=new Node();sandbox.renderCoverage(results,report);assert.equal(results.children.length,1,'One coverage summary, not 139 warning cards');const text=results.allText();assert.match(text,/86 source files outside this scan/);assert.match(text,/52 headers outside this scan/);assert.match(text,/1 other analysis limitation/);assert.doesNotMatch(text,/Needs human investigation/);assert.match(text,/not bug findings/);
});
