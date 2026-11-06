#include "potentiostat.h"
#include "config.h"

const DPVProfile DPV_H2O2 = {"H2O2", DPV_H2O2_START_MV, DPV_H2O2_END_MV,
                             DPV_H2O2_STEP_MV, DPV_H2O2_PULSE_MV};
const DPVProfile DPV_NO3 = {"NO3", DPV_NO3_START_MV, DPV_NO3_END_MV,
                            DPV_NO3_STEP_MV, DPV_NO3_PULSE_MV};

Potentiostat::Potentiostat(ADCReader& adc) : _adc(adc), _ready(false) {}

bool Potentiostat::begin() {
    _ready = _dac.begin(MCP4725_ADDR);
    if (_ready) {
        setPotential(0.0f); // RE at virtual ground: no potential across the cell
    }
    return _ready;
}

uint16_t Potentiostat::mvToCounts(float mV) {
    // E(WE vs RE) = Vgnd - Vdac, so Vdac = Vgnd - E.
    float dacMv = (_adc.vgnd() * 1000.0f) - mV;
    float counts = (dacMv / DAC_VREF_MV) * (float)DAC_MAX_COUNTS;
    if (counts < 0) counts = 0;
    if (counts > DAC_MAX_COUNTS) counts = DAC_MAX_COUNTS;
    return (uint16_t)counts;
}

void Potentiostat::setPotential(float mV) {
    if (!_ready) return;
    _dac.setVoltage(mvToCounts(mV), false);
}

static bool saturated(float vout, float vgnd) {
    return fabsf(vout - vgnd) > TIA_SATURATION_V;
}

DPVResult Potentiostat::runDPV(const DPVProfile& p) {
    DPVResult res;
    res.analyte = p.name;
    res.status = "OK";
    res.peakCurrentUA = 0.0f;
    res.peakVoltageV = 0.0f;
    res.reVoltageV = 0.0f;
    res.rawJson = "[]";
    res.ok = false;

    if (!_ready) {
        return res;
    }

    // One virtual-ground reading for the whole sweep.
    const float vgnd = _adc.updateVgnd();
    const float dir = (p.stepMv < 0) ? -1.0f : 1.0f;
    const int nSteps = (int)floorf((p.endMv - p.startMv) / p.stepMv) + 1;

    String json = "[";
    json.reserve(28 * DPV_MAX_POINTS);
    float bestScore = -1.0e9f;            // peak in the sweep's own direction
    float minDiff = 1.0e9f, maxDiff = -1.0e9f;
    bool anySaturated = false;

    for (int k = 0; k < nSteps && k < DPV_MAX_POINTS; k++) {
        const float base = p.startMv + k * p.stepMv;

        // ---- Base level ----
        setPotential(base);
        delay(DPV_STEP_PERIOD_MS - DPV_PULSE_WIDTH_MS);
        float vBase = _adc.readTIAVolts();

        // ---- Pulse level ----
        setPotential(base + p.pulseMv);
        delay(DPV_PULSE_WIDTH_MS);
        float vPulse = _adc.readTIAVolts();
        float reV = _adc.readRE();

        if (saturated(vBase, vgnd) || saturated(vPulse, vgnd)) {
            anySaturated = true;
        }

        // Differential current is the DPV signal (anodic positive).
        float diff = (vPulse - vBase) / TIA_RF_OHM * 1.0e6f;
        float ev = base / 1000.0f; // electrode potential in volts
        if (diff < minDiff) minDiff = diff;
        if (diff > maxDiff) maxDiff = diff;

        // Oxidation peaks are positive, reduction peaks negative.
        if (diff * dir > bestScore) {
            bestScore = diff * dir;
            res.peakCurrentUA = diff;
            res.peakVoltageV = ev;
            res.reVoltageV = reV;
        }

        if (k) json += ",";
        json += "{\"v\":" + String(ev, 4) + ",\"i\":" + String(diff, 4) + "}";
    }

    json += "]";
    res.rawJson = json;
    res.ok = true;
    if (anySaturated) {
        res.status = "SATURATED";          // current beyond the readable range
    } else if (maxDiff - minDiff < DPV_NO_SIGNAL_UA) {
        res.status = "NO_SIGNAL";          // flat curve: electrode not in contact
    }

    // Return the cell to a safe idle potential.
    setPotential(0.0f);
    return res;
}
