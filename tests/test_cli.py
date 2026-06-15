"""CLI helpers: argument parser, file I/O, hour normalization, logging."""

import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.utils.cli import (
    build_parser,
    configure_logging,
    expand_hours,
    load_request,
    write_result,
)


SAMPLE_PAYLOAD = {
    "vehicle": {"capacity": 50, "current_soc_pct": 40, "target_soc_pct": 70, "max_power_kw": 11.0},
    "forecast": [{"hour": "10:00", "price": 0.3, "solar": 0.0, "confidence": 1.0}],
    "params": {"confidence_floor": 0.95},
}


class BuildParserTests(unittest.TestCase):

    def test_defaults(self):
        args = build_parser().parse_args([])

        self.assertIsNone(args.input)
        self.assertIsNone(args.output)
        self.assertFalse(args.verbose)

    def test_flags(self):
        args = build_parser().parse_args(["-i", "in.json", "-o", "out.json", "-v"])

        self.assertEqual(args.input, Path("in.json"))
        self.assertEqual(args.output, Path("out.json"))
        self.assertTrue(args.verbose)

    def test_version_flag_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            build_parser().parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)


class LoadRequestTests(unittest.TestCase):

    def test_loads_from_file(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "in.json"
            path.write_text(json.dumps(SAMPLE_PAYLOAD))

            raw = load_request(path)

            self.assertEqual(raw["vehicle"]["capacity"], 50)
            # H:MM gets expanded to ISO timestamp.
            self.assertIn("T10:00:00Z", raw["forecast"][0]["hour"])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_request(Path("/nonexistent/path/in.json"))

    def test_loads_from_stdin(self):
        fake_stdin = io.StringIO(json.dumps(SAMPLE_PAYLOAD))
        fake_stdin.isatty = lambda: False  # type: ignore[method-assign]

        with patch.object(sys, "stdin", fake_stdin):
            raw = load_request(None)

        self.assertEqual(raw["vehicle"]["capacity"], 50)

    def test_tty_stdin_raises_system_exit(self):
        fake_stdin = io.StringIO("")
        fake_stdin.isatty = lambda: True  # type: ignore[method-assign]

        with patch.object(sys, "stdin", fake_stdin), self.assertRaises(SystemExit):
            load_request(None)


class ExpandHoursTests(unittest.TestCase):

    def test_short_hour_expanded(self):
        raw = {"forecast": [{"hour": "6:30", "price": 0.2, "solar": 0.0, "confidence": 1.0}]}

        expanded = expand_hours(raw)

        self.assertRegex(expanded["forecast"][0]["hour"], r"^\d{4}-\d{2}-\d{2}T06:30:00Z$")

    def test_iso_timestamp_left_alone(self):
        iso = "2026-06-12T08:00:00Z"
        raw = {"forecast": [{"hour": iso, "price": 0.2, "solar": 0.0, "confidence": 1.0}]}

        expanded = expand_hours(raw)

        self.assertEqual(expanded["forecast"][0]["hour"], iso)

    def test_empty_forecast_handled(self):
        raw = {"forecast": []}

        self.assertEqual(expand_hours(raw), {"forecast": []})

    def test_missing_forecast_key_handled(self):
        self.assertEqual(expand_hours({}), {})


class WriteResultTests(unittest.TestCase):

    def test_writes_to_file_and_creates_parent_dir(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "out.json"

            write_result([{"hour": "x", "charging_power": 1.0}], path)

            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertEqual(data[0]["charging_power"], 1.0)

    def test_writes_to_stdout_when_path_is_none(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            write_result({"ok": True}, None)

        self.assertIn("\"ok\": true", buf.getvalue())


class ConfigureLoggingTests(unittest.TestCase):

    def test_runs_without_error(self):
        # Just exercises the call; basicConfig is idempotent.
        configure_logging(verbose=True)
        configure_logging(verbose=False)


if __name__ == "__main__":
    unittest.main()
