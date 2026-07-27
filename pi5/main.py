"""Main orchestrator for the Raspberry Pi 5 handheld rice disease scanner.

Wires together the camera, AI, comms, display and database packages into a
single scan pipeline:

    capture RGB + NIR  ->  trigger biosensor (UART)  ->  run inference
        ->  late fusion  ->  show on LCD  ->  log to DB

Every subsystem is imported defensively: if a package or its hardware
dependencies are missing the scanner keeps running in a degraded (mock)
mode so the flow can be exercised anywhere.
"""

import os
import time
import uuid

# --- defensive subsystem imports ------------------------------------------

try:
    from pi5 import config
except ImportError:  # running from inside pi5/
    import config  # type: ignore

try:
    from pi5.camera import RGBCapture, NIRCapture
except Exception as exc:  # pragma: no cover
    print(f"[main] camera package unavailable: {exc}")
    RGBCapture = NIRCapture = None

try:
    from pi5.ai import RGBClassifier, NIRClassifier, DecisionFusion
except Exception as exc:  # pragma: no cover
    print(f"[main] ai package unavailable: {exc}")
    RGBClassifier = NIRClassifier = DecisionFusion = None

try:
    from pi5.comms import UARTBridge
except Exception as exc:  # pragma: no cover
    print(f"[main] comms package unavailable: {exc}")
    UARTBridge = None

try:
    from pi5.display import LCDDriver
except Exception as exc:  # pragma: no cover
    print(f"[main] display package unavailable: {exc}")
    LCDDriver = None

try:
    from pi5 import db as db_pkg
except Exception as exc:  # pragma: no cover
    print(f"[main] db package unavailable: {exc}")
    db_pkg = None


