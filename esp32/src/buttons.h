#ifndef BUTTONS_H
#define BUTTONS_H

#include <Arduino.h>

// Buttons handles three momentary push buttons with software debounce.
// poll() returns a button id (1=scan, 2=mode, 3=menu) once per press edge,
// or 0 when nothing new was pressed.
class Buttons {
public:
    Buttons();

    // Configure pin modes (INPUT_PULLUP where supported, INPUT for GPIO34).
    void begin();

    // Non-blocking debounced poll. Returns the button id on a fresh press.
    uint8_t poll();

private:
    struct BtnState {
        uint8_t pin;
        uint8_t id;
        int lastReading;
        int stableState;
        unsigned long lastChangeMs;
        bool reported;
    };

    BtnState _btns[3];

    int readActive(uint8_t pin); // 1 if pressed (active-low aware)
};

#endif // BUTTONS_H
