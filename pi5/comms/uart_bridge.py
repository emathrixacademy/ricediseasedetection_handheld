"""UART bridge between the Raspberry Pi 5 and the ESP32 companion MCU.

Protocol (plain text, newline-terminated, 115200 baud)
------------------------------------------------------
Pi -> ESP32:
    CMD:SCAN            (= CMD:SCAN:H2O2)
    CMD:SCAN:H2O2
    CMD:SCAN:NO3
    CMD:LED:ON | CMD:LED:OFF | CMD:LED:BLINK
    CMD:BATTERY
    CMD:STATUS

ESP32 -> Pi:
    DATA:BIOSENSOR:<analyte>:<status>:<peak_ua>,<peak_v>,<re_v>,<raw_json>
        analyte H2O2 | NO3; status OK | SATURATED | NO_SIGNAL
        (older firmware: DATA:BIOSENSOR:<peak_ua>,<peak_v>,<re_v>,<raw_json>)
    DATA:BATTERY:<voltage_v>
    DATA:BUTTON:<1|2|3>
    DATA:STATUS:OK | DATA:STATUS:DEGRADED:<reason>
    ERR:<msg>

If pyserial or the serial port is unavailable the bridge runs in mock mode
and synthesises plausible responses, every one marked ``mock: True``.
"""

import collections
import json
import random
import time

try:
    import serial  # type: ignore
    _SERIAL_AVAILABLE = True
except Exception:
    serial = None
    _SERIAL_AVAILABLE = False

from .. import config


