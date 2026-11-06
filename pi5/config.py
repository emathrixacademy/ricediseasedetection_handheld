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

# Model artifacts. Each classifier loads the first file that exists, in this
# order: the compiled Hailo-8L .hef (runs on the accelerator), the .onnx
# (CPU fallback), then the PyTorch .pt from training. RGB_MODEL_PATH /
# NIR_MODEL_PATH force one file. None found -> random mock, flagged as such.
MODEL_DIR = os.getenv("MODEL_DIR", "pi5/models")
RGB_MODEL_CANDIDATES = [os.path.join(MODEL_DIR, f) for f in
                        ("rgb_model.hef", "rgb_model.onnx", "rgb_model.pt")]
NIR_MODEL_CANDIDATES = [os.path.join(MODEL_DIR, f) for f in
                        ("nir_model.hef", "nir_model.onnx", "nir_model.pt")]
RGB_MODEL_PATH = os.getenv("RGB_MODEL_PATH")
NIR_MODEL_PATH = os.getenv("NIR_MODEL_PATH")
HAILO_HEF_PATH = os.path.join(MODEL_DIR, "rgb_model.hef")  # hailo_inference demo

# NIR model input: one channel, normalised like training/train_nir.py.
NIR_NORM_MEAN = 0.45
NIR_NORM_STD = 0.225

# ---------------------------------------------------------------------------
# Biosensor (DPV) -- must match esp32/src/config.h
# ---------------------------------------------------------------------------
# Analytes the ESP32 can sweep. polarity +1 = oxidation peak (positive
# current), -1 = reduction peak. NO3 settings are provisional (methods 8.4).
ANALYTES = {
    "H2O2": {"command": "CMD:SCAN:H2O2", "polarity": 1, "label": "H2O2"},
    "NO3": {"command": "CMD:SCAN:NO3", "polarity": -1, "label": "Nitrate"},
}
# What a scan measures, cycled with the MODE button: one analyte or both.
ANALYTE_MODES = [("H2O2",), ("NO3",), ("H2O2", "NO3")]
BIOSENSOR_FULL_SCALE_UA = 16.5   # 1.65 V / 100 kOhm, see WIRING.md section 4
# Calibration from plants of confirmed condition; until it exists the
# biosensor is recorded but left out of fusion (methods 9.7).
BIOSENSOR_CALIBRATION_PATH = os.getenv(
    "BIOSENSOR_CALIBRATION_PATH", os.path.join(MODEL_DIR, "biosensor_calibration.json"))

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
BATTERY_LOW_V = float(os.getenv("BATTERY_LOW_V", "3.4"))  # warn below this
BATTERY_POLL_S = 60          # how often the Pi asks the ESP32 for the voltage

# ---------------------------------------------------------------------------
# GPIO pin configuration (BCM numbering)
# ---------------------------------------------------------------------------

# 2.4" TFT, ILI9341 controller, 240 x 320, on hardware SPI0 (write-only).
# VCC -> 3.3 V (pin 1), GND -> GND, SDI/MOSI -> GPIO10 (pin 19),
# SCK -> GPIO11 (pin 23), CS -> GPIO8/CE0 (pin 24), DC -> GPIO25 (pin 22),
# RESET -> GPIO24 (pin 18), LED -> backlight switch driven by GPIO18 (pin 12).
# The backlight draws more than a GPIO pin may source: GPIO18 drives an
# N-MOSFET (or NPN) low-side switch, it never powers the LED pin directly.
# SDO/MISO is not used. The module's touch pins (T_*) are left unconnected.
LCD_SPI_PORT = 0
LCD_SPI_DEVICE = 0           # CE0 = GPIO8
LCD_DC = 25                  # data / command select
LCD_RST = 24                 # reset
LCD_BL = 18                  # backlight switch gate (PWM capable)
LCD_SPI_HZ = int(os.getenv("LCD_SPI_HZ", "32000000"))
# The ILI9341 is natively 320 x 240 (landscape); luma's rotate=1 turns it to
# portrait. Use 3 if the panel is mounted the other way up; 0 or 2 = landscape.
LCD_ROTATE = int(os.getenv("LCD_ROTATE", "1"))
LCD_WIDTH, LCD_HEIGHT = (240, 320) if LCD_ROTATE % 2 else (320, 240)
# Off the Pi the driver draws each screen into this PNG instead.
LCD_PREVIEW_PATH = os.getenv("LCD_PREVIEW_PATH", "pi5/data/lcd_preview.png")

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

# NDVI from the filtered NoIR camera. With a red-blocking (blue/"infragram")
# filter the sensor's red channel sees NIR and blue sees visible light: set
# NIR=0, VIS=2. With a blue-blocking (red) filter it is the other way round,
# the default here: NIR in blue (2), visible red in red (0).
NDVI_NIR_CHANNEL = int(os.getenv("NDVI_NIR_CHANNEL", "2"))
NDVI_VIS_CHANNEL = int(os.getenv("NDVI_VIS_CHANNEL", "0"))

INFERENCE_RESOLUTION = (224, 224)    # size fed to the models
CAPTURE_RESOLUTION = (640, 480)      # native capture size

# ---------------------------------------------------------------------------
# Filesystem paths and model artifacts
# ---------------------------------------------------------------------------

IMAGE_DIR = "pi5/data/images"

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
