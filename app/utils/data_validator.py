from model.models import ScheduleRequest
from pydantic import ValidationError

class DataValidator:
    """
    Phase 1: Data Validation
    Purpose: Catch bad data before it corrupts downstream math.
    """
    
    @staticmethod
    def validate_data(raw_data: dict) -> tuple[bool, dict | ScheduleRequest, str]:
        """
        Validates raw JSON/dict input. 
        Returns: (is_shortcut, result_payload, message)
        - If shortcut: result_payload is the final zero/empty schedule.
        - If valid: result_payload is the validated ScheduleRequest object.
        """
        try:
            # Pydantic automatically checks: real numbers, ranges (0<=soc<=100, capacity>0, etc.)
            request = ScheduleRequest(**raw_data)
        except ValidationError:
            raise

        vehicle = request.vehicle
        forecast = request.forecast

        # Shortcut Case 1: Empty horizon
        if len(forecast) == 0:
            return True, {"schedule": [], "metadata": {"warnings": ["Empty horizon provided."]}}, "Empty forecast horizon no charging window available."

        # Shortcut Case 2: Already at or above target
        if vehicle.current_soc_pct >= vehicle.target_soc_pct:
            zero_schedule = [
                {"hour": f.hour.isoformat(), "chargingPower": 0.0} 
                for f in forecast
            ]
            return True, {
                "schedule": zero_schedule, 
                "metadata": {"final_soc_pct": vehicle.current_soc_pct, "warnings": ["Already at or above target SoC."]}
            }, "Target state of charge already satisfied."

        # If no shortcuts, return the validated object for Phase 2
        return False, request, "Validation Passed"