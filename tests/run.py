#!/usr/bin/env python3
"""Run native/SDK Python contracts; strict mode rejects skipped evidence.

This does not run editor tests, launch the game, or certify compatibility.
"""
import argparse
import json
from pathlib import Path
import sys
import unittest


def run_suite(suite, *, strict=False, stream=None):
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    has_execution = result.testsRun > len(result.skipped)
    accepted = result.wasSuccessful() and has_execution
    if strict and (result.skipped or result.expectedFailures):
        accepted = False
    status = "passed" if accepted else "failed"
    if accepted and result.skipped:
        status = "passed_with_skips"
    elif accepted and result.expectedFailures:
        status = "passed_with_expected_failures"
    return {
        "schema_version": 1,
        "scope": "Python contracts; not editor-host or runtime compatibility evidence",
        "strict": strict,
        "status": status,
        "tests_run": result.testsRun,
        "skipped": [{"test": t.id(), "reason": reason} for t, reason in result.skipped],
        "failures": [{"test": t.id(), "detail": detail} for t, detail in result.failures],
        "errors": [{"test": t.id(), "detail": detail} for t, detail in result.errors],
        "expected_failures": [{"test": t.id(), "detail": detail} for t, detail in result.expectedFailures],
        "unexpected_successes": [t.id() for t in result.unexpectedSuccesses],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="Fail if any discovered test is skipped or marked as an expected failure.")
    parser.add_argument("--report", type=Path, help="Write a machine-readable JSON result.")
    args = parser.parse_args()
    suite = unittest.TestLoader().discover(str(Path(__file__).resolve().parent))
    summary = run_suite(suite, strict=args.strict)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nWarden test gate: {summary['status']} "
          f"({summary['tests_run']} tests, {len(summary['skipped'])} skipped, "
          f"{len(summary['expected_failures'])} expected failures)", file=sys.stderr)
    if args.strict and (summary["skipped"] or summary["expected_failures"]):
        print("Strict checks require every discovered test to execute successfully. "
              "Prepare the missing SDK/source inputs; do not count skips as evidence.", file=sys.stderr)
    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
