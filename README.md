# EV Charging Schedule Optimization

Given a vehicle spec and an hourly forecast (price, solar, plug-in
confidence), produces an hour-by-hour charging plan.

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)

## Setup

```bash
git clone https://github.com/nenosoft131/ev_charging_schedule_optimization.git
cd ev_charging_schedule_optimization
poetry install
```

## Run

Use the included example payload:

```bash
poetry run app -i data/example_request.json -o result.json -v
```

- `-i` input JSON file (omit to read from stdin)
- `-o` output JSON file (omit to write to stdout)
- `-v` print info logs to stderr

The plan is written to `result.json`.

## Run the tests

```bash
poetry run pytest
```

## Input

See [`data/example_request.json`](data/example_request.json).

```json
{
  "vehicle": {
    "capacity": 100,
    "current_soc_pct": 30,
    "target_soc_pct": 72,
    "max_power_kw": 9.0
  },
  "forecast": [
    {"hour": "6:00", "price": 0.32, "solar": 0.0, "confidence": 1.00},
    {"hour": "7:00", "price": 0.28, "solar": 0.0, "confidence": 1.00},
     ....
     ....
  ],
  "params": {"confidence_floor": 0.95}
}
```

## Output

One entry per forecast hour:

```json
[
  {"hour": "2026-06-13T08:00:00Z", "chargingPower": 0.2},
  {"hour": "2026-06-13T09:00:00Z", "chargingPower": 9.0}
]
```

On invalid input: `{"error": [...]}` with exit code `1`.


## Run with Docker (Web UI)

Build and start the Streamlit web app:

```bash
docker build -t ev-scheduler .
docker run --rm -p 8501:8501 ev-scheduler
```

Open **http://localhost:8501** in your browser.

In the sidebar, set the vehicle (capacity, current/target SoC, max power)
and the params (`confidence_floor`, `confidence_exponent`). For the
forecast, choose one of:

- **Paste JSON** — a forecast array (same shape as `data/example_request.json`).
- **Upload CSV** — a CSV with exactly these columns: `hour, price, solar, confidence`.

Example CSV:

```csv
hour,price,solar,confidence
6:00,0.32,0.0,1.00
7:00,0.28,0.0,1.00
8:00,0.25,0.2,0.95
```

Click **Plan Schedule** to see the per-hour plan, total cost, cost per kWh,
and a feasibility check.

To run the web UI locally without Docker:

```bash
poetry run pip install streamlit pandas
poetry run streamlit run web/streamlit_app.py
```


## How it works

1. **Validate** — Pydantic enforces field ranges on the input request.
2. **Feasibility** — inflate demand by `1 / confidence_floor` and warn
   if `max_power · hours` can't cover it.
3. **Score** — each hour becomes a solar tier (cost 0) and a grid tier
   (cost = price), each divided by `confidence` so uncertain hours rank
   lower.
4. **Allocate** — greedy cheapest-first until the buffered demand is
   met, then opportunistic top-ups while raw cost is below
   `value_of_full`.

## Project layout

```
app/
  main.py                       # run() pipeline + CLI entry
  model/models.py               # Pydantic models
  service/planner_service.py    # Tier-based greedy scheduler
  utils/cli.py                  # argparse + JSON I/O
  utils/data_validator.py       # Input validation + shortcuts
  utils/feasibility_checker.py  # Feasibility report
data/example_request.json       # Sample input
tests/                          # Unit + integration tests
```

## Use as a library

```python
from app.main import run

result = run(my_payload_dict)
```

## Use as a FastAPI endpoint

`run()` is a plain function that takes a dict and returns a dict, so it
drops straight into a FastAPI route:

```python
from fastapi import FastAPI
from app.main import run

app = FastAPI()

@app.post("/schedule")
def schedule(payload: dict):
    return run(payload)
```

Run it with `uvicorn main:app --reload` and POST the same JSON you'd
pass to the CLI.

