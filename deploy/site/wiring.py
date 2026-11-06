"""Wiring schematics of every part, as inline SVG for the project page.

Each section is one part or connection: a drawing, a pin-by-pin table and
notes. The drawings use CSS classes (see WIRING_CSS) so they follow the
page's light and dark theme and print in black on white.

Source of truth for the pins: esp32/src/config.h, pi5/config.py and
docs/WIRING.md in the repository. Keep this file in step with them.
"""

from __future__ import annotations

import html

WIRING_CSS = """
.sch{display:block;width:100%;min-width:640px;height:auto;margin:6px 0 4px}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:12px;padding:6px 8px;background:var(--bg)}
.sch text{font:12px system-ui,"Segoe UI",sans-serif;fill:var(--ink)}
.sch .t{font-weight:700;font-size:13px}
.sch .s{font-size:10.5px;fill:var(--muted)}
.sch .p{font:10.5px ui-monospace,Consolas,monospace;fill:var(--ink)}
.sch .bx{fill:var(--tint);stroke:var(--ink);stroke-width:1.2}
.sch .red{fill:#f6d5d5;stroke:var(--ink);stroke-width:1.2}
.sch .chip{fill:#2b2f33;stroke:#111;stroke-width:1}
.sch .chipt{fill:#fff;font:10px ui-monospace,Consolas,monospace}
.sch .part{fill:var(--bg);stroke:var(--ink);stroke-width:1.2}
.sch .sym{fill:none;stroke:var(--ink);stroke-width:1.3}
.sch .pin{fill:var(--bg);stroke:var(--ink);stroke-width:1}
.sch .used{stroke-width:2}
.sch .w{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.sch .dot{stroke:none}
.w5v{stroke:#d64545}.d5v{fill:#d64545}.l5v{fill:#d64545!important}
.w33{stroke:#dd8500}.d33{fill:#dd8500}.l33{fill:#dd8500!important}
.wgnd{stroke:#7a8288;stroke-dasharray:5 4}.dgnd{fill:#7a8288}.lgnd{fill:#7a8288!important}
.wbat{stroke:#a33a3a}.dbat{fill:#a33a3a}.lbat{fill:#a33a3a!important}
.wi2c{stroke:#3b7dd8}.di2c{fill:#3b7dd8}.li2c{fill:#3b7dd8!important}
.wuart{stroke:#2e9e6b}.duart{fill:#2e9e6b}.luart{fill:#2e9e6b!important}
.wspi{stroke:#8c4dbf}.dspi{fill:#8c4dbf}.lspi{fill:#8c4dbf!important}
.wsig{stroke:#b8860b}.dsig{fill:#b8860b}.lsig{fill:#b8860b!important}
.wana{stroke:var(--ink)}.dana{fill:var(--ink)}.lana{fill:var(--ink)!important}
.wcsi{stroke:#5f7f95;stroke-width:6!important;opacity:.55}.dcsi{fill:#5f7f95}.lcsi{fill:#5f7f95!important}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;margin:8px 0}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{display:inline-block;width:22px;height:0;border-top:3px solid}
.toc{columns:2 220px;font-size:15px}
.toc li{break-inside:avoid}
table.pins td:first-child{white-space:nowrap;font-family:ui-monospace,Consolas,monospace;font-size:13px}
section.part-sec{border-top:1px solid var(--line);margin-top:28px;padding-top:4px}
@media print{.scroll{border:0;overflow:visible}.sch{min-width:0}.noprint{display:none}
section.part-sec{break-inside:avoid-page}}
"""

KIND_NAMES = [("5v", "5 V"), ("33", "3.3 V"), ("bat", "Battery"), ("gnd", "Ground"),
              ("i2c", "I2C"), ("uart", "UART"), ("spi", "SPI"), ("sig", "Signal / GPIO"),
              ("ana", "Analog (electrodes)"), ("csi", "Camera / PCIe ribbon")]
KIND_HEX = {"5v": "#d64545", "33": "#dd8500", "bat": "#a33a3a", "gnd": "#7a8288",
            "i2c": "#3b7dd8", "uart": "#2e9e6b", "spi": "#8c4dbf", "sig": "#b8860b",
            "ana": "currentColor", "csi": "#5f7f95"}


def esc(s: object) -> str:
    return html.escape(str(s))


# --------------------------------------------------------------------------------------------
# Drawing primitives (all return SVG markup)


def svg(w: int, h: int, body: str, label: str) -> str:
    return (f'<div class="scroll"><svg class="sch" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{esc(label)}">{body}</svg></div>')


def text(x, y, s, cls="", anchor="start"):
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}"{c}>{esc(s)}</text>'


def box(x, y, w, h, title, lines=(), cls="bx"):
    out = [f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="7"/>',
           text(x + w / 2, y + 17, title, "t", "middle")]
    for i, ln in enumerate(lines):
        out.append(text(x + w / 2, y + 32 + i * 13, ln, "s", "middle"))
    return "".join(out)


def wire(pts, kind, label=None, at=None, anchor="start", dots=True):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    out = [f'<path class="w w{kind}" d="{d}"/>']
    if dots:
        for x, y in (pts[0], pts[-1]):
            out.append(f'<circle class="dot d{kind}" cx="{x}" cy="{y}" r="2.6"/>')
    if label:
        lx, ly = at if at else ((pts[0][0] + pts[1][0]) / 2 + 4, (pts[0][1] + pts[1][1]) / 2 - 5)
        out.append(text(lx, ly, label, f"s l{kind}", anchor))
    return "".join(out)


def dot(x, y, kind="ana"):
    return f'<circle class="dot d{kind}" cx="{x}" cy="{y}" r="3"/>'


