"""HD44780 1604 (16x4) character LCD driver over an I2C PCF8574 backpack.

Replaces the earlier ILI9341 SPI panel. The module is text-only: 4 lines of
16 characters. Uses RPLCD when available; when RPLCD / smbus are missing
(e.g. on a development laptop) the driver degrades to a console mock so the
UI flow can still be exercised -- and flags itself via ``self.mock``.

Wiring (Pi 5):
    backpack VCC -> 5 V (pin 2)     backpack GND -> common GND
    backpack SDA -> GPIO2 (pin 3)   backpack SCL -> GPIO3  (pin 5)

NOTE: most PCF8574 backpacks carry pull-up resistors to their 5 V rail.
Remove them (or fit a level shifter) so SDA/SCL are only pulled to the Pi's
3.3 V -- the Pi's own 1.8 k pull-ups on GPIO2/3 are sufficient.
"""

from .. import config

LCD_COLS = 16
LCD_ROWS = 4

try:
    from RPLCD.i2c import CharLCD  # type: ignore
    _LCD_AVAILABLE = True
except Exception:
    CharLCD = None
    _LCD_AVAILABLE = False

# Human-readable class labels that fit a 16-column line. Falling back to the
# raw class name (truncated) keeps unknown labels displayable.
DISPLAY_LABELS = {
    "healthy": "Healthy",
    "rice_blast": "Rice Blast",
    "bacterial_leaf_blight": "Bact.Leaf Blight",
    "nitrogen_deficiency": "Nitrogen Defic.",
    "water_deficit": "Water Deficit",
    "heat_stress": "Heat Stress",
    "unknown": "Unknown",
}


def _fit(text, width=LCD_COLS):
    """Clamp a line to the panel width."""
    return str(text)[:width]


class LCDDriver:
    """Minimal high-level interface for the 16x4 character LCD."""

    def __init__(self):
        self.cols = LCD_COLS
        self.rows = LCD_ROWS
        self.mock = not _LCD_AVAILABLE
        self._device = None

    def init(self):
        """Initialise the panel. Safe to call once at startup."""
        if self.mock:
            print("[LCDDriver:mock] init (console rendering, 16x4)")
            return
        try:
            self._device = CharLCD(
                i2c_expander="PCF8574",
                address=config.LCD_I2C_ADDR,
                port=config.LCD_I2C_BUS,
                cols=self.cols,
                rows=self.rows,
                charmap="A00",
                auto_linebreaks=False,
            )
            self._device.clear()
        except Exception as exc:
            print(f"[LCDDriver] hardware init failed, using mock: {exc}")
            self.mock = True
            self._device = None

    def clear(self):
        """Blank the screen."""
        if self.mock or self._device is None:
            print("[LCDDriver:mock] clear")
            return
        self._device.clear()

    def _render_lines(self, lines):
        """Render up to LCD_ROWS lines, mock-aware.

        Lines beyond the panel height are dropped -- callers are expected to
        compose for 4 rows. The mock prints the exact 16x4 window so layout
        problems are visible on a dev machine too.
        """
        lines = [_fit(ln) for ln in lines[:self.rows]]
        while len(lines) < self.rows:
            lines.append("")

        if self.mock or self._device is None:
            print("+" + "-" * self.cols + "+")
            for ln in lines:
                print(f"|{ln:<{self.cols}}|")
            print("+" + "-" * self.cols + "+")
            return

        self._device.clear()
        for row, ln in enumerate(lines):
            self._device.cursor_pos = (row, 0)
            self._device.write_string(ln)

    def show_result(self, diagnosis, confidence, mock=False):
        """Display a diagnosis label and confidence score.

        ``mock=True`` marks the screen as simulated. An operator must never be
        shown a confident-looking diagnosis that came from mock subsystems
        without knowing it. On a 4-line panel the marker takes a whole line.
        """
        label = DISPLAY_LABELS.get(diagnosis, _fit(diagnosis))
        lines = [
            "RESULT [SIM]" if mock else "SCAN RESULT",
            label,
            f"Conf: {confidence:.1%}",
            "**SIMULATED**" if mock else "",
        ]
        self._render_lines(lines)

    def show_status(self, status):
        """Display a status dict, one ``key: value`` per line (max 3 + title)."""
        if not isinstance(status, dict):
            status = {"status": status}
        lines = ["STATUS"]
        for k, v in list(status.items())[:self.rows - 1]:
            lines.append(f"{k}: {v}")
        self._render_lines(lines)


if __name__ == "__main__":
    lcd = LCDDriver()
    print(f"[LCDDriver] mock={lcd.mock}")
    lcd.init()
    lcd.clear()
    lcd.show_status({"battery": "3.9V", "camera": "OK", "uart": "OK"})
    lcd.show_result("bacterial_leaf_blight", 0.873)
    lcd.show_result("rice_blast", 0.62, mock=True)
