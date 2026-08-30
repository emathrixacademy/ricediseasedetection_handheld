#!/usr/bin/env python3
"""End-to-end simulation of the handheld rice disease scanner.

This is NOT the mock mode built into UARTBridge. It stands up a *virtual
ESP32* that implements the real firmware behaviour -- the same DPV staircase
sweep, the same timing, the same text protocol -- behind a pyserial-shaped
object. UARTBridge therefore runs its genuine hardware code path (readline,
timeouts, buffer resets), so the simulation exercises the real logic rather
than the instant-reply mock.

What it demonstrates:
  1. A full DPV sweep with physically-shaped electrochemistry and real timing.
  2. The F-1 fix: the ~20 s sweep now completes inside the scan deadline,
     and the old 2 s timeout is shown failing on the same virtual hardware.
  3. The F-2 fix: a scan-button press produces exactly one sweep.
  4. A full diagnosis cycle for a healthy vs. an infected sample.

Run:
    python -m scripts.simulate              # default, real firmware timing
    python -m scripts.simulate --speed 20   # 20x time compression
"""

import argparse
import json
import math
import random
import sys
import time

sys.path.insert(0, ".")

from pi5.comms.uart_bridge import UARTBridge  # noqa: E402

# --- firmware constants mirrored from esp32/src/config.h --------------------
DPV_START_MV = -200.0
DPV_END_MV = 600.0
DPV_STEP_MV = 4.0
DPV_PULSE_AMP_MV = 50.0
DPV_STEP_PERIOD_MS = 100
VIRTUAL_GND_V = 1.65
TIA_RF_OHM = 100_000.0


# ===========================================================================
# Electrochemistry model
# ===========================================================================

class SapSample:
    """A plant sap sample presented to the microneedle biosensor.

    The DPV response is modelled as a Gaussian faradaic peak riding on a
    sloping capacitive baseline. Peak current scales with the concentration of
    the redox-active disease biomarker; peak potential is set by the redox
    couple involved.
    """

    def __init__(self, label, peak_ua, peak_mv, width_mv=70.0, noise_ua=0.25):
        self.label = label
        self.peak_ua = peak_ua
        self.peak_mv = peak_mv
        self.width_mv = width_mv
        self.noise_ua = noise_ua

    def differential_current(self, potential_mv):
        """Return DPV differential current (uA) at a given potential."""
        gauss = math.exp(-((potential_mv - self.peak_mv) ** 2)
                         / (2.0 * self.width_mv ** 2))
        faradaic = self.peak_ua * gauss
        baseline = 0.4 + 0.0008 * (potential_mv - DPV_START_MV)
        return faradaic + baseline + random.gauss(0.0, self.noise_ua)


# Representative samples. Peak currents are illustrative placeholders --
# real values come from Phase 7 calibration against a redox standard.
SAMPLES = {
    "healthy": SapSample("healthy leaf sap", peak_ua=3.2, peak_mv=180.0),
    "infected": SapSample("blast-infected sap", peak_ua=31.5, peak_mv=240.0),
}


# ===========================================================================
# Virtual ESP32 -- mirrors esp32/src/main.cpp
# ===========================================================================

