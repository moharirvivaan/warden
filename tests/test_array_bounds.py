"""Late bounds-check review against real Cocos SDK declarations."""
import unittest
import hashlib
import json
import subprocess
import test_analyzer

PREFIX = test_analyzer.PREFIX


class ArrayBoundsTests(unittest.TestCase):
    fixture = test_analyzer.AnalyzerTests.fixture
    scan = test_analyzer.AnalyzerTests.scan
    run_warden = test_analyzer.AnalyzerTests.run_warden

    def test_if_initializer_effects_do_not_authorize_a_bounds_repair(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void changingArray(CCArray* data, unsigned i) {
    auto object = data->objectAtIndex(i);
    if (int marker = (data->removeLastObject(), 0); i >= data->count()) return;
    (void)object;
}
'''})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("guard" in u["reason"] and "effect" in u["reason"]
                            for u in report["unknown"]))

    def test_exit_local_to_if_initializer_cannot_be_moved_before_its_declaration(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
int scopedExit(CCArray* data, unsigned i) {
    auto object = data->objectAtIndex(i);
    if (int exitCode = 7; i >= data->count()) return exitCode;
    return 0;
}
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report["findings"]), 1)
        self.assertNotIn("repair", report["findings"][0],
                         "An initializer-local exit must not be inserted outside its scope")

    def test_bounds_check_after_access_produces_review(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
void paging(cocos2d::CCArray* data, unsigned first, unsigned last) {
    for (unsigned i=first; i<last; ++i) {
        auto object = data->objectAtIndex(i);
        if (i >= data->count() || object == nullptr) break;
        object->setTag(42);
    }
}
'''})
        self.assertEqual(r.returncode, 0, r.stdout)
        findings = [f for f in report["findings"] if f["rule"] == "geode.late-array-bounds-check"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["evidence"], "inferred_risk")
        self.assertEqual(findings[0]["severity"], "review")
        self.assertEqual({l["role"] for l in findings[0]["related"]}, {"late_guard"})
        self.assertIn("before", findings[0]["suggestion"])

    def test_author_style_preceding_guard_is_not_flagged(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
void paging(cocos2d::CCArray* data, unsigned first, unsigned last) {
    for (unsigned i=first; i<last; ++i) {
        if (i >= data->count()) break;
        auto object = data->objectAtIndex(i);
        if (object == nullptr) break;
        object->setTag(42);
    }
}
'''})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(report["findings"], [])

    def test_reviewed_repair_preserves_null_exit_and_reparses(self):
        source = PREFIX + '''
void paging(cocos2d::CCArray* data, unsigned first, unsigned last) {
    for (unsigned i=first; i<last; ++i) {
        auto object = data->objectAtIndex(i);
        if (i >= data->count() || object == nullptr) break;
        object->setTag(42);
    }
}
'''
        project,build=self.fixture({"main.cpp":source})
        result=self.run_warden("inspect",project,"-p",build,"--format","json")
        finding=json.loads(result.stdout)["findings"][0]
        self.assertIn("repair",finding)
        repair=finding["repair"]
        original=(project/"main.cpp").read_bytes()
        self.assertEqual(repair["sha256"],hashlib.sha256(original).hexdigest())
        self.assertEqual(original[repair["start_byte"]:repair["end_byte"]].decode(),repair["expected"])
        repaired=original[:repair["start_byte"]]+repair["replacement"].encode()+original[repair["end_byte"]:]
        self.assertIn("if (i >= data->count() || object == nullptr) break;",repaired.decode())
        self.assertLess(repaired.index(b"if (i >= data->count())"),repaired.index(b"objectAtIndex"))
        (project/"main.cpp").write_bytes(repaired)
        after=self.run_warden("inspect",project,"-p",build,"--format","json")
        report=json.loads(after.stdout)
        self.assertEqual(after.returncode,0,after.stdout)
        self.assertEqual(report["findings"],[])
        self.assertTrue(all(f["status"]=="complete" for f in report["files"]))

    def test_ref_array_member_late_guard_matches_actual_mod_shape(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
struct Paging { Ref<cocos2d::CCArray> m_data;
void trim(unsigned first,unsigned last) {
    for(unsigned i=first;i<last;++i) {
        auto object=m_data->objectAtIndex(i);
        if(i>=m_data->count() || object==nullptr) break;
    }
} };
'''})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(report["findings"]), 1)

    def test_terminal_counts_ownership_and_bounds_separately(self):
        project,build=self.fixture({"main.cpp":PREFIX+'''
void queued(){auto node=cocos2d::CCNode::create();Loader::get()->queueInMainThread([node](){node->setTag(42);});}
void paging(cocos2d::CCArray* data,unsigned i){auto object=data->objectAtIndex(i);if(i>=data->count())return;}
'''})
        report=json.loads(self.run_warden("inspect",project,"-p",build,"--format","json").stdout)
        self.assertEqual(len(report["findings"]),2)
        terminal=self.run_warden("inspect",project,"-p",build).stdout
        self.assertIn("1 ownership reviews",terminal)
        self.assertIn("1 bounds reviews",terminal)

    def test_valid_loop_guard_suppresses_redundant_late_guard(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
void guarded(cocos2d::CCArray* data) {
    for (unsigned i=0; i<data->count(); ++i) {
        auto object = data->objectAtIndex(i);
        if (i >= data->count() || object == nullptr) break;
    }
}
'''})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(report["findings"], [])

    def test_prior_return_guard_suppresses_late_guard(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
void guarded(cocos2d::CCArray* data, unsigned i) {
    if (i >= data->count()) return;
    auto object = data->objectAtIndex(i);
    if (i >= data->count() || object == nullptr) return;
}
'''})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(report["findings"], [])

    def test_lookalike_methods_and_different_array_do_not_match(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
struct Other { int* objectAtIndex(unsigned); unsigned count(); };
void other(Other* data, unsigned i) {
    auto object=data->objectAtIndex(i); if(i>=data->count()) return;
}
void unrelated(cocos2d::CCArray* first, cocos2d::CCArray* second, unsigned i) {
    auto object=first->objectAtIndex(i); if(i>=second->count()) return;
}
'''})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(report["findings"], [])

    def test_guard_with_non_terminating_path_is_unknown(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
void conditional(cocos2d::CCArray* data, unsigned i, bool stop) {
    auto object=data->objectAtIndex(i);
    if(i>=data->count()) { if(stop) return; }
}
'''})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("bounds" in u["reason"] for u in report["unknown"]))

    def test_returning_initialized_object_has_no_unsafe_repair(self):
        r,report=self.scan({"main.cpp":PREFIX+'''
cocos2d::CCObject* guarded(cocos2d::CCArray* data,unsigned i){
    auto object=data->objectAtIndex(i);
    if(i>=data->count()) return object;
    return object;
}
'''})
        self.assertEqual(r.returncode,0,r.stdout)
        self.assertEqual(len(report["findings"]),1)
        self.assertNotIn("repair",report["findings"][0])

    def test_mutation_inside_enclosing_guard_remains_unknown(self):
        r,report=self.scan({"main.cpp":PREFIX+'''
void guarded(cocos2d::CCArray* data,unsigned i){
    if(i<data->count()){
        ++i;
        auto object=data->objectAtIndex(i);
        if(i>=data->count()) return;
    }
}
'''})
        self.assertEqual(r.returncode,1,r.stdout)
        self.assertEqual(report["findings"],[])
        self.assertTrue(any("bounds" in u["reason"] for u in report["unknown"]))

    def test_mutation_between_access_and_guard_is_unknown(self):
        r, report = self.scan({"main.cpp": PREFIX + '''
void changed(cocos2d::CCArray* data, unsigned i) {
    auto object=data->objectAtIndex(i);
    ++i;
    if(i>=data->count()) return;
}
'''})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("bounds" in u["reason"] for u in report["unknown"]))

    def test_compound_guard_effects_are_not_bounds_proof_or_repair(self):
        for guards in [
            'if(i>=data->count() || (++i,false)) return;\n    auto object=data->objectAtIndex(i);\n    if(i>=data->count()) return;',
            'auto object=data->objectAtIndex(i);\n    if((++i,false) || i>=data->count()) return;',
        ]:
            with self.subTest(guards=guards):
                r,report=self.scan({"main.cpp":PREFIX+'\nvoid changed(cocos2d::CCArray* data,unsigned i){\n    '+guards+'\n}\n'})
                self.assertEqual(r.returncode,1,r.stdout)
                self.assertEqual(report["findings"],[])
                self.assertTrue(any("bounds" in u["reason"] for u in report["unknown"]))

    def test_bindings_only_array_call_resolves_actual_sdk_provenance(self):
        r,report=self.scan({"main.cpp":'''#include <Geode/Bindings.hpp>
void paging(cocos2d::CCArray* data,unsigned i){
    auto object=data->objectAtIndex(i);
    if(i>=data->count() || object==nullptr) return;
}
'''})
        self.assertEqual(r.returncode,0,r.stdout)
        self.assertEqual(report["toolchain"]["sdk"],"5.11.1")
        self.assertEqual(len(report["findings"]),1)


