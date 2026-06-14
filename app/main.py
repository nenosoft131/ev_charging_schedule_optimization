"""Pipeline orchestration: validate → feasibility → plan."""

from __future__ import annotations

import logging
from typing import Any
import json
import sys
from pydantic import ValidationError
from app.service.planner_service import PlannerService
from app.utils.data_validator import DataValidator
from app.utils.feasibility_checker import FeasibilityChecker
from app.utils.cli import build_parser, configure_logging, load_request, write_result

logger = logging.getLogger("ev_scheduler")


def run(raw_input: dict[str, Any]) -> Any:
    """Execute the validate → feasibility → planning pipeline.

    Library-callable: takes a raw request dict and returns either
    a list-shaped schedule, a shortcut alert dict, or an error dict.
    """

    # 1. Validate input — the only stage that consumes untrusted data.
    try:
        needs_scheduling, validated, message = DataValidator.validate_data(raw_input)
    except ValidationError as exc:
        logger.error("Validation failed: %s", exc)
        return {"error": exc.errors()}

    if not needs_scheduling:
        logger.info("Final response without scheduling: %s", message)
        return {"Alert": message}

    # 2. Feasibility check — operates on a typed ScheduleRequest; no Pydantic errors possible.
    report = FeasibilityChecker.check(validated)
    logger.info(
        "Feasibility | required=%.2f kWh | buffered=%.2f kWh | max=%.2f kWh",
        report.energy_required_kwh,
        report.target_with_buffer_kwh,
        report.max_possible_expected_kwh,
    )
    if report.warning:
        logger.warning("Feasibility warning: %s", report.warning)

    # 3. Plan charging 
    return PlannerService().plan_charging(
        forecast=validated.forecast,
        current_soc_pct=validated.vehicle.current_soc_pct,
        target_soc_pct=validated.vehicle.target_soc_pct,
        capacity_kwh=validated.vehicle.capacity,
        max_power_kw=validated.vehicle.max_power_kw,
        confidence_floor=validated.params.confidence_floor,
        confidence_exponent=validated.params.confidence_exponent,
        solar_is_free=True,
    )

# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code (0 success, 1 input/validation error)."""
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)

    try:
        raw = load_request(args.input)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON input — {exc}", file=sys.stderr)
        return 1

    result = run(raw)
    write_result(result, args.output)

    if isinstance(result, dict) and "error" in result:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())