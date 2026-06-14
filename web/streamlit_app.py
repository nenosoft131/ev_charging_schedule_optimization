"""Streamlit web UI for the EV Charging Schedule Optimizer.

Run locally:
    poetry run streamlit run web/streamlit_app.py

Run in Docker:
    docker build -t ev-scheduler .
    docker run --rm -p 8501:8501 ev-scheduler
    # then open http://localhost:8501
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the project root importable so `from app.main import ...` resolves
# regardless of where this script is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.main import run  # noqa: E402
from app.utils.cli import expand_hours  # noqa: E402
from app.utils.data_validator import DataValidator  # noqa: E402
from app.utils.feasibility_checker import FeasibilityChecker  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults — same shape as data/example_request.json's forecast array.
# ---------------------------------------------------------------------------
DEFAULT_FORECAST = [
    {"hour": "6:00",  "price": 0.32, "solar": 0.0, "confidence": 1.00},
    {"hour": "7:00",  "price": 0.28, "solar": 0.0, "confidence": 1.00},
    {"hour": "8:00",  "price": 0.25, "solar": 0.2, "confidence": 0.95},
    {"hour": "9:00",  "price": 0.22, "solar": 0.6, "confidence": 0.95},
    {"hour": "10:00", "price": 0.18, "solar": 1.5, "confidence": 0.90},
    {"hour": "11:00", "price": 0.16, "solar": 2.8, "confidence": 0.85},
    {"hour": "12:00", "price": 0.17, "solar": 4.0, "confidence": 0.70},
    {"hour": "13:00", "price": 0.21, "solar": 4.5, "confidence": 0.60},
    {"hour": "14:00", "price": 0.27, "solar": 3.2, "confidence": 0.70},
    {"hour": "15:00", "price": 0.35, "solar": 1.2, "confidence": 0.85},
    {"hour": "16:00", "price": 0.42, "solar": 0.4, "confidence": 0.95},
    {"hour": "17:00", "price": 0.48, "solar": 0.1, "confidence": 0.95},
    {"hour": "18:00", "price": 0.45, "solar": 0.0, "confidence": 1.00},
    {"hour": "19:00", "price": 0.38, "solar": 0.0, "confidence": 1.00},
    {"hour": "20:00", "price": 0.33, "solar": 0.0, "confidence": 1.00},
    {"hour": "21:00", "price": 0.29, "solar": 0.0, "confidence": 1.00},
]


REQUIRED_CSV_COLUMNS = {"hour", "price", "solar", "confidence"}


def parse_forecast_from_csv(uploaded_file) -> list[dict]:
    """Parse a forecast list from an uploaded CSV.

    The CSV must contain exactly these columns (case-insensitive, whitespace
    around the header is tolerated): hour, price, solar, confidence. Any
    missing or extra column is rejected.
    """
    df = pd.read_csv(uploaded_file, skipinitialspace=True)
    df.columns = [str(c).strip().lower() for c in df.columns]

    cols = set(df.columns)
    missing = REQUIRED_CSV_COLUMNS - cols
    extra = cols - REQUIRED_CSV_COLUMNS

    if missing:
        raise ValueError(
            f"CSV is missing required columns: {sorted(missing)}. "
            f"Expected columns: {sorted(REQUIRED_CSV_COLUMNS)}."
        )
    if extra:
        raise ValueError(
            f"CSV has unexpected columns: {sorted(extra)}. "
            f"Allowed columns: {sorted(REQUIRED_CSV_COLUMNS)}."
        )

    # Trim whitespace from the hour strings (price/solar/confidence are numeric).
    df["hour"] = df["hour"].astype(str).str.strip()
    return df[list(REQUIRED_CSV_COLUMNS)].to_dict(orient="records")


def parse_forecast_from_json(text: str) -> list[dict]:
    """Parse a forecast list from a JSON string.

    Accepts a bare array of hours or a full request payload (dict with 'forecast').
    """
    data = json.loads(text)
    if isinstance(data, dict) and "forecast" in data:
        return data["forecast"]
    if isinstance(data, list):
        return data
    raise ValueError("Forecast JSON must be an array or an object with a 'forecast' key.")


def compute_feasibility(payload: dict):
    """Run the same validate → feasibility step as run() and return the report."""
    try:
        needs_scheduling, validated, _ = DataValidator.validate_data(payload)
    except Exception:
        return None
    if not needs_scheduling:
        return None
    return FeasibilityChecker.check(validated)


def render_feasibility(report) -> None:
    """Show required / capacity metrics plus a warning if infeasible."""
    if report is None:
        return
    st.markdown("#### Feasibility")
    c1, c2, c3 = st.columns(3)
    c1.metric("Required (raw)", f"{report.energy_required_kwh:.2f} kWh")
    c2.metric("Required (buffered)", f"{report.target_with_buffer_kwh:.2f} kWh")
    c3.metric("Forecast capacity", f"{report.max_possible_expected_kwh:.2f} kWh")
    if not report.is_feasible:
        gap = report.target_with_buffer_kwh - report.max_possible_expected_kwh
        st.warning(
            f"Buffered demand ({report.target_with_buffer_kwh:.2f} kWh) exceeds "
            f"the forecast capacity ({report.max_possible_expected_kwh:.2f} kWh) "
            f"by {gap:.2f} kWh. The schedule may not reach the target SoC."
        )


def render_result(result, forecast: list[dict], report=None):
    """Render the run() output: schedule list, alert dict, or error dict."""
    if isinstance(result, dict) and "error" in result:
        st.error("Validation error — see details below.")
        st.json(result["error"])
        return
    if isinstance(result, dict) and "Alert" in result:
        st.warning(result["Alert"])
        return

    # Success: list of {hour, charging_power}
    st.success(f"Schedule generated — {len(result)} hours.")
    render_feasibility(report)

    df = pd.DataFrame(result)
    df["hour_label"] = df["hour"].str.slice(11, 16)  # HH:MM portion

    # Join with forecast to compute per-hour cost (solar treated as free).
    forecast_by_hour = {f["hour"]: f for f in forecast}
    total_kwh = 0.0
    total_cost = 0.0
    for row in result:
        energy = row["charging_power"]
        f = forecast_by_hour.get(row["hour"])
        if f is not None:
            solar_used = min(f["solar"], energy)
            grid_used = energy - solar_used
            total_cost += grid_used * f["price"]
        total_kwh += energy
    cost_per_kwh = total_cost / total_kwh if total_kwh > 0 else 0.0

    col_chart, col_stats = st.columns([3, 1])
    with col_chart:
        st.bar_chart(df.set_index("hour_label")["charging_power"], height=320)
    with col_stats:
        st.metric("Total energy", f"{total_kwh:.2f} kWh")
        st.metric("Total cost", f"€{total_cost:.2f}")
        st.metric("Cost per kWh", f"€{cost_per_kwh:.4f}")
        st.metric("Hours used", f"{int((df['charging_power'] > 0).sum())}")

    st.subheader("Schedule")
    st.dataframe(
        df[["hour", "charging_power"]],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Raw JSON"):
        st.json(result)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.set_page_config(page_title="EV Charging Scheduler", layout="wide")
st.title("EV Charging Schedule Optimizer")
st.caption(
    "Plan the cheapest, solar-aware charging schedule for an EV. "
    "Configure the vehicle in the sidebar, paste or upload a forecast, "
    "then click *Plan Schedule*."
)

# ---- Sidebar: vehicle + tuning params ----
with st.sidebar:
    st.header("Vehicle")
    capacity = st.number_input("Battery capacity (kWh)", min_value=1.0, value=100.0, step=1.0)
    current_soc = st.slider("Current SoC (%)", 0, 100, 60)
    target_soc = st.slider("Target SoC (%)", 0, 100, 72)
    max_power = st.number_input("Max charging power (kW)", min_value=0.1, value=9.0, step=0.5)

    st.header("Parameters")
    confidence_floor = st.slider(
        "Confidence floor",
        0.5, 1.0, 0.95, 0.01,
        help="Demand-inflation hedge. Lower floor = larger safety buffer.",
    )
    confidence_exponent = st.slider(
        "Confidence exponent",
        0.0, 1.0, 0.5, 0.05,
        help="Softens the per-hour confidence penalty. 0.5 ≈ √conf; 1.0 = hard penalty.",
    )

# ---- Forecast input ----
st.subheader("Forecast")
source = st.radio(
    "Forecast source",
    ("Paste JSON", "Upload CSV"),
    horizontal=True,
    label_visibility="collapsed",
)

if source == "Paste JSON":
    forecast_text = st.text_area(
        "Forecast JSON",
        value=json.dumps(DEFAULT_FORECAST, indent=2),
        height=320,
        label_visibility="collapsed",
    )
    uploaded = None
else:
    uploaded = st.file_uploader(
        "CSV with columns: hour, price, solar, confidence",
        type=["csv"],
    )
    forecast_text = ""

# ---- Action ----
if st.button("Plan Schedule", type="primary"):
    if source == "Upload CSV" and uploaded is None:
        st.error("Please upload a CSV file.")
        st.stop()

    try:
        if source == "Upload CSV":
            forecast = parse_forecast_from_csv(uploaded)
        else:
            forecast = parse_forecast_from_json(forecast_text)
    except Exception as exc:
        st.error(f"Could not parse forecast: {exc}")
        st.stop()

    payload = {
        "vehicle": {
            "capacity": capacity,
            "current_soc_pct": current_soc,
            "target_soc_pct": target_soc,
            "max_power_kw": max_power,
        },
        "forecast": forecast,
        "params": {
            "confidence_floor": confidence_floor,
            "confidence_exponent": confidence_exponent,
        },
    }
    payload = expand_hours(payload)  # normalize "H:MM" → ISO timestamps

    result = run(payload)
    report = compute_feasibility(payload)
    render_result(result, payload["forecast"], report)
