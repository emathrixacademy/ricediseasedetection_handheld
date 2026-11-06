"""Rice Plant Health Scanner project page (Railway).

A showcase: the 3D model, the 3D biosensor, an in-browser simulation of the
scanner's software, how it works, and the bill of materials. Python standard
library only. The image holds only this folder (see /Dockerfile and
/.dockerignore): no source code, firmware, schematics or internal documents
are served or shipped.

Environment:
    PORT                   set by Railway
    RAILWAY_GIT_COMMIT_SHA shown as the version, when Railway provides it
"""

from __future__ import annotations

import csv
import html
import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMIT = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:7]
BOM_CSV = HERE / "bom.csv"
PAGES = {"/cad": "cad.html", "/biosensor": "biosensor.html", "/sim": "sim.html"}
FAVICON = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M16 3C9 9 6 15 6 '
           b'20a10 10 0 0 0 20 0c0-5-3-11-10-17z" fill="#1f7a4a"/></svg>')

CSS = """
:root{--brand:#1f7a4a;--tint:#e7f4ec;--ink:#1d2327;--muted:#5b6770;--line:#d5dee2;--bg:#fff;
--note:#fff8e1;--noteline:#f3d27a;--head:#e9eef0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--brand:#4cc38a;--tint:#14301f;
--ink:#e6eaec;--muted:#9aa7ae;--line:#2c3a40;--bg:#0f1417;--note:#2a2410;--noteline:#6b5a1d;--head:#1a2328}}
:root[data-theme="dark"]{--brand:#4cc38a;--tint:#14301f;--ink:#e6eaec;--muted:#9aa7ae;--line:#2c3a40;
--bg:#0f1417;--note:#2a2410;--noteline:#6b5a1d;--head:#1a2328}
*{box-sizing:border-box}
body{font-family:system-ui,"Segoe UI",Roboto,sans-serif;margin:0;background:var(--bg);color:var(--ink);line-height:1.55}
main{max-width:660px;margin:0 auto;padding:28px 16px 56px}
main.wide{max-width:900px}
h1{color:var(--brand);margin:.2em 0 0;line-height:1.2} h2{margin:1.7em 0 .5em;font-size:19px}
h3{font-size:16px;margin:1.3em 0 .3em} a{color:var(--brand)}
.muted{color:var(--muted);font-size:14px}
.big{display:block;text-align:center;background:var(--brand);color:#fff!important;text-decoration:none;
font-size:17px;font-weight:700;padding:15px;border-radius:12px;margin:10px 0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .big{color:#0f1417!important}}
.box{background:var(--tint);border-radius:12px;padding:12px 16px;font-size:15px}
.note{background:var(--note);border:1px solid var(--noteline);border-radius:12px;padding:12px 16px;font-size:15px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}
.card{display:block;border:1px solid var(--line);border-radius:12px;padding:12px 14px;text-decoration:none;color:var(--ink)}
.card b{display:block;color:var(--brand);margin-bottom:4px} .card span{color:var(--muted);font-size:14px}
a.card:hover{border-color:var(--brand)}
ul,ol{padding-left:20px} li{margin:6px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px}
.wrap{overflow-x:auto}
th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}
th{background:var(--head)} .n{text-align:right;white-space:nowrap} tr.sub td{font-weight:700}
.total{margin-top:20px;font-size:17px;font-weight:700;text-align:right}
svg{max-width:100%;height:auto}
.diagram text{font:13px system-ui,sans-serif;fill:var(--ink)}
.diagram .bx{fill:var(--tint);stroke:var(--brand);stroke-width:1.5}
.diagram .ln{stroke:var(--muted);stroke-width:1.5;fill:none}
.diagram .lb{font-size:11px;fill:var(--muted)}
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath d='M16 3C9 9 6 15 6 20a10 10 0 0 0 20 0c0-5-3-11-10-17z' fill='%231f7a4a'/%3E%3C/svg%3E">
<style>{css}</style></head><body><main class="{cls}">{body}</main></body></html>"""


