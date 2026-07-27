#ifndef LED_H
#define LED_H

#include <Arduino.h>

// Led controls a single status LED with on/off and a non-blocking blink mode.
class Led {
public:
    Led();

    void begin();
    void on();
    void off();

    // Enable/disable blink mode. update() must be called regularly in loop().
    void blink();

    // Non-blocking blink handler; toggles the LED at LED_BLINK_MS intervals.
    void update();

private:
    bool _blinking;
    bool _state;
    unsigned long _lastToggleMs;

    void write(bool state);
};

#endif // LED_H