def resistor(x, y, label, vertical=False, anchor=None):
    """Resistor body centred on (x, y): 26 long, leads not included."""
    if vertical:
        lx = x - 9 if anchor == "end" else x + 9
        return (f'<rect class="part" x="{x - 5}" y="{y - 13}" width="10" height="26"/>'
                + text(lx, y + 4, label, "s", anchor or "start"))
    return (f'<rect class="part" x="{x - 13}" y="{y - 5}" width="26" height="10"/>'
            + text(x, y - 9, label, "s", anchor or "middle"))


def capacitor(x, y, label, vertical=False):
    if vertical:
        return (f'<path class="sym" d="M{x - 9} {y - 3} H{x + 9} M{x - 9} {y + 3} H{x + 9}"/>'
                + text(x + 13, y + 4, label, "s"))
    return (f'<path class="sym" d="M{x - 3} {y - 9} V{y + 9} M{x + 3} {y - 9} V{y + 9}"/>'
            + text(x, y - 13, label, "s", "middle"))


def ground(x, y):
    return f'<path class="sym" d="M{x - 9} {y} H{x + 9} M{x - 6} {y + 4} H{x + 6} M{x - 3} {y + 8} H{x + 3}"/>'


def button(x, y, label):
    """Push button between (x, y) and (x + 40, y)."""
    return (f'<path class="sym" d="M{x} {y} H{x + 10} M{x + 30} {y} H{x + 40} '
            f'M{x + 10} {y} L{x + 30} {y - 9} M{x + 20} {y - 14} V{y - 20} M{x + 12} {y - 20} H{x + 28}"/>'
            + text(x + 20, y + 15, label, "s", "middle"))


def led(x, y, label):
    """LED pointing right, anode at x, cathode at x + 30."""
    return (f'<path class="sym" d="M{x} {y} H{x + 8} M{x + 8} {y - 8} V{y + 8} L{x + 22} {y} Z '
            f'M{x + 22} {y - 8} V{y + 8} M{x + 22} {y} H{x + 30} '
            f'M{x + 14} {y - 12} l6 -6 M{x + 19} {y - 10} l6 -6"/>'
            + text(x + 15, y + 22, label, "s", "middle"))


def opamp(x, y, name, role, inverting_top=True, labels="above"):
    """Op-amp pointing right; inputs at x, output at x + 70. Returns (svg, pins).

    ``labels`` "above" puts name and role over the triangle, "below" under it.
    """
    top, bot = y - 16, y + 16
    minus, plus = (top, bot) if inverting_top else (bot, top)
    ny, ry = (y - 58, y - 44) if labels == "above" else (y + 52, y + 66)
    s = (f'<path class="part" d="M{x} {y - 34} V{y + 34} L{x + 70} {y} Z"/>'
         + text(x + 6, minus + 4, "\u2212", "t") + text(x + 6, plus + 4, "+", "t")
         + text(x, ny, name, "t") + text(x, ry, role, "s"))
    return s, {"-": (x, minus), "+": (x, plus), "out": (x + 70, y)}

def legend(kinds) -> str:
    items = "".join(
        f'<span><i style="border-color:{KIND_HEX[k]};'
        f'{"border-top-style:dashed;" if k == "gnd" else ""}"></i>{esc(n)}</span>'
        for k, n in KIND_NAMES if k in kinds)
    return f'<div class="legend">{items}</div>'


def pin_table(rows, head=("From", "To", "Signal / notes")) -> str:
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    return f'<div class="wrap"><table class="pins"><tr>{th}</tr>{body}</table></div>'


# --------------------------------------------------------------------------------------------
# Sections


def sec_system():
    b = []
    b += [box(20, 20, 140, 46, "Solar panel", ["6 V, top of body"]),
          box(20, 96, 140, 46, "Solar charger", ["1S Li-ion"]),
          box(20, 172, 140, 46, "LiPo 3.7 V", ["1 cell, protected"]),
          box(20, 248, 140, 46, "Power switch", ["SPST"]),
          box(20, 324, 140, 52, "Boost converter", ["5 V / 5 A"])]
    b += [wire([(90, 66), (90, 96)], "5v"), wire([(90, 142), (90, 172)], "bat"),
          wire([(90, 218), (90, 248)], "bat"), wire([(90, 294), (90, 324)], "bat")]
    b.append(box(260, 40, 200, 150, "Raspberry Pi 5", ["4 GB", "cameras, AI models,", "fusion, TFT, database"]))
    b.append(wire([(160, 340), (220, 340), (220, 120), (260, 120)], "5v", "5 V / 5 A to USB-C", (226, 236)))
    b += [box(560, 10, 180, 40, "Hailo-8L AI HAT+", ["PCIe"]),
          box(560, 62, 180, 40, "RGB Camera Module 3", ["CSI port 0"]),
          box(560, 114, 180, 40, "NoIR Camera Module 3", ["CSI port 1"]),
          box(560, 176, 180, 58, "2.4\" TFT ILI9341", ["240 x 320, SPI0", "back face"])]
    b += [wire([(460, 60), (510, 60), (510, 30), (560, 30)], "csi", "PCIe", (486, 26)),
          wire([(460, 82), (560, 82)], "csi", "CSI-0"),
          wire([(460, 134), (560, 134)], "csi", "CSI-1"),
          wire([(460, 170), (510, 170), (510, 205), (560, 205)], "spi", "SPI0 + DC/RST", (470, 196))]
    b.append(box(260, 270, 200, 100, "ESP32 DevKit", ["DPV sweep, buttons,", "LED, battery"]))
    b += [wire([(330, 190), (330, 270)], "uart", "UART", (336, 236)),
          wire([(390, 190), (390, 270)], "uart")]
    b.append(box(190, 410, 110, 40, "Fuse 1 A"))
    b += [wire([(160, 360), (180, 360), (180, 430), (190, 430)], "5v"),
          wire([(300, 430), (360, 430), (360, 370)], "5v", "VIN", (366, 404))]
    b += [box(560, 260, 180, 70, "Potentiostat (AFE)", ["MCP4725 DAC", "MCP6004 op-amps", "ADS1115 ADC"]),
          box(560, 370, 180, 60, "Needle electrodes", ["WE, RE (Ag/AgCl), CE"]),
          box(20, 400, 140, 60, "Buttons + LED", ["SCAN, MODE, MENU", "status LED"])]
    b += [wire([(460, 300), (560, 300)], "i2c", "I2C"),
          wire([(650, 330), (650, 370)], "ana", "3 leads", (656, 354)),
          wire([(160, 440), (175, 440), (175, 470), (420, 470), (420, 370)], "sig", "GPIO", (240, 464))]
    drawing = svg(760, 480, "".join(b), "System block diagram")
    return ("system", "Whole scanner: block diagram", "How the parts connect. Details of each "
            "connection are in the sections below.", drawing,
            legend({"5v", "bat", "uart", "spi", "i2c", "sig", "ana", "csi"}), "",
            ["One star ground: the Pi 5, ESP32, boost converter and front end all return to one "
             "point.", "The Pi 5 needs a full 5 V / 5 A supply; under-sized converters cause "
             "brown-outs during AI inference."])