class UARTBridge:
    """Text-protocol UART link to the ESP32."""

    # A full DPV sweep on the ESP32 takes ~20-24 s (201 steps x 100 ms plus ADC
    # overhead), so the scan deadline must comfortably exceed it. The short
    # default timeout applies to quick commands (status, battery, LED).
    SCAN_TIMEOUT_S = 40.0

    def __init__(self, port=config.UART_PORT, baud=config.UART_BAUD, timeout=2.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.mock = not _SERIAL_AVAILABLE
        self._ser = None
        # Unsolicited lines (button presses) that arrived while waiting for a
        # command's reply. read_event() hands them out before reading the port.
        self._pending = collections.deque()
        self._last_cmd = ""
        if not self.mock:
            try:
                self._ser = serial.Serial(port, baud, timeout=timeout)
            except Exception as exc:
                print(f"[UARTBridge] serial open failed, using mock: {exc}")
                self.mock = True
                self._ser = None

    # -- low level -----------------------------------------------------------

    def send_command(self, cmd):
        """Send a command string. A trailing newline is added if absent."""
        if not cmd.endswith("\n"):
            cmd += "\n"
        self._last_cmd = cmd.strip()
        if self.mock or self._ser is None:
            print(f"[UARTBridge:mock] -> {cmd!r}")
            return
        self._ser.write(cmd.encode("ascii"))
        self._ser.flush()

    def read_response(self, timeout=None):
        """Read one line and parse it into a dict with a ``type`` key.

        ``timeout`` overrides the port timeout for this read only; use it for
        commands (such as a DPV sweep) that take longer than the default.
        """
        if self.mock or self._ser is None:
            line = self._mock_response()
            self._last_cmd = ""
            parsed = self.parse_line(line)
            # Mark synthesised data so it can never be mistaken for a real
            # field reading downstream (result dict, display, dashboard, DB).
            parsed["mock"] = True
            return parsed

        if timeout is not None:
            self._ser.timeout = timeout
        raw = self._ser.readline()
        if timeout is not None:
            self._ser.timeout = self.timeout
        line = raw.decode("ascii", errors="replace").strip()
        return self.parse_line(line)

    def read_event(self, timeout=None):
        """Next unsolicited event: a queued one first, else the port."""
        if self._pending:
            return self._pending.popleft()
        if self.mock or self._ser is None:
            if timeout:
                time.sleep(min(timeout, 0.2))
            return {"type": "empty", "raw": "", "mock": True}
        return self.read_response(timeout=timeout)

    def _await(self, kinds, limit):
        """Read until a line of one of ``kinds`` (or an error) arrives.

        Button presses seen meanwhile are queued for read_event(), so a press
        made during a battery poll or a sweep is not lost.
        """
        deadline = time.monotonic() + limit
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            resp = self.read_response(timeout=remaining)
            kind = resp.get("type")
            if kind in kinds or kind == "error":
                return resp
            if kind == "button":
                self._pending.append(resp)

    def reset_input(self):
        """Discard buffered, unsolicited lines before issuing a command."""
        if not self.mock and self._ser is not None:
            try:
                self._ser.reset_input_buffer()
            except Exception:
                pass

    # -- parsing -------------------------------------------------------------

    @staticmethod
    def parse_line(line):
        """Parse an ESP32 -> Pi line into a dict."""
        line = (line or "").strip()
        if not line:
            return {"type": "empty", "raw": line}

        if line.startswith("ERR:"):
            return {"type": "error", "message": line[4:], "raw": line}

        if line.startswith("DATA:BIOSENSOR:"):
            payload = line[len("DATA:BIOSENSOR:"):]
            result = {"type": "biosensor", "raw": line,
                      "analyte": "H2O2", "status": "OK"}
            # Current firmware prefixes <analyte>:<status>:, older does not.
            if payload[:1].isalpha():
                head = payload.split(":", 2)
                if len(head) == 3:
                    result["analyte"], result["status"], payload = head
            result["valid"] = result["status"] == "OK"
            # First three fields are numeric, the remainder is the raw json
            # (which itself contains commas), so split only 3 times.
            parts = payload.split(",", 3)
            try:
                result["peak_current_ua"] = float(parts[0])
                result["peak_voltage_v"] = float(parts[1])
                result["re_voltage_v"] = float(parts[2])
            except (ValueError, IndexError):
                result["valid"] = False
            if len(parts) > 3:
                result["raw_json_str"] = parts[3]
                try:
                    result["raw_json"] = json.loads(parts[3])
                except (ValueError, json.JSONDecodeError):
                    result["raw_json"] = None
            return result

        if line.startswith("DATA:BATTERY:"):
            try:
                return {"type": "battery",
                        "voltage_v": float(line[len("DATA:BATTERY:"):]),
                        "raw": line}
            except ValueError:
                return {"type": "battery", "voltage_v": None, "raw": line}

        if line.startswith("DATA:BUTTON:"):
            try:
                return {"type": "button",
                        "button": int(line[len("DATA:BUTTON:"):]),
                        "raw": line}
            except ValueError:
                return {"type": "button", "button": None, "raw": line}

        if line.startswith("DATA:STATUS:"):
            payload = line[len("DATA:STATUS:"):]
            result = {"type": "status", "status": payload, "raw": line}
            # DATA:STATUS:DEGRADED:<reason> -- a subsystem failed to init.
            # Must never be flattened into a plain "not OK"; the reason is
            # what tells the operator which device is dead.
            if payload.startswith("DEGRADED"):
                _, _, reason = payload.partition(":")
                result["status"] = "DEGRADED"
                result["degraded"] = True
                result["reason"] = reason or "UNSPECIFIED"
            else:
                result["degraded"] = False
            return result

        return {"type": "unknown", "raw": line}

    # -- high level helpers --------------------------------------------------

    def trigger_scan(self, analyte="H2O2", timeout=None):
        """Run one DPV sweep for ``analyte`` and return the parsed reading.

        Waits up to ``timeout`` (default ``SCAN_TIMEOUT_S``) for the sweep,
        which takes ~20-24 s on real hardware.
        """
        limit = timeout or self.SCAN_TIMEOUT_S
        cmd = config.ANALYTES.get(analyte, {}).get("command", "CMD:SCAN")
        self.reset_input()
        self.send_command(cmd)
        resp = self._await(("biosensor",), limit)
        if resp is None:
            return {"type": "timeout", "analyte": analyte,
                    "message": f"no biosensor response within {limit:.0f}s",
                    "raw": ""}
        return resp

    def get_battery(self):
        """Battery voltage in volts, or None."""
        self.send_command("CMD:BATTERY")
        resp = self._await(("battery",), self.timeout + 1.0)
        if resp and resp.get("type") == "battery":
            return resp.get("voltage_v")
        return None

    def set_led(self, state):
        """Set the status LED. ``state`` in {ON, OFF, BLINK} (case-insensitive)."""
        state = str(state).upper()
        if state not in ("ON", "OFF", "BLINK"):
            raise ValueError(f"invalid LED state: {state}")
        self.send_command(f"CMD:LED:{state}")
        if self.mock:
            self._last_cmd = ""

    def get_status(self):
        self.send_command("CMD:STATUS")
        return self._await(("status",), self.timeout + 1.0) or {
            "type": "timeout", "message": "no status reply", "raw": ""}

    def close(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass

    # -- mock ----------------------------------------------------------------

    @staticmethod
    def mock_curve(analyte="H2O2", peak_ua=None, rng=random):
        """A plausible DPV curve: sloped background, one peak, noise."""
        if analyte == "NO3":
            start, end, step, centre, sign = 0.0, -0.8, -0.004, -0.45, -1
        else:
            start, end, step, centre, sign = -0.2, 0.6, 0.004, 0.25, 1
        peak = rng.uniform(0.5, 6.0) if peak_ua is None else peak_ua
        n = int(round((end - start) / step)) + 1
        pts = []
        for k in range(n):
            v = start + k * step
            bg = 0.35 * (v - start) * sign + 0.05
            i = sign * (bg + peak * 2.718 ** (-((v - centre) / 0.05) ** 2))
            pts.append({"v": round(v, 4), "i": round(i + rng.gauss(0, 0.01), 4)})
        return pts

    def _mock_response(self):
        """Synthesise a reply based on the last mock command."""
        cmd = self._last_cmd
        if cmd.startswith("CMD:SCAN"):
            analyte = "NO3" if cmd.endswith("NO3") else "H2O2"
            curve = self.mock_curve(analyte)
            best = (max if analyte == "H2O2" else min)(curve, key=lambda p: p["i"])
            return (f"DATA:BIOSENSOR:{analyte}:OK:{best['i']:.4f},"
                    f"{best['v']:.4f},{random.uniform(1.0, 1.9):.4f},"
                    f"{json.dumps(curve, separators=(',', ':'))}")
        if cmd == "CMD:BATTERY":
            return f"DATA:BATTERY:{random.uniform(3.5, 4.2):.3f}"
        return "DATA:STATUS:OK"


if __name__ == "__main__":
    bridge = UARTBridge()
    print(f"[UARTBridge] mock={bridge.mock}")
    print("status  :", bridge.get_status())
    print("battery :", bridge.get_battery())
    scan = bridge.trigger_scan("NO3")
    print("scan    :", {k: v for k, v in scan.items() if not k.startswith("raw")})
    print("button  :", UARTBridge.parse_line("DATA:BUTTON:2"))
    print("err     :", UARTBridge.parse_line("ERR:sensor timeout"))
    bridge.close()
