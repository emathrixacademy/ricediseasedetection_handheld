#include "adc_reader.h"
#include "config.h"

ADCReader::ADCReader() : _ready(false) {}

bool ADCReader::begin() {
    // ADS1115 gain: +/-4.096V full scale gives good headroom around 3.3V rails.
    _ads.setGain(GAIN_ONE); // 1x -> +/-4.096V
    _ads.setDataRate(RATE_ADS1115_250SPS);
    _ready = _ads.begin(ADS1115_ADDR);
    return _ready;
}

float ADCReader::readChannelVolts(uint8_t channel) {
    if (!_ready) return 0.0f;
    int16_t raw = _ads.readADC_SingleEnded(channel);
    return _ads.computeVolts(raw);
}

float ADCReader::readWE() {
    // TIA output measured against virtual ground.
    // I = (Vgnd - Vout) / Rf   -> convert amps to microamps.
    float vout = readChannelVolts(ADS_CH_WE);
    float amps = (VIRTUAL_GND_V - vout) / TIA_RF_OHM;
    return amps * 1.0e6f; // microamps
}

float ADCReader::readRE() {
    return readChannelVolts(ADS_CH_RE);
}

float ADCReader::readBattery() {
    float vdiv = readChannelVolts(ADS_CH_BATT);
    return vdiv * BATT_DIVIDER_RATIO;
}