def page(title: str, body: str, desc: str = "", wide: bool = False) -> str:
    return PAGE.format(title=html.escape(title), desc=html.escape(desc), css=CSS,
                       body=body, cls="wide" if wide else "")


def _card(href: str, title: str, text: str) -> str:
    tag = f'a class="card" href="{href}"' if href else 'div class="card"'
    end = "a" if href else "div"
    return f"<{tag}><b>{html.escape(title)}</b><span>{text}</span></{end}>"


# --------------------------------------------------------------------------------------------
# Home


def home() -> str:
    version = f" &middot; version {html.escape(COMMIT)}" if COMMIT else ""
    classes = "".join(_card("", t, d) for t, d in [
        ("Healthy", "No disease or stress found"),
        ("Rice blast", "Fungal: spindle-shaped grey lesions"),
        ("Bacterial leaf blight", "Bacterial: yellow-white streaks from the tip"),
        ("Nitrogen deficiency", "Even yellowing, older leaves first"),
        ("Water deficit", "Rolled, dull leaves with dry tips"),
        ("Heat stress", "Whitened, scorched tips"),
    ])
    specs = "".join(_card("", t, d) for t, d in [
        ("Main computer", "Raspberry Pi 5 with a Hailo-8L AI accelerator"),
        ("Cameras", "Colour (RGB) and near-infrared (NoIR + filter) side by side"),
        ("Biosensor", "Microneedle with three electrodes, κ-carrageenan hydrogel, H₂O₂ and nitrate"),
        ("Controller", "ESP32: potentiostat sweep, buttons, battery"),
        ("Display", "2.4&Prime; colour TFT, 240 &times; 320, three buttons"),
        ("Power", "3.7 V lithium battery, 5 V / 5 A converter, solar panel on top"),
    ])
    return page("Rice Plant Health Scanner", f"""<h1>Rice Plant Health Scanner</h1>
<p class="muted">Built by eMathrix Technologies{version}</p>
<p class="note"><b>Research prototype.</b> A handheld scanner that checks a rice plant in the
field. Two cameras photograph the leaf in colour and near-infrared, a microneedle biosensor reads
H&#8322;O&#8322; and nitrate in the plant's sap, and AI on the scanner combines them into one
diagnosis. No internet needed.</p>

<h2>3D scanner</h2>
<a class="big" href="/cad">Open the interactive 3D model</a>
<div class="box">Turn, zoom and look inside the handheld scanner, tap any part for what it does,
and run a scan: the cameras look, the needle delivers the gel, the screen shows the result.</div>

<h2>3D biosensor</h2>
<a class="big" href="/biosensor">Open the 3D biosensor</a>
<div class="box">The needle, its three electrodes and the hydrogel, inside a rice leaf. Run a
sweep for H&#8322;O&#8322; or nitrate and watch the current curve build up, then try a fault:
no contact, or a sample too strong to read.</div>

<h2>Scanner simulation</h2>
<a class="big" href="/sim">Open the scanner simulation</a>
<div class="box">The scanner's screen and buttons in the browser, with simulated cameras, models
and biosensor. Choose what the leaf really has, press <b>SCAN</b>, and follow each step: images,
biosensor curves, the seven curve features, each model's answer and the fused diagnosis.
<b>MODE</b> chooses H&#8322;O&#8322;, nitrate or both; <b>MENU</b> shows the battery and status.</div>

<h2>How it works</h2>
<a class="big" href="/process">Read how it works</a>
<div class="box">From pressing SCAN to the saved result: the cameras and NDVI, the
electrochemical reading, the AI models, how the three are combined, and the checks along the
way.</div>

<h2>What it detects</h2>
<div class="cards">{classes}</div>

<h2>Inside the scanner</h2>
<div class="cards">{specs}</div>

<h2>Bill of materials</h2>
<a class="big" href="/bom">Open the bill of materials</a>
<div class="box">Every part for one scanner, with estimated prices in Philippine pesos. Also as
CSV for Excel.</div>

<h2>All pages</h2><ul>
<li><a href="/cad">Interactive 3D model of the scanner</a></li>
<li><a href="/biosensor">3D biosensor</a></li>
<li><a href="/sim">Scanner simulation</a></li>
<li><a href="/process">How it works</a></li>
<li><a href="/bom">Bill of materials</a> &middot; <a href="/bom.csv">CSV</a></li></ul>
<p class="muted">eMathrix Technologies &middot; Block 6 Lot 28 Katapatan Main Road, Banaybanay,
Cabuyao City, Laguna</p>""", "Handheld rice plant health scanner: RGB and near-infrared imaging, "
        "a microneedle biosensor and on-device AI.")


