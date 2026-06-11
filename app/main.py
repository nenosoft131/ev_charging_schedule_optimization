import json
from datetime import datetime, timedelta

from app.model import ForecastHour, SchedulerParams, Vehicle
from app.service.planner_service import PlannerService


def _example_forecast(start: datetime, rows):
    return [
        ForecastHour(
            timestamp=start + timedelta(hours=i),
            price=price,
            solar=solar,
            conf=conf,
        )
        for i, (price, solar, conf) in enumerate(rows)
    ]


def main():
    vehicle = Vehicle(
        capacity=100.0,
        current_soc=30.0,
        target_soc=72.0,
        max_charging_power=9.0,
    )

    start = datetime(2026, 6, 11, 10, 0, 0)
    forecast = _example_forecast(
        start,
        [

            (0.32, 0.0, 1.00),
            (0.28, 0.0, 1.00),
            (0.25, 0.2, 0.95), 
            (0.22, 0.6, 0.95),
            (0.18, 1.5, 0.90), 
            (0.16, 2.8, 0.85),
            (0.17, 4.0, 0.70),
            (0.21, 4.5, 0.60),
            (0.27, 3.2, 0.70), 
            (0.35, 1.2, 0.85),
            (0.42, 0.4, 0.95), 
            (0.48, 0.1, 0.95),
            (0.45, 0.0, 1.00), 
            (0.38, 0.0, 1.00),
            (0.33, 0.0, 1.00), 
            (0.29, 0.0, 1.00)

        ],
    )

    planner = PlannerService(SchedulerParams())
    result = planner.build_schedule(vehicle, forecast)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
