from __future__ import annotations

from pydantic import ValidationError

from app.model.models import ScheduleRequest


class DataValidator:
    """
    Phase 1: Data Validation
    Purpose: Catch bad data before it corrupts downstream math.
    """

    @staticmethod
    def validate_data(raw_data: dict) -> tuple[bool, dict | ScheduleRequest, str]:
        """
        Validate raw JSON/dict input.

        Assumes hour fields are already full ISO timestamps (the CLI's
        `load_request` performs that conversion at the input boundary).

        Returns:
            (needs_scheduling, payload, message)
            - needs_scheduling=True  → payload is the validated ScheduleRequest;
                                       continue to feasibility + planning
            - needs_scheduling=False → payload is a final zero/empty schedule
                                       dict; return it as-is
        """
        request = ScheduleRequest(**raw_data)

        vehicle = request.vehicle
        forecast = request.forecast

        # Final response 1: empty horizon
        if len(forecast) == 0:
            return (
                False,
                {"schedule": [], "metadata": {"warnings": ["Empty horizon provided."]}},
                "Empty forecast horizon no charging window available.",
            )

        # Final response 2: already at or above target
        if vehicle.current_soc_pct >= vehicle.target_soc_pct:
            zero_schedule = [
                {"hour": f.hour.isoformat(), "charging_power": 0.0}
                for f in forecast
            ]
            return (
                False,
                {
                    "schedule": zero_schedule,
                    "metadata": {
                        "final_soc_pct": vehicle.current_soc_pct,
                        "warnings": ["Already at or above target SoC."],
                    },
                },
                "Target state of charge already satisfied.",
            )

        return True, request, "Validation Passed"