def sec_power():
    b = [box(20, 20, 150, 50, "Solar panel", ["6 V mini panel"]),
         box(20, 120, 150, 70, "Solar charger", ["1S Li-ion module", "IN+ IN-  BAT+ BAT-"]),
         box(20, 240, 150, 50, "LiPo 3.7 V", ["5000 mAh, protected"]),
         box(240, 240, 100, 50, "Switch", ["SPST"]),
         box(400, 220, 150, 90, "Boost converter", ["IN 3.0-4.2 V", "OUT 5.1 V / 5 A"]),
         box(610, 120, 130, 50, "Pi 5 USB-C", ["5 V / 5 A"]),
         box(610, 240, 70, 40, "Fuse 1 A"),
         box(610, 320, 130, 50, "ESP32 VIN", ["(5V pin)"])]
    b += [wire([(70, 70), (70, 120)], "5v", "+", (76, 98)),
          wire([(120, 70), (120, 120)], "gnd", "-", (126, 98)),
          wire([(70, 190), (70, 240)], "bat", "BAT+", (76, 218)),
          wire([(120, 190), (120, 240)], "gnd", "BAT-", (126, 218)),
          wire([(170, 265), (240, 265)], "bat", "3.7 V"),
          wire([(340, 265), (400, 265)], "bat"),
          wire([(550, 245), (580, 245), (580, 145), (610, 145)], "5v", "5 V", (586, 196)),
          wire([(550, 260), (610, 260)], "5v"),
          wire([(680, 260), (700, 260), (700, 320)], "5v"),
          wire([(475, 310), (475, 440), (30, 440)], "gnd", "GND star point", (480, 430))]
    # battery divider to ADS1115 AIN2
    b += [wire([(95, 290), (95, 330), (200, 330), (200, 340)], "bat"),
          resistor(200, 353, "100 k 1%", True, "end"),
          wire([(200, 366), (200, 392)], "bat", dots=False), dot(200, 379, "bat"),
          resistor(200, 405, "100 k 1%", True, "end"),
          wire([(200, 418), (200, 440)], "gnd", dots=False), dot(200, 440, "gnd"),
          wire([(200, 379), (300, 379)], "bat", "to ADS1115 AIN2 (battery / 2)", (306, 383))]
    drawing = svg(760, 460, "".join(b), "Power wiring")
    rows = [("Solar panel +/-", "Charger IN+ / IN-", "6 V, field top-up"),
            ("Charger BAT+ / BAT-", "LiPo + / -", "charge and protection"),
            ("LiPo +", "Power switch -> boost IN+", "3.0-4.2 V"),
            ("Boost OUT 5 V", "Pi 5 USB-C", "5 V / 5 A (short, thick wires)"),
            ("Boost OUT 5 V", "1 A fuse -> ESP32 VIN (5V pin)", "ESP32 regulates to 3.3 V"),
            ("LiPo +", "100 k -> node -> 100 k -> GND", "node to ADS1115 AIN2; 4.2 V reads 2.1 V"),
            ("All GND", "One star point", "Pi 5, ESP32, boost, front end")]
    return ("power", "Power", "Solar panel, charger, battery, switch, 5 V converter, fuse, and the "
            "battery-voltage divider.", drawing, legend({"5v", "bat", "gnd"}), pin_table(rows),
            ["The battery is one 3.7 V cell (not 2S). Below 3.4 V the scanner shows a warning; "
             "below 3.0 V the cell is treated as empty.",
             "The divider uses 1% resistors; BATT_DIVIDER_RATIO = 2.0 in the firmware must match."])


PI_USED = {1: ("3V3", "TFT VCC", "33"), 6: ("GND", "TFT GND", "gnd"),
           8: ("GPIO14 TXD", "ESP32 GPIO16 RX2", "uart"),
           10: ("GPIO15 RXD", "ESP32 GPIO17 TX2", "uart"),
           12: ("GPIO18", "backlight switch gate", "sig"),
           14: ("GND", "ESP32 GND", "gnd"),
           18: ("GPIO24", "TFT RESET", "sig"), 19: ("GPIO10 MOSI", "TFT SDI", "spi"),
           22: ("GPIO25", "TFT DC", "sig"), 23: ("GPIO11 SCLK", "TFT SCK", "spi"),
           24: ("GPIO8 CE0", "TFT CS", "spi")}


