"""Central configuration for the Pi5 rice disease scanner."""

import os

# Disease classification labels (indices 0-5)
CLASSES = [
    "healthy",
    "rice_blast",
    "bacterial_leaf_blight",
    "nitrogen_deficiency",
    "water_deficit",
    "heat_stress",
]
NUM_CLASSES = len(CLASSES)

# Late-fusion default weights (should sum to ~1.0)
FUSION_WEIGHTS = {
    "rgb": 0.5,
    "nir": 0.3,
    "biosensor": 0.2,
}

# Model input geometry
IMAGE_SIZE = (224, 224)

# ImageNet normalization constants (MobileNetV3-style preprocessing)
NORM_MEAN = [0.485, 0.456, 0.406]
NORM_STD = [0.229, 0.224, 0.225]

# Model artifact paths (may not exist in a fresh checkout -> mock fallback used)
RGB_MODEL_PATH = os.getenv("RGB_MODEL_PATH", "models/rgb_mobilenetv3.pt")
NIR_MODEL_PATH = os.getenv("NIR_MODEL_PATH", "models/nir_mobilenetv3.pt")
HAILO_HEF_PATH = os.getenv("HAILO_HEF_PATH", "models/rice_disease.hef")

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://scanner_user:password@localhost:5432/ricescanner",
)

# Dashboard
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")

# ---------------------------------------------------------------------------
# Battery — single-cell 3.7 V LiPo (1S). NOT a 2S pack.
# ---------------------------------------------------------------------------
# The ESP32 reads the pack through a 2 x 100 kOhm divider (ratio 2.0) on
# ADS1115 AIN2 and reports the already-undivided value via DATA:BATTERY.
# At full charge 4.2 V / 2 = 2.1 V at the ADC pin, safely inside both the
# GAIN_ONE +/-4.096 V range and the ADS1115 VDD+0.3 V absolute limit.
BATTERY_CELLS = 1
BATTERY_NOMINAL_V = 3.7     # pack nominal
BATTERY_MIN_V = 3.0         # treated as empty; below this the pack is damaged
BATTERY_MAX_V = 4.2         # full charge
BATTERY_DIVIDER_RATIO = 2.0  # must match BATT_DIVIDER_RATIO in esp32/src/config.h

# ---------------------------------------------------------------------------
# GPIO pin configuration (BCM numbering)
# ---------------------------------------------------------------------------

# HD44780 1604 (16x4) character LCD via PCF8574 I2C backpack.
# Replaces the earlier ILI9341/SPI panel -- SPI0 pins are now free.
# Backpack SDA -> GPIO2 (pin 3), SCL -> GPIO3 (pin 5), VCC -> 5V, GND -> GND.
# Backpacks usually ship at 0x27; some are 0x3F. Verify with `i2cdetect -y 1`.
LCD_I2C_BUS = int(os.getenv("LCD_I2C_BUS", "1"))
LCD_I2C_ADDR = int(os.getenv("LCD_I2C_ADDR", "0x27"), 16)
LCD_COLS = 16
LCD_ROWS = 4

# UART link to the ESP32 companion MCU
UART_TXD = 14                    # Pi TXD -> ESP32 RX (GPIO14)
UART_RXD = 15                    # Pi RXD <- ESP32 TX (GPIO15)
UART_PORT = os.getenv("UART_PORT", "/dev/ttyAMA0")
UART_BAUD = int(os.getenv("UART_BAUD", "115200"))

# ---------------------------------------------------------------------------
# Camera configuration
# ---------------------------------------------------------------------------

RGB_CAMERA_NUM = 0                   # RGB camera on CSI port 0
NIR_CAMERA_NUM = 1                   # NIR / NoIR camera on CSI port 1

INFERENCE_RESOLUTION = (224, 224)    # size fed to the models
CAPTURE_RESOLUTION = (640, 480)      # native capture size

# ---------------------------------------------------------------------------
# Filesystem paths and model artifacts
# ---------------------------------------------------------------------------

IMAGE_DIR = "pi5/data/images"
MODEL_DIR = "pi5/models"

# HEF (Hailo) primary targets plus ONNX fallbacks
RGB_MODEL_PATH_HEF = os.path.join(MODEL_DIR, "rgb_model.hef")
RGB_MODEL_PATH_ONNX = os.path.join(MODEL_DIR, "rgb_model.onnx")
NIR_MODEL_PATH_HEF = os.path.join(MODEL_DIR, "nir_model.hef")
NIR_MODEL_PATH_ONNX = os.path.join(MODEL_DIR, "nir_model.onnx")

# Late-fusion scalar weights (dict form provided above as FUSION_WEIGHTS)
FUSION_WEIGHT_RGB = FUSION_WEIGHTS["rgb"]
FUSION_WEIGHT_NIR = FUSION_WEIGHTS["nir"]
FUSION_WEIGHT_BIOSENSOR = FUSION_WEIGHTS["biosensor"]


if __name__ == "__main__":
    print("CLASSES:", CLASSES)
    print("FUSION_WEIGHTS:", FUSION_WEIGHTS)
    print("DATABASE_URL:", DATABASE_URL)
    print("UART:", UART_PORT, "@", UART_BAUD)
    print("RGB cam:", RGB_CAMERA_NUM, "NIR cam:", NIR_CAMERA_NUM)
    print("Inference res:", INFERENCE_RESOLUTION, "Capture res:", CAPTURE_RESOLUTION)
    print("IMAGE_DIR:", IMAGE_DIR, "MODEL_DIR:", MODEL_DIR)
