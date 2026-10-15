'use strict';
const vscode = acquireVsCodeApi();
const $ = id => document.getElementById(id);
let state = {report: null, stale: false, running: false}, tab = 'interactions';
const post = (type, data = {}) => vscode.postMessage({type, ...data});
const nameOf = value => value?.split(/[\\/]/).filter(Boolean).at(-1);
const titles = {
  'geode.deferred-cocos-ownership': 'Deferred object lifetime',
  'geode.late-array-bounds-check': 'Bounds check runs too late'
};
function element(tag, text, className) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (className) e.className = className;
  return e;
}
function button(label, action) {
  const b = element('button', label, 'link');
  b.disabled = state.stale || state.running;
  b.onclick = action;
  return b;
}
function source(card, loc, kind, index, related, label) {
  if (!loc?.file || !loc.line) return;
  card.append(button(label || `${loc.file}:${loc.line}`, () => post('source', {kind, index, ...(related === undefined ? {} : {related})})));
}
function card(title, badge) {
  const c = element('article', undefined, 'card');
  const h = element('div', undefined, 'card-heading');
  h.append(element('h2', title));
  if (badge) h.append(element('span', badge, 'badge'));
  c.append(h);
  return c;
}
function render() {
  const r = state.report;
  document.body.dataset.state = state.running ? 'running' : state.stale ? 'stale' : r?.status || 'ready';
  $('project').textContent = r?.mod.name || r?.mod.id || nameOf(state.project) || 'Choose a Geode project';
  $('projectPath').textContent = state.project || 'Choose the folder containing mod.json.';
  $('build').textContent = state.build ? `Compiler settings: ${state.build}` : 'Select compile_commands.json from your configured SDK build.';
  $('analyze').disabled = state.running;
  $('cancel').hidden = !state.running;
  $('status').textContent = state.running ? 'Analyzing saved source…' : state.stale ? 'Source changed. Analyze again for current results.' : r ? (r.status === 'complete' ? 'Scan complete · supported checks only' : r.status === 'partial' ? 'Limited scan · see Coverage' : 'Setup needs attention') : 'Ready for your first scan';
  const diagnostics = r?.files.flatMap(f => f.diagnostics) || [];
  $('attentionCount').textContent = (r?.findings.length || 0) + diagnostics.length;
  $('hookCount').textContent = r?.hooks.length || 0;
  $('unknownCount').textContent = r ? (r.status==='complete'?'Complete':'Limited') : '—';
  $('interactionCount').textContent = state.discovery?.candidates?.length || 0;
  document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
  $('overview').hidden = !r;
  $('reviewTotal').textContent = (r?.findings.length || 0) + diagnostics.length;
  $('fileTotal').textContent = r ? `${r.files.filter(f => f.status === 'complete').length}/${r.files.length}` : '0/0';
  $('sdkVersion').textContent = r?.toolchain.sdk || 'Unknown';
  const results = $('results');
  results.replaceChildren();
  if (!r) {
    const c = card('Your next step');
    c.append(element('p', 'Open a Geode mod and select its compiler settings. Warden will inspect real SDK types and show supported lifetime and array-access risks.'), element('p', 'First use? Project setup lets you select your compiled analyzer.', 'meta'));
    results.append(c);
    return;
  }
  if(tab === 'interactions'){renderInteractions(results);return;}
  if (tab === 'attention') {
    r.findings.forEach((f, index) => {
      const c = card(titles[f.rule] || f.rule, 'REVIEW');
      c.classList.add('review');
      c.append(element('p', f.evidence.replaceAll('_', ' ').toUpperCase(), 'meta'), element('p', f.message));
      source(c, f.location, 'finding', index);
      c.append(element('h3', 'Suggested fix'), element('p', f.suggestion));
      const details = element('details');
      details.append(element('summary', 'Source evidence & limits'), element('p', f.rule, 'meta'));
      f.related.forEach((l, related) => source(details, l.location, 'finding', index, related, `${l.role.replaceAll('_', ' ')} · ${l.location.file}:${l.location.line}`));
      if (f.factory_contract) details.append(element('p', `SDK ownership contract: ${f.factory_contract}`));
      details.append(element('p', f.limitations));
      c.append(details);
      if (f.repair) {
        const actions = element('div', undefined, 'actions');
        actions.append(button('Preview fix', () => post('preview', {index})));
        const apply = button('Apply reviewed fix', () => post('apply', {index}));
        apply.hidden = true;
        apply.dataset.repair = String(index);
        actions.append(apply);
        c.append(actions, element('p', 'Preview first. You approve the edit. Undo stays available.', 'meta'));
      } else c.append(element('p', 'Guidance only · choose the repair that fits your code.', 'meta'));
      results.append(c);
    });
    diagnostics.forEach((d, index) => {
      const c = card('Compiler ' + d.severity, d.severity.toUpperCase());
      c.append(element('p', d.message));
      source(c, d.location, 'diagnostic', index);
      c.append(element('p', 'Resolve this build or source issue, then analyze again.', 'meta'));
      results.append(c);
    });
    if (!r.findings.length && !diagnostics.length) {
      const c = card('No supported findings');
      c.append(element('p', 'These checks found no review items. Coverage shows unsupported and incomplete analysis.'), element('p', 'This result does not prove the mod is safe or compatible.', 'meta'));
      results.append(c);
    }
  } else if (tab === 'hooks') {
    const c = card('Hook map', `${r.hooks.length} HOOKS`);
    c.append(element('p', 'Compiler-resolved declarations, with helpers kept separate.'), element('p', 'Shared targets are normal. This inventory does not establish cross-mod conflicts.', 'meta'));
    results.append(c);
    for (const [kind, items] of [['hook', r.hooks], ['helper', r.helpers]]) {
      items.forEach((h, index) => {
        const c = card(`${h.target_class}::${h.method}`, kind.toUpperCase());
        c.append(element('code', h.signature));
        source(c, h.location, kind, index);
        results.append(c);
      });
    }
  } else {
    renderCoverage(results,r);
  }
}
function renderCoverage(results,r){
  const c=card('What Warden checked');
  c.append(element('p','These entries describe analysis limits, not bug findings.'),element('p',r.coverage,'meta'),element('p',`Geode ${r.toolchain.sdk||'unknown'} · ${r.toolchain.target||'unknown target'}`,'meta'));
  const groups=[
    {label:'source files outside this scan',items:[]},
    {label:'headers outside this scan',items:[]},
    {label:'other analysis limitation',items:[]}
  ];
  r.unknown.forEach((u,index)=>{
    const group=u.reason==='Source file has no command in the selected compilation database.'?0:u.reason==='Header was not included by the selected translation units.'?1:2;
    groups[group].items.push({u,index});
  });
  for(const [i,group] of groups.entries()){
    if(!group.items.length)continue;
    const details=element('details');details.append(element('summary',`${group.items.length} ${group.label}${i===2&&group.items.length!==1?'s':''}`));
    details.append(element('p',i<2?'The selected compiler settings do not cover these files. Their behavior is unexamined; this does not indicate a defect.':'Warden cannot yet interpret these constructs or configurations. Inspect the details if they matter to your review.','meta'));
    for(const {u,index} of group.items){details.append(element('p',i<2?(u.location.file||'Unspecified file'):`${u.location.file?u.location.file+': ':''}${u.reason}`,'meta'));source(details,u.location,'unknown',index);}
    c.append(details);
  }
  const files=element('details');files.append(element('summary','All file analysis statuses'));r.files.forEach(f=>files.append(element('p',`${f.status} · ${f.file}`,'meta')));c.append(files);results.append(c);
}
function renderInteractions(results){
  const d=state.discovery;
  const intro=card('Interactions to investigate',state.catalogLoading?'LOADING':'SOURCE REVIEW');
  intro.append(element('p','Warden finds supported relationships in a bounded catalog. These are investigation leads, not detected crashes.'));
  if(state.catalogLoading)intro.append(element('p','Loading the prepared catalog…'));
  if(!d?.candidates){intro.append(element('p',d?.reason||'Analyze saved source to check the prepared mod catalog.'),button('Choose catalog folder',()=>post('catalog')));results.append(intro);renderManualComparison(results);return;}
  intro.append(element('p',`${d.checked.length} entries checked · ${d.unavailable.length} unavailable/configuration gaps · ${d.excluded.length} self entries excluded`, 'meta'));
  intro.append(element('p',`Snapshot ${d.snapshotId.slice(0,12)} · ${d.createdAt}`, 'meta'),element('p',d.coverage,'meta'));
  const coverage=element('details');coverage.append(element('summary','Which mods and source units were checked?'));
  d.checked.forEach(e=>coverage.append(element('p',`${e.mod.name||e.mod.id} ${e.mod.version} · ${e.scope.join(', ')} · ${e.status}`, 'meta')));
  d.unavailable.forEach(e=>coverage.append(element('p',`${e.entryId}: ${e.reason}`, 'meta')));intro.append(coverage);results.append(intro);
  if(!d.candidates.length){const empty=card('No supported relationship found');empty.append(element('p','This result applies only to the displayed catalog and source coverage. It is not a compatibility verdict.'));results.append(empty);}
  for(const candidate of d.candidates){
    const entry=state.catalogEntries.find(e=>e.id===candidate.entryId);if(!entry)continue;
    const c=card(`${entry.mod.name||entry.mod.id} ${entry.mod.version}`,candidate.group.replaceAll('_',' ').toUpperCase());
    c.append(element('p',`Source revision ${entry.revision.slice(0,12)} · selected units · runtime not tested`,'meta'));
    candidate.metadataRelationships.forEach(m=>c.append(element('p',m.message),element('p',`Version constraint: ${m.versionStatus}. This relationship comes from mod metadata.`,'meta')));
    candidate.comparison.reasons.forEach(reason=>c.append(element('p',reason,'hint')));
    if(!candidate.comparison.relationships.length)c.append(element('p','No shared hooks in the selected source units. Review the declared relationship and intended versions; API interactions are not inferred from this alone.'));
    candidate.comparison.relationships.forEach((relationship,ri)=>{
      const group=element('details');group.open=candidate.group!=='shared_target';group.append(element('summary',`${relationship.target_class}::${relationship.method} ${relationship.signature}`));
      relationship.observations.forEach((o,oi)=>{
        const item=element('div',undefined,'interaction-observation');item.append(element('p',`${o.evidence.toUpperCase()} · ${o.message}`));
        o.sources.forEach((src,si)=>item.append(button(src.side==='primary'?'Open your source':'Open pinned mod source',()=>post('interactionSource',{entryId:candidate.entryId,relationship:ri,observation:oi,source:si,generation:state.generation,catalogGeneration:state.catalogGeneration}))));
        item.append(element('p',o.suggestion,'hint'));group.append(item);
      });c.append(group);
    });
    const limits=element('details');limits.append(element('summary','Configuration and provenance'));entry.adaptations.forEach(a=>limits.append(element('p',a,'meta')));limits.append(element('p',`License review: ${entry.license_status}; catalog is local alpha data.`,'meta'));c.append(limits);results.append(c);
  }
  renderManualComparison(results);
}
function renderManualComparison(results){
  if(state.peer){const c=card('Advanced local comparison',state.peer.error?'UNAVAILABLE':'SOURCE FACTS');
    if(state.peer.error||state.peer.stale)c.append(element('p',state.peer.error||'Comparison is stale. Compare again.'));
    else {c.append(element('p',state.peer.report.mod.id));state.peer.comparison.reasons.forEach(x=>c.append(element('p',x,'hint')));state.peer.comparison.relationships.forEach((r,ri)=>{c.append(element('h3',`${r.target_class}::${r.method}`));r.observations.forEach((o,oi)=>{c.append(element('p',o.message),element('p',o.suggestion,'hint'));o.sources.forEach((src,si)=>c.append(button(src.side==='primary'?'Open your source':'Open peer source',()=>post('peerSource',{generation:state.generation,relationship:ri,observation:oi,source:si}))));});});}
    results.append(c);
  }
}
for (const [id, type] of [['choose', 'choose'], ['configure', 'configure'], ['analyzer', 'analyzer'], ['analyze', 'analyze'], ['cancel', 'cancel'], ['catalog','catalog'], ['compare','compare'], ['removePeer','removePeer']]) {
  $(id).onclick = () => {$('error').hidden = true; post(type);};
}
$('autosave').onchange = () => post('autosave', {enabled: $('autosave').checked});
document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {
  tab = b.dataset.tab;
  document.querySelectorAll('[data-tab]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  render();
});
window.addEventListener('message', ({data}) => {
  if (data.type === 'state') {state = data; render();}
  else if (data.type === 'tab') {tab=data.tab;render();}
  else if (data.type === 'settings') $('autosave').checked = data.autosave === true;
  else if (data.type === 'error') {$('error').textContent = data.message; $('error').hidden = false; $('setup').open = true;}
  else if (data.type === 'previewed') {
    const apply = document.querySelector(`[data-repair="${data.index}"]`);
    if (apply) apply.hidden = false;
    $('status').textContent = data.message;
  } else if (data.type === 'repairApplied') $('status').textContent = data.message;
});
render();
post('ready');