def sec_pi():
    x0, y0, dy = 340, 40, 18
    b = ['<rect class="bx" x="300" y="20" width="160" height="384" rx="8"/>',
         text(380, 14, "Raspberry Pi 5 - 40-pin header", "t", "middle")]
    for n in range(1, 41):
        row, right = (n - 1) // 2, n % 2 == 0
        px = x0 + (60 if right else 20)
        py = y0 + row * dy
        used = n in PI_USED
        kind = PI_USED[n][2] if used else None
        cls = f"pin used w{kind}" if used else "pin"
        b.append(f'<rect class="{cls}" x="{px - 6}" y="{py - 6}" width="12" height="12" rx="2"/>')
        b.append(text(px + (14 if right else -14), py + 4, str(n), "p", "start" if right else "end"))
        if used:
            name, dest, k = PI_USED[n]
            if right:
                b.append(wire([(px + 34, py), (560, py)], k, dots=False))
                b.append(text(566, py + 4, f"{name} -> {dest}", f"s l{k}"))
            else:
                b.append(wire([(px - 34, py), (200, py)], k, dots=False))
                b.append(text(194, py + 4, f"{dest} <- {name}", f"s l{k}", "end"))
    b.append(text(380, 420, "pin 1 = top left (square pad); odd pins left, even pins right", "s", "middle"))
    drawing = svg(760, 430, "".join(b), "Raspberry Pi 5 header pin map")
    rows = [(f"pin {n}  {v[0]}", v[1], {"33": "3.3 V", "gnd": "ground", "uart": "UART 115200 8N1",
                                         "spi": "SPI0", "sig": "GPIO"}[v[2]])
            for n, v in sorted(PI_USED.items())]
    rows += [("USB-C", "Boost converter 5 V / 5 A", "power"),
             ("CSI/DSI port 0", "RGB Camera Module 3", "22-pin, 0.5 mm ribbon"),
             ("CSI/DSI port 1", "NoIR Camera Module 3", "22-pin, 0.5 mm ribbon"),
             ("PCIe FFC", "Hailo-8L AI HAT+", "16-pin ribbon, HAT on the header")]
    return ("pi5", "Raspberry Pi 5 header", "Every pin the scanner uses on the Pi 5's 40-pin "
            "header (BCM GPIO numbers and physical pin numbers).", drawing,
            legend({"33", "gnd", "uart", "spi", "sig"}), pin_table(rows, ("Pi 5 pin", "To", "Type")),
            ["Enable SPI and the UART (setup.sh does it): raspi-config SPI on, serial hardware on, "
             "serial login shell off.", "All Pi pins are 3.3 V logic: never connect a 5 V signal."])


def sec_tft():
    b = [box(20, 20, 170, 260, "Raspberry Pi 5", ["header pins"]),
         box(560, 20, 180, 300, "2.4\" TFT module", ["ILI9341, red PCB"], "red")]
    rows = [("pin 1  3V3", "VCC", "33"), ("pin 6  GND", "GND", "gnd"),
            ("pin 24 GPIO8 CE0", "CS", "spi"), ("pin 18 GPIO24", "RESET", "sig"),
            ("pin 22 GPIO25", "DC", "sig"), ("pin 19 GPIO10 MOSI", "SDI (MOSI)", "spi"),
            ("pin 23 GPIO11 SCLK", "SCK", "spi")]
    for i, (pi, tft, k) in enumerate(rows):
        y = 70 + i * 28
        b += [text(184, y + 4, pi, "p", "end"), text(570, y + 4, tft, "p"),
              wire([(190, y), (560, y)], k)]
    b += [text(570, 270, "LED   <- backlight switch", "p"),
          text(570, 288, "SDO, T_CLK, T_CS, T_DIN,", "s"), text(570, 301, "T_DO, T_IRQ: not connected", "s")]
    # backlight switch
    b += [text(20, 304, "Backlight switch (GPIO18 high = on)", "t"),
          text(184, 340 + 4, "pin 12 GPIO18", "p", "end"),
          wire([(190, 340), (225, 340)], "sig"), resistor(238, 340, "100 Ω"),
          wire([(251, 340), (300, 340)], "sig"), dot(275, 340, "sig"),
          wire([(275, 340), (275, 360)], "sig", dots=False), resistor(275, 373, "100 k", True, "end"),
          wire([(275, 386), (275, 396)], "gnd", dots=False), ground(275, 396),
          box(300, 320, 90, 70, "2N7002", ["N-MOSFET", "G  D  S"]),
          wire([(345, 390), (345, 404)], "gnd", "S", (350, 402), dots=False), ground(345, 404),
          wire([(390, 335), (430, 335)], "sig", "D", (394, 330)),
          box(430, 300, 90, 70, "AO3401", ["P-MOSFET", "G  S  D"]),
          wire([(410, 335), (410, 300), (410, 290)], "sig", dots=False), dot(410, 335, "sig"),
          resistor(410, 277, "10 k", True), wire([(410, 264), (410, 252), (475, 252)], "33", dots=False),
          wire([(475, 252), (475, 300)], "33", "3.3 V (source)", (480, 262)),
          wire([(520, 345), (545, 345), (545, 266), (560, 266)], "33", "LED", (526, 340))]
    drawing = svg(760, 420, "".join(b), "TFT display wiring")
    trows = [("TFT VCC", "Pi pin 1 (3.3 V)", "panel and logic"),
             ("TFT GND", "Pi pin 6", ""),
             ("TFT CS", "Pi pin 24, GPIO8 (SPI0 CE0)", "chip select"),
             ("TFT RESET", "Pi pin 18, GPIO24", ""),
             ("TFT DC", "Pi pin 22, GPIO25", "data / command"),
             ("TFT SDI (MOSI)", "Pi pin 19, GPIO10", "SPI0 data, 32 MHz"),
             ("TFT SCK", "Pi pin 23, GPIO11", "SPI0 clock"),
             ("TFT LED", "AO3401 drain", "backlight, 30-60 mA"),
             ("AO3401 source", "3.3 V; 10 k from gate to 3.3 V", "off by default"),
             ("AO3401 gate", "2N7002 drain", ""),
             ("2N7002 gate", "100 Ω to GPIO18 (pin 12); 100 k to GND", "PWM dims"),
             ("TFT SDO, T_*", "not connected", "write-only, no touch")]
    return ("tft", "2.4\" TFT display", "The ILI9341 colour screen on the back of the scanner, on "
            "the Pi 5's SPI0, and its backlight switch.", drawing,
            legend({"33", "gnd", "spi", "sig"}), pin_table(trows, ("TFT / part pin", "To", "Notes")),
            ["Never wire the TFT's LED pin to a GPIO pin: the backlight draws 30-60 mA, a Pi GPIO "
             "about 16 mA. If dimming isn't needed, tie LED straight to 3.3 V.",
             "Software: luma.lcd ili9341, rotate = 1 (portrait); rpi-lgpio on the Pi 5."])


