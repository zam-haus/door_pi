# door_pi

Controls electric door locks/openers via GPIO or a USB-serial microcontroller,
and exposes them over MQTT (see `door_manager/`). `uc/` is the firmware that
runs on the microcontroller for the USB HAL variant.

## Running the simulation

`run_simulation.py` runs the real `door_manager` (including a real MQTT
connection) against an in-process simulated microcontroller
(`DoorHalUsbSimulatedUc` in `door_manager/door_hal.py`), so you can exercise
the whole stack without any hardware attached.

1. Install both `door_manager` and `uc` as editable packages into the project
   venv (only needed once, or after changing dependencies):

   ```sh
   uv sync
   ```

2. Start a local MQTT broker with the compose file in `testing/`:

   ```sh
   (cd testing; podman compose up -d --build)   # or: docker compose up -d --build
   ```

   This builds `testing/mosquitto/Dockerfile` (based on `eclipse-mosquitto`,
   with the config and password file baked in — see below) and starts it on
   `127.0.0.1:8001`, with auth for user/pass `test`/`test` — matching
   `door_manager/config.json.example-usb`, which the simulation uses by
   default.

   > If you have the `mosquitto` package installed on the host, its AppArmor
   > profile attaches by executable path (`/usr/sbin/mosquitto`), which
   > confines *this* container's mosquitto too on exec and blocks it from
   > reading its own config — regardless of container boundaries or
   > `--security-opt apparmor=unconfined`. `testing/mosquitto/Dockerfile`
   > works around this by copying the binary to a different path before
   > running it, so the host profile's attachment never matches. That's also
   > why the config/password file are baked into the image via `COPY`
   > rather than bind-mounted: the same host profile only allows the
   > mosquitto binary to read `/etc/mosquitto/**`.

3. Run the simulation:

   ```sh
   uv run run_simulation.py
   ```

   Pass `-c FILE` to point it at a different `door_manager` config.

   By default this also drives random simulated events, so you don't have
   to trigger everything by hand: the mode-switch buttons (`in1`/`in2`,
   `cycle-forward-input`/`cycle-backward-input` in the config) get pressed
   at random, and a simulated door-position sensor reacts to open impulses
   on `out3` -- except sometimes (by default 20% of the time) it doesn't,
   to exercise a flaky-sensor path. Every simulated event is logged with a
   `SIM:` prefix. Tune or disable this with:

   ```
   --no-random-events               turn it off entirely
   --button-min=SECONDS              min delay between button presses [default: 1.5]
   --button-max=SECONDS              max delay between button presses [default: 4.0]
   --pulse-hold=SECONDS               how long a button press is held [default: 0.3]
   --malfunction-rate=RATE            chance (0-1) the door sensor misses an open [default: 0.2]
   --sensor-check-interval=SECONDS   how often the sensor polls for an open impulse [default: 0.05]
   ```

4. When done, stop the broker:

   ```sh
   cd testing
   podman compose down   # or: docker compose down
   ```

## Sending MQTT messages

The `eclipse-mosquitto` image bundles the `mosquitto_pub`/`mosquitto_sub`
CLI tools, so you don't need to install an MQTT client locally — just run
them inside the broker container via `podman compose exec` (from the
`testing/` directory, with the broker already up). Use `localhost`/`1883`
(the container's own view of the broker), not the host-mapped `8001`.

Watch everything the door publishes and any commands sent to it:

```sh
podman compose exec mosquitto mosquitto_sub -h localhost -p 1883 \
  -u test -P test -t 'door/#' -v
```

Send an open command (door-id `1234`, matching
`door_manager/config.json.example-usb`) — `not_after` is a Unix timestamp
the request must arrive before:

```sh
(cd testing; podman compose exec mosquitto mosquitto_pub -h localhost -p 1883 \
  -u test -P test -t door/1234/open -m "{\"not_after\": $(($(date +%s) + 60))}")
```

With the simulation running, this should trigger `DoorManager.open_door()`
and impulse the configured output GPIOs on the simulated microcontroller.
