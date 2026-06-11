from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Vehicle(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity: float = Field(gt=0, description="Battery capacity in kWh")
    current_soc: float = Field(ge=0, le=100, description="Current SoC %")
    target_soc: float = Field(ge=0, le=100, description="Target SoC %")
    max_charging_power: float = Field(gt=0, description="Max charge power in kW")


class ForecastHour(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime = Field(description="Start of the hour (assumed UTC)")
    price: float = Field(description="€/kWh, may be negative")
    solar: float = Field(ge=0, description="Solar availability in kW")
    conf: float = Field(ge=0, le=1, description="Plug-in confidence, 0..1")


class SchedulerParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    confidence_floor: float = Field(default=0.95, gt=0, le=1)
    min_useful_conf: float = Field(default=0.05, ge=0, le=1)
    precision: float = Field(default=0.01, gt=0)
