"""UART bridge between the Raspberry Pi 5 and the ESP32 companion MCU.

Protocol (plain text, newline-terminated, 115200 baud)
------------------------------------------------------
Pi -> ESP32:
    CMD:SCAN
    CMD:LED:ON
    CMD:LED:OFF
    CMD:LED:BLINK
    CMD:BATTERY
    CMD:STATUS

ESP32 -> Pi:
    DATA:BIOSENSOR:<peak_current_ua>,<peak_voltage_v>,<re_voltage_v>,<raw_json>
    DATA:BATTERY:<voltage_v>
    DATA:BUTTON:<1|2|3>
    DATA:STATUS:OK
    ERR:<msg>

If pyserial or the serial port is unavailable the bridge runs in mock mode
and synthesises plausible responses.
"""

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
        if self.mock or self._ser is None:
            print(f"[UARTBridge:mock] -> {cmd!r}")
            self._last_cmd = cmd.strip()
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
            parsed = self.parse_line(line)
            # Mark synthesised data so it can never be mistaken for a real
            # field reading downstream (result dict, LCD, dashboard, DB).
            parsed["mock"] = True
            return parsed

        if timeout is not None:
            self._ser.timeout = timeout
        raw = self._ser.readline()
        if timeout is not None:
            self._ser.timeout = self.timeout
        line = raw.decode("ascii", errors="replace").strip()
        return self.parse_line(line)

    def reset_input(self):
        """Discard any buffered, unsolicited lines before issuing a command.

        The ESP32 emits DATA:BUTTON (and, on a local scan-button press, an
        unsolicited DATA:BIOSENSOR) without being asked. Clearing the buffer
        first keeps a stale line from being mistaken for a command response.
        """
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
            # first three fields are numeric, remainder is raw json (may
            # itself contain commas) so split only 3 times.
            parts = payload.split(",", 3)
            result = {"type": "biosensor", "raw": line}
            try:
                result["peak_current_ua"] = float(parts[0])
                result["peak_voltage_v"] = float(parts[1])
                result["re_voltage_v"] = float(parts[2])
            except (ValueError, IndexError):
                pass
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

    def trigger_scan(self, timeout=None):
        """Ask the ESP32 to run a biosensor sweep, return parsed reading.

        Waits up to ``timeout`` (default ``SCAN_TIMEOUT_S``) for the sweep,
        which takes ~20-24 s on real hardware. Unsolicited button/status lines
        arriving while we wait are skipped rather than returned as the result.
        """
        limit = timeout or self.SCAN_TIMEOUT_S
        deadline = time.monotonic() + limit
        self.reset_input()
        self.send_command("CMD:SCAN")

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            resp = self.read_response(timeout=remaining)
            kind = resp.get("type")
            if kind in ("biosensor", "error"):
                return resp
            # "empty" is a read timeout tick; button/status are unsolicited.
            # Keep waiting for the sweep in both cases.

        return {"type": "timeout",
                "message": f"no biosensor response within {limit:.0f}s",
                "raw": ""}

    def get_battery(self):
        """Request battery voltage, return parsed dict."""
        self.send_command("CMD:BATTERY")
        return self.read_response()

    def set_led(self, state):
        """Set the status LED. ``state`` in {ON, OFF, BLINK} (case-insensitive)."""
        state = str(state).upper()
        if state not in ("ON", "OFF", "BLINK"):
            raise ValueError(f"invalid LED state: {state}")
        self.send_command(f"CMD:LED:{state}")

    def get_status(self):
        self.send_command("CMD:STATUS")
        return self.read_response()

    def close(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass

    # -- mock ----------------------------------------------------------------

    def _mock_response(self):
        """Synthesise a reply based on the last mock command."""
        cmd = getattr(self, "_last_cmd", "")
        if cmd == "CMD:SCAN":
            raw = json.dumps({"n_points": 3,
                              "curve": [random.random() for _ in range(3)]})
            return (f"DATA:BIOSENSOR:{random.uniform(1, 50):.2f},"
                    f"{random.uniform(0.1, 0.9):.3f},"
                    f"{random.uniform(-0.2, 0.2):.3f},{raw}")
        if cmd == "CMD:BATTERY":
            return f"DATA:BATTERY:{random.uniform(3.5, 4.2):.2f}"
        if cmd == "CMD:STATUS":
            return "DATA:STATUS:OK"
        if cmd.startswith("CMD:LED:"):
            return "DATA:STATUS:OK"
        return "DATA:STATUS:OK"


if __name__ == "__main__":
    bridge = UARTBridge()
    print(f"[UARTBridge] mock={bridge.mock}")
    print("status  :", bridge.get_status())
    print("battery :", bridge.get_battery())
    bridge.set_led("BLINK")
    print("scan    :", bridge.trigger_scan())
    # test parser directly
    sample = ("DATA:BIOSENSOR:12.34,0.456,-0.010,"
              '{"curve":[1,2,3]}')
    print("parse   :", UARTBridge.parse_line(sample))
    print("button  :", UARTBridge.parse_line("DATA:BUTTON:2"))
    print("err     :", UARTBridge.parse_line("ERR:sensor timeout"))
    bridge.close()
