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

// Perform a DPV scan and report the result to the Pi.
static void handleScan() {
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
        uart.sendBattery(adc.readBattery());
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
        uart.sendStatusOk();
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

    // Analog front-end.
    if (!adc.begin()) {
        Serial.println("[ERR] ADS1115 init failed");
    }
    if (!potentiostat.begin()) {
        Serial.println("[ERR] MCP4725 init failed");
    }

    // Alert pin from ADS1115 (input; polling used, but keep configured).
    pinMode(ADS_ALERT_PIN, INPUT);

    // HMI.
    buttons.begin();
    led.begin();

    Serial.println("[BOOT] Ready.");
}

void loop() {
    // 1. Poll buttons and forward presses to the Pi.
    uint8_t btn = buttons.poll();
    if (btn != BTN_NONE) {
        uart.sendButton(btn);
        // Local shortcut: SCAN button also triggers a scan.
        if (btn == BTN_ID_SCAN) {
            handleScan();
        }
    }

    // 2. Handle any incoming UART command.
    String cmd = uart.readCommand();
    if (cmd.length() > 0) {
        dispatch(cmd);
    }

    // 3. Keep the non-blocking LED blink running.
    led.update();
}
