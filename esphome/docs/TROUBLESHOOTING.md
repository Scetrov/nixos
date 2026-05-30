# Troubleshooting

The active ESPHome configuration lives at `src/esphome.yml`. Run commands from the repository root unless a note says otherwise.

## Waveshare ESP32-C6-Touch-LCD-1.47 display

### Hardware identity

- Board: Waveshare ESP32-C6-Touch-LCD-1.47
- Display controller: JD9853
- Touch controller: AXS5106L
- Resolution: 172 × 320
- Factory BSP pins confirmed from Waveshare's touch demo:
  - SPI SCLK: GPIO1
  - SPI MOSI: GPIO2
  - LCD CS: GPIO14
  - LCD DC: GPIO15
  - LCD RST: GPIO22
  - LCD BL: GPIO23

Do not use ESPHome's `WAVESHARE-ESP32-C6-LCD-1.47` preset for this board. That preset targets the non-touch ST7789 variant.

### Final working display state

The working configuration uses:

- ESPHome `display.platform: mipi_spi`
- `model: CUSTOM`
- JD9853 vendor init sequence
- vendor-ordered init: `SLPOUT (0x11)`, wait 120 ms, then vendor bank commands
- `invert_colors: true`
- explicit `INVON (0x21)` near the end of `init_sequence`
- explicit `MADCTL (0x36, 0x68)` near the end of `init_sequence`
- no `transform:` block on the display

Observed final result:

- OTA update: white text on black background; correct orientation with USB-C on the right.
- Cold boot: same as OTA update; colour and orientation remain stable.

### Why the final config works

Waveshare's ESP-IDF JD9853 driver sends `SLPOUT (0x11)` before vendor bank commands, then waits 120 ms. Sending vendor commands before sleep-out caused cold-boot-only state differences.

The current known-good environment validated with ESPHome 2026.5.1 from the project virtualenv. ESPHome's `mipi_spi` flow also appends display state commands after custom init. During the investigation, the working environment needed these behaviors:

1. Avoid appending a duplicate `SLPOUT (0x11)` if the custom sequence already contains one.
2. Preserve manual `MADCTL (0x36)` from `init_sequence` instead of overwriting it later in `reset_params_()`.

Without preserving manual MADCTL, ESPHome's post-init rotation handling could overwrite the tested orientation value. If you rebuild against a different ESPHome version, re-check OTA and cold-boot orientation before assuming the display path is still stable.

### Values tested

- `0x20` / `invert_colors: false`: produced black-on-white / wrong colour state.
- `0x21` / `invert_colors: true`: fixed white-on-black colour state.
- `0x28`: became cold-boot stable but required a top mirror to read correctly.
- `0xA8`: fixed mirroring after OTA but was rotated 180 degrees, and cold-boot behaviour still differed.
- `0x68`: final working MADCTL value after the local `mipi_spi` patches.

### Diagnostic marker test

Temporary markers were used to diagnose transforms:

- green dot at logical top-left `(6, 6)`
- purple/pink dot at logical top-right `(313, 6)`

Findings:

- With `0xA8`, OTA and cold boot both placed pink bottom-left and green bottom-right with USB-C on the right, confirming a stable 180-degree rotation from the desired logical orientation.
- Switching to `0x68` corrected this.

The markers have been removed from `esphome.yml` after the fix.

### OTA rollback gotcha

If power is removed too soon after OTA, ESPHome/ESP-IDF may roll back to the previous OTA partition. Logs showed:

```text
OTA rollback detected! Rolled back from partition 'app1'
The device reset before the boot was marked successful
```

This made it look like cold boot had lost the latest code. `safe_mode.boot_is_good_after` is now set to `10s`, but still wait at least 10-15 seconds after OTA before removing power for a cold-boot test.

### Sources

- Waveshare ESP32-C6-Touch-LCD-1.47 wiki: https://www.waveshare.com/wiki/ESP32-C6-Touch-LCD-1.47
- Waveshare ESP32-C6-Touch-LCD-1.47 docs: https://docs.waveshare.com/ESP32-C6-Touch-LCD-1.47
- Waveshare touch demo ZIP: https://files.waveshare.com/wiki/ESP32-C6-Touch-LCD-1.47/ESP32-C6-Touch-LCD-1.47-Demo.zip
- JD9853 datasheet: https://files.waveshare.com/wiki/common/Jd9853_datasheet.pdf
- Home Assistant community thread: https://community.home-assistant.io/t/esp32-c6-touch-lcd-1-47-jd9853-and-axs5106l-chip/936585
