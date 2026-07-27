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
| GPIO10 (SPI0 MOSI) | LCD DIN | SPI data |
| GPIO11 (SCLK) | LCD SCK | SPI clock |
| GPIO8 (CE0) | LCD CS | SPI chip select |
| GPIO25 | LCD DC | Data/command |
| GPIO24 | LCD RST | Reset |
| GPIO18 | LCD BL | Backlight |
| 3.3V | LCD VCC | LCD power |
| GPIO14 (TXD) | ESP32 GPIO16 (RX2) | UART TX |
| GPIO15 (RXD) | ESP32 GPIO17 (TX2) | UART RX |
| GND | Common GND | **SHARED — CRITICAL** |

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
| 3.3V | MCP4725 / ADS1115 / MCP6002 VDD | Analog supply |

---

## 4. POTENTIOSTAT (Analog Front End)

| Node | Connection | Notes |
|------|-----------|-------|
| MCP4725 VOUT | → CE via 10kΩ | Excitation to counter electrode |
| RE | → MCP6002 A IN+ | Reference follower |
| MCP6002 A OUT | → A IN- | Unity buffer (voltage follower) |
| MCP6002 A OUT | → ADS1115 AIN1 | RE voltage sense |
| WE | → MCP6002 B IN- | Working electrode into TIA |
| MCP6002 B IN+ | → Virtual GND 1.65V | 2×10kΩ divider from 3.3V, 100nF cap |
| MCP6002 B feedback | Rf = 100kΩ | Optional 100pF in parallel |
| MCP6002 B OUT | → ADS1115 AIN0 | TIA current output |
| ADS1115 AIN2 | ← Battery via 2×100kΩ divider | Battery voltage monitor |
| ADS1115 ALERT | → GPIO35 | Ready/alert |
| MCP4725 ADDR | → GND | I2C address 0x60 |
| ADS1115 ADDR | → 3.3V | I2C address 0x49 |

**Transimpedance (TIA) gain:** `Vout = Vgnd - (I_we × Rf)` with Rf = 100kΩ.
Virtual ground is 1.65V so the single-supply op-amp can read bidirectional current.

---

## 5. ELECTRODES (3-electrode cell)

| Electrode | Material | To |
|-----------|----------|----|
| WE (Working) | Carbon rod / gold wire | MCP6002 B IN- |
| RE (Reference) | Ag/AgCl | MCP6002 A IN+ |
| CE (Counter) | Pt / carbon | MCP4725 VOUT via 10kΩ |

> **Note:** Use short shielded wires inside the stainless-steel needle housing.
> Terminate with JST headers for field-swappable electrode cartridges.

---

## 6. SIGNAL FLOW (ASCII)

```
BIOSENSOR PATH
  Plant Sap ──> Hydrogel ──> WE ──> MCP6002 TIA ──> ADS1115 ──> ESP32 (DPV)
                                                                    │
                                                              UART 115200
                                                                    │
                                                                    v
                                                                  Pi 5

VISION / FUSION PATH
  RGB Cam (CSI0) ─┐
                  ├─> Pi 5 ──> Hailo-8L ──> Late Fusion ──> LCD
  NoIR Cam (CSI1)─┘                            │
                                               v
                                          PostgreSQL (ricescanner)
```
