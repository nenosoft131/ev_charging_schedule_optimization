"""Simple tests for the Streamlit web UI helper functions.

We only exercise the pure (non-UI) helpers: forecast parsing and the
feasibility lookup. Importing ``web.streamlit_app`` runs Streamlit code at
module level in "bare mode" (no ScriptRunContext) — that's harmless, it just
emits warnings which we silence here.
"""

from __future__ import annotations

import io
import json
import logging
import unittest
import warnings

# Silence Streamlit's bare-mode warnings before the import.
warnings.filterwarnings("ignore")
logging.getLogger("streamlit").setLevel(logging.ERROR)

from web import streamlit_app  # noqa: E402


VALID_FORECAST = [
    {"hour": "2026-06-12T10:00:00Z", "price": 0.3, "solar": 0.0, "confidence": 1.0},
    {"hour": "2026-06-12T11:00:00Z", "price": 0.2, "solar": 1.0, "confidence": 0.9},
]

VALID_PAYLOAD = {
    "vehicle": {"capacity": 50, "current_soc_pct": 40, "target_soc_pct": 70, "max_power_kw": 11.0},
    "forecast": VALID_FORECAST,
    "params": {"confidence_floor": 0.95},
}


def _csv(text: str) -> io.BytesIO:
    buf = io.BytesIO(text.encode("utf-8"))
    buf.name = "f.csv"
    return buf


class ParseForecastFromCSVTests(unittest.TestCase):

    def test_lowercase_headers(self):
        result = streamlit_app.parse_forecast_from_csv(
            _csv("hour,price,solar,confidence\n6:00,0.32,0.0,1.0\n")
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["price"], 0.32)
        self.assertEqual(result[0]["hour"], "6:00")

    def test_uppercase_headers_with_spaces(self):
        result = streamlit_app.parse_forecast_from_csv(
            _csv("Hour, Price, Solar, Confidence\n6:00, 0.32, 0.0, 1.0\n")
        )
        self.assertEqual(result[0]["hour"], "6:00")
        self.assertEqual(result[0]["confidence"], 1.0)

    def test_missing_column_raises(self):
        with self.assertRaises(ValueError) as ctx:
            streamlit_app.parse_forecast_from_csv(
                _csv("hour,price,solar\n6:00,0.32,0.0\n")
            )
        self.assertIn("missing", str(ctx.exception).lower())

    def test_extra_column_raises(self):
        with self.assertRaises(ValueError) as ctx:
            streamlit_app.parse_forecast_from_csv(
                _csv("hour,price,solar,confidence,notes\n6:00,0.32,0.0,1.0,x\n")
            )
        self.assertIn("unexpected", str(ctx.exception).lower())


class ParseForecastFromJSONTests(unittest.TestCase):

    def test_bare_array(self):
        self.assertEqual(
            streamlit_app.parse_forecast_from_json(json.dumps(VALID_FORECAST)),
            VALID_FORECAST,
        )

    def test_payload_dict_extracts_forecast(self):
        text = json.dumps({"forecast": VALID_FORECAST, "vehicle": {}})
        self.assertEqual(streamlit_app.parse_forecast_from_json(text), VALID_FORECAST)

    def test_invalid_shape_raises(self):
        with self.assertRaises(ValueError):
            streamlit_app.parse_forecast_from_json('"just a string"')

    def test_malformed_json_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            streamlit_app.parse_forecast_from_json("{not valid")


class ComputeFeasibilityTests(unittest.TestCase):

    def test_valid_payload_returns_report(self):
        report = streamlit_app.compute_feasibility(VALID_PAYLOAD)

        self.assertIsNotNone(report)
        self.assertTrue(report.is_feasible)
        self.assertGreater(report.energy_required_kwh, 0)

    def test_invalid_payload_returns_none(self):
        bad = {**VALID_PAYLOAD, "vehicle": {**VALID_PAYLOAD["vehicle"], "capacity": -1}}

        self.assertIsNone(streamlit_app.compute_feasibility(bad))

    def test_empty_forecast_returns_none(self):
        empty = {**VALID_PAYLOAD, "forecast": []}

        self.assertIsNone(streamlit_app.compute_feasibility(empty))


class RenderFeasibilityTests(unittest.TestCase):

    def test_none_report_returns_early(self):
        # Should be a no-op (and not touch any Streamlit widgets).
        self.assertIsNone(streamlit_app.render_feasibility(None))


# ---------------------------------------------------------------------------
# UI flow tests via Streamlit's AppTest harness
# ---------------------------------------------------------------------------

SCRIPT = "web/streamlit_app.py"


def _msg(elements) -> str:
    return " | ".join(getattr(e, "value", "") for e in elements)


class StreamlitUIFlowTests(unittest.TestCase):

    def _new(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(SCRIPT)

    def test_app_boots_without_exception(self):
        at = self._new().run(timeout=20)

        self.assertFalse(at.exception)

    def test_default_click_produces_schedule(self):
        at = self._new().run(timeout=20)
        at.button[0].click().run(timeout=20)

        self.assertFalse(at.exception)
        self.assertIn("Schedule generated", _msg(at.success))

    def test_invalid_json_shows_parse_error(self):
        at = self._new().run(timeout=20)
        at.text_area[0].set_value("{not valid")
        at.button[0].click().run(timeout=20)

        self.assertIn("Could not parse", _msg(at.error))

    def test_empty_forecast_shows_alert(self):
        at = self._new().run(timeout=20)
        at.text_area[0].set_value("[]")
        at.button[0].click().run(timeout=20)

        # Empty forecast triggers the Alert dict path in render_result.
        self.assertTrue(at.warning)

    def test_validation_error_shows_error_panel(self):
        # solar: -1 violates Hour's ge=0 constraint → run() returns {"error": [...]}.
        bad = [{"hour": "10:00", "price": 0.3, "solar": -1, "confidence": 1.0}]
        at = self._new().run(timeout=20)
        at.text_area[0].set_value(json.dumps(bad))
        at.button[0].click().run(timeout=20)

        self.assertIn("Validation error", _msg(at.error))

    def test_csv_mode_without_upload_shows_error(self):
        at = self._new().run(timeout=20)
        at.radio[0].set_value("Upload CSV").run(timeout=20)
        at.button[0].click().run(timeout=20)

        self.assertIn("Please upload", _msg(at.error))

    def test_infeasible_target_shows_feasibility_warning(self):
        # Tiny max_power against a 100% target → buffered demand > capacity.
        at = self._new().run(timeout=20)
        at.number_input[0].set_value(100.0)   # capacity
        at.slider[0].set_value(0)             # current_soc
        at.slider[1].set_value(100)           # target_soc
        at.number_input[1].set_value(1.0)     # max_power
        at.button[0].click().run(timeout=20)

        self.assertIn("exceeds", _msg(at.warning).lower())

    def test_csv_upload_produces_schedule(self):
        # Cover the parse_forecast_from_csv branch of the main flow.
        csv_bytes = (
            b"hour,price,solar,confidence\n"
            b"6:00,0.32,0.0,1.0\n"
            b"7:00,0.28,0.0,1.0\n"
            b"8:00,0.25,0.2,0.95\n"
        )

        at = self._new().run(timeout=20)
        at.radio[0].set_value("Upload CSV").run(timeout=20)
        at.file_uploader[0].set_value([("t.csv", csv_bytes, "text/csv")])
        at.button[0].click().run(timeout=20)

        self.assertFalse(at.exception)
        self.assertIn("Schedule generated", _msg(at.success))


if __name__ == "__main__":
    unittest.main()