def sec_cameras():
    b = [box(280, 30, 200, 140, "Raspberry Pi 5", ["CSI/DSI 0     CSI/DSI 1", "", "PCIe FFC"]),
         box(20, 20, 190, 56, "RGB Camera Module 3", ["IMX708, colour"]),
         box(20, 120, 190, 56, "NoIR Camera Module 3", ["IMX708 + NIR filter"]),
         box(560, 50, 180, 70, "Hailo-8L AI HAT+", ["13 TOPS", "sits on the header"])]
    b += [wire([(210, 48), (245, 48), (245, 80), (280, 80)], "csi", "22-to-15 pin ribbon", (60, 96)),
          wire([(210, 148), (245, 148), (245, 110), (280, 110)], "csi"),
          wire([(480, 140), (520, 140), (520, 85), (560, 85)], "csi", "16-pin PCIe ribbon", (496, 160)),
          text(115, 200, "Both cameras in one fixed mount, side by side,", "s", "middle"),
          text(115, 214, "so they see the same leaf from the same angle.", "s", "middle")]
    drawing = svg(760, 225, "".join(b), "Cameras and AI accelerator wiring")
    rows = [("RGB Camera Module 3", "Pi 5 CSI/DSI port 0 (CAM0)", "Pi 5 22-pin to camera 15-pin ribbon"),
            ("NoIR Camera Module 3", "Pi 5 CSI/DSI port 1 (CAM1)", "same cable; optical filter on the lens"),
            ("Hailo-8L AI HAT+", "Pi 5 PCIe FFC + 40-pin header", "standoffs; header pins pass through"),
            ("Active cooler", "Pi 5 fan connector", "keeps the Pi 5 below throttling")]
    return ("cameras", "Cameras and AI accelerator", "The two camera modules and the Hailo-8L on "
            "the Pi 5's ribbon connectors.", drawing, legend({"csi"}),
            pin_table(rows, ("Part", "Connects to", "Cable / notes")),
            ["Ribbon contacts face the board on the Pi 5 connectors; lock the latches.",
             "pi5/config.py: RGB_CAMERA_NUM = 0, NIR_CAMERA_NUM = 1. The NDVI colour channels "
             "depend on the filter fitted (NDVI_NIR_CHANNEL / NDVI_VIS_CHANNEL)."])


def sec_uart():
    b = [box(40, 30, 220, 140, "Raspberry Pi 5", ["/dev/ttyAMA0, 115200 8N1"]),
         box(500, 30, 220, 140, "ESP32 DevKit", ["UART2 (Serial2)"])]
    b += [text(250, 84, "pin 8  GPIO14 TXD", "p", "end"), text(510, 84, "GPIO16 RX2", "p"),
          wire([(260, 80), (500, 80)], "uart", "Pi transmits -> ESP32 receives", (300, 72)),
          text(250, 124, "pin 10 GPIO15 RXD", "p", "end"), text(510, 124, "GPIO17 TX2", "p"),
          wire([(260, 120), (500, 120)], "uart", "ESP32 transmits -> Pi receives", (300, 112)),
          text(250, 160, "pin 14 GND", "p", "end"), text(510, 160, "GND", "p"),
          wire([(260, 156), (500, 156)], "gnd", "common ground - required", (300, 150))]
    drawing = svg(760, 190, "".join(b), "UART link")
    rows = [("Pi pin 8, GPIO14 TXD", "ESP32 GPIO16 (RX2)", "Pi -> ESP32 commands"),
            ("Pi pin 10, GPIO15 RXD", "ESP32 GPIO17 (TX2)", "ESP32 -> Pi data"),
            ("Pi pin 14, GND", "ESP32 GND", "shared ground"),
            ("Pi -> ESP32", "CMD:SCAN:H2O2 | CMD:SCAN:NO3 | CMD:BATTERY | CMD:STATUS | CMD:LED:*", "text, newline"),
            ("ESP32 -> Pi", "DATA:BIOSENSOR:<analyte>:<status>:... | DATA:BATTERY | DATA:BUTTON:<1|2|3>", "")]
    return ("uart", "Pi 5 to ESP32 link (UART)", "A crossed serial link: each side's transmit "
            "goes to the other's receive.", drawing, legend({"uart", "gnd"}),
            pin_table(rows, ("From", "To", "Notes")),
            ["Both sides are 3.3 V logic: no level shifter.",
             "Without the shared ground the link works intermittently, the hardest fault to find."])


# ESP32-DevKitC (38-pin) header, top to bottom, as printed on the board.
ESP_LEFT = ["3V3", "EN", "VP 36", "VN 39", "34", "35", "32", "33", "25", "26", "27", "14", "12",
            "GND", "13", "D2 9", "D3 10", "CMD 11", "5V"]
ESP_RIGHT = ["GND", "23", "22", "TX 1", "RX 3", "21", "GND", "19", "18", "5", "17", "16", "4",
             "0", "2", "15", "D1 8", "D0 7", "CLK 6"]
ESP_USED = {"3V3": ("front end VDD, pull-ups", "33"), "5V": ("VIN from 1 A fuse", "5v"),
            "GND": ("common ground", "gnd"), "34": ("MENU button + 10 k pull-up", "sig"),
            "35": ("ADS1115 ALERT", "sig"), "32": ("SCAN button", "sig"),
            "33": ("MODE button", "sig"), "27": ("status LED via 220 Ω", "sig"),
            "22": ("I2C SCL", "i2c"), "21": ("I2C SDA", "i2c"),
            "17": ("TX2 -> Pi GPIO15", "uart"), "16": ("RX2 <- Pi GPIO14", "uart")}


