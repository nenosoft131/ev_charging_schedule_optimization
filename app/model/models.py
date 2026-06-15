from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ---------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------

class Vehicle(BaseModel):
    """Represents EV charging constraints and battery state."""

    capacity: float = Field(..., gt=0, description="Battery capacity in kWh")
    current_soc_pct: float = Field(..., ge=0, le=100, description="Current state of charge (%)")
    target_soc_pct: float = Field(..., ge=0, le=100, description="Target state of charge (%)")
    max_power_kw: float = Field(..., gt=0, description="Maximum charging power (kW)")


class Hour(BaseModel):
    """Single forecast time slot."""
    hour: datetime
    price: float  # Can be negative (market incentives)
    solar: float = Field(..., ge=0, description="Available solar power (kW)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Forecast confidence [0–1]")


class SchedulerParams(BaseModel):
    """Optional tuning parameters for scheduling behavior."""

    confidence_floor: float = Field(
        default=0.95,
        ge=0.5,
        le=1.0,
        description="Minimum confidence threshold for reliable forecast usage",
    )
    confidence_exponent: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Exponent applied to per-hour confidence when ranking tiers. "
            "1.0 = full penalty (raw_cost / conf); 0.5 = softened "
        ),
    )


class ScheduleRequest(BaseModel):
    """Input payload for the charging scheduler."""

    vehicle: Vehicle
    forecast: List[Hour]
    params: SchedulerParams = Field(default_factory=SchedulerParams)

# ---------------------------------------------------------------------
# Feasibility analysis
# ---------------------------------------------------------------------

class FeasibilityReport(BaseModel):
    """Checks whether requested charging is physically and practically feasible."""

    is_feasible: bool
    energy_required_kwh: float
    target_with_buffer_kwh: float
    max_possible_expected_kwh: float
    warning: Optional[str] = None