"""AI inference package: RGB / NIR classifiers, decision fusion, Hailo backend."""

from .model_loader import load_model
from .rgb_classifier import RGBClassifier
from .nir_classifier import NIRClassifier
from .fusion import DecisionFusion

__all__ = ["load_model", "RGBClassifier", "NIRClassifier", "DecisionFusion"]
