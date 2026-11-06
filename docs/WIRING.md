# Wiring Reference — Rice Disease Handheld Scanner

Pin-by-pin wiring for the Raspberry Pi 5 + ESP32 handheld rice disease scanner.

> **CRITICAL:** All grounds (GND) MUST be common/shared across Pi 5, ESP32,
> potentiostat, ADC, DAC and power rails. A floating ground will corrupt the
> analog biosensor readings and can damage the UART lines.

---

## 1. POWER

| From | To | Notes |
|------|----|-------|
| Solar Panel 20W (5-6V) | Charge Controller **IN** | Outdoor field charging |
| Charge Controller **OUT** | LiPo 3.7V (JST) | Battery charge / protection |
| Battery | Power Switch | Main on/off |
| Power Switch | Buck-Boost **IN** | Regulated conversion |
| Buck-Boost **OUT 5V / 5A** | Pi 5 USB-C | **Pi 5 requires 5V/5A** |
| Buck-Boost 5V | ESP32 **VIN** | **Through 1A fuse** |

---

## 2. RASPBERRY PI 5

| Pi 5 Pin / Bus | To | Signal |
|----------------|----|--------|
| USB-C | Buck-Boost 5V/5A | Power in |
| PCIe (M.2 x1) | Hailo-8L AI HAT | AI accelerator |
| CSI0 | RGB Camera Module 3 | Visible imaging |
| CSI1 | NoIR Camera Module 3 | NIR imaging |
| GPIO10 (MOSI, pin 19) | TFT SDI (MOSI) | SPI0 data |
| GPIO11 (SCLK, pin 23) | TFT SCK | SPI0 clock |
| GPIO8 (CE0, pin 24) | TFT CS | SPI0 chip select |
| GPIO25 (pin 22) | TFT DC | Data / command |
| GPIO24 (pin 18) | TFT RESET | Reset |
| GPIO18 (pin 12) | Backlight switch gate (see below) | Backlight on/off, PWM |
| 3.3V (pin 1) | TFT VCC | Panel power |
| GPIO14 (TXD) | ESP32 GPIO16 (RX2) | UART TX |
| GPIO15 (RXD) | ESP32 GPIO17 (TX2) | UART RX |
| GND | Common GND | **SHARED — CRITICAL** |

> **Display: 2.4" TFT, ILI9341 controller, 240 × 320, on SPI0.** Leave SDO/MISO and
> the touch pins (T_CLK, T_CS, T_DIN, T_DO, T_IRQ) unconnected. **Do not wire the
> TFT's LED pin to GPIO18 directly**: the backlight draws 30–60 mA and a Pi GPIO pin
> may source about 16 mA. Switch the LED pin from 3.3 V with a high-side switch:
>
> ```
> 3.3V ── AO3401 P-MOSFET source;  drain ── TFT LED pin
> AO3401 gate ── 10 kΩ ── 3.3V            (off by default)
> AO3401 gate ── 2N7002 N-MOSFET drain;  2N7002 source ── GND
> 2N7002 gate ── 100 Ω ── GPIO18;        2N7002 gate ── 100 kΩ ── GND
> ```
>
> GPIO18 high = backlight on (PWM on GPIO18 dims it). If dimming is not needed,
> tie the LED pin straight to 3.3 V instead.

---

## 3. ESP32

| ESP32 Pin | To | Notes |
|-----------|----|-------|
| VIN | Buck-Boost 5V | Through 1A fuse |
| GND | Common GND | Shared |
| GPIO16 (RX2) | Pi GPIO14 (TXD) | UART in |
| GPIO17 (TX2) | Pi GPIO15 (RXD) | UART out |
| GPIO21 (SDA) | MCP4725 + ADS1115 SDA | I2C data |
| GPIO22 (SCL) | MCP4725 + ADS1115 SCL | I2C clock |
| GPIO32 | Button 1 — Scan | Active low, internal pull-up |
| GPIO33 | Button 2 — Mode | Active low, internal pull-up |
| GPIO34 | Button 3 — Menu | **Input-only, external pull-up** |
| GPIO27 | 220Ω → LED anode | Cathode → GND |
| 3.3V | MCP4725 / ADS1115 / MCP6004 VDD | Analog supply |