class RiceScanner:
    """Top-level device controller."""

    def __init__(self, use_db=False):
        self.use_db = use_db
        self._start_time = time.time()

        # Cameras
        self.rgb_cam = RGBCapture() if RGBCapture else None
        self.nir_cam = NIRCapture() if NIRCapture else None

        # AI
        self.rgb_clf = RGBClassifier() if RGBClassifier else None
        self.nir_clf = NIRClassifier() if NIRClassifier else None
        self.fusion = DecisionFusion() if DecisionFusion else None

        # Comms + display
        self.uart = UARTBridge() if UARTBridge else None
        self.lcd = LCDDriver() if LCDDriver else None
        if self.lcd:
            self.lcd.init()

        os.makedirs(config.IMAGE_DIR, exist_ok=True)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _biosensor_signal(reading):
        """Reduce a biosensor dict to a scalar in [0, 1] for fusion.

        Uses peak current normalised against a nominal full-scale of 50 uA.
        """
        if not reading:
            return None
        current = reading.get("peak_current_ua")
        if current is None:
            return None
        return max(0.0, min(1.0, current / 50.0))

    # -- pipeline ------------------------------------------------------------

    def run_scan(self, session_notes=None):
        """Execute one full scan cycle and return a result dict."""
        scan_id = uuid.uuid4().hex[:8]
        ts = int(time.time())
        result = {"scan_id": scan_id}

        if self.lcd:
            self.lcd.show_status({"state": "scanning", "id": scan_id})
        if self.uart:
            try:
                self.uart.set_led("BLINK")
            except Exception:
                pass

        # 1. Capture imaging modalities
        rgb_img = self.rgb_cam.capture() if self.rgb_cam else None
        nir_img = self.nir_cam.capture() if self.nir_cam else None

        rgb_path = os.path.join(config.IMAGE_DIR, f"{ts}_{scan_id}_rgb.png")
        nir_path = os.path.join(config.IMAGE_DIR, f"{ts}_{scan_id}_nir.png")
        try:
            if self.rgb_cam:
                self.rgb_cam.save(rgb_path)
            if self.nir_cam:
                self.nir_cam.save(nir_path)
        except Exception as exc:
            print(f"[main] image save failed: {exc}")

        # NDVI as an auxiliary vegetation metric
        ndvi = None
        if self.nir_cam and nir_img is not None:
            try:
                ndvi = float(self.nir_cam.compute_ndvi(nir_img).mean())
            except Exception:
                ndvi = None

        # 2. Trigger the electrochemical biosensor over UART
        biosensor = self.uart.trigger_scan() if self.uart else None
        if biosensor:
            result["biosensor"] = biosensor

        # 3. Per-modality inference
        rgb_res = None
        nir_res = None
        if self.rgb_clf and rgb_img is not None:
            rgb_res = self.rgb_clf.predict(rgb_img)
        if self.nir_clf and nir_img is not None:
            nir_res = self.nir_clf.predict(nir_img)

        # 4. Late fusion
        bio_signal = self._biosensor_signal(biosensor)
        if self.fusion:
            fused = self.fusion.fuse(rgb_res, nir_res, biosensor_signal=bio_signal)
        else:
            # No AI available -> fall back to whatever single result exists.
            fallback = rgb_res or nir_res or {}
            fused = {
                "final_diagnosis": fallback.get("prediction", "unknown"),
                "final_confidence": fallback.get("confidence", 0.0),
            }

        result.update({
            "rgb": rgb_res,
            "nir": nir_res,
            "ndvi": ndvi,
            "biosensor_signal": bio_signal,
            "fused": fused,
            "rgb_path": rgb_path if self.rgb_cam else None,
            "nir_path": nir_path if self.nir_cam else None,
        })

        # 5. Display
        if self.lcd:
            self.lcd.show_result(
                fused.get("final_diagnosis", "unknown"),
                float(fused.get("final_confidence", 0.0)),
            )
        if self.uart:
            try:
                self.uart.set_led("ON")
            except Exception:
                pass

        # 6. Persist
        if self.use_db:
            self._log_to_db(result, session_notes)

        return result

    def _log_to_db(self, result, session_notes):
        """Write a scan result to the database (best effort)."""
        if not db_pkg:
            print("[main] db unavailable, skipping persistence")
            return
        try:
            with db_pkg.get_session() as sess:
                session = db_pkg.ScanSession(location_notes=session_notes)
                sess.add(session)
                sess.flush()  # assign session.id

                fused = result.get("fused", {})
                rgb = result.get("rgb") or {}
                nir = result.get("nir") or {}
                sess.add(db_pkg.FusedDiagnosis(
                    session_id=session.id,
                    rgb_prediction=rgb.get("prediction"),
                    rgb_confidence=rgb.get("confidence"),
                    nir_prediction=nir.get("prediction"),
                    nir_confidence=nir.get("confidence"),
                    biosensor_signal=result.get("biosensor_signal"),
                    final_diagnosis=fused.get("final_diagnosis"),
                    final_confidence=fused.get("final_confidence"),
                ))
            print(f"[main] logged scan {result['scan_id']} to db")
        except Exception as exc:
            print(f"[main] db logging failed: {exc}")

    # -- event loop ----------------------------------------------------------

    def run_forever(self, poll_interval=0.2):
        """Block waiting for scan-button events over UART."""
        if not self.uart:
            print("[main] no UART -> cannot listen for buttons")
            return
        print("[main] entering event loop (Ctrl-C to exit)")
        try:
            while True:
                event = self.uart.read_response()
                if event.get("type") == "button":
                    print(f"[main] button {event.get('button')} pressed")
                    res = self.run_scan()
                    fused = res.get("fused", {})
                    print(f"[main] result: {fused.get('final_diagnosis')} "
                          f"({fused.get('final_confidence', 0.0):.1%})")
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\n[main] shutting down")
        finally:
            self.close()

    def close(self):
        for obj in (self.rgb_cam, self.nir_cam, self.uart):
            if obj and hasattr(obj, "close"):
                try:
                    obj.close()
                except Exception:
                    pass


if __name__ == "__main__":
    print("=" * 50)
    print("Rice disease scanner - mock scan cycle")
    print("=" * 50)
    scanner = RiceScanner(use_db=False)
    result = scanner.run_scan(session_notes="mock __main__ run")
    fused = result.get("fused", {})
    print("-" * 50)
    print(f"Scan ID     : {result['scan_id']}")
    print(f"Diagnosis   : {fused.get('final_diagnosis')}")
    print(f"Confidence  : {float(fused.get('final_confidence', 0.0)):.1%}")
    print(f"NDVI (mean) : {result.get('ndvi')}")
    print(f"Biosensor   : {result.get('biosensor_signal')}")
    scanner.close()
