"""AI inference package: RGB / NIR classifiers, biosensor model, fusion, Hailo backend."""

from .model_loader import load_model
from .rgb_classifier import RGBClassifier
from .nir_classifier import NIRClassifier
from .biosensor_model import BiosensorClassifier
from .fusion import DecisionFusion

__all__ = ["load_model", "RGBClassifier", "NIRClassifier", "BiosensorClassifier",
           "DecisionFusion"]
