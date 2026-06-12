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


class ScheduleRequest(BaseModel):
    """Input payload for the charging scheduler."""

    vehicle: Vehicle
    forecast: List[Hour]
    params: SchedulerParams = Field(default_factory=SchedulerParams)

class EnergyTier(BaseModel):
    adjusted_cost: float
    raw_cost: float
    energy_kwh: float
    hour_index: int

# ---------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------

class HourPlan(BaseModel):
    """Result for a single hour of charging."""

    time: datetime
    charging_power_kw: float
    soc_percent: float

    solar_kwh_used: float
    grid_kwh_used: float
    cost_eur: float


class PlanResult(BaseModel):
    """Full charging plan output."""

    hours: List[HourPlan] = Field(default_factory=list)
    total_kwh: float = 0.0
    total_cost_eur: float = 0.0
    avg_cost_per_kwh: float = 0.0
    clearing_price: float = 0.0


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