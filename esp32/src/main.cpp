// =============================================================
// Handheld Rice Disease Scanner - ESP32 firmware entry point
//
// The ESP32 acts as the biosensor controller: it drives the
// potentiostat (MCP4725 DAC + ADS1115 ADC), reads buttons and
// battery, and talks to a Raspberry Pi over UART2.
// =============================================================

#include <Arduino.h>
#include <Wire.h>

#include "config.h"
#include "adc_reader.h"
#include "potentiostat.h"
#include "buttons.h"
#include "led.h"
#include "uart_comm.h"

// ----- Global subsystem instances -----
ADCReader    adc;
Potentiostat potentiostat(adc);
Buttons      buttons;
Led          led;
UartComm     uart;

// ----- Analog front-end readiness -----
// Latched at boot. A failed ADC or DAC init must never present as a healthy
// device: without these flags the firmware answers DATA:STATUS:OK and returns
// 0.00 uA scans, which look like real measurements of an inert sample.
static bool adcReady = false;
static bool dacReady = false;
static bool afeReady = false;

// Reason string for CMD:STATUS when the front end is degraded.
static String afeFaultReason() {
    if (!adcReady && !dacReady) return "ADC_AND_DAC_INIT";
    if (!adcReady)              return "ADC_INIT";
    if (!dacReady)              return "DAC_INIT";
    return "";
}

// Perform a DPV scan and report the result to the Pi.
static void handleScan() {
    // Refuse to sweep with a dead front end rather than returning zeros.
    if (!afeReady) {
        uart.sendError("AFE_NOT_READY:" + afeFaultReason());
        return;
    }

    DPVResult r = potentiostat.runDPV();
    if (r.ok) {
        uart.sendBiosensor(r.peakCurrentUA, r.peakVoltageV, r.reVoltageV, r.rawJson);
    } else {
        uart.sendError("DPV_FAILED");
    }
}

// Dispatch a single command line from the Pi.
static void dispatch(const String& cmd) {
    if (cmd == "CMD:SCAN") {
        handleScan();
    } else if (cmd == "CMD:BATTERY") {
        if (!adcReady) {
            uart.sendError("AFE_NOT_READY:ADC_INIT");
        } else {
            uart.sendBattery(adc.readBattery());
        }
    } else if (cmd == "CMD:LED:ON") {
        led.on();
        uart.sendStatusOk();
    } else if (cmd == "CMD:LED:OFF") {
        led.off();
        uart.sendStatusOk();
    } else if (cmd == "CMD:LED:BLINK") {
        led.blink();
        uart.sendStatusOk();
    } else if (cmd == "CMD:STATUS") {
        // OK is only permitted when every subsystem initialised.
        if (afeReady) {
            uart.sendStatusOk();
        } else {
            uart.sendStatusDegraded(afeFaultReason());
        }
    } else {
        uart.sendError("UNKNOWN_CMD");
    }
}

void setup() {
    // Debug serial over USB.
    Serial.begin(DEBUG_BAUD);
    Serial.println("[BOOT] Rice disease scanner controller starting...");

    // UART link to the Raspberry Pi.
    uart.begin();

    // I2C bus for DAC and ADC.
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ_HZ);

    // Analog front-end. Latch the outcome -- a failure here must stay visible
    // for the lifetime of the session, not just scroll past on the console.
    adcReady = adc.begin();
    if (!adcReady) {
        Serial.println("[ERR] ADS1115 init failed");
    }
    dacReady = potentiostat.begin();
    if (!dacReady) {
        Serial.println("[ERR] MCP4725 init failed");
    }
    afeReady = adcReady && dacReady;

    // Alert pin from ADS1115 (input; polling used, but keep configured).
    pinMode(ADS_ALERT_PIN, INPUT);

    // HMI.
    buttons.begin();
    led.begin();

    if (afeReady) {
        Serial.println("[BOOT] Ready.");
    } else {
        // Announce degradation unprompted so the Pi knows before its first
        // scan, and blink the LED so the fault is visible on the bench too.
        Serial.println("[BOOT] DEGRADED: " + afeFaultReason());
        uart.sendStatusDegraded(afeFaultReason());
        led.blink();
    }
}

void loop() {
    // 1. Poll buttons and forward presses to the Pi.
    //
    // The Pi is the sole owner of the scan trigger: it receives DATA:BUTTON
    // and answers with CMD:SCAN. The ESP32 deliberately does NOT run a local
    // sweep here -- doing both produced two 20 s sweeps per press and let the
    // Pi pair an unsolicited reading with the wrong set of captured images.
    uint8_t btn = buttons.poll();
    if (btn != BTN_NONE) {
        uart.sendButton(btn);
    }

    // 2. Handle any incoming UART command.
    String cmd = uart.readCommand();
    if (cmd.length() > 0) {
        dispatch(cmd);
    }

    // 3. Keep the non-blocking LED blink running.
    led.update();
}
