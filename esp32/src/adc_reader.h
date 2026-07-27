#ifndef ADC_READER_H
#define ADC_READER_H

#include <Arduino.h>
#include <Adafruit_ADS1X15.h>

// ADCReader wraps the ADS1115 and converts raw readings into
// physically meaningful biosensor quantities.
class ADCReader {
public:
    ADCReader();

    // Initialize the ADS1115. Wire.begin() must be called first.
    // Returns true on success.
    bool begin();

    // Working electrode current in microamps.
    // TIA output voltage is referenced to virtual ground; current = (Vgnd - Vout) / Rf.
    float readWE();

    // Reference electrode potential in volts.
    float readRE();

    // Battery voltage in volts (divider ratio applied).
    float readBattery();

    // Raw single-ended volts on an arbitrary channel (0..3).
    float readChannelVolts(uint8_t channel);

private:
    Adafruit_ADS1115 _ads;
    bool _ready;
};

#endif // ADC_READER_H
