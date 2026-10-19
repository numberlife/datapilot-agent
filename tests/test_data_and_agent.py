import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import agent
from app.data import initialize_database, inspect_dataset, run_readonly_query


class SQLiteFixture:
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATABASE_PATH": str(Path(self.temp_dir.name) / "test.sqlite3")})
        self.env.start()
        initialize_database()

    def tearDown(self):
        self.env.stop()
        self.temp_dir.cleanup()


class DataToolTests(SQLiteFixture, unittest.TestCase):
    def test_dataset_can_be_inspected_and_queried(self):
        info = inspect_dataset()
        self.assertEqual(info["rows"], 24)
        result = run_readonly_query(
            "SELECT region, SUM(revenue) AS revenue FROM sales GROUP BY region ORDER BY revenue DESC"
        )
        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(result["rows"][0]["region"], "North")

    def test_query_cannot_read_sqlite_metadata(self):
        with self.assertRaises(sqlite3.DatabaseError):
            run_readonly_query("SELECT name FROM sqlite_master")

    def test_query_rejects_multiple_statements(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            run_readonly_query("SELECT * FROM sales; DROP TABLE sales")

    def test_agent_runs_a_tool_and_returns_trace(self):
        tool_response = {
            "choices": [{"message": {"tool_calls": [{
                "id": "call-1",
                "function": {"name": "inspect_dataset", "arguments": "{}"},
            }]}}]
        }
        answer_response = {"choices": [{"message": {"content": "The sample contains 24 sales rows."}}]}
        with patch.object(agent, "_config", return_value=("https://example.invalid/v1", "key", "model")), \
                patch.object(agent, "_post_json", side_effect=[tool_response, answer_response]):
            result = agent.analyze("How many rows are in the sample?")
        self.assertEqual(result["answer"], "The sample contains 24 sales rows.")
        self.assertEqual(result["trace"][0]["tool"], "inspect_dataset")
        self.assertEqual(result["trace"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
