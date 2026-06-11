# EV Charging Schedule Optimization

A six-phase scheduler that turns a vehicle spec and an hourly forecast
(price, solar, plug-in confidence) into an hour-by-hour charging plan.

## Quick start

```bash
poetry install
poetry run app                                         # example
poetry run python -m unittest discover -s tests -v     # tests
```

## Usage


Returns `{ "schedule": [{hour, chargingPower}, ...], "metadata": {feasible, final_soc_pct, expected_energy_delivered_kwh, estimated_cost_eur, warnings} }`.

## Algorithm

1. **Validate** — Pydantic enforces field ranges; service rejects `NaN` price.
2. **Feasibility** — inflate demand by `1/confidence_floor`; warn if `Σ P_max·conf` falls short.
3. **Score** — `eff_price = price · max(0, P_max−solar)/P_max`, then divide by `conf` (positive) or multiply (negative). Hours below `min_useful_conf` get `+∞`. Tiebreak by `(score, -conf, index)`.
4. **Allocate** — greedy in score order: `allocate = min(P_max, remaining, headroom)`, subtract `allocate·conf` from remaining.

## Tuning (`SchedulerParams`)

| Field | Default | Meaning |
|---|---|---|
| `confidence_floor` | `0.95` | Inflate demand by `1/this` to absorb missed plug-ins. |
| `min_useful_conf` | `0.05` | Skip hours below this confidence. |
| `precision` | `0.01` | Charger power rounding step (kW). |