# --------------------------------------------------------------------------------------------
# How it works

FLOW_SVG = """<svg class="diagram" viewBox="0 0 640 300" role="img"
aria-label="Data flow: cameras and biosensor feed the AI models, fused into one diagnosis">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"
orient="auto"><path d="M0 0L10 5L0 10z" fill="currentColor" style="color:var(--muted)"/></marker></defs>
<rect class="bx" x="10" y="20" width="150" height="50" rx="10"/><text x="85" y="42" text-anchor="middle">RGB camera</text>
<text class="lb" x="85" y="58" text-anchor="middle">colour image</text>
<rect class="bx" x="10" y="110" width="150" height="50" rx="10"/><text x="85" y="132" text-anchor="middle">NoIR camera</text>
<text class="lb" x="85" y="148" text-anchor="middle">near-infrared, NDVI</text>
<rect class="bx" x="10" y="200" width="150" height="70" rx="10"/><text x="85" y="224" text-anchor="middle">Biosensor</text>
<text class="lb" x="85" y="240" text-anchor="middle">ESP32 DPV sweep</text>
<text class="lb" x="85" y="255" text-anchor="middle">H&#8322;O&#8322; &middot; nitrate</text>
<rect class="bx" x="230" y="20" width="160" height="50" rx="10"/><text x="310" y="42" text-anchor="middle">RGB model</text>
<text class="lb" x="310" y="58" text-anchor="middle">Hailo-8L</text>
<rect class="bx" x="230" y="110" width="160" height="50" rx="10"/><text x="310" y="132" text-anchor="middle">NIR model</text>
<text class="lb" x="310" y="148" text-anchor="middle">Hailo-8L</text>
<rect class="bx" x="230" y="200" width="160" height="70" rx="10"/><text x="310" y="224" text-anchor="middle">Curve features</text>
<text class="lb" x="310" y="240" text-anchor="middle">7 per analyte, then</text>
<text class="lb" x="310" y="255" text-anchor="middle">calibrated classifier</text>
<rect class="bx" x="450" y="100" width="180" height="70" rx="10"/><text x="540" y="126" text-anchor="middle">Weighted late fusion</text>
<text class="lb" x="540" y="144" text-anchor="middle">RGB 0.5 &middot; NIR 0.3 &middot; bio 0.2</text>
<text class="lb" x="540" y="159" text-anchor="middle">diagnosis + confidence</text>
<path class="ln" d="M160 45H228" marker-end="url(#ar)"/><path class="ln" d="M160 135H228" marker-end="url(#ar)"/>
<path class="ln" d="M160 235H228" marker-end="url(#ar)"/>
<path class="ln" d="M390 45C420 45 420 120 448 125" marker-end="url(#ar)"/>
<path class="ln" d="M390 135H448" marker-end="url(#ar)"/>
<path class="ln" d="M390 235C420 235 420 150 448 145" marker-end="url(#ar)"/>
<text class="lb" x="540" y="200" text-anchor="middle">screen + saved with images,</text>
<text class="lb" x="540" y="215" text-anchor="middle">curves and results</text>
</svg>"""


