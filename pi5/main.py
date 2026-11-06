"""Main orchestrator for the Raspberry Pi 5 handheld rice disease scanner.

One scan:

    capture RGB + NIR  ->  DPV sweep(s) on the ESP32 (UART)  ->  inference
        ->  biosensor features  ->  late fusion  ->  TFT  ->  database

Buttons (on the ESP32, forwarded as DATA:BUTTON:<n>):
    1 SCAN  run a scan
    2 MODE  cycle what the biosensor measures: H2O2, nitrate, or both
    3 MENU  show the status screen (battery, mode, subsystems)

Every subsystem is imported defensively: if a package or its hardware is
missing the scanner keeps running in a degraded (mock) mode, and says so on
the console, the screen and in every stored row.

    python -m pi5.main            # the device: wait for buttons, log to the DB
    python -m pi5.main --once     # one scan and exit (no DB unless --db)
"""

import argparse
import os
import sys
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
    from pi5.ai.biosensor_model import BiosensorClassifier
    from pi5.ai.dpv_features import extract_features
except Exception as exc:  # pragma: no cover
    print(f"[main] ai package unavailable: {exc}")
    RGBClassifier = NIRClassifier = DecisionFusion = BiosensorClassifier = None
    extract_features = None

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

BTN_SCAN, BTN_MODE, BTN_MENU = 1, 2, 3


