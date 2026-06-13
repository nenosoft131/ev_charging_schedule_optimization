"""PlannerService — turns a forecast into a per-hour charging plan."""

import unittest
from datetime import datetime, timedelta

from app.model.models import Hour
from app.service.planner_service import PlannerService


START = datetime(2026, 6, 12, 10, 0, 0)


def forecast(rows):
    """rows = [(price, solar, confidence), ...]"""
    return [
        Hour(hour=START + timedelta(hours=i), price=p, solar=s, confidence=c)
        for i, (p, s, c) in enumerate(rows)
    ]


def plan(fc, *, current=40, target=70, capacity=50, p_max=11, confidence_floor=0.95):
    return PlannerService().plan_charging(
        forecast=fc,
        current_soc_pct=current,
        target_soc_pct=target,
        capacity_kwh=capacity,
        max_power_kw=p_max,
        confidence_floor=confidence_floor,
    )


class PlannerServiceTests(unittest.TestCase):

    def test_no_hour_exceeds_max_power(self):
        schedule = plan(forecast([(0.30, 0.0, 1.0)] * 6))

        for row in schedule:
            self.assertLessEqual(row["chargingPower"], 11.0)
            self.assertGreaterEqual(row["chargingPower"], 0)

    def test_total_energy_meets_buffered_target(self):
        # Need (70 - 40)/100 * 50 / 0.95 ≈ 15.79 kWh delivered.
        schedule = plan(forecast([(0.30, 0.0, 1.0)] * 6))

        total = sum(row["chargingPower"] for row in schedule)
        self.assertGreaterEqual(total, 15.79 - 0.05)

    def test_cheapest_hour_is_filled_first(self):
        schedule = plan(
            forecast([(0.50, 0.0, 1.0), (0.10, 0.0, 1.0), (0.40, 0.0, 1.0)]),
            target=50,
        )

        powers = [row["chargingPower"] for row in schedule]
        self.assertEqual(powers.index(max(powers)), 1)

    # def test_total_charge_never_exceeds_battery_headroom(self):
    #     # Vehicle: (100 - 10)% of 100 kWh = 90 kWh required.
    #     #          buffered demand: 90 / 0.95 ≈ 94.7 kWh (wants more).
    #     # Battery has only 90 kWh of physical room (already 10% full).
    #     # → schedule must cap total allocation at 90 kWh, not 94.7.
    #     schedule = plan(
    #         forecast([(0.30, 0.0, 1.0)] * 10),
    #         current=10,
    #         target=100,
    #         capacity=100,
    #     )

    #     total = sum(row["chargingPower"] for row in schedule)
    #     self.assertLessEqual(
    #         total,
    #         90.0 + 1e-6,
    #         f"Scheduled {total:.2f} kWh; battery only has 90 kWh of room.",
    #     )

    def test_solar_is_used_before_priced_grid(self):
        # 4 kW free solar in a single hour should fill before grid kicks in.
        schedule = plan(forecast([(0.40, 4.0, 1.0)]), target=48)

        self.assertGreater(schedule[0]["chargingPower"], 0)


if __name__ == "__main__":
    unittest.main()