def process() -> str:
    return page("How the Rice Scanner Works", f"""<p><a href="/">&larr; Project page</a></p>
<h1>How it works</h1>
<p class="muted">From pressing SCAN to the saved result.</p>

<h2>The scan, step by step</h2>
<ol>
<li><b>Point and press.</b> The scanner is held by its grip with the cameras toward the leaf.
<b>SCAN</b> starts a scan; <b>MODE</b> chooses what the biosensor measures (H&#8322;O&#8322;,
nitrate, or both); <b>MENU</b> shows the battery and the scanner's status.</li>
<li><b>Two photos of the same leaf.</b> The colour camera and the near-infrared camera sit side
by side in one fixed mount and take their pictures in the same scan.</li>
<li><b>Biosensor reading.</b> The needle delivers the &kappa;-carrageenan hydrogel into the leaf
tissue; the ESP32 sweeps the electrodes, about 20 seconds per substance.</li>
<li><b>AI on the scanner.</b> The Raspberry Pi 5 runs the colour and near-infrared models on its
Hailo-8L accelerator.</li>
<li><b>One diagnosis.</b> The three results are combined into one diagnosis and a confidence
value, shown on the 2.4&Prime; screen.</li>
<li><b>Everything is kept.</b> The two images, the full biosensor curves, every model's answer and
the final result are saved on the scanner for later analysis.</li>
</ol>

{FLOW_SVG}

<h2>Cameras and NDVI</h2>
<p>The colour camera sees what a person sees: lesions, streaks, yellowing. The second camera has
no infrared-blocking filter and carries an optical filter instead, so one colour channel records
near-infrared light and another visible light. Healthy leaves reflect a lot of near-infrared and
absorb red; stressed leaves less so. The scanner turns the two into NDVI, a vegetation index from
&minus;1 to 1, and the near-infrared model learns from the same image.</p>

<h2>The biosensor</h2>
<p>Three electrodes sit in the needle housing: a working electrode, an Ag/AgCl reference
electrode and a counter electrode. The hydrogel carries the sap to them. A small potentiostat on
the ESP32 sets the working electrode's potential through a control amplifier and measures the
tiny current with a transimpedance amplifier and a 16-bit converter, up to &plusmn;16.5 &micro;A.</p>
<p>The method is <b>differential pulse voltammetry</b>: the potential climbs in 4 mV steps, and
each step gets a 50 mV pulse for 50 ms. The current is measured just before and at the end of each
pulse; the difference is the signal. H&#8322;O&#8322; is oxidised and shows a peak near
+0.25 V; nitrate is reduced and shows a negative peak. Each substance is read on its own, with its
own settings.</p>
<p>Before a reading is used it is checked: if the current ran beyond what the reader can measure,
it is marked <i>saturated</i>; if the curve is flat, the needle is not in contact and it is marked
<i>no signal</i>. Neither is used for the diagnosis.</p>
<p>From each good curve the scanner measures seven things: the peak's height, position, area and
width, the slope of the background, the number of peaks, and the signal-to-noise ratio.</p>

<h2>The AI models</h2>
<p>There is one model for colour images and one for near-infrared images, both MobileNetV3
networks trained by transfer learning: they start from a network pretrained on general images and
are trained on rice-leaf photos of the six classes, first phone photos, then photos from the
scanner's own cameras. During training the photos are randomly flipped, brightened, darkened and
shifted, so the models do not depend on one lighting or framing.</p>
<p>Photos are divided into training (70%), validation (15%) and test (15%) by session, so pictures
of the same leaf on the same day never appear in both training and testing. The trained models
are compiled for the Hailo-8L, so they run on the scanner without internet.</p>

<h2>Combining the results</h2>
<p>Each model gives a probability for each of the six classes. The scanner adds them with
weights, colour 0.5, near-infrared 0.3 and biosensor 0.2, and the class with the highest total
is the diagnosis; its share is the confidence.</p>
<p>The biosensor joins only after it has been <b>calibrated</b> with readings from plants whose
condition was confirmed. Until then it is measured and saved, but the diagnosis comes from the
cameras alone. Once calibrated it gives its own probabilities for the six classes, so a strong
reading can change the diagnosis; for example, a leaf that still looks healthy but shows the
chemistry of an infection.</p>

<h2>On the screen</h2>
<p>The 2.4&Prime; colour screen shows the diagnosis with a confidence bar, the NDVI and the
biosensor peaks, which parts were combined, and the battery voltage. The battery is checked every
minute and a warning appears before it runs low. If any part is not working, or running on
simulated data, the screen says so; a simulated result never looks like a real one.</p>

<p class="muted" style="margin-top:2em">eMathrix Technologies &middot; Rice Plant Health Scanner
research prototype</p>""", "How the rice plant health scanner works: imaging, the biosensor, "
        "the AI models and fusion.")


