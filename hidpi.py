#!/usr/bin/env python3
"""
hidpi.py -- minimal HiDPI display override for macOS.

Generates Apple's display-override plist with HiDPI scaled resolutions and
installs it to /Library/Displays/Contents/Resources/Overrides/. This is the
same mechanism BetterDisplay and Crisp use -- no daemon, no menu bar app,
no network calls, just a plist.

Usage:
  hidpi.py list
      Print connected displays (from system_profiler) to find your monitor.

  hidpi.py enable --vendor 0x10ac --product 0x4149 --width 3440 --height 1440
      Generate the override and install it. Asks for your admin password once
      via the standard macOS prompt. Then reconnect the display or reboot,
      and the new "looks like" resolutions appear in System Settings.

  hidpi.py enable ... --scales 1.0,0.8,0.5
      Custom logical scales (fractions of native). Default: 1.0,0.8,0.75,0.625,0.5

  hidpi.py disable --vendor 0x10ac --product 0x4149
      Remove the override and restore stock behavior.

Find your display's Vendor ID / Product ID:
  Apple menu -> About This Mac -> More Info -> System Report ->
  Graphics/Displays -> your monitor -> "Display Vendor ID" / "Display Product ID".
  (Hex values like 0x10ac work; plain decimal works too.)
"""

import argparse
import plistlib
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

OVERRIDES_BASE = Path("/Library/Displays/Contents/Resources/Overrides")
DEFAULT_SCALES = [1.0, 0.8, 0.75, 0.625, 0.5]


def parse_id(s: str) -> int:
    s = s.strip().lower().removeprefix("0x")
    try:
        return int(s, 16)
    except ValueError:
        return int(s, 10)


def override_paths(vendor: int, product: int) -> tuple[Path, Path]:
    d = OVERRIDES_BASE / f"DisplayVendorID-{vendor:x}"
    return d, d / f"DisplayProductID-{product:x}"


def scaled_modes(width: int, height: int, scales: list[float]) -> list[bytes]:
    """Each mode: 8 bytes big-endian (backing_width, backing_height).

    HiDPI "looks like WxH" = backing store 2Wx2H. macOS renders at the
    backing resolution and maps it to the panel, so text stays sharp.
    """
    modes: list[bytes] = []
    for scale in scales:
        logical_w = int(round(width * scale)) & ~1
        logical_h = int(round(height * scale)) & ~1
        if logical_w < 800 or logical_h < 600:
            continue
        modes.append(struct.pack(">II", logical_w * 2, logical_h * 2))
    # Deduplicate while preserving order.
    seen, unique = set(), []
    for m in modes:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def privileged_run(shell_cmd: str) -> bool:
    """Run a shell command with admin rights via the standard macOS prompt."""
    script = f'do shell script "{shell_cmd}" with administrator privileges'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Authorization failed: {r.stderr.strip()}", file=sys.stderr)
        return False
    return True


def cmd_list(_args: argparse.Namespace) -> int:
    r = subprocess.run(
        ["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True
    )
    print(r.stdout)
    print(
        "Tip: match your monitor's name above, then find its Vendor/Product IDs in\n"
        "System Information (Graphics/Displays) -- they are shown in hex.",
        file=sys.stderr,
    )
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    vendor = parse_id(args.vendor)
    product = parse_id(args.product)
    scales = [float(s) for s in args.scales.split(",")]

    modes = scaled_modes(args.width, args.height, scales)
    plist_bytes = plistlib.dumps({"scale-resolutions": modes}, fmt=plistlib.FMT_XML)

    print(f"Display: vendor 0x{vendor:x}, product 0x{product:x}, "
          f"native {args.width}x{args.height}")
    print("HiDPI modes (looks like -> backing):")
    for m in modes:
        bw, bh = struct.unpack(">II", m)
        print(f"  {bw // 2}x{bh // 2}  (backing {bw}x{bh})")

    with tempfile.NamedTemporaryFile(
        suffix=".plist", delete=False, prefix="hidpi_override_"
    ) as f:
        f.write(plist_bytes)
        tmp = f.name

    d, plist_path = override_paths(vendor, product)
    ok = privileged_run(f"mkdir -p '{d}' && cp '{tmp}' '{plist_path}' && rm -f '{tmp}'")
    if not ok:
        Path(tmp).unlink(missing_ok=True)
        return 1

    print(f"\nInstalled: {plist_path}")
    print("Reconnect the display (or reboot) for the new resolutions to appear\n"
          "in System Settings -> Displays.")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    vendor = parse_id(args.vendor)
    product = parse_id(args.product)
    _d, plist_path = override_paths(vendor, product)
    if privileged_run(f"rm -f '{plist_path}'"):
        print(f"Removed: {plist_path}")
        print("Reconnect the display (or reboot) to restore stock resolutions.")
        return 0
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Minimal HiDPI display override for macOS.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Show connected displays.")

    e = sub.add_parser("enable", help="Generate and install the HiDPI override.")
    e.add_argument("--vendor", required=True, help="Display Vendor ID (hex or decimal).")
    e.add_argument("--product", required=True, help="Display Product ID (hex or decimal).")
    e.add_argument("--width", required=True, type=int, help="Native width, e.g. 3440.")
    e.add_argument("--height", required=True, type=int, help="Native height, e.g. 1440.")
    e.add_argument("--scales", default=",".join(map(str, DEFAULT_SCALES)),
                   help="Comma-separated logical scales (default: %(default)s).")

    d = sub.add_parser("disable", help="Remove the HiDPI override.")
    d.add_argument("--vendor", required=True, help="Display Vendor ID (hex or decimal).")
    d.add_argument("--product", required=True, help="Display Product ID (hex or decimal).")

    args = p.parse_args()
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "enable":
        return cmd_enable(args)
    return cmd_disable(args)


if __name__ == "__main__":
    sys.exit(main())
