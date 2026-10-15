'use strict';

function panelHtml(webview, extensionUri, vscode, nonce) {
  const asset = name => webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', name));
  return `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource}; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
<link rel="stylesheet" href="${asset('panel.css')}"><title>Warden · Geode Preflight</title>
</head><body>
<header class="hero">
  <div class="hero-top"><span class="eyebrow">GEODE DEV TOOLS</span><span class="alpha">LOCAL ALPHA</span></div>
  <div class="brand"><img src="${asset('cube.svg')}" width="72" height="72" alt="Warden cube mascot"><div><h1>WARDEN</h1><p>Find the risk. Understand the fix.</p></div></div>
  <div class="ground" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
</header>
<main>
  <section class="cockpit" aria-label="Analysis controls">
    <div class="project-heading"><div><span class="eyebrow">YOUR MOD</span><p id="project">Choose a Geode project</p></div><button id="choose" class="small secondary">Change mod</button></div>
    <details id="setup"><summary>Project setup</summary><p id="projectPath" class="path"></p><small id="build"></small><div class="actions"><button id="configure" class="small secondary">Compiler settings</button><button id="analyzer" class="small secondary">Configure analyzer</button></div><p class="hint">Uses your configured SDK build. No game launch.</p></details>
    <button id="analyze" class="scan"><span class="play" aria-hidden="true">▶</span> ANALYZE MOD</button>
    <button id="cancel" class="cancel" hidden>Cancel analysis</button>
    <label class="autosave"><input id="autosave" type="checkbox"> Analyze when I save C++ changes</label>
  </section>
  <div class="scan-state"><span id="statusLight" class="status-light" aria-hidden="true"></span><p id="status" role="status" aria-live="polite">Ready for your first scan</p></div>
  <section id="error" role="alert" hidden></section>
  <section id="overview" class="overview" aria-label="Scan overview" hidden><div><strong id="reviewTotal">0</strong><span>to review</span></div><div><strong id="fileTotal">0/0</strong><span>files complete</span></div><div><strong id="sdkVersion">—</strong><span>Geode SDK</span></div></section>
  <nav aria-label="Results"><button data-tab="attention" aria-pressed="true">Reviews <span id="attentionCount">0</span></button><button data-tab="hooks" aria-pressed="false">Hooks <span id="hookCount">0</span></button><button data-tab="coverage" aria-pressed="false">Coverage <span id="unknownCount">0</span></button></nav>
  <section id="results" aria-label="Analysis results"></section>
  <footer><strong>YOU MAKE THE CALL.</strong><p>Warden explains supported source risks. It does not certify runtime safety or cross-mod compatibility.</p></footer>
</main><script nonce="${nonce}" src="${asset('panel.js')}"></script>
</body></html>`;
}
module.exports = {panelHtml};
