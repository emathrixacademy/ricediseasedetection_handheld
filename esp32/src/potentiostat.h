#ifndef POTENTIOSTAT_H
#define POTENTIOSTAT_H

#include <Arduino.h>
#include <Adafruit_MCP4725.h>
#include "adc_reader.h"

// Result of a DPV sweep.
struct DPVResult {
    float peakCurrentUA;   // peak differential current (microamps)
    float peakVoltageV;    // electrode potential at the peak (volts)
    float reVoltageV;      // reference electrode voltage at peak (volts)
    String rawJson;        // JSON array of {v, i} sampled points
    bool ok;
};

// Potentiostat drives the cell potential via the MCP4725 DAC and
// samples current/voltage through the shared ADCReader.
class Potentiostat {
public:
    Potentiostat(ADCReader& adc);

    // Initialize the DAC. Wire.begin() must be called first.
    bool begin();

    // Command an electrode potential in millivolts (relative to virtual GND).
    void setVoltage(float mV);

    // Run a differential pulse voltammetry sweep and return the analysis.
    DPVResult runDPV();

private:
    Adafruit_MCP4725 _dac;
    ADCReader& _adc;
    bool _ready;

    // Convert a desired electrode potential (mV) to a DAC count.
    uint16_t mvToCounts(float mV);
};

#endif // POTENTIOSTAT_H
