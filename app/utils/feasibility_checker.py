from app.model.models import ScheduleRequest, FeasibilityReport


class FeasibilityChecker:
    """
    Phase 2: Feasibility check

    Determines whether the requested charging target is achievable
    given battery state and forecasted power availability.
    """

    @staticmethod
    def check(request: ScheduleRequest) -> FeasibilityReport:
        """
        Evaluates charging feasibility.

        Steps:
        - Convert SoC to kWh
        - Apply battery constraints
        - Add confidence buffer
        - Compare with forecast capacity

        Returns:
            FeasibilityReport with feasibility status and energy metrics
        """
        
        vehicle = request.vehicle
        forecast = request.forecast
        params = request.params

        # ------------------------------------------------------------------
        # 1. Convert SoC to absolute energy values (kWh)
        # ------------------------------------------------------------------
        current_kwh = (vehicle.current_soc_pct / 100) * vehicle.capacity
        target_kwh = (vehicle.target_soc_pct / 100) * vehicle.capacity

        energy_required_kwh = max(0.0, target_kwh - current_kwh)

        # ------------------------------------------------------------------
        # 2. Physical constraint: remaining battery capacity
        # ------------------------------------------------------------------
        max_physical_kwh = vehicle.capacity - current_kwh

        # ------------------------------------------------------------------
        # 3. Adjust for uncertainty (confidence buffer)
        # ------------------------------------------------------------------
        target_with_buffer_kwh = min(
            energy_required_kwh / params.confidence_floor,
            max_physical_kwh,
        )

        # ------------------------------------------------------------------
        # 4. Forecast-based maximum deliverable energy
        # ------------------------------------------------------------------
        # max_possible_kwh = sum(
        #     vehicle.max_power_kw * hour.confidence for hour in forecast
        # )
        max_possible_kwh =  vehicle.max_power_kw * len(forecast)
    

        # ------------------------------------------------------------------
        # 5. Feasibility decision
        # ------------------------------------------------------------------
        is_feasible = (
            target_with_buffer_kwh <= max_possible_kwh
        )

        warning = None
        if not is_feasible:
            warning = (
                "Infeasible target: required {:.2f} kWh (buffered), "
                "but only {:.2f} kWh expected from forecast."
            ).format(target_with_buffer_kwh, max_possible_kwh)

        # ------------------------------------------------------------------
        # 6. Return structured report
        # ------------------------------------------------------------------
        return FeasibilityReport(
            is_feasible=is_feasible,
            energy_required_kwh=round(energy_required_kwh, 4),
            target_with_buffer_kwh=round(target_with_buffer_kwh, 4),
            max_possible_expected_kwh=round(max_possible_kwh, 4),
            warning=warning,
        )