# --------------------------------------------------------------------------------------------
# Bill of materials


def bom_sections() -> list[tuple[str, list[dict[str, str]], float]]:
    out: list[tuple[str, list[dict[str, str]], float]] = []
    with BOM_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            amount = float(row["qty"]) * float(row["unit_price_php"])
            row["amount"] = f"{amount:.2f}"
            if not out or out[-1][0] != row["section"]:
                out.append((row["section"], [], 0.0))
            name, rows, sub = out[-1]
            out[-1] = (name, [*rows, row], sub + amount)
    return out


def peso(v: float) -> str:
    return f"&#8369;{v:,.2f}"


def bom() -> str:
    parts, total = [], 0.0
    for section, rows, sub in bom_sections():
        total += sub
        body = "".join(
            f"<tr><td>{html.escape(r['item'])}</td><td>{html.escape(r['specification'])}</td>"
            f'<td class="n">{float(r["qty"]):g}</td><td>{html.escape(r["unit"])}</td>'
            f'<td class="n">{peso(float(r["unit_price_php"]))}</td>'
            f'<td class="n">{peso(float(r["amount"]))}</td></tr>'
            for r in rows)
        parts.append(
            f"<h2>{html.escape(section)}</h2><div class=\"wrap\"><table><tr><th>Item</th>"
            '<th>Specification</th><th class="n">Qty</th><th>Unit</th><th class="n">Unit price</th>'
            f'<th class="n">Amount</th></tr>{body}<tr class="sub"><td colspan="5">Subtotal</td>'
            f'<td class="n">{peso(sub)}</td></tr></table></div>')
    date = time.strftime("%B %d, %Y").replace(" 0", " ")
    return page("Rice Scanner Bill of Materials", f"""<p><a href="/">&larr; Project page</a></p>
<h1>Bill of materials</h1>
<p class="muted">One handheld scanner &middot; prepared by eMathrix Technologies &middot; {date}
&middot; <a href="/bom.csv">Download as CSV (opens in Excel)</a></p>
{''.join(parts)}
<p class="total">Total, one scanner: {peso(total)}</p>
<p class="muted">Prices are estimates for budgeting (Philippine market, November 2026); confirm
with the supplier before ordering.</p>""", "Parts list with estimated prices for one rice plant "
                "health scanner.", wide=True)


# --------------------------------------------------------------------------------------------
# Server


class Handler(BaseHTTPRequestHandler):
    server_version = "ricescanner-site"

    def _send(self, status: int, body: bytes | str, ctype: str = "text/html; charset=utf-8",
              headers: dict | None = None) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _route(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            return self._send(200, "ok", "text/plain")
        if path == "/favicon.ico":
            return self._send(200, FAVICON, "image/svg+xml")
        if path in ("/", "/index.html"):
            return self._send(200, home())
        if path in PAGES:
            f = HERE / "pages" / PAGES[path]
            if f.is_file():
                return self._send(200, f.read_bytes())
        if path == "/process":
            return self._send(200, process())
        if path == "/bom":
            return self._send(200, bom())
        if path == "/bom.csv":
            return self._send(200, BOM_CSV.read_bytes(), "text/csv; charset=utf-8",
                              {"Content-Disposition": 'attachment; filename="rice-scanner-bom.csv"'})
        return self._send(404, page("Not found", '<p>Page not found. <a href="/">Project page</a></p>'))

    do_GET = do_HEAD = _route

    def log_message(self, fmt: str, *args: object) -> None:  # no IPs in the logs
        status = args[1] if len(args) > 1 else ""
        print(f"{self.command} {urllib.parse.urlparse(self.path).path} -> {status}", flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"Rice scanner site on port {port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
