#!/usr/bin/env python3
"""Generate docs/wiring_schematic.pdf — a labeled block diagram of the
Rice Disease Handheld Scanner.

Uses ReportLab if available, else falls back to matplotlib.

    pip install reportlab      # preferred
    # or
    pip install matplotlib     # fallback

Run:
    python docs/generate_schematic.py
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiring_schematic.pdf")

# (label, x, y, w, h) in an abstract 0..100 grid
BOXES = {
    "Solar 20W":     (4,  82, 18, 10),
    "Battery LiPo":  (4,  66, 18, 10),
    "Buck-Boost 5V": (28, 74, 18, 10),
    "Pi 5":          (52, 74, 18, 12),
    "Hailo-8L":      (78, 82, 18, 10),
    "RGB Cam":       (78, 66, 18, 8),
    "NoIR Cam":      (78, 54, 18, 8),
    "LCD":           (52, 54, 18, 10),
    "ESP32":         (28, 40, 18, 12),
    "Potentiostat":  (4,  24, 20, 12),
    "MCP4725":       (28, 20, 16, 8),
    "ADS1115":       (28, 8,  16, 8),
    "Electrodes":    (52, 20, 18, 10),
}

# (a, b, label)
LINES = [
    ("Solar 20W", "Battery LiPo", "charge"),
    ("Battery LiPo", "Buck-Boost 5V", "power"),
    ("Buck-Boost 5V", "Pi 5", "5V/5A"),
    ("Buck-Boost 5V", "ESP32", "5V/fuse"),
    ("Pi 5", "Hailo-8L", "PCIe"),
    ("Pi 5", "RGB Cam", "CSI0"),
    ("Pi 5", "NoIR Cam", "CSI1"),
    ("Pi 5", "LCD", "SPI"),
    ("Pi 5", "ESP32", "UART"),
    ("ESP32", "MCP4725", "I2C"),
    ("ESP32", "ADS1115", "I2C"),
    ("Potentiostat", "MCP4725", "CE"),
    ("Potentiostat", "ADS1115", "WE/RE"),
    ("Potentiostat", "Electrodes", "3-elec"),
]


def _center(box):
    x, y, w, h = box
    return (x + w / 2.0, y + h / 2.0)


def generate_reportlab():
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.pdfgen import canvas as rcanvas

    pw, ph = landscape(A4)
    c = rcanvas.Canvas(OUT, pagesize=(pw, ph))

    def sx(v):  # scale 0..100 grid to page
        return 20 + (v / 100.0) * (pw - 40)

    def sy(v):
        return 20 + (v / 100.0) * (ph - 40)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(sx(4), sy(96), "Rice Disease Handheld Scanner — Wiring Schematic")

    # lines first (under boxes)
    c.setFont("Helvetica", 7)
    for a, b, lbl in LINES:
        ax, ay = _center(BOXES[a])
        bx, by = _center(BOXES[b])
        c.setStrokeColorRGB(0.4, 0.4, 0.4)
        c.line(sx(ax), sy(ay), sx(bx), sy(by))
        c.setFillColorRGB(0.1, 0.1, 0.6)
        c.drawString(sx((ax + bx) / 2), sy((ay + by) / 2), lbl)

    # boxes
    for label, (x, y, w, h) in BOXES.items():
        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0.90, 0.94, 1.0)
        c.rect(sx(x), sy(y), sx(x + w) - sx(x), sy(y + h) - sy(y), fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 9)
        cx, cy = _center((x, y, w, h))
        c.drawCentredString(sx(cx), sy(cy) - 3, label)

    c.showPage()
    c.save()
    print("Wrote", OUT, "(reportlab)")


def generate_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_title("Rice Disease Handheld Scanner — Wiring Schematic",
                 fontsize=14, fontweight="bold")

    for a, b, lbl in LINES:
        ax_, ay_ = _center(BOXES[a])
        bx_, by_ = _center(BOXES[b])
        ax.plot([ax_, bx_], [ay_, by_], color="0.4", lw=1, zorder=1)
        ax.text((ax_ + bx_) / 2, (ay_ + by_) / 2, lbl, fontsize=6,
                color="navy", ha="center", zorder=3,
                bbox=dict(boxstyle="round", fc="white", ec="none", alpha=0.7))

    for label, (x, y, w, h) in BOXES.items():
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3",
                                    fc="#e6f0ff", ec="black", zorder=2))
        cx, cy = _center((x, y, w, h))
        ax.text(cx, cy, label, ha="center", va="center",
                fontsize=8, fontweight="bold", zorder=4)

    fig.savefig(OUT, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print("Wrote", OUT, "(matplotlib fallback)")


def main():
    try:
        import reportlab  # noqa: F401
        generate_reportlab()
        return
    except ImportError:
        pass
    try:
        import matplotlib  # noqa: F401
        generate_matplotlib()
        return
    except ImportError:
        raise SystemExit(
            "Neither reportlab nor matplotlib is installed.\n"
            "Install one:  pip install reportlab   (or)   pip install matplotlib"
        )


if __name__ == "__main__":
    main()
