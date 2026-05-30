# Session Learnings

## Constitution

- Write durable research findings, test outcomes, and hardware-specific lessons to markdown before ending an investigation. Use `README.md` for user-facing project notes, `TROUBLESHOOTING.md` for issue-specific investigations, and `AGENTS.md` for agent/operator memory.
- Keep deployment commands exact and include flags required for non-interactive completion.
- Preserve failed attempts as findings when they narrow the problem space.

## ESPHome terminal behavior

- `run_in_terminal` is not returning command output directly in this workspace, even for simple commands like `printf`.
- Use `terminal_last_command` to read the actual output and exit code after `esphome compile` / `esphome run` when using terminal tools.
- In this harness, direct shell deploys work with `.venv/bin/esphome`.

## OTA deploy procedure

- Always deploy OTA with the project virtualenv binary and `--no-logs` so the command terminates after upload:

```sh
.venv/bin/esphome run esphome.yml --device 10.229.5.40 --no-logs
```

- Treat this as the successful deploy signature:

```text
INFO OTA successful
INFO Successfully uploaded program.
```

- If logs are needed, run them separately after deployment, however note the logs are tailed so the process will need Ctrl-C to exit:

```sh
.venv/bin/esphome logs esphome.yml --device 10.229.5.40
```

- Do not replace `.venv/bin/esphome` with bare `esphome`; bare `esphome` may not be on PATH in this workspace.

## OTA validation behavior

- If power is removed too soon after OTA, ESPHome/ESP-IDF can roll back to the previous OTA partition.
- Do not judge cold-boot results until logs show the new compile time and the boot has been marked successful.
- `safe_mode.boot_is_good_after` is set to `10s` in `esphome.yml` to shorten the post-OTA validation window.
- After OTA, wait at least 10-15 seconds before removing power for a cold-boot test.

## Hardware summary

- The target board is Waveshare ESP32-C6-Touch-LCD-1.47.
- The target display chip is JD9853.
- The target touch chip is AXS5106L.
- Do not switch this config to the ESPHome `WAVESHARE-ESP32-C6-LCD-1.47` preset; that preset targets the non-touch ST7789 variant.
- Factory BSP pins from Waveshare's touch demo:
  - SPI SCLK: GPIO1
  - SPI MOSI: GPIO2
  - LCD CS: GPIO14
  - LCD DC: GPIO15
  - LCD RST: GPIO22
  - LCD BL: GPIO23
  - Touch I2C SDA: GPIO18
  - Touch I2C SCL: GPIO19
  - Touch INT: GPIO21
  - Touch RST: GPIO20
- Disket Mono fonts compile successfully:
  - `Disket-Mono-Bold.ttf` for `font_header` and `font_data`
  - `Disket-Mono-Regular.ttf` for `font_sub`
- Power optimization deployed 2026-05-30:
  - `cpu_frequency: 80MHz`
  - `wifi.power_save_mode: HIGH`
  - passive BLE scanning with `interval: 1100ms`, `window: 30ms`, `duration: 5s`
  - `display.data_rate: 40MHz`
  - `display.update_interval: 30s`
  - status LED off after boot
  - backlight wakes to 35% on boot/touch and turns off after 30s
  - touch uses external `github://widget/esphome-components` `axs5106` component

## Documentation map

- User-facing setup and deploy notes: `README.md`
- Display troubleshooting archive: `TROUBLESHOOTING.md`
- Agent/operator memory and repo workflow notes: `AGENTS.md`

## Web tooling note

- `web_search` originally failed because `BRAVE_SEARCH_API_KEY` was not set.
- After configuring `BRAVE_SEARCH_API_KEY`, Brave search worked.
- `web_fetch` and direct `curl` were also used to retrieve Waveshare wiki/demo resources.
