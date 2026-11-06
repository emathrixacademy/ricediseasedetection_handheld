"""2.4" ILI9341 TFT (240 x 320, SPI0) driver for the handheld scanner.

Every screen is drawn into a Pillow image first and then pushed to the panel
with luma.lcd. Without the panel (no luma / spidev / lgpio, e.g. on a laptop)
the driver runs as a mock: it still draws the same image, saves it to
``config.LCD_PREVIEW_PATH`` and prints a text summary, and flags itself via
``self.mock``.

Wiring (Pi 5, BCM numbering):
    VCC  -> 3.3 V (pin 1)         GND   -> common GND
    SDI  -> GPIO10 MOSI (pin 19)  SCK   -> GPIO11 SCLK (pin 23)
    CS   -> GPIO8 CE0  (pin 24)   DC    -> GPIO25 (pin 22)
    RST  -> GPIO24     (pin 18)   LED   -> backlight switch, gate on GPIO18
SDO/MISO and the touch pins are not connected.

On a Pi 5 luma's GPIO calls go through ``rpi-lgpio`` (RPi.GPIO itself does
not support the Pi 5's RP1 chip).
"""

import os

from .. import config

LCD_WIDTH = config.LCD_WIDTH
LCD_HEIGHT = config.LCD_HEIGHT

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - Pillow is in requirements
    Image = ImageDraw = ImageFont = None
    _PIL_AVAILABLE = False

try:
    from luma.core.interface.serial import spi  # type: ignore
    from luma.lcd.device import ili9341  # type: ignore
    _LCD_AVAILABLE = True
except Exception:
    spi = ili9341 = None
    _LCD_AVAILABLE = False

# Colours (RGB).
BG = (12, 18, 16)
INK = (235, 240, 236)
MUTED = (140, 156, 150)
BRAND = (46, 160, 96)
WARN = (240, 180, 40)
BAD = (225, 72, 60)

# Screen label and accent colour per class.
DISPLAY_LABELS = {
    "healthy": ("Healthy", BRAND),
    "rice_blast": ("Rice blast", BAD),
    "bacterial_leaf_blight": ("Bacterial leaf blight", BAD),
    "nitrogen_deficiency": ("Nitrogen deficiency", WARN),
    "water_deficit": ("Water deficit", WARN),
    "heat_stress": ("Heat stress", WARN),
    "unknown": ("Unknown", MUTED),
}

_FONT_FILES = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arialbd.ttf", "arial.ttf")


def _font(size):
    """A TrueType font at ``size`` px, or Pillow's built-in bitmap font."""
    for name in _FONT_FILES:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    """Split ``text`` into lines that fit ``width`` pixels."""
    lines, line = [], ""
    for word in str(text).split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


