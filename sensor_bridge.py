"""
Reads ultrasonic-distance lines from an Arduino over serial and forwards them
to the Smart Parking API as occupancy updates.

Expected serial line format (one reading per line, CSV):
    <spot_number>,<distance_cm>
e.g.
    A12,23.4

Usage:
    python sensor_bridge.py --port COM3 --baud 9600 --api http://localhost:8000

Env vars override flags if set:
    PARKLEE_API, PARKLEE_SERIAL_PORT, PARKLEE_BAUD, PARKLEE_THRESHOLD
"""
import argparse
import os
import sys
import time

import requests
import serial


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Arduino → Smart Parking API bridge")
    p.add_argument(
        "--port",
        default=os.environ.get("PARKLEE_SERIAL_PORT", "COM4"),
        help="Serial port (e.g. COM3 on Windows, /dev/ttyUSB0 on Linux)",
    )
    p.add_argument(
        "--baud",
        type=int,
        default=int(os.environ.get("PARKLEE_BAUD", "9600")),
        help="Baud rate matching the Arduino sketch",
    )
    p.add_argument(
        "--api",
        default=os.environ.get("PARKLEE_API", "http://localhost:8000"),
        help="Backend base URL",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=float(os.environ.get("PARKLEE_THRESHOLD", "50")),
        help="Occupancy threshold in cm (distance < threshold => occupied)",
    )
    p.add_argument(
        "--default-spot",
        default=os.environ.get("PARKLEE_DEFAULT_SPOT"),
        help="Spot number to use when the Arduino emits distance only (no spot id)",
    )
    p.add_argument(
        "--debounce",
        type=int,
        default=int(os.environ.get("PARKLEE_DEBOUNCE", "5")),
        help="Consecutive readings required before flipping the spot's state",
    )
    return p.parse_args()


def parse_line(raw: str, default_spot: str | None) -> tuple[str, float] | None:
    """Accepts either 'spot_number,distance_cm' or just 'distance_cm'."""
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.split(",")]
    try:
        if len(parts) == 2:
            return parts[0], float(parts[1])
        if len(parts) == 1:
            if not default_spot:
                return None
            return default_spot, float(parts[0])
    except ValueError:
        return None
    return None


def post_reading(api: str, spot_number: str, distance_cm: float, threshold: float) -> None:
    url = f"{api.rstrip('/')}/sensors/reading"
    payload = {
        "spot_number": spot_number,
        "distance_cm": distance_cm,
        "threshold_cm": threshold,
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
    except requests.RequestException as e:
        print(f"[bridge] POST failed: {e}", file=sys.stderr)
        return
    if r.ok:
        data = r.json()
        marker = "*" if data.get("changed") else " "
        print(
            f"[bridge] {marker} spot={data['spot_number']} "
            f"distance={distance_cm:.1f}cm -> {data['status']}"
        )
    else:
        print(f"[bridge] {r.status_code} {r.text}", file=sys.stderr)


def classify(distance_cm: float, threshold: float) -> str:
    return "occupied" if distance_cm < threshold else "empty"


def main() -> int:
    args = parse_args()
    print(
        f"[bridge] opening {args.port} @ {args.baud} baud, posting to {args.api} "
        f"(threshold={args.threshold}cm, debounce={args.debounce})"
    )
    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"[bridge] cannot open {args.port}: {e}", file=sys.stderr)
        return 2

    # Give the Arduino a moment to reset on connect.
    time.sleep(2)

    # Per-spot debounce state: spot_number -> {"pending": str, "count": int, "confirmed": str | None}
    state: dict[str, dict] = {}

    try:
        while True:
            raw = ser.readline().decode("utf-8", errors="ignore")
            parsed = parse_line(raw, args.default_spot)
            if parsed is None:
                continue
            spot_number, distance_cm = parsed
            classification = classify(distance_cm, args.threshold)

            s = state.setdefault(
                spot_number, {"pending": classification, "count": 0, "confirmed": None}
            )
            if classification == s["pending"]:
                s["count"] += 1
            else:
                s["pending"] = classification
                s["count"] = 1

            print(
                f"[bridge] spot={spot_number} distance={distance_cm:.1f}cm "
                f"-> {classification} (streak {s['count']}/{args.debounce})"
            )

            if s["count"] >= args.debounce and s["confirmed"] != classification:
                post_reading(args.api, spot_number, distance_cm, args.threshold)
                s["confirmed"] = classification
    except KeyboardInterrupt:
        print("\n[bridge] stopping.")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
