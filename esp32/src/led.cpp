#include "led.h"
#include "config.h"

Led::Led() : _blinking(false), _state(false), _lastToggleMs(0) {}

void Led::begin() {
    pinMode(LED_PIN, OUTPUT);
    off();
}

void Led::write(bool state) {
    _state = state;
    digitalWrite(LED_PIN, state ? HIGH : LOW);
}

void Led::on() {
    _blinking = false;
    write(true);
}

void Led::off() {
    _blinking = false;
    write(false);
}

void Led::blink() {
    _blinking = true;
    _lastToggleMs = millis();
}

void Led::update() {
    if (!_blinking) return;
    unsigned long now = millis();
    if ((now - _lastToggleMs) >= LED_BLINK_MS) {
        _lastToggleMs = now;
        write(!_state);
    }
}