def sec_esp32():
    x0, y0, dy = 330, 50, 19
    b = ['<rect class="chip" x="300" y="22" width="160" height="410" rx="6"/>',
         text(380, 14, "ESP32 DevKitC, 38 pins (top = antenna end)", "t", "middle"),
         '<rect x="340" y="28" width="80" height="22" rx="3" fill="#c9a227" opacity=".85"/>']
    for side, names in (("L", ESP_LEFT), ("R", ESP_RIGHT)):
        for i, nm in enumerate(names):
            px = x0 if side == "L" else x0 + 100
            py = y0 + 14 + i * dy
            key = nm if nm in ESP_USED else nm.split()[0] if nm.split()[0] in ("GND",) else nm
            used = key in ESP_USED
            k = ESP_USED[key][1] if used else None
            b.append(f'<circle class="{"pin used w" + k if used else "pin"}" cx="{px}" cy="{py}" r="5"/>')
            b.append(f'<text x="{px + (10 if side == "L" else -10)}" y="{py + 4}" '
                     f'text-anchor="{"start" if side == "L" else "end"}" class="chipt">{esc(nm)}</text>')
            if used:
                if side == "L":
                    b.append(wire([(px - 8, py), (210, py)], k, dots=False))
                    b.append(text(204, py + 4, ESP_USED[key][0], f"s l{k}", "end"))
                else:
                    b.append(wire([(px + 8, py), (550, py)], k, dots=False))
                    b.append(text(556, py + 4, ESP_USED[key][0], f"s l{k}"))
    drawing = svg(760, 445, "".join(b), "ESP32 pin map")
    rows = [("GPIO16 (RX2)", "Pi pin 8 GPIO14 TXD", "UART 115200"),
            ("GPIO17 (TX2)", "Pi pin 10 GPIO15 RXD", "UART 115200"),
            ("GPIO21 (SDA)", "MCP4725 SDA, ADS1115 SDA", "I2C 400 kHz, 4.7 k pull-up"),
            ("GPIO22 (SCL)", "MCP4725 SCL, ADS1115 SCL", "I2C 400 kHz, 4.7 k pull-up"),
            ("GPIO32", "SCAN button -> GND", "internal pull-up"),
            ("GPIO33", "MODE button -> GND", "internal pull-up"),
            ("GPIO34", "MENU button -> GND", "input-only: external 10 k to 3.3 V"),
            ("GPIO35", "ADS1115 ALERT/RDY", "input-only, 10 k pull-up if used"),
            ("GPIO27", "220 Ω -> LED -> GND", "about 6 mA"),
            ("5V (VIN)", "boost 5 V via 1 A fuse", ""), ("3V3", "front end and pull-ups", "about 1 mA"),
            ("GND", "common ground", "")]
    return ("esp32", "ESP32 pin map", "Every ESP32 pin the scanner uses. Pin names as printed on "
            "the common 38-pin DevKitC; check your board's silkscreen.", drawing,
            legend({"5v", "33", "gnd", "i2c", "uart", "sig"}), pin_table(rows, ("ESP32 pin", "To", "Notes")),
            ["Leave GPIO0, 2, 12 and 15 free (boot-mode straps) and never use GPIO6-11 (flash).",
             "GPIO34-39 are inputs only and have no internal pull-ups."])


def sec_buttons():
    b = [box(20, 20, 130, 250, "ESP32", ["GPIO side"])]
    for i, (gpio, name) in enumerate((("GPIO32", "SCAN (trigger)"), ("GPIO33", "MODE"), ("GPIO34", "MENU"))):
        y = 60 + i * 60
        b += [text(144, y + 4, gpio, "p", "end"), wire([(150, y), (300, y)], "sig"),
              button(300, y, name), wire([(340, y), (400, y)], "gnd", dots=False), ground(400, y + 2)]
    b += [dot(230, 180, "sig"), wire([(230, 180), (230, 173)], "sig", dots=False),
          resistor(230, 160, "", True), wire([(230, 147), (230, 140)], "33", dots=False),
          '<path class="w w33" d="M218 140 H242"/>', text(212, 144, "3.3 V", "s l33", "end"),
          text(242, 164, "10 k", "s"),
          text(144, 234, "GPIO27", "p", "end"), wire([(150, 230), (220, 230)], "sig"),
          resistor(233, 230, "220 Ω"), wire([(246, 230), (290, 230)], "sig", dots=False),
          led(290, 230, "status LED"), wire([(320, 230), (400, 230)], "gnd", dots=False), ground(400, 232)]
    drawing = svg(560, 280, "".join(b), "Buttons and LED")
    rows = [("SCAN", "GPIO32 to GND", "runs a scan (trigger on the grip)"),
            ("MODE", "GPIO33 to GND", "H2O2 / nitrate / both"),
            ("MENU", "GPIO34 to GND, 10 k from GPIO34 to 3.3 V", "battery and status screen"),
            ("Status LED", "GPIO27 -> 220 Ω -> LED anode, cathode -> GND", "blinks while scanning")]
    return ("buttons", "Buttons and status LED", "Three active-low push buttons and the LED.",
            drawing, legend({"sig", "33", "gnd"}), pin_table(rows, ("Part", "Wiring", "Function")),
            ["Buttons are debounced in firmware (40 ms) and sent to the Pi as DATA:BUTTON:1/2/3."])


