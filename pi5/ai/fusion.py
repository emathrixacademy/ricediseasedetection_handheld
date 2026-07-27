"""Late decision fusion of RGB, NIR and biosensor evidence."""

import numpy as np

try:
    from config import CLASSES, FUSION_WEIGHTS
except ImportError:  # pragma: no cover
    from pi5.config import CLASSES, FUSION_WEIGHTS


class DecisionFusion:
    """Weighted late fusion over per-modality softmax probability vectors.

    RGB and NIR contribute full class-probability distributions. The biosensor
    provides a scalar signal in [0, 1] interpreted as a confidence weight that
    boosts the disease evidence coming from the imaging modalities.
    """

    def __init__(self, weights=None, classes=None):
        self.weights = dict(weights or FUSION_WEIGHTS)
        self.classes = list(classes or CLASSES)

    def _probs_vector(self, result):
        """Extract an ordered probability vector from a classifier result."""
        if result is None:
            return None
        probs = result.get("probs")
        if not probs:
            return None
        return np.array([probs.get(c, 0.0) for c in self.classes], dtype=np.float32)

    def fuse(self, rgb_result, nir_result, biosensor_signal=None):
        """Combine modality outputs into a final diagnosis dict.

        biosensor_signal: scalar in [0, 1] (or None if unavailable).
        """
        rgb_vec = self._probs_vector(rgb_result)
        nir_vec = self._probs_vector(nir_result)

        combined = np.zeros(len(self.classes), dtype=np.float32)
        total_weight = 0.0

        if rgb_vec is not None:
            combined += self.weights["rgb"] * rgb_vec
            total_weight += self.weights["rgb"]
        if nir_vec is not None:
            combined += self.weights["nir"] * nir_vec
            total_weight += self.weights["nir"]

        # Biosensor: scale its weight by the incoming signal strength and use it
        # to reinforce the current imaging consensus (non-healthy classes).
        bio_weight = 0.0
        if biosensor_signal is not None and total_weight > 0:
            signal = float(np.clip(biosensor_signal, 0.0, 1.0))
            bio_weight = self.weights["biosensor"] * signal
            base = combined / total_weight
            combined += bio_weight * base
            total_weight += bio_weight

        if total_weight == 0:
            # Nothing to fuse -> uniform.
            combined = np.ones(len(self.classes), dtype=np.float32)
            total_weight = 1.0

        fused = combined / total_weight
        fused = fused / fused.sum()  # renormalize to a valid distribution
        idx = int(np.argmax(fused))

        return {
            "final_diagnosis": self.classes[idx],
            "final_confidence": float(fused[idx]),
            "fused_probs": {c: float(p) for c, p in zip(self.classes, fused)},
            "biosensor_signal": biosensor_signal,
            "biosensor_weight": round(bio_weight, 4),
            "weights_used": self.weights,
        }


if __name__ == "__main__":
    rgb = {"probs": {c: (0.6 if c == "rice_blast" else 0.08) for c in CLASSES}}
    nir = {"probs": {c: (0.5 if c == "rice_blast" else 0.1) for c in CLASSES}}
    fusion = DecisionFusion()
    print(fusion.fuse(rgb, nir, biosensor_signal=0.8))
