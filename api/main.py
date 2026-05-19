import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Data Models from PDF
class Sample(BaseModel):
    t: int      # UTC timestamp (ms)
    ax: float   # accelerometer x-axis (m/s²)
    ay: float   # accelerometer y-axis (m/s²)
    az: float   # accelerometer z-axis (m/s²)
    gx: float   # gyroscope x-axis (rad/s)
    gy: float   # gyroscope y-axis (rad/s)
    gz: float   # gyroscope z-axis (rad/s)

class Reading(BaseModel):
    device_id: str
    session_id: str
    samples: list[Sample]


# Set Parameters
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Arrival Window
SIMULTANEOUS_WINDOW_S = 5.0
recent_arrivals: list[dict] = []


@app.get("/health")
def health():
    """Quick ping endpoint."""
    return {"status": "ok"}


@app.post("/readings")
def receive_reading(reading: Reading):
    """
    Main ingestion endpoint.

      1. Record arrival time.
      2. Save the validated payload to disk as a JSON file.
      3. Search the log for a recent arrival from a *different* device.
      4. If a near-simultaneous pair is found, hand it off to the assessment
         algorithm.
    """

    arrival_time = time.time()

    # Save to Disk
    filename = f"{reading.device_id}_{reading.session_id}_{int(arrival_time)}.json"
    filepath = DATA_DIR / filename

    with open(filepath, "w") as f:
        json.dump(reading.model_dump(), f, indent=2)

    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] Saved {filename}  ({len(reading.samples)} samples)")

    recent_arrivals.append({
        "arrival_time": arrival_time,
        "device_id": reading.device_id,
        "filepath": str(filepath),
    })

    # Drop entries that are too old.
    cutoff = arrival_time - SIMULTANEOUS_WINDOW_S
    recent_arrivals[:] = [e for e in recent_arrivals if e["arrival_time"] >= cutoff]

    # Look for other arrival times that match this one
    matches = [
        e for e in recent_arrivals
        if e["device_id"] != reading.device_id
        and abs(e["arrival_time"] - arrival_time) <= SIMULTANEOUS_WINDOW_S
    ]

    for match in matches:
        print(f"[MATCH] Near-simultaneous pair: {reading.device_id} + {match['device_id']}")
        trigger_assessment(str(filepath), match["filepath"])

    return {
        "status": "ok",
        "saved": filename,
        "matches_found": len(matches),
    }


# Handoff to Assessment Algorithm
def trigger_assessment(filepath_a: str, filepath_b: str):
    """
    Called when two readings arrive near-simultaneously.

    TODO: Add actual algorithm call.
    """
    print(f"[ASSESSMENT] Comparing:")
    print(f"  A: {filepath_a}")
    print(f"  B: {filepath_b}")
