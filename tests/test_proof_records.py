"""Validate the evidence format with synthetic records, never runtime claims."""
import copy
import json
from pathlib import Path
import unittest
import jsonschema

SCHEMA = json.loads((Path(__file__).resolve().parents[1] /
                     "examples/compatibility-proof/run-record.schema.json").read_text())


class ProofRecordTests(unittest.TestCase):
    def record(self):
        return {"run_id": "synthetic-schema-test", "scenario": "combined",
                "package_hashes": {"warden.proof-remover": "a" * 64,
                                   "warden.proof-consumer": "b" * 64},
                "versions": {"sdk": "5.11.1", "loader": "5.11.1", "game": "2.2081", "node_ids": "1.23.3"},
                "architecture": "arm64", "operation_order": [], "outcome": "unknown",
                "artifacts": [], "intended_behavior_observed": None,
                "human_review_status": "pending", "notes": "Synthetic fixture only"}

    def test_combined_run_requires_actual_pair_hashes(self):
        # Permitting an empty hash map makes evidence unverifiable.
        record = self.record()
        jsonschema.validate(record, SCHEMA)
        record["package_hashes"] = {}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(record, SCHEMA)

    def test_consumer_alternatives_cannot_be_combined(self):
        record = self.record()
        record["package_hashes"]["warden.proof-consumer-guarded"] = "c" * 64
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(record, SCHEMA)

    def test_every_scenario_accepts_only_its_selected_package_set(self):
        choices = {"baseline": [], "remover-alone": ["warden.proof-remover"],
                   "consumer-alone": ["warden.proof-consumer"], "guarded-alone": ["warden.proof-consumer-guarded"],
                   "combined": ["warden.proof-remover", "warden.proof-consumer"],
                   "combined-repeat": ["warden.proof-remover", "warden.proof-consumer"],
                   "combined-guarded": ["warden.proof-remover", "warden.proof-consumer-guarded"]}
        for scenario, ids in choices.items():
            record = self.record()
            record.update(scenario=scenario, package_hashes={mod_id: "d" * 64 for mod_id in ids})
            jsonschema.validate(record, SCHEMA)
            invalid = copy.deepcopy(record)
            invalid["package_hashes"]["warden.proof-consumer" if scenario == "baseline" else "warden.proof-consumer-guarded"] = "e" * 64
            if invalid["package_hashes"] != record["package_hashes"] and set(invalid["package_hashes"]) != set(ids):
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(invalid, SCHEMA)


if __name__ == "__main__":
    unittest.main()
