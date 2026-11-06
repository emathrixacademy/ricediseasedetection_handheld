#ifndef CONFIG_H
#define CONFIG_H

// =============================================================
// Handheld Rice Disease Scanner - Biosensor Controller
// Central pin and constant definitions (ESP32 DevKit / esp32dev)
// =============================================================

// ----- UART2 (link to Raspberry Pi) -----
#define UART2_RX_PIN      16      // RX2
#define UART2_TX_PIN      17      // TX2
#define UART2_BAUD        115200

// ----- Debug serial (USB) -----
#define DEBUG_BAUD        115200

// ----- I2C bus -----
#define I2C_SDA_PIN       21
#define I2C_SCL_PIN       22
#define I2C_FREQ_HZ       400000

// ----- Buttons (active low) -----
// NOTE: GPIO34 is input-only and has NO internal pull-up.
//       An EXTERNAL pull-up resistor is required for BTN_MENU.
#define BTN_SCAN_PIN      32
#define BTN_MODE_PIN      33
#define BTN_MENU_PIN      34      // input-only, external pull-up needed
#define BTN_ACTIVE_LOW    1

// Button identifiers returned by Buttons::poll()
#define BTN_NONE          0
#define BTN_ID_SCAN       1
#define BTN_ID_MODE       2
#define BTN_ID_MENU       3

#define BTN_DEBOUNCE_MS   40

// ----- Status LED -----
#define LED_PIN           27
#define LED_BLINK_MS      250     // default non-blocking blink interval

// ----- ADS1115 ALERT/RDY -----
#define ADS_ALERT_PIN     35

// ----- I2C device addresses -----
#define MCP4725_ADDR      0x60
#define ADS1115_ADDR      0x49

// ----- ADS1115 channels -----
#define ADS_CH_WE         0       // AIN0: working electrode current (TIA output)
#define ADS_CH_RE         1       // AIN1: reference electrode voltage
#define ADS_CH_BATT       2       // AIN2: battery voltage (through divider)
#define ADS_CH_VGND       3       // AIN3: measured virtual ground (MCP6004 U1D buffer)

// ----- Analog front-end constants -----
#define VIRTUAL_GND_V     1.65f   // nominal virtual ground; sweeps use the measured AIN3 value
#define TIA_RF_OHM        100000.0f  // transimpedance feedback resistor (100 kOhm)

// Battery voltage divider: two 100k resistors -> ratio 2.0 (measured, adjust if needed)
#define BATT_DIVIDER_RATIO 2.0f

// MCP4725 DAC characteristics
#define DAC_VREF_MV       3300.0f // DAC reference / supply in millivolts
#define DAC_MAX_COUNTS    4095    // 12-bit

// ----- Differential Pulse Voltammetry (DPV) -----
// Potentials are the WORKING electrode vs the REFERENCE electrode (mV).
// The control amplifier holds V_RE = V_DAC and the TIA holds WE at V_GND, so
// E(WE vs RE) = V_GND - V_DAC and the DAC is commanded to V_GND - E.
// Current is reported anodic-positive (oxidation > 0), in microamps.

// H2O2 (oxidation): anodic sweep, positive pulses (Development Methods, 8.4).
#define DPV_H2O2_START_MV    -200.0f
#define DPV_H2O2_END_MV       600.0f
#define DPV_H2O2_STEP_MV        4.0f
#define DPV_H2O2_PULSE_MV      50.0f

// Nitrate (reduction): cathodic sweep, negative pulses.
// PROVISIONAL: set and confirmed during biosensor integration (methods, 8.4).
#define DPV_NO3_START_MV        0.0f
#define DPV_NO3_END_MV       -800.0f
#define DPV_NO3_STEP_MV        -4.0f
#define DPV_NO3_PULSE_MV      -50.0f

// Timing, shared by both analytes.
#define DPV_PULSE_WIDTH_MS   50     // pulse length (ms)
#define DPV_STEP_PERIOD_MS  100     // total time per step (base + pulse)

// Max samples buffered for a DPV sweep (safety cap for raw JSON output)
#define DPV_MAX_POINTS      256

// ----- Reading validity -----
// The TIA output swings about +/-1.6 V around V_GND: +/-16.5 uA at 100 kOhm.
// Beyond this margin the amplifier is at its rail and the current is unknown.
#define TIA_SATURATION_V     1.55f   // |Vout - Vgnd| above this = saturated
// Below this peak-to-peak differential current the curve is flat: the
// electrodes are not in contact (open cell). ADS1115 LSB is 1.25 nA here.
#define DPV_NO_SIGNAL_UA     0.02f

#endif // CONFIG_H
