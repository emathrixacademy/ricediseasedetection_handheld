#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Rice Disease Detection Handheld — one-command setup (no Docker)
# Run on the Raspberry Pi 5:  bash setup.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "==> [1/6] Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3-pip python3-venv \
    postgresql postgresql-contrib libpq-dev \
    libcamera-dev python3-picamera2 python3-libcamera \
    i2c-tools

echo "==> [2/6] Creating Python virtual environment..."
if [ ! -d venv ]; then
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> [3/6] Setting up PostgreSQL database (ricescanner)..."
bash scripts/setup_db.sh

echo "==> [4/6] Enabling interfaces (UART, SPI, I2C)..."
echo "    NOTE: enabling hardware interfaces requires a reboot."
sudo raspi-config nonint do_serial_hw 0   || true   # UART hardware ON
sudo raspi-config nonint do_serial_cons 1 || true   # serial login shell OFF
sudo raspi-config nonint do_spi 0         || true   # SPI ON
sudo raspi-config nonint do_i2c 0         || true   # I2C ON
# Ensure UART overlay present
CONFIG_TXT=/boot/firmware/config.txt
if [ -f "$CONFIG_TXT" ]; then
    grep -q "^enable_uart=1" "$CONFIG_TXT" || echo "enable_uart=1" | sudo tee -a "$CONFIG_TXT"
    grep -q "^dtoverlay=uart0" "$CONFIG_TXT" || echo "dtoverlay=uart0" | sudo tee -a "$CONFIG_TXT"
fi

echo "==> [5/6] Creating data directories..."
mkdir -p pi5/data/images pi5/models

echo "==> [6/6] Running hardware self-test..."
python scripts/test_hardware.py || echo "    (hardware test reported issues — review above)"

cat <<'EOF'

────────────────────────────────────────────────────────────
Setup complete.

  * Install the Hailo runtime separately:
      https://github.com/hailo-ai/hailo-rpi5-examples
  * Flash the ESP32 firmware:
      pip install platformio && pio run -d esp32 --target upload
  * Reboot to apply UART/SPI/I2C changes:  sudo reboot
  * Start the system:                      bash scripts/run.sh
────────────────────────────────────────────────────────────
EOF
