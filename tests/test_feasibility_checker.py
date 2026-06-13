"""FeasibilityChecker — does the requested target fit in the forecast?"""

import unittest
from datetime import datetime, timedelta

from app.model.models import Hour, ScheduleRequest, SchedulerParams, Vehicle
from app.utils.feasibility_checker import FeasibilityChecker


START = datetime(2026, 6, 12, 10, 0, 0)


def make_request(*, current=40, target=70, horizon=6, conf=1.0, confidence_floor=0.95):
    return ScheduleRequest(
        vehicle=Vehicle(capacity=50, current_soc_pct=current, target_soc_pct=target, max_power_kw=11.0),
        forecast=[
            Hour(hour=START + timedelta(hours=i), price=0.25, solar=0.0, confidence=conf)
            for i in range(horizon)
        ],
        params=SchedulerParams(confidence_floor=confidence_floor),
    )


class FeasibilityCheckerTests(unittest.TestCase):

    def test_comfortable_target_is_feasible(self):
        # Need 15 kWh; forecast can deliver 6 * 11 = 66 kWh at full confidence.
        report = FeasibilityChecker.check(make_request())

        self.assertTrue(report.is_feasible)
        self.assertIsNone(report.warning)

    def test_infeasible_target_emits_warning(self):
        # Need 30 kWh; only 2 * 11 * 0.1 = 2.2 kWh expected.
        report = FeasibilityChecker.check(make_request(current=40, target=100, horizon=2, conf=0.1))

        self.assertFalse(report.is_feasible)
        self.assertIn("Infeasible target", report.warning)

    def test_required_kwh_exceeds_max_forecast_capacity(self):
        # Vehicle: (90 - 10)% of 50 kWh = 40 kWh required.
        #          buffered: 40 / 0.95 ≈ 42.1 kWh.
        # Forecast: 3 hours × 11 kW × conf 1.0 = 33 kWh max possible.
        # → 42.1 kWh demand > 33 kWh supply → infeasible by ~9 kWh.
        report = FeasibilityChecker.check(
            make_request(current=10, target=90, horizon=3, conf=1.0)
        )

        self.assertFalse(report.is_feasible)
        self.assertIsNotNone(report.warning)
        self.assertAlmostEqual(report.energy_required_kwh, 40.0, places=2)
        self.assertAlmostEqual(report.max_possible_expected_kwh, 33.0, places=2)
        self.assertGreater(
            report.target_with_buffer_kwh,
            report.max_possible_expected_kwh,
        )

    def test_confidence_floor_inflates_demand(self):
        # 15 kWh required / 0.95 ≈ 15.79 kWh buffered demand.
        report = FeasibilityChecker.check(make_request(confidence_floor=0.95))

        self.assertAlmostEqual(report.target_with_buffer_kwh, 15.0 / 0.95, places=2)


if __name__ == "__main__":
    unittest.main()
