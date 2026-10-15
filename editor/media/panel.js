'use strict';
const vscode = acquireVsCodeApi();
const $ = id => document.getElementById(id);
let state = {report: null, stale: false, running: false}, tab = 'attention';
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
  $('status').textContent = state.running ? 'Analyzing saved source…' : state.stale ? 'Source changed. Analyze again for current results.' : r ? (r.status === 'complete' ? 'Scan complete · supported checks only' : r.status === 'partial' ? 'Partial scan · check unknown coverage' : 'Setup needs attention') : 'Ready for your first scan';
  const diagnostics = r?.files.flatMap(f => f.diagnostics) || [];
  $('attentionCount').textContent = (r?.findings.length || 0) + diagnostics.length;
  $('hookCount').textContent = r?.hooks.length || 0;
  $('unknownCount').textContent = r?.unknown.length || 0;
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
    const c = card('Coverage, not a safety score');
    c.append(element('p', r.coverage), element('p', `Geode ${r.toolchain.sdk || 'unknown'} · ${r.toolchain.target || 'unknown target'}`, 'meta'));
    const files = element('details');
    files.append(element('summary', `${r.files.filter(f => f.status === 'complete').length}/${r.files.length} files complete · inspect file status`));
    r.files.forEach(f => files.append(element('p', `${f.status.toUpperCase()} · ${f.file}`, 'meta')));
    c.append(files);
    results.append(c);
    r.unknown.forEach((u, index) => {
      const c = card('Needs human investigation', 'UNKNOWN');
      c.append(element('p', u.reason));
      source(c, u.location, 'unknown', index);
      results.append(c);
    });
  }
}
for (const [id, type] of [['choose', 'choose'], ['configure', 'configure'], ['analyzer', 'analyzer'], ['analyze', 'analyze'], ['cancel', 'cancel']]) {
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
