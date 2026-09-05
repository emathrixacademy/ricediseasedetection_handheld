#!/usr/bin/env python3
"""Generate docs/gpio_pinout_esp32_pi5.pdf — per-pin GPIO connection diagrams
for the ESP32 and the Raspberry Pi 5.

One landscape A4 page per controller. Wires are colour-coded by signal class
(5 V, 3.3 V, GND, I2C, UART, analog) with a legend on each page. Pin data
mirrors esp32/src/config.h, pi5/config.py and docs/WIRING.md — if the repo
changes, re-run this script.

    pip install reportlab
    python docs/generate_gpio_pinout.py
"""
import os

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas as rcanvas

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "gpio_pinout_esp32_pi5.pdf")

# Signal-class colours (RGB 0..1)
COLORS = {
    "pwr5": (0.84, 0.27, 0.27),   # 5 V
    "pwr33": (0.87, 0.52, 0.00),  # 3.3 V
    "gnd": (0.49, 0.53, 0.56),    # ground (drawn dashed)
    "i2c": (0.23, 0.49, 0.85),    # I2C
    "uart": (0.18, 0.62, 0.42),   # UART
    "ana": (0.72, 0.57, 0.12),    # analog / GPIO
}
LEGEND = [("5 V power", "pwr5"), ("3.3 V rail", "pwr33"), ("Ground", "gnd"),
          ("I2C", "i2c"), ("UART", "uart"), ("Analog / GPIO", "ana")]

# (pin label, destination, signal class)
ESP32_ROWS = [
    ("VIN",         "Buck-boost 5 V via 1 A fuse",             "pwr5"),
    ("GND",         "Common GND (shared with Pi + AFE)",       "gnd"),
    ("3V3",         "MCP4725 / ADS1115 / MCP6002 VDD",         "pwr33"),
    ("GPIO16 RX2",  "Pi GPIO14 TXD (header pin 8)",            "uart"),
    ("GPIO17 TX2",  "Pi GPIO15 RXD (header pin 10)",           "uart"),
    ("GPIO21 SDA",  "MCP4725 + ADS1115 SDA",                   "i2c"),
    ("GPIO22 SCL",  "MCP4725 + ADS1115 SCL (400 kHz)",         "i2c"),
    ("GPIO32",      "Button 1 Scan -> GND (internal pull-up)", "ana"),
    ("GPIO33",      "Button 2 Mode -> GND (internal pull-up)", "ana"),
    ("GPIO34",      "Button 3 Menu -> GND  ** EXTERNAL 10k pull-up REQUIRED **", "ana"),
    ("GPIO35",      "ADS1115 ALERT/RDY (polled)",              "ana"),
    ("GPIO27",      "220 ohm -> status LED -> GND",            "ana"),
]
ESP32_NOTES = [
    "GPIO34 and GPIO35 are input-only and have no internal pull-ups.",
    "I2C addresses: MCP4725 = 0x60 (ADDR->GND), ADS1115 = 0x49 (ADDR->3.3V).",
    "UART2 crosses over: TX->RX both directions. 115200 8N1, text protocol.",
]

PI5_ROWS = [
    ("USB-C",           "Buck-boost 5 V / 5 A",                    "pwr5"),
    ("PCIe M.2 x1",     "Hailo-8L AI HAT",                         "ana"),
    ("CSI-0",           "RGB Camera Module 3",                     "ana"),
    ("CSI-1",           "NoIR Camera Module 3",                    "ana"),
    ("GPIO14 TXD [8]",  "ESP32 GPIO16 RX2",                        "uart"),
    ("GPIO15 RXD [10]", "ESP32 GPIO17 TX2",                        "uart"),
    ("GPIO2 SDA1 [3]",  "1604 LCD backpack SDA (PCF8574 @ 0x27)",  "i2c"),
    ("GPIO3 SCL1 [5]",  "1604 LCD backpack SCL",                   "i2c"),
    ("5V [2]",          "1604 LCD backpack VCC (HD44780 needs 5V)", "pwr5"),
    ("GND [6]",         "Common GND (shared with ESP32 + AFE)",    "gnd"),
]
PI5_NOTES = [
    "[n] = physical 40-pin header position. BCM numbering elsewhere.",
    "Remove the LCD backpack's 5V SDA/SCL pull-ups (or level-shift): Pi I2C "
    "pins are 3.3V; the Pi's onboard 1.8k pull-ups suffice.",
    "GPIO8/10/11/18/24/25 freed by the ILI9341 -> 1604 LCD change.",
    "UART link is 3.3V logic on both ends - no level shifter needed.",
]