class RiceScanner:
    """Top-level device controller."""

    def __init__(self, use_db=False, session_factory=None):
        self.use_db = use_db
        self._session_factory = session_factory or (db_pkg.get_session if db_pkg else None)
        self._start_time = time.time()
        self.mode_index = 0
        self.battery_v = None
        self._last_battery_poll = 0.0
        self._battery_warned = False

        # Cameras
        self.rgb_cam = RGBCapture() if RGBCapture else None
        self.nir_cam = NIRCapture() if NIRCapture else None

        # AI
        self.rgb_clf = RGBClassifier() if RGBClassifier else None
        self.nir_clf = NIRClassifier() if NIRClassifier else None
        self.bio_clf = BiosensorClassifier() if BiosensorClassifier else None
        self.fusion = DecisionFusion() if DecisionFusion else None

        # Comms + display
        self.uart = UARTBridge() if UARTBridge else None
        self.lcd = LCDDriver() if LCDDriver else None
        if self.lcd:
            self.lcd.init()

        os.makedirs(config.IMAGE_DIR, exist_ok=True)

        # -- degradation accounting -----------------------------------------
        # A fallback that nobody can see is indistinguishable from success.
        # Record every subsystem that is absent or running on mock data.
        self.degraded = self._collect_degraded()
        self.mock = bool(self.degraded)
        self._report_degradation()

    @property
    def analytes(self):
        return config.ANALYTE_MODES[self.mode_index % len(config.ANALYTE_MODES)]

    def _collect_degraded(self):
        """Return the sorted names of subsystems that are absent or mocked."""
        degraded = set()

        for name, obj, cls in (
            ("rgb_camera", self.rgb_cam, RGBCapture),
            ("nir_camera", self.nir_cam, NIRCapture),
            ("rgb_classifier", self.rgb_clf, RGBClassifier),
            ("nir_classifier", self.nir_clf, NIRClassifier),
            ("uart", self.uart, UARTBridge),
            ("lcd", self.lcd, LCDDriver),
        ):
            if cls is None or obj is None:
                degraded.add(f"{name}:unavailable")
            elif getattr(obj, "mock", False):
                degraded.add(f"{name}:mock")

        if DecisionFusion is None or self.fusion is None:
            degraded.add("fusion:unavailable")
        if db_pkg is None:
            degraded.add("database:unavailable")

        return sorted(degraded)

    def _report_degradation(self):
        """Print degradation state; abort if nothing at all came up.

        Exiting 0 after silently disabling every subsystem is the defect being
        removed here -- a scan that produced nothing must not look like a pass.
        """
        core = ("rgb_camera", "nir_camera", "rgb_classifier",
                "nir_classifier", "uart", "lcd")
        dead = [n for n in core
                if f"{n}:unavailable" in self.degraded]

        if not self.degraded:
            print("[main] all subsystems nominal")
            return

        print(f"[main] DEGRADED -- {len(self.degraded)} subsystem(s) "
              f"not fully operational:")
        for entry in self.degraded:
            name, _, why = entry.partition(":")
            note = ("package/hardware missing" if why == "unavailable"
                    else "running on SIMULATED data")
            print(f"[main]   - {name}: {note}")

        if len(dead) == len(core):
            print("[main] FATAL: every subsystem failed to initialise. "
                  "Nothing can be measured.", file=sys.stderr)
            print("[main] If launched as 'python pi5/main.py', use "
                  "'python -m pi5.main' from the project root instead.",
                  file=sys.stderr)
            raise SystemExit(2)

    # -- helpers -------------------------------------------------------------

    def _measure_biosensor(self):
        """Run one sweep per selected analyte; return a list of readings.

        Each reading is the parsed UART reply plus ``features`` (None when the
        reading is invalid: saturated, no signal, error or timeout).
        """
        readings = []
        for analyte in self.analytes:
            if self.lcd:
                label = config.ANALYTES[analyte]["label"]
                self.lcd.show_status({"state": "measuring", "biosensor": label,
                                      "time": "about 20 s"})
            r = self.uart.trigger_scan(analyte) if self.uart else None
            if not isinstance(r, dict):
                continue
            r.setdefault("analyte", analyte)
            kind = r.get("type")
            if kind == "error":
                r["status"] = "ERROR"
            elif kind == "timeout":
                r["status"] = "TIMEOUT"
            r["features"] = None
            if kind == "biosensor" and r.get("valid") and r.get("raw_json") \
                    and extract_features:
                polarity = config.ANALYTES.get(analyte, {}).get("polarity", 1)
                r["features"] = extract_features(r["raw_json"], polarity)
            readings.append(r)
        return readings

    def poll_battery(self, force=False):
        """Ask the ESP32 for the battery voltage every BATTERY_POLL_S."""
        if not self.uart:
            return self.battery_v
        now = time.monotonic()
        if not force and now - self._last_battery_poll < config.BATTERY_POLL_S:
            return self.battery_v
        self._last_battery_poll = now
        v = self.uart.get_battery()
        if v is not None:
            self.battery_v = v
            if self.lcd:
                self.lcd.battery_v = v
            low = v < config.BATTERY_LOW_V
            if low and not self._battery_warned and self.lcd:
                self.lcd.show_warning("LOW BATTERY",
                                      f"Battery {v:.2f} V. Charge the scanner "
                                      f"(solar or USB) before the next scans.")
            self._battery_warned = low
        return self.battery_v

    # -- pipeline ------------------------------------------------------------

    def run_scan(self, session_notes=None):
        """Execute one full scan cycle and return a result dict."""
        scan_id = uuid.uuid4().hex[:8]
        ts = int(time.time())
        result = {"scan_id": scan_id, "analytes": list(self.analytes)}

        self.poll_battery(force=True)
        if self.lcd:
            self.lcd.show_status({"state": "scanning", "id": scan_id})
        if self.uart:
            try:
                self.uart.set_led("BLINK")
            except Exception:
                pass

        # 1. Capture imaging modalities; the saved files are these frames.
        rgb_img = self.rgb_cam.capture() if self.rgb_cam else None
        nir_img = self.nir_cam.capture() if self.nir_cam else None

        rgb_path = os.path.join(config.IMAGE_DIR, f"{ts}_{scan_id}_rgb.png")
        nir_path = os.path.join(config.IMAGE_DIR, f"{ts}_{scan_id}_nir.png")
        try:
            if self.rgb_cam and rgb_img is not None:
                self.rgb_cam.save(rgb_path, frame=rgb_img)
            if self.nir_cam and nir_img is not None:
                self.nir_cam.save(nir_path, frame=nir_img)
        except Exception as exc:
            print(f"[main] image save failed: {exc}")

        # 2. Biosensor sweeps on the ESP32 (one per selected analyte).
        readings = self._measure_biosensor()

        # 3. Per-modality inference
        rgb_res = self.rgb_clf.predict(rgb_img) if self.rgb_clf and rgb_img is not None else None
        nir_res = self.nir_clf.predict(nir_img) if self.nir_clf and nir_img is not None else None
        ndvi = nir_res.get("ndvi_value") if nir_res else None

        valid = {r["analyte"]: r["features"] for r in readings if r.get("features")}
        bio_res = self.bio_clf.predict(valid) if self.bio_clf else None

        # 4. Late fusion
        if self.fusion:
            fused = self.fusion.fuse(rgb_res, nir_res, biosensor_result=bio_res)
        else:
            fallback = rgb_res or nir_res or {}
            fused = {
                "final_diagnosis": fallback.get("prediction", "unknown"),
                "final_confidence": fallback.get("confidence", 0.0),
            }

        # Per-scan provenance: a reading is mock if any contributing subsystem
        # was mocked, including a biosensor reply synthesised by the bridge.
        scan_degraded = set(self.degraded)
        for r in readings:
            if r.get("mock"):
                scan_degraded.add("uart:mock")
            if r.get("status") not in (None, "OK"):
                scan_degraded.add(f"biosensor_{r['analyte']}:{r['status'].lower()}")
                print(f"[main] WARNING: biosensor {r['analyte']} "
                      f"{r['status']} {r.get('message', '')}".rstrip())
        if self.bio_clf and not self.bio_clf.calibrated:
            scan_degraded.add("biosensor:uncalibrated")
        scan_mock = any(not e.endswith(":uncalibrated") and
                        not e.startswith("biosensor_") for e in scan_degraded)

        result.update({
            "rgb": rgb_res,
            "nir": nir_res,
            "ndvi": ndvi,
            "biosensor": readings,
            "biosensor_result": bio_res,
            "fused": fused,
            "rgb_path": rgb_path if self.rgb_cam else None,
            "nir_path": nir_path if self.nir_cam else None,
            "battery_v": self.battery_v,
            "mock": scan_mock,
            "degraded": sorted(scan_degraded),
        })

        # 5. Display
        if self.lcd:
            details = {}
            if ndvi is not None:
                details["NDVI"] = f"{ndvi:.2f}"
            for r in readings:
                label = config.ANALYTES.get(r["analyte"], {}).get("label", r["analyte"])
                f = r.get("features")
                details[label] = (f"{f['peak_height_ua']:.2f} uA" if f
                                  else r.get("status", "-").replace("_", " ").lower())
            details["Fused"] = "+".join(fused.get("modalities", [])) or "-"
            self.lcd.show_result(
                fused.get("final_diagnosis", "unknown"),
                float(fused.get("final_confidence", 0.0)),
                mock=scan_mock,
                details=details,
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
        """Write a scan to every table: session, images, biosensor, fusion."""
        if not self._session_factory:
            print("[main] db unavailable, skipping persistence")
            return
        try:
            with self._session_factory() as sess:
                session = db_pkg.ScanSession(location_notes=session_notes)
                sess.add(session)
                sess.flush()  # assign session.id

                rgb = result.get("rgb") or {}
                nir = result.get("nir") or {}
                if result.get("rgb_path") or rgb:
                    sess.add(db_pkg.RGBScan(
                        session_id=session.id, image_path=result.get("rgb_path"),
                        prediction=rgb.get("prediction"),
                        confidence=rgb.get("confidence"),
                        processing_time_ms=rgb.get("processing_time_ms")))
                if result.get("nir_path") or nir:
                    sess.add(db_pkg.NIRScan(
                        session_id=session.id, image_path=result.get("nir_path"),
                        ndvi_value=result.get("ndvi"),
                        prediction=nir.get("prediction"),
                        confidence=nir.get("confidence"),
                        processing_time_ms=nir.get("processing_time_ms")))
                for r in result.get("biosensor") or []:
                    sess.add(db_pkg.BiosensorReading(
                        session_id=session.id,
                        analyte=r.get("analyte"),
                        status=r.get("status"),
                        features=r.get("features"),
                        dpv_peak_current_ua=r.get("peak_current_ua"),
                        dpv_peak_voltage_v=r.get("peak_voltage_v"),
                        re_voltage_v=r.get("re_voltage_v"),
                        raw_adc_values={"curve": r.get("raw_json"),
                                        "mock": bool(r.get("mock"))}))

                fused = result.get("fused", {})
                bio = result.get("biosensor_result") or {}
                sess.add(db_pkg.FusedDiagnosis(
                    session_id=session.id,
                    rgb_prediction=rgb.get("prediction"),
                    rgb_confidence=rgb.get("confidence"),
                    nir_prediction=nir.get("prediction"),
                    nir_confidence=nir.get("confidence"),
                    biosensor_signal=bio.get("confidence"),
                    final_diagnosis=fused.get("final_diagnosis"),
                    final_confidence=fused.get("final_confidence"),
                    mock=bool(result.get("mock")),
                    degraded=",".join(result.get("degraded") or []) or None,
                ))
                if result.get("battery_v") is not None:
                    sess.add(db_pkg.SystemLog(
                        battery_voltage_v=result["battery_v"],
                        uptime_seconds=time.time() - self._start_time))
            print(f"[main] logged scan {result['scan_id']} to db")
        except Exception as exc:
            print(f"[main] db logging failed: {exc}")

    # -- event loop ----------------------------------------------------------

    def show_menu(self):
        """MENU button: battery, biosensor mode and subsystem state."""
        if not self.lcd:
            return
        self.poll_battery(force=True)
        mode = " + ".join(config.ANALYTES[a]["label"] for a in self.analytes)
        self.lcd.show_status({
            "battery": f"{self.battery_v:.2f} V" if self.battery_v else "unknown",
            "biosensor": mode,
            "calibrated": "yes" if self.bio_clf and self.bio_clf.calibrated else "no",
            "subsystems": "all OK" if not self.degraded else f"{len(self.degraded)} degraded",
        })

    def handle_button(self, button):
        if button == BTN_SCAN:
            res = self.run_scan()
            fused = res.get("fused", {})
            print(f"[main] result: {fused.get('final_diagnosis')} "
                  f"({fused.get('final_confidence', 0.0):.1%})")
        elif button == BTN_MODE:
            self.mode_index = (self.mode_index + 1) % len(config.ANALYTE_MODES)
            mode = " + ".join(config.ANALYTES[a]["label"] for a in self.analytes)
            print(f"[main] biosensor mode: {mode}")
            if self.lcd:
                self.lcd.show_status({"biosensor": mode, "press": "SCAN to measure"})
        elif button == BTN_MENU:
            self.show_menu()

    def run_forever(self, poll_interval=0.2):
        """Block waiting for button events over UART."""
        if not self.uart:
            print("[main] no UART -> cannot listen for buttons")
            return
        print("[main] entering event loop (Ctrl-C to exit)")
        self.poll_battery(force=True)
        if self.lcd:
            self.show_menu()
        try:
            while True:
                event = self.uart.read_event(timeout=poll_interval)
                if event.get("type") == "button":
                    print(f"[main] button {event.get('button')} pressed")
                    self.handle_button(event.get("button"))
                self.poll_battery()
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


def _print_result(result):
    fused = result.get("fused", {})
    print("-" * 50)
    print(f"Scan ID     : {result['scan_id']}")
    print(f"Diagnosis   : {fused.get('final_diagnosis')}")
    print(f"Confidence  : {float(fused.get('final_confidence', 0.0)):.1%}")
    print(f"Fused from  : {', '.join(fused.get('modalities', [])) or '-'}")
    print(f"NDVI (mean) : {result.get('ndvi')}")
    for r in result.get("biosensor") or []:
        f = r.get("features") or {}
        print(f"Biosensor   : {r.get('analyte')} {r.get('status')} "
              f"peak {f.get('peak_height_ua', '-')} uA")
    if result.get("mock"):
        print("-" * 50)
        print("*** SIMULATED RESULT -- NOT A REAL MEASUREMENT ***")
    if result.get("degraded"):
        print(f"Degraded    : {', '.join(result['degraded'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rice disease handheld scanner")
    parser.add_argument("--once", action="store_true",
                        help="run one scan and exit instead of waiting for buttons")
    parser.add_argument("--db", action="store_true",
                        help="with --once: also log the scan to the database")
    args = parser.parse_args(argv)

    if args.once:
        scanner = RiceScanner(use_db=args.db)
        _print_result(scanner.run_scan(session_notes="--once run"))
        scanner.close()
        return
    RiceScanner(use_db=True).run_forever()


if __name__ == "__main__":
    main()
