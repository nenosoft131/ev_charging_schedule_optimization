"""app.main — run() pipeline glue and the CLI entry point."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.main import main, run


VALID_INPUT = {
    "vehicle": {"capacity": 50, "current_soc_pct": 40, "target_soc_pct": 70, "max_power_kw": 11.0},
    "forecast": [
        {"hour": "2026-06-12T10:00:00Z", "price": 0.3, "solar": 0.0, "confidence": 1.0},
        {"hour": "2026-06-12T11:00:00Z", "price": 0.2, "solar": 1.0, "confidence": 0.9},
    ],
    "params": {"confidence_floor": 0.95},
}


class RunPipelineTests(unittest.TestCase):

    def test_happy_path_returns_schedule_list(self):
        result = run(VALID_INPUT)

        self.assertIsInstance(result, list)
        self.assertTrue(all("charging_power" in row for row in result))

    def test_invalid_input_returns_error_dict(self):
        bad = {**VALID_INPUT, "vehicle": {**VALID_INPUT["vehicle"], "capacity": -1}}

        result = run(bad)

        self.assertIn("error", result)
        self.assertIsInstance(result["error"], list)

    def test_empty_forecast_returns_alert(self):
        result = run({**VALID_INPUT, "forecast": []})

        self.assertIn("Alert", result)

    def test_infeasible_target_logs_warning_but_still_returns_schedule(self):
        # Tiny horizon vs. big SoC gap → infeasible buffered demand.
        payload = {
            **VALID_INPUT,
            "vehicle": {"capacity": 100, "current_soc_pct": 10, "target_soc_pct": 100, "max_power_kw": 9.0},
            "forecast": [VALID_INPUT["forecast"][0]],  # only 1 hour
        }
        with self.assertLogs("ev_scheduler", level="WARNING") as logs:
            result = run(payload)

        self.assertIsInstance(result, list)
        self.assertTrue(any("Feasibility warning" in m for m in logs.output))


class CLIMainTests(unittest.TestCase):

    def test_main_succeeds_with_file_input_and_output(self):
        with TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "in.json"
            out_path = Path(tmp) / "out.json"
            in_path.write_text(json.dumps(VALID_INPUT))

            code = main(["-i", str(in_path), "-o", str(out_path), "-v"])

            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists())
            self.assertIsInstance(json.loads(out_path.read_text()), list)

    def test_main_returns_1_for_missing_input_file(self):
        code = main(["-i", "/nonexistent/path/in.json"])

        self.assertEqual(code, 1)

    def test_main_returns_1_for_invalid_json(self):
        with TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "in.json"
            in_path.write_text("{not valid json")

            code = main(["-i", str(in_path)])

        self.assertEqual(code, 1)

    def test_main_returns_1_when_run_returns_error(self):
        with TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "in.json"
            bad = {**VALID_INPUT, "vehicle": {**VALID_INPUT["vehicle"], "capacity": -1}}
            in_path.write_text(json.dumps(bad))

            # Capture stdout so we don't pollute test output.
            with patch("sys.stdout", io.StringIO()):
                code = main(["-i", str(in_path)])

        self.assertEqual(code, 1)

    def test_main_writes_to_stdout_when_no_output_path(self):
        with TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "in.json"
            in_path.write_text(json.dumps(VALID_INPUT))

            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = main(["-i", str(in_path)])

        self.assertEqual(code, 0)
        self.assertIn("charging_power", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
