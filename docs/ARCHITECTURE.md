# System Architecture — Rice Disease Handheld Scanner

## 1. Overview

A portable, solar-powered handheld device that diagnoses rice plant conditions
by fusing three sensing modalities: RGB imaging, near-infrared (NIR) imaging,
and an electrochemical biosensor. On-device AI runs on a Hailo-8L accelerator.

**Disease / condition classes (6):**
`healthy`, `rice_blast`, `bacterial_leaf_blight`, `nitrogen_deficiency`,
`water_deficit`, `heat_stress`.

## 2. Components

| Component | Role |
|-----------|------|
| Raspberry Pi 5 | Main compute: cameras, AI orchestration, LCD, DB, Flask monitor |
| Hailo-8L AI HAT | Neural inference accelerator (M.2 PCIe x1) |
| ESP32 | Real-time C++: potentiostat control, ADC sampling, buttons, LED, UART |
| RGB Camera Module 3 | Visible-light leaf imaging (CSI0) |
| NoIR Camera Module 3 | NIR imaging for NDVI / stress (CSI1) |
| Electrochemical biosensor | 3-electrode DPV cell for sap biomarkers |
| SPI LCD | Field UI / results display |
| Power subsystem | Solar → charge controller → LiPo → buck-boost |

## 3. Data Flow

```
Buttons ─> ESP32 ─(UART)─> Pi 5 ─> capture RGB + NIR ─> Hailo inference
Biosensor ─> ESP32 DPV ─(UART DATA:BIOSENSOR)─> Pi 5
                                                   │
                        RGB pred + NIR pred + Bio signal
                                                   │
                                            Late Fusion
                                                   │
                              Final diagnosis ─> LCD + PostgreSQL
```

### UART Protocol (115200 baud, text, newline-terminated)

**Pi → ESP32:** `CMD:SCAN`, `CMD:LED:ON`, `CMD:LED:OFF`, `CMD:LED:BLINK`,
`CMD:BATTERY`, `CMD:STATUS`

**ESP32 → Pi:**
- `DATA:BIOSENSOR:<peak_current_ua>,<peak_voltage_v>,<re_voltage_v>,<raw_json>`
- `DATA:BATTERY:<voltage_v>`
- `DATA:BUTTON:<1|2|3>`
- `DATA:STATUS:OK`
- `ERR:<msg>`

## 4. AI Pipeline

- **RGB branch:** MobileNetV3 classifier → 6-class softmax.
- **NIR branch:** NIR/NDVI-informed classifier → 6-class softmax.
- **Biosensor branch:** DPV feature vector → condition likelihood.
- **Late fusion (weighted):**

  ```
  final = 0.5 * RGB + 0.3 * NIR + 0.2 * Bio
  ```

  Weights: **RGB 0.5 / NIR 0.3 / Bio 0.2**.

- **Deployment:** Train in PyTorch → export **ONNX** → compile to Hailo **HEF**
  for on-device acceleration.

## 5. Database Logging (PostgreSQL `ricescanner`)

Tables: `scan_sessions`, `rgb_scans`, `nir_scans`, `biosensor_readings`,
`fused_diagnoses`, `system_logs`. Each scan opens a session; per-modality rows
reference `session_id`; the fused result and system telemetry are logged.
See `scripts/setup_db.sql`.

## 6. Monitoring Dashboard

A Flask app (`pi5/monitor/dashboard.py`) exposes device telemetry (CPU temp,
memory, battery voltage, uptime from `system_logs`) and recent diagnoses for
field/bench diagnostics over the local network.
