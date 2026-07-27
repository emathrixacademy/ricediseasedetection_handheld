"""Convert an ONNX model to a Hailo-8L HEF using the Hailo toolchain.

This shells out to the Hailo Dataflow Compiler / Model Zoo CLI. Because the
Hailo SDK is often absent on dev machines, the script supports a ``--dry-run``
mode that only prints the commands it would run.

Typical real pipeline (Hailo DFC / hailomz):

    1. Parse ONNX      -> HAR   (hailo parser onnx)
    2. Optimize/quant  -> HAR   (hailo optimize, needs calibration images)
    3. Compile         -> HEF   (hailo compiler)

Or, in one shot via the Model Zoo:  ``hailomz compile ...``

Usage::

    python convert_hef.py --onnx models/rgb_classifier.onnx \
        --output models/rgb_classifier.hef --calib-dir dataset/annotated/test \
        [--dry-run]
"""

import argparse
import os
import shutil
import subprocess
import sys

HAILO_ARCH = "hailo8l"  # target device


def _run(cmd, dry_run):
    """Print and (unless dry-run) execute a subprocess command."""
    printable = " ".join(cmd)
    print(f"[hailo] {printable}")
    if dry_run:
        return 0
    return subprocess.call(cmd)


def _tool_available(name):
    return shutil.which(name) is not None


def convert(onnx_path, output_path, calib_dir=None, dry_run=False):
    """Drive the Hailo ONNX -> HEF conversion.

    Prefers the single-shot ``hailomz compile`` entrypoint when present;
    otherwise falls back to the explicit parse/optimize/compile steps.
    """
    if not dry_run and not os.path.isfile(onnx_path):
        sys.exit(f"ONNX not found: {onnx_path}")

    have_hailomz = _tool_available("hailomz")
    have_hailo = _tool_available("hailo")

    if not (have_hailomz or have_hailo) and not dry_run:
        sys.exit("Hailo toolchain not found on PATH. Install the Hailo "
                 "Dataflow Compiler / Model Zoo, or re-run with --dry-run.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    base = os.path.splitext(output_path)[0]
    har_path = base + ".har"
    quant_har = base + "_quantized.har"

    # Preferred: Model Zoo single-shot compile.
    if have_hailomz or dry_run:
        cmd = ["hailomz", "compile",
               "--ckpt", onnx_path,
               "--hw-arch", HAILO_ARCH,
               "--output", output_path]
        if calib_dir:
            cmd += ["--calib-path", calib_dir]
        rc = _run(cmd, dry_run)
        if rc == 0:
            print(f"HEF written to {output_path}")
            return output_path
        print("hailomz compile failed; falling back to explicit steps.")

    # Fallback: explicit DFC steps.
    steps = [
        ["hailo", "parser", "onnx", onnx_path, "--hw-arch", HAILO_ARCH,
         "--har", har_path],
        ["hailo", "optimize", har_path, "--hw-arch", HAILO_ARCH,
         "--output-har", quant_har]
        + (["--calib-set-path", calib_dir] if calib_dir else []),
        ["hailo", "compiler", quant_har, "--hw-arch", HAILO_ARCH,
         "--output-hef", output_path],
    ]
    for cmd in steps:
        rc = _run(cmd, dry_run)
        if rc != 0 and not dry_run:
            sys.exit(f"Step failed (rc={rc}): {' '.join(cmd)}")

    print(f"HEF written to {output_path}" if not dry_run
          else "[dry-run] no files produced")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="ONNX -> Hailo-8L HEF.")
    parser.add_argument("--onnx", required=True, help="input .onnx model")
    parser.add_argument("--output", required=True, help="output .hef path")
    parser.add_argument("--calib-dir", default=None,
                        help="calibration image dir for quantization")
    parser.add_argument("--dry-run", action="store_true",
                        help="print commands without executing")
    args = parser.parse_args()

    convert(args.onnx, args.output, args.calib_dir, args.dry_run)


if __name__ == "__main__":
    main()