def sec_i2c():
    b = [box(20, 90, 130, 150, "ESP32", ["GPIO21 SDA", "GPIO22 SCL", "3V3, GND"]),
         box(360, 50, 170, 120, "MCP4725 DAC", ["address 0x60", "A0 -> GND", "VOUT -> control amp"]),
         box(580, 50, 170, 210, "ADS1115 ADC", ["address 0x49", "ADDR -> 3.3 V", "A0 TIA output",
                                               "A1 RE buffer", "A2 battery / 2", "A3 virtual ground",
                                               "ALERT -> GPIO35"])]
    b += [wire([(150, 200), (580, 200)], "i2c", "SDA", (160, 194)),
          wire([(150, 222), (580, 222)], "i2c", "SCL", (160, 238)),
          dot(400, 200, "i2c"), wire([(400, 200), (400, 170)], "i2c", dots=False),
          dot(470, 222, "i2c"), wire([(470, 222), (470, 170)], "i2c", dots=False),
          text(404, 186, "SDA", "s li2c"), text(474, 186, "SCL", "s li2c")]
    b += [wire([(150, 110), (190, 110), (190, 30), (665, 30), (665, 50)], "33", "3.3 V", (196, 60)),
          dot(445, 30, "33"), wire([(445, 30), (445, 50)], "33", dots=False),
          dot(240, 30, "33"), wire([(240, 30), (240, 157)], "33", dots=False),
          resistor(240, 170, "4.7 k", True, "end"), wire([(240, 183), (240, 200)], "i2c", dots=False),
          dot(240, 200, "i2c"),
          dot(290, 30, "33"), wire([(290, 30), (290, 157)], "33", dots=False),
          resistor(290, 170, "4.7 k", True), wire([(290, 183), (290, 222)], "i2c", dots=False),
          dot(290, 222, "i2c"), text(430, 24, "VDD", "s l33"), text(650, 24, "VDD", "s l33")]
    drawing = svg(760, 270, "".join(b), "I2C bus")
    rows = [("ESP32 GPIO21", "MCP4725 SDA, ADS1115 SDA", "4.7 k to 3.3 V"),
            ("ESP32 GPIO22", "MCP4725 SCL, ADS1115 SCL", "4.7 k to 3.3 V, 400 kHz"),
            ("MCP4725 A0", "GND", "address 0x60"), ("ADS1115 ADDR", "3.3 V", "address 0x49"),
            ("ADS1115 ALERT", "ESP32 GPIO35", "10 k pull-up to 3.3 V"),
            ("VDD (both)", "ESP32 3V3, 100 nF at each chip", ""), ("GND (both)", "common ground", "")]
    return ("i2c", "I2C bus: DAC and ADC", "The ESP32 talks to the converter chips of the "
            "biosensor front end.", drawing, legend({"i2c", "33"}), pin_table(rows, ("Pin", "To", "Notes")),
            ["At bring-up an I2C scan must find exactly 0x60 and 0x49. Missing pull-ups are the usual "
             "cause when it does not."])

def sec_afe():
    b = []
    # Virtual ground: 10 k / 10 k divider, 100 nF, buffered by U1D.
    b += [text(50, 26, "3.3 V", "s l33", "middle"), wire([(50, 32), (50, 50)], "33", dots=False),
          resistor(50, 63, "10 k", True, "end"), wire([(50, 76), (50, 125)], "ana", dots=False),
          resistor(50, 138, "10 k", True, "end"), wire([(50, 151), (50, 162)], "ana", dots=False),
          ground(50, 162), dot(50, 100), wire([(50, 100), (170, 100)], "ana", dots=False),
          dot(110, 100), wire([(110, 100), (110, 124)], "ana", dots=False),
          capacitor(110, 127, "100 nF", True), wire([(110, 130), (110, 150)], "ana", dots=False),
          ground(110, 150)]
    s1, d = opamp(180, 100, "U1D (12, 13, 14)", "virtual-ground buffer", inverting_top=False)
    b.append(s1)
    b += [wire([(170, 100), (170, d["+"][1]), d["+"]], "ana", dots=False),
          wire([d["out"], (265, 100), (265, 150), (165, 150), (165, d["-"][1]), d["-"]], "ana",
               dots=False),
          dot(265, 100), wire([(265, 100), (700, 100)], "ana", "VGND 1.65 V -> A3", (560, 94),
                              dots=False)]
    # TIA: U1B, WE into the inverting input, Rf || Cf feedback above.
    s1, t = opamp(420, 250, "U1B (5, 6, 7)", "transimpedance amplifier (TIA)", labels="below")
    b.append(s1)
    b += [dot(330, 100), wire([(330, 100), (330, t["+"][1]), t["+"]], "ana", dots=False),
          wire([(240, 234), t["-"]], "ana", "WE (working electrode)", (240, 226)),
          dot(395, 234), wire([(395, 234), (395, 160), (440, 160)], "ana", dots=False),
          resistor(453, 160, "Rf 100 k 1%"), wire([(466, 160), (520, 160), (520, 250)], "ana", dots=False),
          dot(395, 195), wire([(395, 195), (450, 195)], "ana", dots=False), capacitor(453, 195, "Cf 100 pF"),
          wire([(456, 195), (520, 195)], "ana", dots=False), dot(520, 195), dot(520, 250),
          wire([t["out"], (700, 250)], "ana", "TIA out -> A0", (560, 244), dots=False)]
    # DAC and the control amplifier U1C driving CE.
    b.append(box(20, 370, 120, 60, "MCP4725", ["VOUT = VGND - E"]))
    s1, c = opamp(220, 400, "U1C (8, 9, 10)", "control amplifier", inverting_top=False)
    b.append(s1)
    b += [wire([(140, 384), c["+"]], "sig", "VOUT", (150, 378), dots=False),
          wire([c["out"], (318, 400)], "ana", dots=False), resistor(331, 400, "1 k"),
          wire([(344, 400), (395, 400)], "ana", "to CE", (360, 418)),
          dot(300, 400), wire([(300, 400), (300, 448), (261, 448)], "ana", dots=False),
          capacitor(258, 448, "10 nF"), wire([(255, 448), (210, 448), (210, 416)], "ana", dots=False),
          wire([(200, 416), c["-"]], "ana", dots=False), dot(210, 416)]
    # RE buffer U1A; its output feeds A1 and, through 10 k, the control amplifier.
    s1, a = opamp(520, 400, "U1A (1, 2, 3)", "reference-electrode buffer", inverting_top=False)
    b.append(s1)
    b += [wire([(455, 384), a["+"]], "ana", "RE (Ag/AgCl)", (440, 376)),
          wire([a["out"], (620, 400), (620, 476), (505, 476), (505, a["-"][1]), a["-"]], "ana",
               dots=False),
          dot(620, 400), wire([(620, 400), (700, 400)], "ana", "-> A1", (640, 394), dots=False),
          dot(505, 476), wire([(505, 476), (380, 476)], "ana", dots=False), resistor(367, 476, "10 k"),
          wire([(354, 476), (200, 476), (200, 416)], "ana", "RE feedback", (220, 492), dots=False),
          box(700, 40, 55, 450, "ADS", ["1115"]),
          text(727, 104, "A3", "p", "middle"), text(727, 254, "A0", "p", "middle"),
          text(727, 404, "A1", "p", "middle")]
    drawing = svg(760, 505, "".join(b), "Potentiostat circuit")
    rows = [("MCP4725 VOUT", "U1C + (pin 10)", "commanded potential"),
            ("U1C out (pin 8)", "1 k -> CE", "drives the counter electrode"),
            ("U1C - (pin 9)", "10 k from U1A out; 10 nF to pin 8", "control loop"),
            ("RE", "U1A + (pin 3)", "shielded lead"),
            ("U1A out (pin 1)", "U1A - (pin 2), ADS1115 A1, 10 k to U1C -", "RE buffer"),
            ("WE", "U1B - (pin 6)", "shielded lead"),
            ("U1B out (pin 7)", "ADS1115 A0; Rf 100 k ‖ Cf 100 pF to pin 6", "TIA"),
            ("Divider 10 k / 10 k", "U1D + (pin 12), 100 nF to GND", "1.65 V"),
            ("U1D out (pin 14)", "U1D - (pin 13), U1B + (pin 5), ADS1115 A3", "VGND buffer"),
            ("MCP6004 pin 4 / 11", "3.3 V / GND, 100 nF at pin 4", "supply")]
    return ("afe", "Potentiostat (biosensor front end)", "MCP6004 quad op-amp: the control "
            "amplifier holds the reference electrode at the DAC's voltage, the TIA holds the "
            "working electrode at virtual ground and turns its current into a voltage.", drawing,
            legend({"ana", "sig", "33"}), pin_table(rows, ("Node", "Connects to", "Role")),
            ["E(WE vs RE) = VGND - VDAC. The H2O2 sweep -0.2 ... +0.6 V needs VDAC 1.85 ... 1.05 V.",
             "Current I = (V_A0 - V_A3) / 100 k, oxidation positive; readable range +/-16.5 uA.",
             "Fit Cf (100 pF): without it the TIA oscillates and every reading is noise."])


