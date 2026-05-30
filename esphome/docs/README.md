# ESP32-C6 Touch LCD Proxy

ESPHome configuration for a Waveshare ESP32-C6 Touch LCD 1.47 board running a BLE proxy and small status display.

All commands below assume you are running from the repository root.

## Repository layout

- `src/esphome.yml`: main ESPHome configuration
- `src/typefaces/`: bundled font assets referenced by the display config
- `docs/README.md`: operator notes for setup, validation, build, and deployment
- `docs/TROUBLESHOOTING.md`: display investigation history and known caveats
- `firmware/waveshare-official/`: vendor reference firmware artifact

## Prerequisites

- Use the project virtualenv at `.venv/`. The current known-good environment validates with ESPHome 2026.5.1.
- Ensure `git` is installed. ESPHome fetches the external `axs5106` touch component from `github://widget/esphome-components` during config/build.
- Install the pinned CLI dependency with `.venv/bin/pip install -r esphome/requirements.txt` if you are running ESPHome commands directly outside the Ansible workflow.
- Create a local `src/secrets.yaml` before validating, compiling, or deploying. This file is git-ignored.

Example `src/secrets.yaml`:

```yaml
wifi_ssid: "your-ssid"
wifi_password: "your-password"
```

If you provision secrets from Ansible or NixOS, render those same keys into `src/secrets.yaml` before running ESPHome.

## Ansible workflow

The repository now provides an `esphome` Ansible tag for the validated local workflow. The role is owned through the `habiki` inventory path, but phase 1 execution stays on the controller via `delegate_to: localhost` so it can reuse this checked-in project and `.venv` toolchain.

The role also bootstraps the pinned ESPHome CLI from `esphome/requirements.txt` into the repo `.venv` before it validates, compiles, or deploys.

Validate the configuration and render `src/secrets.yaml` from vault-backed variables:

```sh
./scripts/play.sh --limit habiki --tags esphome
```

Compile firmware through the same role:

```sh
./scripts/play.sh --limit habiki --tags esphome --extra-vars esphome_action=compile
```

Deploy OTA through the same role:

```sh
./scripts/play.sh --limit habiki --tags esphome --extra-vars esphome_action=deploy
```

## Validate and build

Validate the config and secret resolution:

```sh
.venv/bin/esphome config src/esphome.yml
```

Compile the firmware locally:

```sh
.venv/bin/esphome compile src/esphome.yml
```

## Deploy OTA

Deploy over the network with the project virtualenv. Use `--no-logs` so the command exits after the OTA upload instead of attaching to device logs:

```sh
.venv/bin/esphome run src/esphome.yml --device 10.229.5.40 --no-logs
```

Expected successful ending:

```text
INFO OTA successful
INFO Successfully uploaded program.
```

After OTA, wait at least 10-15 seconds before removing power for a cold-boot test. ESPHome safe mode/OTA rollback can revert to the previous partition if the device is power-cycled before the boot is marked successful. This project sets `safe_mode.boot_is_good_after: 10s` to shorten that validation window.

If you need logs after deployment, run a separate logs command instead of dropping `--no-logs` from deploy:

```sh
.venv/bin/esphome logs src/esphome.yml --device 10.229.5.40
```

## Runtime expectations

- The display config in `src/esphome.yml` renders two Home Assistant entities: `sensor.thermo_hygrometer_outside_shed_temperature` and `sensor.thermo_hygrometer_outside_shed_humidity`.
- If those entities are unavailable, the display still boots and shows `NO HA TEMP` / `NO HA HUM` instead of values.
- The current display path relies on manual `MADCTL` handling in `mipi_spi`. If you move away from the known-good ESPHome environment, re-check OTA and cold-boot orientation.

## Hardware

- Board: Waveshare ESP32-C6-Touch-LCD-1.47
- Display controller: JD9853
- Touch controller: AXS5106L
- Resolution: 172 × 320
- Factory BSP pins confirmed from Waveshare demo:
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

## Heat/power behavior

The configuration reduces heat by running the ESP32-C6 at 80 MHz, using passive BLE scanning, reducing display SPI/update activity, and dimming the LCD backlight to 35% on boot or touch. The status LED is turned off after boot. The display refreshes every 30 seconds, and the backlight turns off after 30 seconds of no touch; touch wakes it and restarts the timer.

## Troubleshooting

Display-specific investigation notes, tested register values, and source links are archived in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
