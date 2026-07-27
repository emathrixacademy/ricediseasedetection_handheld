#include "potentiostat.h"
#include "config.h"

Potentiostat::Potentiostat(ADCReader& adc) : _adc(adc), _ready(false) {}

bool Potentiostat::begin() {
    _ready = _dac.begin(MCP4725_ADDR);
    if (_ready) {
        setVoltage(0.0f); // park at virtual ground
    }
    return _ready;
}

uint16_t Potentiostat::mvToCounts(float mV) {
    // The DAC output is centered on virtual ground so that a 0 mV command
    // produces VIRTUAL_GND_V at the DAC. Positive potentials go above it.
    float dacMv = (VIRTUAL_GND_V * 1000.0f) + mV;
    float counts = (dacMv / DAC_VREF_MV) * (float)DAC_MAX_COUNTS;
    if (counts < 0) counts = 0;
    if (counts > DAC_MAX_COUNTS) counts = DAC_MAX_COUNTS;
    return (uint16_t)counts;
}

void Potentiostat::setVoltage(float mV) {
    if (!_ready) return;
    _dac.setVoltage(mvToCounts(mV), false);
}

DPVResult Potentiostat::runDPV() {
    DPVResult res;
    res.peakCurrentUA = 0.0f;
    res.peakVoltageV = 0.0f;
    res.reVoltageV = 0.0f;
    res.rawJson = "[]";
    res.ok = false;

    if (!_ready) {
        return res;
    }

    String json = "[";
    bool first = true;
    int points = 0;

    float bestDiff = -1.0e9f; // most positive differential current

    // Staircase from start to end; at each step measure current before the
    // pulse (base) and at the end of the pulse, taking the difference (DPV).
    for (float base = DPV_START_MV;
         base <= DPV_END_MV && points < DPV_MAX_POINTS;
         base += DPV_STEP_MV) {

        // ---- Base level ----
        setVoltage(base);
        delay(DPV_STEP_PERIOD_MS - DPV_PULSE_WIDTH_MS);
        float iBase = _adc.readWE();

        // ---- Pulse level ----
        setVoltage(base + DPV_PULSE_AMP_MV);
        delay(DPV_PULSE_WIDTH_MS);
        float iPulse = _adc.readWE();
        float reV = _adc.readRE();

        // Differential current is the DPV signal.
        float diff = iPulse - iBase;
        float ev = base / 1000.0f; // electrode potential in volts

        // Track the peak (largest magnitude differential current).
        if (diff > bestDiff) {
            bestDiff = diff;
            res.peakCurrentUA = diff;
            res.peakVoltageV = ev;
            res.reVoltageV = reV;
        }

        if (!first) json += ",";
        json += "{\"v\":" + String(ev, 4) + ",\"i\":" + String(diff, 3) + "}";
        first = false;
        points++;
    }

    json += "]";
    res.rawJson = json;
    res.ok = true;

    // Return the cell to a safe idle potential.
    setVoltage(0.0f);
    return res;
}