def sec_electrodes():
    b = ['<path class="sym" d="M40 110 L300 110 L330 100 L330 120 L300 110"/>',
         '<rect class="bx" x="40" y="96" width="260" height="28" rx="4" opacity=".55"/>',
         text(170, 88, "Stainless-steel needle housing with hydrogel", "s", "middle"),
         wire([(310, 104), (360, 70), (600, 70)], "ana", "WE  working (carbon / gold)", (400, 64)),
         wire([(316, 110), (600, 110)], "ana", "RE  reference (Ag/AgCl)", (400, 104)),
         wire([(310, 116), (360, 150), (600, 150)], "ana", "CE  counter (platinum)", (400, 144)),
         box(600, 50, 140, 130, "AFE board", ["WE -> U1B pin 6", "RE -> U1A pin 3", "CE <- 1 k <- U1C",
                                              "shield -> GND"]),
         text(170, 150, "JST connector at the housing:", "s", "middle"),
         text(170, 164, "field-swappable electrode cartridge", "s", "middle")]
    drawing = svg(760, 200, "".join(b), "Electrodes")
    rows = [("WE (working)", "AFE U1B - (pin 6)", "carbon fibre or gold wire"),
            ("RE (reference)", "AFE U1A + (pin 3)", "Ag/AgCl wire"),
            ("CE (counter)", "AFE U1C out via 1 k", "platinum wire"),
            ("Cable shields", "AFE ground at one end only", "2-core shielded cable")]
    return ("electrodes", "Needle electrodes", "The three electrodes in the needle housing and "
            "their leads to the front end.", drawing, legend({"ana"}),
            pin_table(rows, ("Electrode", "To", "Material / cable")),
            ["Keep the leads short and shielded: the signal is microamps.",
             "Ground each shield at the AFE end only, so it cannot carry a ground loop."])


SECTIONS = [sec_system, sec_power, sec_pi, sec_tft, sec_cameras, sec_uart, sec_esp32,
            sec_buttons, sec_i2c, sec_afe, sec_electrodes]

BRINGUP = [
    ("1", "Continuity-check the ground bus before any power", "every ground under 1 Ω to the star point"),
    ("2", "5 V to ESP32 VIN only", "3V3 pin reads 3.30 V ± 0.1 V"),
    ("3", "Measure the virtual ground (U1D out)", "1.650 V ± 20 mV"),
    ("4", "I2C scan from the ESP32", "exactly 0x60 and 0x49"),
    ("5", "Command DAC codes, measure VOUT", "0.806 mV per code"),
    ("6", "Inject a known current into U1B pin 6", "reading = I × 100 kΩ within 1 %"),
    ("7", "Connect the UART, send CMD:STATUS", "DATA:STATUS:OK"),
    ("8", "Press each button", "one DATA:BUTTON per press"),
    ("9", "Power the Pi 5, run scripts/test_hardware.py", "cameras, UART, ADC, TFT test screen"),
]


def sections():
    """[(anchor, title, intro, drawing, legend, table, notes)] for the page."""
    return [f() for f in SECTIONS]