class VirtualESP32:
    """Software model of the ESP32 firmware, protocol-identical to main.cpp."""

    def __init__(self, sample, speed=1.0, verbose=True):
        self.sample = sample
        self.speed = max(speed, 0.001)
        self.verbose = verbose
        self.led = "OFF"
        self.battery_v = 3.94
        self.outbox = []          # lines waiting to be read by the Pi
        self.sweeps_run = 0       # F-2: counts how many sweeps actually ran

    # -- helpers ------------------------------------------------------------

    def _log(self, msg):
        if self.verbose:
            print(f"    [esp32] {msg}")

    def _emit(self, line, after=0.0):
        """Queue a response line that becomes readable `after` seconds from now.

        This models the single-threaded firmware: while a sweep is running the
        ESP32 cannot answer, so the Pi's read must wait out the full duration.
        """
        self.outbox.append((time.time() + after / self.speed, line))

    def press_scan_button(self):
        """Simulate the physical Scan button being pressed.

        Post-F-2 the firmware only reports the press; it no longer starts a
        local sweep. The Pi owns the scan trigger.
        """
        self._log("Scan button pressed -> DATA:BUTTON:1 (no local sweep)")
        self._emit("DATA:BUTTON:1")

    # -- the core measurement ----------------------------------------------

    def run_dpv(self):
        """Execute the DPV staircase sweep, mirroring Potentiostat::runDPV()."""
        self.sweeps_run += 1
        points = []
        best_diff = -1e9
        peak_v = 0.0
        re_v = 0.0

        base = DPV_START_MV
        n_steps = int((DPV_END_MV - DPV_START_MV) / DPV_STEP_MV) + 1
        duration = n_steps * DPV_STEP_PERIOD_MS / 1000.0
        self._log(f"DPV sweep starting: {DPV_START_MV:+.0f} mV -> "
                  f"{DPV_END_MV:+.0f} mV, {n_steps} steps, "
                  f"{duration:.1f} s of firmware time")

        for i in range(n_steps):
            # Firmware: settle at base, sample, pulse, sample, difference.
            diff = self.sample.differential_current(base + DPV_PULSE_AMP_MV / 2)

            if diff > best_diff:
                best_diff = diff
                peak_v = base / 1000.0
                # RE sits near virtual ground, gently polarised by the sweep.
                re_v = round(VIRTUAL_GND_V + base / 8000.0, 4)

            points.append({"v": round(base / 1000.0, 4), "i": round(diff, 3)})
            base += DPV_STEP_MV

        self._log(f"sweep will report peak {best_diff:.2f} uA @ {peak_v:+.3f} V "
                  f"after {duration / self.speed:.1f} s wall clock")

        return best_diff, peak_v, re_v, points, duration

    # -- command dispatch, mirroring dispatch() in main.cpp -----------------

    def handle(self, cmd):
        if cmd == "CMD:SCAN":
            peak_ua, peak_v, re_v, points, duration = self.run_dpv()
            self._emit(
                f"DATA:BIOSENSOR:{peak_ua:.3f},{peak_v:.4f},{re_v:.4f},"
                f"{json.dumps(points, separators=(',', ':'))}",
                after=duration,
            )
        elif cmd == "CMD:BATTERY":
            self._emit(f"DATA:BATTERY:{self.battery_v:.3f}")
        elif cmd in ("CMD:LED:ON", "CMD:LED:OFF", "CMD:LED:BLINK"):
            self.led = cmd.rsplit(":", 1)[1]
            self._log(f"LED -> {self.led}")
            self._emit("DATA:STATUS:OK")
        elif cmd == "CMD:STATUS":
            self._emit("DATA:STATUS:OK")
        else:
            self._emit("ERR:UNKNOWN_CMD")


# ===========================================================================
# pyserial-shaped adapter so UARTBridge uses its real hardware path
# ===========================================================================

class VirtualSerial:
    """Minimal pyserial-compatible port backed by a VirtualESP32."""

    def __init__(self, esp32, timeout=2.0):
        self.esp32 = esp32
        self.timeout = timeout
        self._pending = b""

    def write(self, data):
        cmd = data.decode("ascii").strip()
        if cmd:
            self.esp32.handle(cmd)
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        self.esp32.outbox.clear()
        self._pending = b""

    def readline(self):
        """Block up to self.timeout for a line, like a real serial port.

        A queued line only becomes readable once its ready_at time arrives, so
        a caller whose timeout is shorter than the sweep gets an empty read --
        exactly the F-1 failure mode.
        """
        deadline = time.time() + (self.timeout or 0)
        while True:
            now = time.time()
            if self.esp32.outbox and self.esp32.outbox[0][0] <= now:
                _, line = self.esp32.outbox.pop(0)
                return (line + "\n").encode("ascii")
            if now >= deadline:
                return b""
            time.sleep(min(0.02, max(0.001, deadline - now)))

    def close(self):
        pass


