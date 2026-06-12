"""
Entry point: drives validation → feasibility check → planning.
"""

import json
import logging
from typing import Any
from pydantic import ValidationError
from app.service.planner_service import PlannerService
from app.utils.data_validator import DataValidator
from app.utils.feasibility_checker import FeasibilityChecker

logger = logging.getLogger(__name__)
raw_input = {
    "vehicle": {"capacity": 100, "current_soc_pct": 30, "target_soc_pct": 72, "max_power_kw": 9.0},
    "forecast": [
        {"hour": "2026-06-11T06:00:00Z", "price": 0.32, "solar": 0.0, "confidence": 1.00},
        {"hour": "2026-06-11T07:00:00Z", "price": 0.28, "solar": 0.0, "confidence": 1.00},
        {"hour": "2026-06-11T08:00:00Z", "price": 0.25, "solar": 0.2, "confidence": 0.95},
        {"hour": "2026-06-11T09:00:00Z", "price": 0.22, "solar": 0.6, "confidence": 0.95},
        {"hour": "2026-06-11T10:00:00Z", "price": 0.18, "solar": 1.5, "confidence": 0.90},
        {"hour": "2026-06-11T11:00:00Z", "price": 0.16, "solar": 2.8, "confidence": 0.85},
        {"hour": "2026-06-11T12:00:00Z", "price": 0.17, "solar": 4.0, "confidence": 0.70},
        {"hour": "2026-06-11T13:00:00Z", "price": 0.21, "solar": 4.5, "confidence": 0.60},
        {"hour": "2026-06-11T14:00:00Z", "price": 0.27, "solar": 3.2, "confidence": 0.70},
        {"hour": "2026-06-11T15:00:00Z", "price": 0.35, "solar": 1.2, "confidence": 0.85},
        {"hour": "2026-06-11T16:00:00Z", "price": 0.42, "solar": 0.4, "confidence": 0.95},
        {"hour": "2026-06-11T17:00:00Z", "price": 0.48, "solar": 0.1, "confidence": 0.95},
        {"hour": "2026-06-11T18:00:00Z", "price": 0.45, "solar": 0.0, "confidence": 1.00},
        {"hour": "2026-06-11T19:00:00Z", "price": 0.38, "solar": 0.0, "confidence": 1.00},
        {"hour": "2026-06-11T20:00:00Z", "price": 0.33, "solar": 0.0, "confidence": 1.00},
        {"hour": "2026-06-11T21:00:00Z", "price": 0.29, "solar": 0.0, "confidence": 1.00}
        ],
    "params": {"confidence_floor": 0.95}
}

def run(raw_input: dict[str, Any]) -> dict[str, Any]:
    """Execute validation → feasibility → planning pipeline."""

    # ------------------------------------------------------------------
    # 1. Validate input
    # ------------------------------------------------------------------
    try:
        data_validator = DataValidator()
        is_shortcut, validated_request, message = data_validator.validate_data(raw_input)

        if is_shortcut:
            logger.info("Shortcut triggered: %s", message)
            return validated_request

    except ValidationError as exc:
        logger.error("Validation failed: %s", exc)
        return {"error": exc.errors()}

    # ------------------------------------------------------------------
    # 2. Feasibility check
    # ------------------------------------------------------------------
    try:
        feasibility_checker = FeasibilityChecker()
        report = feasibility_checker.check(validated_request)

        logger.info(
            "Feasibility check | required=%.2f kWh | buffered=%.2f kWh | max=%.2f kWh",
            report.energy_required_kwh,
            report.target_with_buffer_kwh,
            report.max_possible_expected_kwh,
        )

        if report.warning:
            logger.warning("Feasibility warning: %s", report.warning)

    except ValidationError as exc:
        logger.error("Feasibility check failed: %s", exc)
        return {"error": exc.errors()}
    # ------------------------------------------------------------------
    # 3. Plan charging
    # ------------------------------------------------------------------
    try:
        planner_service = PlannerService()

        result = planner_service.plan_charging(
            forecast=validated_request.forecast,
            current_soc_pct=validated_request.vehicle.current_soc_pct,
            target_soc_pct=validated_request.vehicle.target_soc_pct,
            capacity_kwh=validated_request.vehicle.capacity,
            max_power_kw = validated_request.vehicle.max_power_kw,
            use_cash_cost=True,
        )

        return result

    except ValidationError as exc:
        logger.error("Planning failed: %s", exc)
        return {"error": exc.errors()}


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    output = run(raw_input=raw_input)
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()