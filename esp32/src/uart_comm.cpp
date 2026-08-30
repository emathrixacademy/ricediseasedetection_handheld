#include "uart_comm.h"
#include "config.h"

UartComm::UartComm() : _rxBuffer("") {}

void UartComm::begin() {
    Serial2.begin(UART2_BAUD, SERIAL_8N1, UART2_RX_PIN, UART2_TX_PIN);
    _rxBuffer = "";
}

String UartComm::readCommand() {
    // Accumulate characters until a newline; return the completed line.
    while (Serial2.available() > 0) {
        char c = (char)Serial2.read();
        if (c == '\n') {
            String line = _rxBuffer;
            _rxBuffer = "";
            line.trim(); // strip trailing \r and whitespace
            if (line.length() > 0) {
                return line;
            }
        } else {
            _rxBuffer += c;
            if (_rxBuffer.length() > 512) {
                _rxBuffer = ""; // overflow guard
            }
        }
    }
    return "";
}

void UartComm::sendBiosensor(float peakCurrentUA, float peakVoltageV,
                             float reVoltageV, const String& rawJson) {
    Serial2.print("DATA:BIOSENSOR:");
    Serial2.print(peakCurrentUA, 3);
    Serial2.print(",");
    Serial2.print(peakVoltageV, 4);
    Serial2.print(",");
    Serial2.print(reVoltageV, 4);
    Serial2.print(",");
    Serial2.print(rawJson);
    Serial2.print("\n");
}

void UartComm::sendBattery(float voltageV) {
    Serial2.print("DATA:BATTERY:");
    Serial2.print(voltageV, 3);
    Serial2.print("\n");
}

void UartComm::sendButton(uint8_t id) {
    Serial2.print("DATA:BUTTON:");
    Serial2.print(id);
    Serial2.print("\n");
}

void UartComm::sendStatusOk() {
    Serial2.print("DATA:STATUS:OK\n");
}

void UartComm::sendStatusDegraded(const String& reason) {
    Serial2.print("DATA:STATUS:DEGRADED:");
    Serial2.print(reason);
    Serial2.print("\n");
}

void UartComm::sendError(const String& msg) {
    Serial2.print("ERR:");
    Serial2.print(msg);
    Serial2.print("\n");
}
