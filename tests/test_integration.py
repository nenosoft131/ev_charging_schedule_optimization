"""End-to-end: validate → feasibility → planning, driven by main.run()."""

import unittest

from app.main import run


SAMPLE_INPUT = {
    "vehicle": {"capacity": 100, "current_soc_pct": 30, "target_soc_pct": 72, "max_power_kw": 9.0},
    "forecast": [
        {"hour": "2026-06-12T06:00:00Z", "price": 0.32, "solar": 0.0, "confidence": 1.00},
        {"hour": "2026-06-12T07:00:00Z", "price": 0.18, "solar": 1.5, "confidence": 0.90},
        {"hour": "2026-06-12T08:00:00Z", "price": 0.16, "solar": 2.8, "confidence": 0.85},
        {"hour": "2026-06-12T09:00:00Z", "price": 0.17, "solar": 4.0, "confidence": 0.70},
        {"hour": "2026-06-12T10:00:00Z", "price": 0.21, "solar": 4.5, "confidence": 0.60},
        {"hour": "2026-06-12T11:00:00Z", "price": 0.27, "solar": 3.2, "confidence": 0.70},
        {"hour": "2026-06-12T12:00:00Z", "price": 0.35, "solar": 1.2, "confidence": 0.85},
        {"hour": "2026-06-12T13:00:00Z", "price": 0.42, "solar": 0.4, "confidence": 0.95},
    ],
    "params": {"confidence_floor": 0.95},
}


class IntegrationTests(unittest.TestCase):

    def test_happy_path_meets_buffered_target(self):
        # Need (72 - 30)/100 * 100 / 0.95 ≈ 44.2 kWh delivered across the horizon.
        result = run(SAMPLE_INPUT)

        total = sum(row["charging_power"] for row in result)
        self.assertGreaterEqual(total, 44.2 - 0.1)

    def test_empty_forecast_short_circuits(self):
        result = run({**SAMPLE_INPUT, "forecast": []})

        self.assertIn("Alert", result)
        self.assertIn("Empty forecast horizon", result["Alert"])


if __name__ == "__main__":
    unittest.main()
