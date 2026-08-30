"""Collect Raspberry Pi system statistics.

CPU temperature is read from the kernel thermal zone or ``vcgencmd``. Battery
voltage is typically supplied by an external fuel-gauge/ADC, so it is passed in
(or mocked). Memory is read via psutil when available.
"""

import os
import subprocess
import time

try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:  # pragma: no cover - dev machines may lack psutil
    psutil = None
    _HAS_PSUTIL = False

_START_TIME = time.time()
_THERMAL_PATH = "/sys/class/thermal/thermal_zone0/temp"

# Placeholder shown when no hardware reading is provided. NOTE: this value does
# not match the specified 3.7 V LiPo (it reads like a 2S pack) and exists only
# so the panel renders. Real readings arrive via CMD:BATTERY from the ESP32.
_MOCK_BATTERY_V = 7.4


def _read_cpu_temp():
    """Return CPU temperature in Celsius, or None if unavailable."""
    # Preferred: kernel thermal zone.
    try:
        if os.path.exists(_THERMAL_PATH):
            with open(_THERMAL_PATH, "r") as fh:
                return round(int(fh.read().strip()) / 1000.0, 1)
    except (OSError, ValueError):
        pass

    # Fallback: vcgencmd (Raspberry Pi userland).
    try:
        out = subprocess.check_output(
            ["vcgencmd", "measure_temp"], text=True, timeout=2
        )
        # Format: temp=48.3'C
        return round(float(out.split("=")[1].split("'")[0]), 1)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def _read_memory_pct():
    if _HAS_PSUTIL:
        return round(psutil.virtual_memory().percent, 1)
    return None


def get_stats(battery_voltage_v=None, inference_time_ms=None):
    """Return a dict of current system statistics.

    battery_voltage_v: measured value from an external gauge, else mocked.
    inference_time_ms: last recorded model inference time, if known.
    """
    # Track the provenance of every field so synthesised values are never
    # displayed as if they were live telemetry.
    sources = {}

    cpu_temp = _read_cpu_temp()
    if cpu_temp is None:
        cpu_temp = 45.0  # mock value on non-Pi hardware
        sources["cpu_temp_c"] = "mock"
    else:
        sources["cpu_temp_c"] = "measured"

    memory_pct = _read_memory_pct()
    if memory_pct is None:
        memory_pct = 0.0
        sources["memory_usage_pct"] = "unavailable"
    else:
        # psutil.virtual_memory() is WHOLE-SYSTEM memory, not this process.
        # Meaningful on a dedicated Pi 5; on a shared workstation it reflects
        # everything else running and should not be read as scanner usage.
        sources["memory_usage_pct"] = "system-wide"

    if battery_voltage_v is None:
        battery_voltage_v = _MOCK_BATTERY_V
        sources["battery_voltage_v"] = "mock"
    else:
        sources["battery_voltage_v"] = "measured"

    sources["inference_time_ms"] = (
        "measured" if inference_time_ms is not None else "unavailable"
    )

    return {
        "cpu_temp_c": cpu_temp,
        "memory_usage_pct": memory_pct,
        "battery_voltage_v": round(float(battery_voltage_v), 2),
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "inference_time_ms": inference_time_ms,
        "sources": sources,
        "mock": any(v == "mock" for v in sources.values()),
    }


if __name__ == "__main__":
    print(get_stats(inference_time_ms=42.0))
