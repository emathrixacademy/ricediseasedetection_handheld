#ifndef UART_COMM_H
#define UART_COMM_H

#include <Arduino.h>

// UartComm handles the text-based, newline-terminated protocol between the
// Raspberry Pi and the ESP32 over Serial2.
//
// Pi -> ESP32 commands:
//   CMD:SCAN, CMD:LED:ON, CMD:LED:OFF, CMD:LED:BLINK, CMD:BATTERY, CMD:STATUS
//
// ESP32 -> Pi responses:
//   DATA:BIOSENSOR:<peak_current_ua>,<peak_voltage_v>,<re_voltage_v>,<raw_json>
//   DATA:BATTERY:<voltage_v>
//   DATA:BUTTON:<1|2|3>
//   DATA:STATUS:OK                    (only when every subsystem initialised)
//   DATA:STATUS:DEGRADED:<reason>     (a subsystem failed to initialise)
//   ERR:<msg>
class UartComm {
public:
    UartComm();

    // Start Serial2 with the configured pins and baud.
    void begin();

    // Return a complete command line (without newline) or "" if none ready.
    String readCommand();

    // Response senders.
    void sendBiosensor(float peakCurrentUA, float peakVoltageV,
                       float reVoltageV, const String& rawJson);
    void sendBattery(float voltageV);
    void sendButton(uint8_t id);
    void sendStatusOk();
    void sendStatusDegraded(const String& reason);
    void sendError(const String& msg);

private:
    String _rxBuffer;
};

#endif // UART_COMM_H
