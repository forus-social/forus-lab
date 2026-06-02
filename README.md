SENSOR READING JSON FORMAT:
{
  "device_id": "phoneA",
  "session_id": "abc123",
  "samples": [
    {"t": 1234567890, "ax": 0.12, "ay": -0.34, "az": 9.81,
                      "gx": 0.01, "gy": 0.02, "gz": -0.01},
  ]
}

---

## Running locally (laptop + 2 phones on same WiFi)

1. Install Python deps: `pip install -r requirements.txt`
2. From the **repo root** (so `from scripts.assessment import ...` resolves):
   `uvicorn api.main:app --host 0.0.0.0 --port 8000`
   `--host 0.0.0.0` is required — the default `127.0.0.1` is unreachable from the phones.
   The first time you run it, Windows Firewall will prompt to allow inbound on port 8000 — accept "Private networks".
3. Find your laptop's LAN IP with `ipconfig` (look for the IPv4 of the active WiFi adapter, usually `192.168.x.x`).
4. From a phone browser, `http://<laptop-ip>:8000/health` should return `{"status":"ok"}`. If not, check that both devices are on the same WiFi and the firewall rule was added.
5. In the Flutter app on each phone, set the Server URL field to `http://<laptop-ip>:8000`, give the two phones distinct Device IDs (e.g. `phoneA` and `phoneB`), record together, then tap **Upload to Server** on each. Uploads arriving within 5s of each other are paired and the assessment score prints in the uvicorn terminal.
