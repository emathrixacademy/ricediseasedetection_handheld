# Rice Disease Detection Handheld Scanner

**Statement No.:** EMX-2026-RICEBOT-02
**Builder:** Emathrix Technologies, Cabuyao City, Laguna

Solar-powered, AI-assisted handheld multimodal diagnostic device integrating
**RGB–NIR spectral imaging** and a **κ-carrageenan microneedle electrochemical
biosensor** for in-field rice disease detection.

---

## Hardware Target

| Subsystem | Component |
|-----------|-----------|
| Compute | Raspberry Pi 5 (4 GB) + Hailo-8L AI HAT (13 TOPS, PCIe) |
| Cameras | RGB Camera Module 3 (CSI 0), NoIR / NIR Module 3 (CSI 1) |
| Display | 2.4" ILI9341 LCD (SPI) |
| MCU | ESP32 DevKit (potentiostat, ADC, buttons, LED) |
| Biosensor | DIY potentiostat — MCP4725 DAC + MCP6002 TIA + ADS1115 16-bit ADC, three-electrode microneedle (WE / RE Ag/AgCl / CE) |
| Power | LiPo + buck-boost 5V/5A + 20 W solar top-up |
| Link | Pi 5 ↔ ESP32 over UART @ 115200 (Pi GPIO14/15 ↔ ESP32 GPIO16/17) |

---

## Repository Layout

```
pi5/         Raspberry Pi 5 Python — cameras, AI, fusion, LCD, UART, DB, Flask monitor
esp32/       ESP32 C++/Arduino — potentiostat DPV, ADS1115, buttons, LED, UART (PlatformIO)
training/    Workstation model training — PyTorch → ONNX → HEF, dataset tooling
docs/        WIRING.md, ARCHITECTURE.md, CAPTURE_GUIDE.md, schematic generator
scripts/     setup_db, run, hardware self-test
tests/       pytest suites (hardware-aware, mock fallbacks)
setup.sh     One-command Pi 5 setup (no Docker)
```

---

## Quick Start

### Raspberry Pi 5
```bash
git clone https://github.com/emathrixacademy/ricediseasedetection_handheld.git
cd ricediseasedetection_handheld
bash setup.sh            # system deps, venv, PostgreSQL, interfaces, self-test
sudo reboot             # apply UART/SPI/I2C changes
bash scripts/run.sh     # start main.py + monitoring dashboard
```
Install the Hailo runtime separately per
[hailo-rpi5-examples](https://github.com/hailo-ai/hailo-rpi5-examples).

### ESP32 Firmware
```bash
pip install platformio
pio run -d esp32 --target upload --upload-port /dev/ttyUSB0
pio device monitor --baud 115200
```

### Running Components Individually
```bash
python -m pi5.main                 # scanner (one mock scan cycle)
python -m pi5.monitor.dashboard    # http://<pi-ip>:5000
python scripts/simulate.py         # hardware-in-the-loop simulation
```

> **Run modules with `-m` from the project root.** `pi5/` and `training/utils/`
> use relative imports, so invoking them by file path (`python
> pi5/monitor/dashboard.py`) raises `ImportError: attempted relative import
> with no known parent package`. Worse, `python pi5/main.py` does *not* error —
> it silently disables every subsystem and reports `unknown`. Always use
> `python -m pi5.main` and `python -m pi5.monitor.dashboard`.

---

## Disease Classes

| Idx | Label | Type |
|-----|-------|------|
| 0 | `healthy` | Control |
| 1 | `rice_blast` | Biotic — *Magnaporthe oryzae* |
| 2 | `bacterial_leaf_blight` | Biotic — *Xanthomonas oryzae* pv. *oryzae* |
| 3 | `nitrogen_deficiency` | Abiotic |
| 4 | `water_deficit` | Abiotic |
| 5 | `heat_stress` | Abiotic |

---

## Signal Flow

```
Plant Sap → Hydrogel → WE redox → MCP6002 TIA → ADS1115 → ESP32 DPV → UART ─┐
RGB Camera → Pi 5 CSI0 → Hailo-8L → disease classification ─────────────────┤
NoIR Camera → Pi 5 CSI1 → NDVI + AI → stress classification ────────────────┤
                                                                            ↓
                                              Decision Fusion (RGB 0.5 / NIR 0.3 / Bio 0.2)
                                                                            ↓
                                                    LCD result  +  PostgreSQL log
```

See [docs/WIRING.md](docs/WIRING.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
and [docs/CAPTURE_GUIDE.md](docs/CAPTURE_GUIDE.md) for full detail.

---

## UART Protocol (115200 baud, text, newline-terminated)

**Pi → ESP32:** `CMD:SCAN` · `CMD:LED:ON` · `CMD:LED:OFF` · `CMD:LED:BLINK` · `CMD:BATTERY` · `CMD:STATUS`

**ESP32 → Pi:**
```
DATA:BIOSENSOR:<peak_current_ua>,<peak_voltage_v>,<re_voltage_v>,<raw_json>
DATA:BATTERY:<voltage_v>
DATA:BUTTON:<1|2|3>
DATA:STATUS:OK
ERR:<message>
```

---

## Build Rules

1. Pi 5 = Python only; ESP32 = C++/Arduino only.
2. Local PostgreSQL (`ricescanner`), no cloud, no Docker.
3. PyTorch primary → ONNX → HEF (Hailo); TensorFlow secondary.
4. Config lives in one place: `pi5/config.py` (Python), `esp32/src/config.h` (C++).
5. UART protocol strings match exactly on both sides.
6. All images saved to disk **and** logged to PostgreSQL with metadata.

---

## License

Proprietary — Emathrix Technologies. Background IP per service agreement EMX-2026-RICEBOT-02.
