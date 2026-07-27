"""ILI9341 240x320 SPI LCD driver for the handheld scanner.

Uses luma.lcd when available for rendering. When luma / spidev / RPi.GPIO
are missing (e.g. on a development laptop) the driver degrades to a console
mock so the UI flow can still be exercised.
"""

from .. import config

# ILI9341 native panel geometry
LCD_WIDTH = 240
LCD_HEIGHT = 320

try:
    from luma.lcd.device import ili9341  # type: ignore
    from luma.core.interface.serial import spi  # type: ignore
    from luma.core.render import canvas  # type: ignore
    from PIL import ImageFont  # type: ignore
    _LCD_AVAILABLE = True
except Exception:
    ili9341 = None
    spi = None
    canvas = None
    ImageFont = None
    _LCD_AVAILABLE = False


class LCDDriver:
    """Minimal high-level LCD interface."""

    def __init__(self):
        self.width = LCD_WIDTH
        self.height = LCD_HEIGHT
        self.mock = not _LCD_AVAILABLE
        self._device = None

    def init(self):
        """Initialise the panel. Safe to call once at startup."""
        if self.mock:
            print("[LCDDriver:mock] init (console rendering)")
            return
        try:
            serial = spi(
                port=config.LCD_SPI_BUS,
                device=config.LCD_SPI_DEVICE,
                gpio_DC=config.LCD_DC,
                gpio_RST=config.LCD_RST,
            )
            self._device = ili9341(serial, width=self.width, height=self.height,
                                    rotate=0)
        except Exception as exc:
            print(f"[LCDDriver] hardware init failed, using mock: {exc}")
            self.mock = True
            self._device = None

    def clear(self):
        """Blank the screen."""
        if self.mock or self._device is None:
            print("[LCDDriver:mock] clear")
            return
        with canvas(self._device) as draw:
            draw.rectangle(self._device.bounding_box, outline="black",
                           fill="black")

    def _render_lines(self, lines, title=None):
        """Render a list of text lines, mock-aware."""
        if self.mock or self._device is None:
            print("+" + "-" * 30 + "+")
            if title:
                print(f"| {title[:28]:<28} |")
                print("+" + "-" * 30 + "+")
            for ln in lines:
                print(f"| {str(ln)[:28]:<28} |")
            print("+" + "-" * 30 + "+")
            return
        with canvas(self._device) as draw:
            draw.rectangle(self._device.bounding_box, fill="black")
            y = 6
            if title:
                draw.text((6, y), title, fill="cyan")
                y += 22
            for ln in lines:
                draw.text((6, y), str(ln), fill="white")
                y += 18

    def show_result(self, diagnosis, confidence):
        """Display a diagnosis label and confidence score."""
        self._render_lines(
            [f"Diagnosis:", f"  {diagnosis}", f"Confidence: {confidence:.1%}"],
            title="SCAN RESULT",
        )

    def show_status(self, status):
        """Display a status dict (key: value per line)."""
        if not isinstance(status, dict):
            status = {"status": status}
        lines = [f"{k}: {v}" for k, v in status.items()]
        self._render_lines(lines, title="STATUS")


if __name__ == "__main__":
    lcd = LCDDriver()
    print(f"[LCDDriver] mock={lcd.mock}")
    lcd.init()
    lcd.clear()
    lcd.show_status({"battery": "4.1V", "camera": "OK", "uart": "OK"})
    lcd.show_result("rice_blast", 0.873)
