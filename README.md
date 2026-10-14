# hidpi

Minimal HiDPI display override for macOS. One Python script, no daemon, no menu
bar app, no network calls.

## What it does

Writes Apple's display-override plist with HiDPI scaled resolutions to
`/Library/Displays/Contents/Resources/Overrides/` -- the same mechanism
BetterDisplay and Crisp use. After installing, macOS offers sharp "looks like"
resolutions for your external monitor in System Settings -> Displays, instead
of only the blurry low-res list.

The whole trick is ~3 steps:

1. Build `scale-resolutions` entries: 8-byte big-endian `(backing_width, backing_height)`
   pairs. A HiDPI "looks like WxH" mode gets a 2Wx2H backing store, so macOS
   renders at full resolution and text stays sharp.
2. Write the plist to `DisplayVendorID-<hex>/DisplayProductID-<hex>` under the
   overrides directory (needs admin -- one standard macOS password prompt).
3. Reconnect the display (or reboot) so macOS re-reads the modes.

## Usage

```sh
# Find your monitor in the list
./hidpi.py list

# Install (example: Dell 34" ultrawide, 3440x1440)
./hidpi.py enable --vendor 0x10ac --product 0x4149 --width 3440 --height 1440

# Custom scales (fractions of native; default: 1.0,0.8,0.75,0.625,0.5)
./hidpi.py enable --vendor 0x10ac --product 0x4149 --width 3440 --height 1440 \
    --scales 1.0,0.8,0.5

# Remove the override
./hidpi.py disable --vendor 0x10ac --product 0x4149
```

Find your display's Vendor ID / Product ID in System Information:
Apple menu -> About This Mac -> More Info -> System Report ->
Graphics/Displays -> your monitor. Hex (`0x10ac`) or decimal both work.

## Notes

- Only integer 2x scales (e.g. "looks like" exactly half native) are
  pixel-perfect. Fractional HiDPI modes render huge and downscale -- text stays
  razor sharp, miles better than macOS's non-HiDPI scaled list.
- The override is per display model (vendor+product ID), not per port.
- To revert: `hidpi.py disable ...`, then reconnect the display.

## Origin

Built after auditing [Crisp](https://github.com/caicaiks/crisp)'s HiDPI
mechanism -- turned out the core is a plist write, so here's just the plist
write. MIT.
