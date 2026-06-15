"""DataValidator — input parsing and early-exit detection."""

import unittest

from app.model.models import ScheduleRequest
from app.utils.data_validator import DataValidator


VALID_INPUT = {
    "vehicle": {"capacity": 50, "current_soc_pct": 40, "target_soc_pct": 70, "max_power_kw": 11.0},
    "forecast": [
        {"hour": "2026-06-12T10:00:00Z", "price": 0.3, "solar": 0.0, "confidence": 1.0},
    ],
    "params": {"confidence_floor": 0.95},
}


class DataValidatorTests(unittest.TestCase):

    def test_valid_input_returns_parsed_request(self):
        needs_scheduling, result, _ = DataValidator.validate_data(VALID_INPUT)

        self.assertTrue(needs_scheduling)
        self.assertIsInstance(result, ScheduleRequest)

    def test_empty_forecast_returns_final_empty_schedule(self):
        payload = {**VALID_INPUT, "forecast": []}

        needs_scheduling, result, _ = DataValidator.validate_data(payload)

        self.assertFalse(needs_scheduling)
        self.assertEqual(result["schedule"], [])

    def test_already_at_target_returns_final_zero_schedule(self):
        payload = {**VALID_INPUT, "vehicle": {**VALID_INPUT["vehicle"], "current_soc_pct": 80}}

        needs_scheduling, result, _ = DataValidator.validate_data(payload)

        self.assertFalse(needs_scheduling)
        self.assertTrue(all(row["charging_power"] == 0.0 for row in result["schedule"]))

    def test_bad_input_raises(self):
        payload = {**VALID_INPUT, "vehicle": {**VALID_INPUT["vehicle"], "capacity": -1}}

        with self.assertRaises(ValueError):
            DataValidator.validate_data(payload)


if __name__ == "__main__":
    unittest.main()