def draw_page(c, pw, ph, title, subtitle, rows, notes):
    ink = (0.11, 0.16, 0.14)
    c.setFillColorRGB(*ink)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, ph - 46, title)
    c.setFont("Helvetica", 9.5)
    c.setFillColorRGB(0.36, 0.40, 0.38)
    c.drawString(40, ph - 62, subtitle)

    # Legend (top right)
    lx = pw - 360
    c.setFont("Helvetica", 8.5)
    for i, (label, key) in enumerate(LEGEND):
        x = lx + (i % 3) * 110
        y = ph - 46 - (i // 3) * 14
        c.setStrokeColorRGB(*COLORS[key])
        c.setLineWidth(2.5)
        if key == "gnd":
            c.setDash(4, 3)
        c.line(x, y + 3, x + 22, y + 3)
        c.setDash()
        c.setFillColorRGB(*ink)
        c.drawString(x + 27, y, label)

    # Chip body
    top = ph - 96
    row_h = 26
    chip_h = len(rows) * row_h + 16
    c.setFillColorRGB(0.945, 0.937, 0.914)
    c.setStrokeColorRGB(*ink)
    c.setLineWidth(1.2)
    c.roundRect(40, top - chip_h, 150, chip_h, 6, stroke=1, fill=1)
    c.setFillColorRGB(*ink)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(115, top - 16, title.split(" — ")[0])

    # Pin rows
    for i, (pin, dest, key) in enumerate(rows):
        y = top - 34 - i * row_h
        c.setFillColorRGB(*ink)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(185, y - 3, pin)
        c.setStrokeColorRGB(*ink)
        c.setLineWidth(2)
        c.line(190, y, 200, y)                      # pin stub
        c.setStrokeColorRGB(*COLORS[key])
        if key == "gnd":
            c.setDash(5, 4)
        c.line(200, y, 470, y)                      # wire
        c.setDash()
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*ink)
        c.drawString(478, y - 3, dest)

    # Notes
    ny = top - chip_h - 24
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, ny, "Notes")
    c.setFont("Helvetica", 8.5)
    for j, note in enumerate(notes):
        c.drawString(52, ny - 14 - j * 12, "-  " + note)

    # Footer
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.drawString(40, 24, "Sources: esp32/src/config.h, pi5/config.py, "
                 "docs/WIRING.md - regenerate with docs/generate_gpio_pinout.py. "
                 "Common ground across all boards is mandatory.")
    c.showPage()


def main():
    pw, ph = landscape(A4)
    c = rcanvas.Canvas(OUT, pagesize=(pw, ph))
    c.setTitle("Rice Scanner - ESP32 & Pi 5 GPIO Pinout")
    draw_page(c, pw, ph,
              "ESP32 — GPIO connections",
              "Biosensor controller (esp32dev) - potentiostat, buttons, LED, "
              "UART2 link to the Pi",
              ESP32_ROWS, ESP32_NOTES)
    draw_page(c, pw, ph,
              "Raspberry Pi 5 — GPIO connections",
              "Main compute - cameras, Hailo-8L, 1604 I2C LCD, UART link to "
              "the ESP32",
              PI5_ROWS, PI5_NOTES)
    c.save()
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
