import json
import unittest
from pathlib import Path

from test_data_and_agent import SQLiteFixture
from app.data import run_readonly_query


class EvaluationCaseTests(SQLiteFixture, unittest.TestCase):
    def test_gold_queries_match_expected_outputs(self):
        cases_path = Path(__file__).resolve().parents[1] / "evals" / "cases.json"
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(case=case["id"]):
                actual = run_readonly_query(case["query"])["rows"]
                if "expected_first_row" in case:
                    self.assertEqual(actual[0], case["expected_first_row"])
                else:
                    self.assertEqual(actual, case["expected_rows"])


if __name__ == "__main__":
    unittest.main()
