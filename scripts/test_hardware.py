#!/usr/bin/env python3
"""test_hardware.py — hardware self-test for the Rice Disease Handheld Scanner.

Checks each subsystem and prints PASS / FAIL / SKIP. Designed to run on the
Pi 5 but degrade gracefully (SKIP) when hardware or drivers are absent, so it
can also be run on a dev machine.

    python scripts/test_hardware.py
"""
import sys

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

UART_PORT = "/dev/ttyAMA0"


def report(name, status, detail=""):
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def check_cameras():
    """RGB (CSI0) + NoIR (CSI1) via Picamera2."""
    try:
        from picamera2 import Picamera2  # type: ignore
    except ImportError:
        report("Cameras (Picamera2)", SKIP, "picamera2 not installed")
        return
    try:
        infos = Picamera2.global_camera_info()
        if len(infos) >= 2:
            report("Cameras (Picamera2)", PASS, f"{len(infos)} cameras detected")
        elif len(infos) == 1:
            report("Cameras (Picamera2)", FAIL, "only 1 camera (need RGB + NoIR)")
        else:
            report("Cameras (Picamera2)", FAIL, "no cameras detected")
    except Exception as exc:  # noqa: BLE001
        report("Cameras (Picamera2)", FAIL, str(exc))


def check_uart():
    """UART bridge to ESP32 on /dev/ttyAMA0 @ 115200."""
    try:
        import serial  # type: ignore
    except ImportError:
        report("UART", SKIP, "pyserial not installed")
        return
    try:
        ser = serial.Serial(UART_PORT, 115200, timeout=1)
        ser.write(b"CMD:STATUS\n")
        line = ser.readline().decode(errors="replace").strip()
        ser.close()
        if line.startswith("DATA:STATUS"):
            report("UART", PASS, f"reply: {line}")
        else:
            report("UART", FAIL, f"unexpected/no reply: {line!r}")
    except Exception as exc:  # noqa: BLE001
        report("UART", SKIP, f"{UART_PORT} unavailable: {exc}")


def check_i2c_adc():
    """ADS1115 (0x49) and MCP4725 (0x60) presence on the I2C bus."""
    try:
        from smbus2 import SMBus  # type: ignore
    except ImportError:
        report("I2C / ADC", SKIP, "smbus2 not installed")
        return
    try:
        found = []
        with SMBus(1) as bus:
            for addr in (0x49, 0x60):
                try:
                    bus.write_quick(addr)
                    found.append(hex(addr))
                except OSError:
                    pass
        if 0x49 in [int(a, 16) for a in found]:
            report("I2C / ADC (ADS1115 0x49, MCP4725 0x60)", PASS,
                   f"found {found}")
        else:
            report("I2C / ADC", FAIL, f"expected 0x49/0x60, found {found}")
    except Exception as exc:  # noqa: BLE001
        report("I2C / ADC", SKIP, str(exc))


def check_lcd_spi():
    """LCD on SPI0 (CE0). Confirm spidev device is openable."""
    try:
        import spidev  # type: ignore
    except ImportError:
        report("LCD SPI", SKIP, "spidev not installed")
        return
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)  # bus 0, CE0
        spi.max_speed_hz = 4_000_000
        spi.close()
        report("LCD SPI (SPI0 CE0)", PASS, "spidev opened")
    except Exception as exc:  # noqa: BLE001
        report("LCD SPI", SKIP, f"spidev unavailable: {exc}")


def check_led():
    """LED driven by ESP32 via UART command CMD:LED:ON/OFF."""
    try:
        import serial  # type: ignore
    except ImportError:
        report("LED (via UART)", SKIP, "pyserial not installed")
        return
    try:
        ser = serial.Serial(UART_PORT, 115200, timeout=1)
        ser.write(b"CMD:LED:ON\n")
        ser.write(b"CMD:LED:OFF\n")
        ser.close()
        report("LED (via UART)", PASS, "LED on/off commands sent")
    except Exception as exc:  # noqa: BLE001
        report("LED (via UART)", SKIP, f"{UART_PORT} unavailable: {exc}")


def main():
    print("=== Rice Scanner Hardware Self-Test ===")
    check_cameras()
    check_uart()
    check_i2c_adc()
    check_lcd_spi()
    check_led()
    print("=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
