#include "adc_reader.h"
#include "config.h"

ADCReader::ADCReader() : _ready(false), _vgnd(VIRTUAL_GND_V) {}

bool ADCReader::begin() {
    // ADS1115 gain: +/-4.096V full scale gives good headroom around 3.3V rails.
    _ads.setGain(GAIN_ONE); // 1x -> +/-4.096V
    _ads.setDataRate(RATE_ADS1115_250SPS);
    _ready = _ads.begin(ADS1115_ADDR);
    if (_ready) {
        updateVgnd();
    }
    return _ready;
}

float ADCReader::readChannelVolts(uint8_t channel) {
    if (!_ready) return 0.0f;
    int16_t raw = _ads.readADC_SingleEnded(channel);
    return _ads.computeVolts(raw);
}

float ADCReader::updateVgnd() {
    // The 3.3 V rail is not calibrated, so the real mid-rail can sit tens of
    // mV off 1.65 V. Average a few readings of the buffered divider.
    float sum = 0.0f;
    for (int i = 0; i < 8; i++) {
        sum += readChannelVolts(ADS_CH_VGND);
    }
    float v = sum / 8.0f;
    // Implausible (buffer not fitted): keep the nominal value.
    _vgnd = (v > 1.2f && v < 2.1f) ? v : VIRTUAL_GND_V;
    return _vgnd;
}

float ADCReader::readTIAVolts() {
    return readChannelVolts(ADS_CH_WE);
}

float ADCReader::readWE() {
    // Anodic current leaves the TIA node into WE and is supplied through Rf
    // from the output: I = (Vout - Vgnd) / Rf. Convert amps to microamps.
    float amps = (readTIAVolts() - _vgnd) / TIA_RF_OHM;
    return amps * 1.0e6f;
}

float ADCReader::readRE() {
    return readChannelVolts(ADS_CH_RE);
}

float ADCReader::readBattery() {
    float vdiv = readChannelVolts(ADS_CH_BATT);
    return vdiv * BATT_DIVIDER_RATIO;
}
