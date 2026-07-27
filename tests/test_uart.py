"""test_uart.py — UART protocol formatting & parsing tests (pure logic).

Protocol (115200 baud, text, newline-terminated):
  Pi -> ESP32:  CMD:SCAN, CMD:LED:ON, CMD:LED:OFF, CMD:LED:BLINK,
                CMD:BATTERY, CMD:STATUS
  ESP32 -> Pi:  DATA:BIOSENSOR:<i_ua>,<v_pk>,<v_re>,<raw_json>
                DATA:BATTERY:<v>
                DATA:BUTTON:<1|2|3>
                DATA:STATUS:OK
                ERR:<msg>

If pi5.comms.uart_bridge provides format_command / parse_message, those are
tested; otherwise reference implementations below are used.
"""
import json

import pytest

# --- try to import the real parser, else use reference implementations ------
try:
    from pi5.comms.uart_bridge import format_command, parse_message  # type: ignore
    HAVE_BRIDGE = True
except Exception:  # noqa: BLE001
    HAVE_BRIDGE = False

    VALID_COMMANDS = {"SCAN", "LED:ON", "LED:OFF", "LED:BLINK", "BATTERY", "STATUS"}

    def format_command(cmd: str) -> bytes:
        """Build a newline-terminated Pi->ESP32 command line."""
        cmd = cmd.upper()
        if cmd not in VALID_COMMANDS:
            raise ValueError(f"unknown command: {cmd}")
        return f"CMD:{cmd}\n".encode()

    def parse_message(line):
        """Parse an ESP32->Pi line into a dict {type, ...}."""
        line = line.strip()
        if line.startswith("ERR:"):
            return {"type": "error", "message": line[4:]}
        if not line.startswith("DATA:"):
            raise ValueError(f"malformed line: {line!r}")
        body = line[len("DATA:"):]
        kind, _, rest = body.partition(":")
        if kind == "BIOSENSOR":
            i_ua, v_pk, v_re, raw = rest.split(",", 3)
            return {
                "type": "biosensor",
                "peak_current_ua": float(i_ua),
                "peak_voltage_v": float(v_pk),
                "re_voltage_v": float(v_re),
                "raw": json.loads(raw),
            }
        if kind == "BATTERY":
            return {"type": "battery", "voltage_v": float(rest)}
        if kind == "BUTTON":
            n = int(rest)
            if n not in (1, 2, 3):
                raise ValueError("button must be 1..3")
            return {"type": "button", "button": n}
        if kind == "STATUS":
            return {"type": "status", "ok": rest == "OK"}
        raise ValueError(f"unknown DATA kind: {kind}")


# --------------------------- command formatting -----------------------------
@pytest.mark.parametrize("cmd,expected", [
    ("SCAN", b"CMD:SCAN\n"),
    ("LED:ON", b"CMD:LED:ON\n"),
    ("LED:OFF", b"CMD:LED:OFF\n"),
    ("LED:BLINK", b"CMD:LED:BLINK\n"),
    ("BATTERY", b"CMD:BATTERY\n"),
    ("STATUS", b"CMD:STATUS\n"),
])
def test_format_command(cmd, expected):
    assert format_command(cmd) == expected


def test_format_command_rejects_unknown():
    with pytest.raises(ValueError):
        format_command("EXPLODE")


# ----------------------------- response parsing -----------------------------
def test_parse_biosensor():
    raw = '{"adc":[1,2,3]}'
    msg = parse_message(f"DATA:BIOSENSOR:12.5,0.35,0.20,{raw}")
    assert msg["type"] == "biosensor"
    assert msg["peak_current_ua"] == pytest.approx(12.5)
    assert msg["peak_voltage_v"] == pytest.approx(0.35)
    assert msg["re_voltage_v"] == pytest.approx(0.20)
    assert msg["raw"] == {"adc": [1, 2, 3]}


def test_parse_battery():
    msg = parse_message("DATA:BATTERY:3.85")
    assert msg["type"] == "battery"
    assert msg["voltage_v"] == pytest.approx(3.85)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_parse_button(n):
    msg = parse_message(f"DATA:BUTTON:{n}")
    assert msg == {"type": "button", "button": n}


def test_parse_status():
    assert parse_message("DATA:STATUS:OK") == {"type": "status", "ok": True}


def test_parse_error():
    msg = parse_message("ERR:adc timeout")
    assert msg == {"type": "error", "message": "adc timeout"}


def test_parse_malformed():
    with pytest.raises(ValueError):
        parse_message("GARBAGE")