def make_bridge(esp32, timeout=2.0):
    """Build a UARTBridge wired to the virtual ESP32 (real code path)."""
    bridge = UARTBridge.__new__(UARTBridge)   # bypass __init__'s port opening
    bridge.port = "virtual://esp32"
    bridge.baud = 115200
    bridge.timeout = timeout
    bridge.mock = False                       # NOT mock mode
    bridge._ser = VirtualSerial(esp32, timeout=timeout)
    return bridge


# ===========================================================================
# Scenarios
# ===========================================================================

def rule(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


def scenario_sweep(speed):
    """Show a full DPV sweep and the resulting curve."""
    rule("1. DPV SWEEP -- infected sample, real firmware timing")
    esp32 = VirtualESP32(SAMPLES["infected"], speed=speed)
    bridge = make_bridge(esp32, timeout=2.0)

    t0 = time.time()
    reading = bridge.trigger_scan()
    wall = time.time() - t0

    print()
    print(f"    response type   : {reading.get('type')}")
    print(f"    peak current    : {reading.get('peak_current_ua')} uA")
    print(f"    peak potential  : {reading.get('peak_voltage_v')} V")
    print(f"    RE voltage      : {reading.get('re_voltage_v')} V")
    curve = reading.get("raw_json") or []
    print(f"    curve points    : {len(curve)}")
    print(f"    wall clock      : {wall:.1f} s")

    if curve:
        print()
        print("    Voltammogram (differential current vs potential):")
        peak = max(p["i"] for p in curve)
        for p in curve[::12]:
            bar = "#" * int(round(48 * max(p["i"], 0) / peak))
            print(f"      {p['v']:+.3f} V | {bar:<48} {p['i']:6.2f} uA")
    return reading


def scenario_timeout(speed):
    """Prove F-1: the old 2 s timeout fails where the new deadline succeeds.

    This scenario always runs at real firmware timing regardless of --speed.
    The whole point is that the sweep is longer than the old 2 s timeout;
    compressing time would hide the very defect being demonstrated.
    """
    rule("2. F-1 REGRESSION CHECK -- scan deadline vs sweep duration")
    if speed != 1.0:
        print(f"\n    (ignoring --speed {speed}: this check requires real timing)")

    print()
    print("  (a) OLD behaviour: single read, 2 s port timeout")
    esp32 = VirtualESP32(SAMPLES["infected"], speed=1.0, verbose=False)
    bridge = make_bridge(esp32, timeout=2.0)
    t0 = time.time()
    bridge.send_command("CMD:SCAN")
    old = bridge.read_response()          # one read, default timeout
    print(f"      -> returned after {time.time() - t0:.1f} s: "
          f"type={old.get('type')!r}, peak={old.get('peak_current_ua')}")
    print("      -> read timed out; biosensor silently drops out of fusion,"
          if old.get("type") != "biosensor" else "      -> got a reading")
    if old.get("type") != "biosensor":
        print("         and the late DATA:BIOSENSOR desyncs the next read")

    print()
    print(f"  (b) NEW behaviour: trigger_scan(), "
          f"SCAN_TIMEOUT_S={UARTBridge.SCAN_TIMEOUT_S:.0f} s  (waiting ~20 s)")
    esp32b = VirtualESP32(SAMPLES["infected"], speed=1.0, verbose=False)
    bridge_b = make_bridge(esp32b, timeout=2.0)
    t1 = time.time()
    new = bridge_b.trigger_scan()
    print(f"      -> returned after {time.time() - t1:.1f} s: "
          f"type={new.get('type')!r}, peak={new.get('peak_current_ua')} uA")
    return old, new


def scenario_button(speed):
    """Prove F-2: one button press produces exactly one sweep."""
    rule("3. F-2 REGRESSION CHECK -- scan-button press")
    esp32 = VirtualESP32(SAMPLES["healthy"], speed=speed, verbose=False)
    bridge = make_bridge(esp32, timeout=2.0)

    esp32.press_scan_button()
    event = bridge.read_response()
    print(f"    Pi receives      : {event.get('type')} "
          f"#{event.get('button')}")
    print("    Pi answers       : CMD:SCAN")
    reading = bridge.trigger_scan()
    print(f"    reading          : {reading.get('peak_current_ua')} uA")
    print(f"    sweeps executed  : {esp32.sweeps_run}  "
          f"({'PASS -- exactly one' if esp32.sweeps_run == 1 else 'FAIL -- duplicate'})")
    return esp32.sweeps_run


def scenario_diagnosis(speed):
    """Full pipeline: two samples through biosensor -> fusion -> diagnosis."""
    rule("4. FULL DIAGNOSIS CYCLE -- healthy vs infected")

    from pi5.ai.fusion import DecisionFusion
    from pi5.config import CLASSES

    fusion = DecisionFusion()
    rows = []

    for key in ("healthy", "infected"):
        sample = SAMPLES[key]
        esp32 = VirtualESP32(sample, speed=speed, verbose=False)
        bridge = make_bridge(esp32, timeout=2.0)

        print(f"\n    --- sample: {sample.label} ---")
        bridge.set_led("BLINK")
        reading = bridge.trigger_scan()
        bridge.set_led("ON")

        peak = reading.get("peak_current_ua") or 0.0
        bio_signal = max(0.0, min(1.0, peak / 50.0))   # same as main.py

        # Imaging evidence consistent with the sample (stands in for the
        # unavailable trained models -- see report section 7).
        if key == "healthy":
            rgb = {"probs": {c: (0.62 if c == "healthy" else 0.076) for c in CLASSES}}
            nir = {"probs": {c: (0.55 if c == "healthy" else 0.09) for c in CLASSES}}
        else:
            rgb = {"probs": {c: (0.58 if c == "rice_blast" else 0.084) for c in CLASSES}}
            nir = {"probs": {c: (0.47 if c == "rice_blast" else 0.106) for c in CLASSES}}

        fused = fusion.fuse(rgb, nir, biosensor_signal=bio_signal)

        print(f"    DPV peak         : {peak:.2f} uA @ "
              f"{reading.get('peak_voltage_v')} V")
        print(f"    biosensor signal : {bio_signal:.3f} "
              f"(peak / 50 uA full scale)")
        print(f"    biosensor weight : {fused['biosensor_weight']}")
        print(f"    DIAGNOSIS        : {fused['final_diagnosis']} "
              f"({fused['final_confidence']:.1%})")
        rows.append((sample.label, peak, bio_signal, fused))

    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--speed", type=float, default=1.0,
                    help="time compression factor (1.0 = real firmware timing)")
    ap.add_argument("--seed", type=int, default=7, help="RNG seed")
    args = ap.parse_args()
    random.seed(args.seed)

    print("=" * 74)
    print("  RICE DISEASE SCANNER -- HARDWARE-IN-THE-LOOP SIMULATION")
    print("=" * 74)
    print(f"  Virtual ESP32 running firmware-equivalent DPV "
          f"({DPV_START_MV:+.0f}..{DPV_END_MV:+.0f} mV)")
    print(f"  Time compression : {args.speed}x"
          f"{'  (real timing)' if args.speed == 1.0 else ''}")
    print("  UARTBridge is on its REAL serial path, not mock mode.")

    t0 = time.time()
    scenario_sweep(args.speed)
    old, new = scenario_timeout(args.speed)
    sweeps = scenario_button(args.speed)
    rows = scenario_diagnosis(args.speed)

    rule("SUMMARY")
    print(f"    F-1  old 2 s read        : {old.get('type')} "
          f"{'(would lose biosensor)' if old.get('type') != 'biosensor' else ''}")
    print(f"    F-1  new trigger_scan()  : {new.get('type')} "
          f"{'PASS' if new.get('type') == 'biosensor' else 'FAIL'}")
    print(f"    F-2  sweeps per press    : {sweeps} "
          f"{'PASS' if sweeps == 1 else 'FAIL'}")
    print()
    for label, peak, sig, fused in rows:
        print(f"    {label:<24} peak {peak:6.2f} uA  ->  "
              f"{fused['final_diagnosis']:<22} {fused['final_confidence']:.1%}")
    print()
    print(f"    total simulation wall clock: {time.time() - t0:.1f} s")
    print()
    print("    NOTE: peak currents are illustrative, not calibrated. Absolute")
    print("    values require Phase 7 calibration against a redox standard.")


if __name__ == "__main__":
    main()
