"""The test gate must reject missing evidence, not just assertion failures."""
import importlib.util
import io
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch


def gate_module():
    path = Path(__file__).with_name("run.py")
    spec = importlib.util.spec_from_file_location("warden_test_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def suite_for(*behaviors):
    def method(behavior):
        def run(self):
            if behavior == "skip":
                self.skipTest("historical SDK cache missing")
            elif behavior == "fail":
                self.fail("detector missed supported defect")
            elif behavior == "error":
                raise RuntimeError("setup unavailable")
        return run
    case = type("ExampleContracts", (unittest.TestCase,),
                {"test_" + str(i): method(b) for i, b in enumerate(behaviors)})
    return unittest.defaultTestLoader.loadTestsFromTestCase(case)


class RunnerTests(unittest.TestCase):
    def check(self, *behaviors, strict=False):
        return gate_module().run_suite(suite_for(*behaviors), strict=strict, stream=io.StringIO())

    def test_release_gate_rejects_skipped_benchmark_and_records_reason(self):
        summary = self.check("pass", "skip", strict=True)
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["tests_run"], 2)
        self.assertEqual(summary["skipped"][0]["reason"], "historical SDK cache missing")
        self.assertIn("ExampleContracts.test_1", summary["skipped"][0]["test"])

    def test_development_run_preserves_optional_skip_without_release_claim(self):
        summary = self.check("pass", "skip")
        self.assertEqual(summary["status"], "passed_with_skips")
        self.assertFalse(summary["strict"])

    def test_no_discovered_tests_cannot_pass(self):
        self.assertEqual(self.check(strict=True)["status"], "failed")

    def test_only_skipped_tests_cannot_pass_in_development(self):
        self.assertEqual(self.check("skip")["status"], "failed")

    def test_all_executed_contracts_can_pass(self):
        summary = self.check("pass", "pass", strict=True)
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["failures"], [])
        self.assertEqual(summary["errors"], [])

    def test_assertion_failures_and_setup_errors_remain_failures(self):
        summary = self.check("fail", "error")
        self.assertEqual(summary["status"], "failed")
        self.assertIn("detector missed", summary["failures"][0]["detail"])
        self.assertIn("setup unavailable", summary["errors"][0]["detail"])

    def test_expected_failure_is_not_accepted_as_release_evidence(self):
        @unittest.expectedFailure
        def still_broken(self):
            self.fail("known defect")
        case = type("KnownFailure", (unittest.TestCase,), {"test_known": still_broken})
        summary = gate_module().run_suite(
            unittest.defaultTestLoader.loadTestsFromTestCase(case), strict=True, stream=io.StringIO())
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(len(summary["expected_failures"]), 1)

    def test_actual_historical_benchmark_missing_inputs_fail_the_strict_gate(self):
        import test_analyzer
        import test_array_bounds
        benchmark = test_array_bounds.HistoricalBoundsTests(
            "test_actual_betterinfo_source_repair_with_declared_sdk")
        with tempfile.TemporaryDirectory() as directory, patch.object(test_analyzer, "ROOT", Path(directory)):
            summary = gate_module().run_suite(
                unittest.TestSuite([benchmark]), strict=True, stream=io.StringIO())
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(len(summary["skipped"]), 1)
        self.assertIn("Historical SDK-backed source configurations are absent", summary["skipped"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
