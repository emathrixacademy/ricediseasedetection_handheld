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
    """Print and (unless dry-run) execute a subprocess command.

    Returns the process return code, or None in dry-run mode. A dry run must
    not report 0, or callers cannot distinguish "the command succeeded" from
    "the command was never executed".
    """
    printable = " ".join(cmd)
    print(f"[hailo] {printable}")
    if dry_run:
        return None
    return subprocess.call(cmd)


def preflight():
    """Report whether this machine can run the Hailo Dataflow Compiler.

    The DFC is not distributed on PyPI: it is an authenticated download from
    the Hailo Developer Zone, and it targets Ubuntu x86_64 on Python 3.8-3.11.
    Printing these facts up front turns "command not found" into an actionable
    procurement item.
    """
    import platform

    print("[preflight] Hailo toolchain environment")
    print(f"[preflight]   host OS        : {platform.system()} "
          f"{platform.release()} ({platform.machine()})")
    print(f"[preflight]   python         : "
          f"{sys.version.split()[0]}")
    print(f"[preflight]   target arch    : {HAILO_ARCH}")
    for tool in ("hailomz", "hailo", "hailortcli"):
        found = shutil.which(tool)
        print(f"[preflight]   {tool:<14} : {found or 'NOT FOUND on PATH'}")
    if platform.system() != "Linux":
        print("[preflight]   NOTE: the Dataflow Compiler is distributed for "
              "Ubuntu x86_64 only; it does not run natively on this host.")
    return shutil.which("hailomz") or shutil.which("hailo")


def _tool_available(name):
    return shutil.which(name) is not None


def _confirm_hef(output_path):
    """Verify the HEF actually exists before claiming success.

    A zero return code from a wrapper script is not evidence that a file was
    written. Report what is on disk, not what was requested.
    """
    if not os.path.isfile(output_path):
        sys.exit(f"Compiler reported success but no file exists at "
                 f"{output_path}. Treat this as a FAILED compilation.")
    size = os.path.getsize(output_path)
    if size == 0:
        sys.exit(f"HEF at {output_path} is empty (0 bytes). "
                 f"Treat this as a FAILED compilation.")
    print(f"HEF written to {output_path} ({size:,} bytes)")
    return output_path


def convert(onnx_path, output_path, calib_dir=None, dry_run=False):
    """Drive the Hailo ONNX -> HEF conversion.

    Prefers the single-shot ``hailomz compile`` entrypoint when present;
    otherwise falls back to the explicit parse/optimize/compile steps.
    """
    if not dry_run and not os.path.isfile(onnx_path):
        sys.exit(f"ONNX not found: {onnx_path}")

    # Record the opset actually present. The Hailo parser is opset-sensitive,
    # and export_onnx.py is known to emit a newer opset than requested when
    # torch cannot downgrade the graph.
    if os.path.isfile(onnx_path):
        try:
            import onnx

            model = onnx.load(onnx_path)
            for imp in model.opset_import:
                if imp.domain in ("", "ai.onnx"):
                    print(f"[hailo] input ONNX declares opset {imp.version}")
                    break
        except ImportError:
            print("[hailo] onnx not installed -- cannot report input opset")

    have_hailomz = _tool_available("hailomz")
    have_hailo = _tool_available("hailo")

    if not (have_hailomz or have_hailo) and not dry_run:
        preflight()
        sys.exit(
            "\nHailo toolchain not found on PATH.\n"
            "The Dataflow Compiler is NOT on PyPI -- it is an authenticated\n"
            "download from the Hailo Developer Zone "
            "(https://hailo.ai/developer-zone/software-downloads/)\n"
            "and requires an approved developer account.\n"
            "Re-run with --dry-run to print the commands without executing.")

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
            return _confirm_hef(output_path)
        if rc is not None:
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
        if rc is not None and rc != 0:
            stage = cmd[1] if len(cmd) > 1 else cmd[0]
            sys.exit(f"Hailo '{stage}' stage failed (rc={rc}): "
                     f"{' '.join(cmd)}")

    if dry_run:
        print("[dry-run] no compiler was invoked and NO FILES WERE PRODUCED")
        return None
    return _confirm_hef(output_path)


def main():
    parser = argparse.ArgumentParser(description="ONNX -> Hailo-8L HEF.")
    # Not required=True: --preflight is a standalone environment check.
    parser.add_argument("--onnx", help="input .onnx model")
    parser.add_argument("--output", help="output .hef path")
    parser.add_argument("--calib-dir", default=None,
                        help="calibration image dir for quantization")
    parser.add_argument("--dry-run", action="store_true",
                        help="print commands without executing")
    parser.add_argument("--preflight", action="store_true",
                        help="report toolchain availability and exit")
    args = parser.parse_args()

    if args.preflight:
        preflight()
        return

    if not args.onnx or not args.output:
        parser.error("--onnx and --output are required unless --preflight")

    convert(args.onnx, args.output, args.calib_dir, args.dry_run)


if __name__ == "__main__":
    main()
