#ifndef POTENTIOSTAT_H
#define POTENTIOSTAT_H

#include <Arduino.h>
#include <Adafruit_MCP4725.h>
#include "adc_reader.h"

// One analyte's DPV settings (potentials in mV, WE vs RE).
struct DPVProfile {
    const char* name;      // "H2O2" or "NO3", sent back with the reading
    float startMv;
    float endMv;
    float stepMv;          // signed: negative for a cathodic sweep
    float pulseMv;         // signed: same sign as stepMv
};

extern const DPVProfile DPV_H2O2;
extern const DPVProfile DPV_NO3;

// Result of a DPV sweep.
struct DPVResult {
    const char* analyte;   // profile name
    const char* status;    // "OK", "SATURATED" or "NO_SIGNAL"
    float peakCurrentUA;   // peak differential current (microamps, signed)
    float peakVoltageV;    // electrode potential at the peak (volts)
    float reVoltageV;      // reference electrode voltage at peak (volts)
    String rawJson;        // JSON array of {v, i} sampled points
    bool ok;               // the sweep ran (false = front end not ready)
};

// Potentiostat drives the cell potential via the MCP4725 DAC (through the
// control amplifier) and samples current/voltage through the ADCReader.
class Potentiostat {
public:
    Potentiostat(ADCReader& adc);

    // Initialize the DAC. Wire.begin() must be called first.
    bool begin();

    // Command a working-electrode potential (mV, WE vs RE).
    void setPotential(float mV);

    // Run a differential pulse voltammetry sweep with the given settings.
    DPVResult runDPV(const DPVProfile& p);

private:
    Adafruit_MCP4725 _dac;
    ADCReader& _adc;
    bool _ready;

    // Convert a desired electrode potential (mV) to a DAC count.
    uint16_t mvToCounts(float mV);
};

#endif // POTENTIOSTAT_H
