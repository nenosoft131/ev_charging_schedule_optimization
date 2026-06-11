import math
from typing import List, Optional

from app.model import ForecastHour, SchedulerParams, Vehicle
from app.utils import TimeFormatter


class PlannerService:
    """Six-phase EV charging scheduler.

    Pipeline: validate → feasibility check → score each hour →
    greedy capacity-aware allocation → simulate / repair → emit.
    """

    def __init__(self, params: Optional[SchedulerParams] = None):
        self.params = params or SchedulerParams()

    def build_schedule(
        self,
        vehicle: Vehicle,
        forecast: List[ForecastHour],
    ) -> dict:
        # Phase 1 — validate
        self._validate(vehicle, forecast)
        H = len(forecast)
        soc_kwh_initial = vehicle.current_soc / 100.0 * vehicle.capacity
        soc_kwh_target = vehicle.target_soc / 100.0 * vehicle.capacity

        if H == 0 or vehicle.current_soc >= vehicle.target_soc:
            return self._emit([0.0] * H, vehicle, forecast, [], soc_kwh_initial)

        # Phase 2 — feasibility
        energy_required = soc_kwh_target - soc_kwh_initial
        target_with_buffer = energy_required / self.params.confidence_floor

        max_possible_expected = sum(
            vehicle.max_charging_power * f.conf for f in forecast
        )
        warnings: List[str] = []
        if target_with_buffer > max_possible_expected:
            warnings.append(
                "Cannot reach target reliably. "
                f"Expected delivery cap: {max_possible_expected:.2f} kWh. "
                f"Requested: {energy_required:.2f} kWh."
            )

        # Phase 3 — score
        scores = [
            self._score_hour(forecast[i], vehicle.max_charging_power)
            for i in range(H)
        ]
        sorted_hours = sorted(
            range(H),
            key=lambda i: (scores[i], -forecast[i].conf, i),
        )

        # Phase 4 — greedy allocation
        schedule = [0.0] * H
        headroom = vehicle.capacity - soc_kwh_initial
        remaining = target_with_buffer

        for i in sorted_hours:
            if remaining <= 0 or headroom <= 0:
                break
            if math.isinf(scores[i]):
                continue

            allocate = min(
                vehicle.max_charging_power,
                remaining,
                headroom,
            )
            if allocate <= 0:
                continue

            schedule[i] = allocate
            headroom -= allocate
            remaining -= allocate * forecast[i].conf

        # Phase 5 — repair & validate
        schedule = self._round_schedule(schedule, self.params.precision)
        trajectory = self._simulate(schedule, soc_kwh_initial)

        if max(trajectory) > vehicle.capacity + 1e-6:
            schedule = self._repair_capacity(schedule, vehicle, soc_kwh_initial)
            trajectory = self._simulate(schedule, soc_kwh_initial)

        if trajectory[-1] < soc_kwh_target * 0.99:
            final_pct = trajectory[-1] / vehicle.capacity * 100
            warnings.append(
                "Target SoC may not be reached. "
                f"Final expected: {final_pct:.1f}% (target {vehicle.target_soc:.1f}%)."
            )

        # Phase 6 — emit
        return self._emit(schedule, vehicle, forecast, warnings, soc_kwh_initial)

    # --- helpers ---------------------------------------------------------

    def _score_hour(self, f: ForecastHour, p_max: float) -> float:
        if f.conf < self.params.min_useful_conf:
            return float("inf")
        grid_share = max(0.0, p_max - f.solar) / p_max
        eff_price = f.price * grid_share
        if eff_price < 0:
            return eff_price * f.conf
        return eff_price / f.conf

    def _validate(self, vehicle: Vehicle, forecast: List[ForecastHour]) -> None:
        for i, f in enumerate(forecast):
            if math.isnan(f.price):
                raise ValueError(f"NaN price in forecast hour {i}.")

    def _round_schedule(self, schedule: List[float], precision: float) -> List[float]:
        if precision <= 0:
            return list(schedule)
        ndigits = max(0, -int(round(math.log10(precision))))
        return [round(p, ndigits) for p in schedule]

    def _simulate(self, schedule: List[float], soc_initial: float) -> List[float]:
        soc = soc_initial
        traj = [soc]
        for p in schedule:
            soc += p
            traj.append(soc)
        return traj

    def _repair_capacity(
        self,
        schedule: List[float],
        vehicle: Vehicle,
        soc_initial: float,
    ) -> List[float]:
        # Walk chronologically; trim any hour that would push SoC over capacity.
        # In practice this only fires for tiny rounding overshoots.
        result = list(schedule)
        soc = soc_initial
        for i, p in enumerate(result):
            if soc + p > vehicle.capacity:
                result[i] = max(0.0, vehicle.capacity - soc)
            soc += result[i]
        return result

    def _emit(
        self,
        schedule: List[float],
        vehicle: Vehicle,
        forecast: List[ForecastHour],
        warnings: List[str],
        soc_initial: float,
    ) -> dict:
        H = len(forecast)
        trajectory = self._simulate(schedule, soc_initial)
        final_soc = trajectory[-1]
        expected_delivered = sum(schedule[i] * forecast[i].conf for i in range(H))
        # Grid energy = the portion of the allocation not covered by solar.
        grid_energy = [
            max(0.0, schedule[i] - forecast[i].solar) for i in range(H)
        ]
        estimated_cost = sum(grid_energy[i] * forecast[i].price for i in range(H))

        return {
            "schedule": [
                {
                    "hour": TimeFormatter.iso_z(forecast[i].timestamp),
                    "chargingPower": schedule[i],
                }
                for i in range(H)
            ],
            "metadata": {
                "feasible": len(warnings) == 0,
                "final_soc_pct": round(final_soc / vehicle.capacity * 100, 2),
                "expected_energy_delivered_kwh": round(expected_delivered, 3),
                "estimated_cost_eur": round(estimated_cost, 3),
                "warnings": warnings,
            },
        }