class LCDDriver:
    """High-level screens for the 2.4\" TFT (240 x 320 portrait by default)."""

    def __init__(self):
        self.width = LCD_WIDTH
        self.height = LCD_HEIGHT
        self.mock = not _LCD_AVAILABLE
        self._device = None
        self.battery_v = None      # shown in the header when known
        self.last_image = None     # the most recent frame, for tests/preview

    def init(self):
        """Initialise the panel. Safe to call once at startup."""
        if self.mock:
            print("[LCDDriver:mock] init (240x320 TFT, preview at "
                  f"{config.LCD_PREVIEW_PATH})")
            return
        try:
            serial = spi(
                port=config.LCD_SPI_PORT,
                device=config.LCD_SPI_DEVICE,
                gpio_DC=config.LCD_DC,
                gpio_RST=config.LCD_RST,
                bus_speed_hz=config.LCD_SPI_HZ,
            )
            self._device = ili9341(
                serial,
                width=320,             # native panel geometry; rotate sets
                height=240,            # the orientation we draw in
                rotate=config.LCD_ROTATE,
                gpio_LIGHT=config.LCD_BL,
                active_low=False,
            )
            self._device.backlight(True)
        except Exception as exc:
            print(f"[LCDDriver] hardware init failed, using mock: {exc}")
            self.mock = True
            self._device = None

    # -- drawing -------------------------------------------------------------

    def _frame(self, title, accent=BRAND, sim=False):
        """A blank frame with the header bar; returns (image, draw)."""
        img = Image.new("RGB", (self.width, self.height), BG)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, self.width, 34), fill=accent)
        d.text((10, 8), title, font=_font(17), fill=(10, 14, 12))
        if self.battery_v is not None:
            low = self.battery_v < config.BATTERY_LOW_V
            d.text((self.width - 10, 9), f"{self.battery_v:.2f} V",
                   font=_font(14), fill=BAD if low else (10, 14, 12),
                   anchor="ra")
        if sim:
            d.rectangle((0, self.height - 30, self.width, self.height), fill=WARN)
            d.text((self.width // 2, self.height - 15), "SIMULATED - not a reading",
                   font=_font(13), fill=(20, 16, 0), anchor="mm")
        return img, d

    def _show(self, img, summary):
        self.last_image = img
        if self.mock or self._device is None:
            path = config.LCD_PREVIEW_PATH
            try:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                img.save(path)
            except Exception:
                pass
            print(f"[LCDDriver:mock] {summary}")
            return
        self._device.display(img)

    # -- public API ----------------------------------------------------------

    def clear(self):
        """Blank the screen."""
        img = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        self._show(img, "clear")

    def show_status(self, status):
        """Show a status dict, one ``key: value`` per line."""
        if not isinstance(status, dict):
            status = {"status": status}
        img, d = self._frame("RICE SCANNER")
        y = 50
        for k, v in status.items():
            d.text((12, y), str(k).upper(), font=_font(12), fill=MUTED)
            d.text((12, y + 15), str(v), font=_font(20), fill=INK)
            y += 50
            if y > self.height - 60:
                break
        self._show(img, "status " + ", ".join(f"{k}={v}" for k, v in status.items()))

    def show_result(self, diagnosis, confidence, mock=False, details=None):
        """Show a diagnosis, its confidence bar and optional detail lines.

        ``mock=True`` marks the screen as simulated: an operator must never see
        a confident-looking diagnosis from mock subsystems without knowing it.
        """
        label, accent = DISPLAY_LABELS.get(diagnosis, (str(diagnosis), MUTED))
        img, d = self._frame("SCAN RESULT", accent=accent, sim=mock)
        big = _font(28)
        y = 52
        for line in _wrap(d, label, big, self.width - 24)[:3]:
            d.text((12, y), line, font=big, fill=INK)
            y += 34
        y += 8
        conf = max(0.0, min(1.0, float(confidence)))
        d.text((12, y), "CONFIDENCE", font=_font(12), fill=MUTED)
        d.text((self.width - 12, y), f"{conf:.0%}", font=_font(14), fill=INK,
               anchor="ra")
        y += 20
        d.rounded_rectangle((12, y, self.width - 12, y + 14), 7, fill=(40, 52, 48))
        d.rounded_rectangle((12, y, 12 + int((self.width - 24) * conf), y + 14),
                            7, fill=accent)
        y += 30
        for k, v in (details or {}).items():
            if y > self.height - 56:
                break
            d.text((12, y), str(k), font=_font(13), fill=MUTED)
            d.text((self.width - 12, y), str(v), font=_font(13), fill=INK,
                   anchor="ra")
            y += 22
        self._show(img, f"result {diagnosis} {conf:.1%}" + (" [SIM]" if mock else ""))

    def show_warning(self, title, message):
        """A full-screen warning (low battery, biosensor fault...)."""
        img, d = self._frame(title, accent=WARN)
        y = 56
        for line in _wrap(d, message, _font(18), self.width - 24)[:8]:
            d.text((12, y), line, font=_font(18), fill=INK)
            y += 26
        self._show(img, f"warning {title}: {message}")


if __name__ == "__main__":
    lcd = LCDDriver()
    print(f"[LCDDriver] mock={lcd.mock}")
    lcd.init()
    lcd.battery_v = 3.86
    lcd.show_status({"state": "ready", "battery": "3.86 V", "uart": "OK"})
    lcd.show_result("bacterial_leaf_blight", 0.873,
                    details={"NDVI": "0.41", "H2O2 peak": "2.31 uA"})
    print("preview:", config.LCD_PREVIEW_PATH)
