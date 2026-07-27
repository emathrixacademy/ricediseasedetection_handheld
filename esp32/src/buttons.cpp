#include "buttons.h"
#include "config.h"

Buttons::Buttons() {
    _btns[0] = { BTN_SCAN_PIN, BTN_ID_SCAN, 0, 0, 0, false };
    _btns[1] = { BTN_MODE_PIN, BTN_ID_MODE, 0, 0, 0, false };
    _btns[2] = { BTN_MENU_PIN, BTN_ID_MENU, 0, 0, 0, false };
}

void Buttons::begin() {
    // GPIO34 (BTN_MENU) is input-only with no internal pull-up.
    pinMode(BTN_SCAN_PIN, INPUT_PULLUP);
    pinMode(BTN_MODE_PIN, INPUT_PULLUP);
    pinMode(BTN_MENU_PIN, INPUT); // external pull-up required

    for (int i = 0; i < 3; i++) {
        int r = readActive(_btns[i].pin);
        _btns[i].lastReading = r;
        _btns[i].stableState = r;
        _btns[i].reported = (r == 1);
    }
}

int Buttons::readActive(uint8_t pin) {
    int level = digitalRead(pin);
#if BTN_ACTIVE_LOW
    return (level == LOW) ? 1 : 0;
#else
    return (level == HIGH) ? 1 : 0;
#endif
}

uint8_t Buttons::poll() {
    unsigned long now = millis();

    for (int i = 0; i < 3; i++) {
        BtnState& b = _btns[i];
        int reading = readActive(b.pin);

        if (reading != b.lastReading) {
            b.lastReading = reading;
            b.lastChangeMs = now;
        }

        if ((now - b.lastChangeMs) >= BTN_DEBOUNCE_MS) {
            if (reading != b.stableState) {
                b.stableState = reading;
                if (b.stableState == 1 && !b.reported) {
                    b.reported = true;
                    return b.id; // fresh press edge
                }
                if (b.stableState == 0) {
                    b.reported = false; // released, allow next press
                }
            }
        }
    }
    return BTN_NONE;
}
