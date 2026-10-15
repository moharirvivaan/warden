"""Real selected-source catalog contracts; no runtime compatibility claim."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class InteractionCatalogTests(unittest.TestCase):
    def test_three_real_pinned_sources_have_verified_evidence(self):
        manifest = json.loads((ROOT / 'build/interaction-catalog/manifest.json').read_text())
        self.assertEqual(len(manifest['entries']), 3)
        reports = {}
        for entry in manifest['entries']:
            raw = (ROOT / 'build/interaction-catalog' / entry['report_file']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['report_sha256'])
            report = json.loads(raw)
            self.assertEqual(report['toolchain']['sdk'], '5.10.1')
            self.assertEqual(report['project_root'], '')
            self.assertEqual(entry['runtime_status'], 'not_run')
            self.assertTrue(entry['source_files'])
            reports[report['mod']['id']] = report
            self.assertFalse(any(d['severity'] in ('error','fatal') for f in report['files'] for d in f['diagnostics']))
        node = reports['geode.node-ids']
        init = next(h for h in node['hooks'] if h['target_class'] == 'LevelInfoLayer' and h['method'] == 'init')
        self.assertTrue(init['behavior']['forwarding_calls'])
        self.assertEqual(init['behavior']['priority_requests'][0]['pre_order_value'], 2000)
        server = reports['km7dev.server_api']
        self.assertTrue(any(h['method'] == 'send' for h in server['hooks']))
        self.assertFalse(any(h['target_class'] == 'LevelInfoLayer' for h in server['hooks']))