---

## 4. POTENTIOSTAT (Analog Front End)

One **MCP6004** quad op-amp (3.3 V single supply) does four jobs. The earlier
design drove the counter electrode straight from the DAC through 10 kΩ, so
nothing held the reference electrode at the commanded potential and the cell
current shifted the applied voltage. The control amplifier (U1C) closes that
loop.

| Amp | Pins | Role | Connections |
|-----|------|------|-------------|
| U1A | 3 IN+, 2 IN−, 1 OUT | **RE buffer** (unity follower) | IN+ ← RE; OUT → IN−, → ADS1115 AIN1, → U1C IN− via 10 kΩ |
| U1B | 5 IN+, 6 IN−, 7 OUT | **TIA** (current → voltage) | IN− ← WE; IN+ ← VGND buffer; Rf 100 kΩ ‖ Cf 100 pF from OUT to IN−; OUT → AIN0 |
| U1C | 10 IN+, 9 IN−, 8 OUT | **Control amplifier** | IN+ ← MCP4725 VOUT; IN− ← RE buffer (10 kΩ) with 10 nF from OUT to IN−; OUT → 1 kΩ → CE |
| U1D | 12 IN+, 13 IN−, 14 OUT | **Virtual-ground buffer** | IN+ ← 10 kΩ/10 kΩ divider from 3.3 V (100 nF to GND); OUT → IN−, → U1B IN+, → AIN3 |
| — | 4 VDD, 11 VSS | Supply | 3.3 V / GND, 100 nF at pin 4 |

| Node | Connection | Notes |
|------|-----------|-------|
| ADS1115 AIN0 | U1B OUT (TIA) | Cell current: I = (V_AIN0 − V_AIN3) / 100 kΩ, anodic positive |
| ADS1115 AIN1 | U1A OUT (RE) | Reference electrode potential |
| ADS1115 AIN2 | Battery via 2 × 100 kΩ divider | Battery voltage monitor |
| ADS1115 AIN3 | U1D OUT (VGND) | Measured virtual ground, used instead of a fixed 1.65 V |
| ADS1115 ALERT | → GPIO35 | Ready/alert (10 kΩ pull-up to 3.3 V) |
| MCP4725 ADDR | → GND | I2C address 0x60 |
| ADS1115 ADDR | → 3.3V | I2C address 0x49 |

**Potential.** The loop forces V_RE = V_DAC and the TIA holds WE at V_GND, so the
working-electrode potential is **E(WE vs RE) = V_GND − V_DAC**. The firmware
commands V_DAC = V_GND − E. A sweep from −0.2 V to +0.6 V puts the DAC between
1.85 V and 1.05 V, inside its 0–3.3 V range.

**Readable current.** The TIA output swings about ±1.6 V around V_GND, so with
Rf = 100 kΩ the largest readable current is **±16.5 µA**. Readings beyond about
±15.5 µA are flagged as saturated.

---

## 5. ELECTRODES (3-electrode cell)

| Electrode | Material | To |
|-----------|----------|----|
| WE (Working) | Carbon rod / gold wire | U1B IN− (pin 6), TIA |
| RE (Reference) | Ag/AgCl | U1A IN+ (pin 3), RE buffer |
| CE (Counter) | Pt / carbon | U1C OUT (pin 8) via 1 kΩ, control amp |

> **Note:** Use short shielded wires inside the stainless-steel needle housing.
> Terminate with JST headers for field-swappable electrode cartridges.

---

## 6. SIGNAL FLOW (ASCII)

```
BIOSENSOR PATH
  Plant Sap ──> Hydrogel ──> WE ──> MCP6004 TIA ──> ADS1115 ──> ESP32 (DPV)
                                                                    │
                                                              UART 115200
                                                                    │
                                                                    v
                                                                  Pi 5

VISION / FUSION PATH
  RGB Cam (CSI0) ─┐
                  ├─> Pi 5 ──> Hailo-8L ──> Late Fusion ──> TFT
  NoIR Cam (CSI1)─┘                            │
                                               v
                                          PostgreSQL (ricescanner)
```
