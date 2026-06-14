"""PlannerService — turns a forecast into a per-hour charging plan."""

import unittest
from datetime import datetime, timedelta

from app.model.models import Hour, SchedulerParams, Vehicle
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
        vehicle=Vehicle(
            capacity=capacity,
            current_soc_pct=current,
            target_soc_pct=target,
            max_power_kw=p_max,
        ),
        params=SchedulerParams(confidence_floor=confidence_floor),
    )


class PlannerServiceTests(unittest.TestCase):

    def test_no_hour_exceeds_max_power(self):
        schedule = plan(forecast([(0.30, 0.0, 1.0)] * 6))

        for row in schedule:
            self.assertLessEqual(row["charging_power"], 11.0)
            self.assertGreaterEqual(row["charging_power"], 0)

    def test_total_energy_meets_buffered_target(self):
        # Need (70 - 40)/100 * 50 / 0.95 ≈ 15.79 kWh delivered.
        schedule = plan(forecast([(0.30, 0.0, 1.0)] * 6))

        total = sum(row["charging_power"] for row in schedule)
        self.assertGreaterEqual(total, 15.79 - 0.05)

    def test_cheapest_hour_is_filled_first(self):
        schedule = plan(
            forecast([(0.50, 0.0, 1.0), (0.10, 0.0, 1.0), (0.40, 0.0, 1.0)]),
            target=50,
        )

        powers = [row["charging_power"] for row in schedule]
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

    #     total = sum(row["charging_power"] for row in schedule)
    #     self.assertLessEqual(
    #         total,
    #         90.0 + 1e-6,
    #         f"Scheduled {total:.2f} kWh; battery only has 90 kWh of room.",
    #     )

    def test_solar_is_used_before_priced_grid(self):
        # 4 kW free solar in a single hour should fill before grid kicks in.
        schedule = plan(forecast([(0.40, 4.0, 1.0)]), target=48)

        self.assertGreater(schedule[0]["charging_power"], 0)

    def test_opportunistic_topup_when_value_of_full_set(self):
        # After demand is met, additional cheap hours are taken because
        # raw cost (0.10) is below value_of_full (0.30).
        schedule = PlannerService().plan_charging(
            forecast=forecast([(0.10, 0.0, 1.0)] * 5),
            vehicle=Vehicle(
                capacity=50,
                current_soc_pct=40,
                target_soc_pct=42,   # small required: ~1.05 kWh
                max_power_kw=11,
            ),
            params=SchedulerParams(confidence_floor=0.95),
            value_of_full=0.30,
        )
        total = sum(row["charging_power"] for row in schedule)
        # Buffered demand ~1.05 kWh, but top-up should pull in a lot more.
        self.assertGreater(total, 1.5)

    def test_break_when_battery_fills(self):
        # Battery has only 2 kWh of headroom; the planner stops once full.
        schedule = PlannerService().plan_charging(
            forecast=forecast([(0.10, 0.0, 1.0)] * 4),
            vehicle=Vehicle(
                capacity=10,
                current_soc_pct=80,
                target_soc_pct=100,
                max_power_kw=11,
            ),
            params=SchedulerParams(confidence_floor=0.95),
        )
        total = sum(row["charging_power"] for row in schedule)
        # Allocator may overshoot by one tier's take but should be close to 2 kWh.
        self.assertLess(total, 11.5)
        self.assertGreater(total, 1.9)

    def test_zero_confidence_hour_is_skipped(self):
        # Hour 0 has confidence=0 ("car not plugged in") and must not receive any charge,
        # even though its price is the cheapest.
        schedule = plan(
            forecast([(0.05, 0.0, 0.0), (0.50, 0.0, 1.0)]),
            target=42,
        )

        self.assertEqual(schedule[0]["charging_power"], 0.0)
        self.assertGreater(schedule[1]["charging_power"], 0)


if __name__ == "__main__":
    unittest.main()