class HistoricalBoundsTests(unittest.TestCase):
    run_warden=test_analyzer.AnalyzerTests.run_warden

    def test_actual_betterinfo_source_repair_with_declared_sdk(self):
        # Fixed revision is a separate real source snapshot, not an edited fixture.
        roots=[test_analyzer.ROOT/".deps/betterinfo-original-sdk",test_analyzer.ROOT/".deps/betterinfo-bounds-fixed"]
        builds=[roots[0]/"build/bounds-only",roots[1]/"build"]
        if any(not (b/"compile_commands.json").exists() for b in builds):
            self.skipTest("Historical SDK-backed source configurations are absent; no substituted headers.")
        lock = json.loads((test_analyzer.ROOT / "docs/toolchain-lock.json").read_text())["benchmarks"]["betterinfo_bounds"]
        source = "src/layers/_bases/BIViewLayer.cpp"
        for root, revision in zip(roots, [lock["baseline_revision"], lock["repair_revision"]]):
            head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            self.assertEqual(head, revision, "Historical snapshot must match the pinned revision")
            pinned = subprocess.check_output(["git", "-C", str(root), "show", revision + ":" + source])
            self.assertEqual((root / source).read_bytes(), pinned, "Historical source has local edits")
        before,after=[json.loads(self.run_warden("inspect",root,"-p",build,"--format","json").stdout) for root,build in zip(roots,builds)]
        for report in [before,after]:
            self.assertEqual(report["toolchain"]["sdk"],"5.10.1")
            units=[f for f in report["files"] if f["kind"]=="translation_unit"]
            self.assertEqual([(u["file"],u["status"]) for u in units],[("src/layers/_bases/BIViewLayer.cpp","complete")])
        bounds=[f for f in before["findings"] if f["rule"]=="geode.late-array-bounds-check"]
        self.assertEqual(len(bounds),1)
        self.assertEqual(bounds[0]["location"]["line"],206)
        self.assertIn("repair",bounds[0])
        self.assertEqual([f for f in after["findings"] if f["rule"]=="geode.late-array-bounds-check"],[])


if __name__ == "__main__":
    unittest.main()
