#!/usr/bin/env -S uv run
''' run_simulation

Runs door_manager exactly as it would run against real hardware -- including
connecting to MQTT per the given config -- but backs the GPIO/serial HAL with
DoorHalUsbSimulatedUc, which runs the uc firmware's Logic in-process and talks
to it over a pair of os.pipe()s instead of a real USB-serial microcontroller.

Usage:
  run_simulation.py [-c FILE] [--no-random-events] [--button-min=SECONDS]
                     [--button-max=SECONDS] [--malfunction-rate=RATE]
                     [--sensor-check-interval=SECONDS] [--pulse-hold=SECONDS]

Options:
  -c FILE                        Config file for door_manager
                                  [default: door_manager/config.json.example-usb]
  --no-random-events             Disable the simulated button presses and door sensor
  --button-min=SECONDS           Minimum delay between simulated button presses [default: 1.5]
  --button-max=SECONDS           Maximum delay between simulated button presses [default: 4.0]
  --malfunction-rate=RATE        Probability (0-1) the door sensor fails to report an open [default: 0.2]
  --sensor-check-interval=SECONDS  How often the door sensor checks for an open impulse [default: 0.05]
  --pulse-hold=SECONDS           How long a simulated button press is held [default: 0.3]
'''

import asyncio
import random
import sys
import threading
import time
from json import loads
from pathlib import Path

# The script's own directory (this repo's root) is auto-prepended to sys.path
# and contains a door_manager/ subdirectory, which shadows the installed
# door_manager module as an empty namespace package. Drop it so the editable
# install (from the workspace's [tool.uv.sources]) is found instead.
_here = str(Path(__file__).parent)
if _here in sys.path:
    sys.path.remove(_here)

from docopt import docopt

from door_hal import DoorHalUsbSimulatedUc
from door_manager import DoorManager

DEFAULT_CONFIG = Path(__file__).parent / "door_manager" / "config.json.example-usb"

# "L"/"H"/"Z" encode as two digital lines each, per uc/logic.py's Logic.get_input:
# a and not b -> L, b and not a -> H, a and b -> Z. Buttons rest at Z and pulse H.
INPUT_LEVELS = {"L": (True, False), "H": (False, True), "Z": (True, True)}
RESTING_LEVEL = "Z"

# Mode-switch buttons, matching config.json.example-usb's cycle-forward/backward-input.
BUTTON_INPUTS = ["in1", "in2"]
# Door-position sensor input, made up for this simulation (not read by door_manager
# under the "dormakaba_ed_100_250" input-type, but it exercises the uc firmware's
# interrupt-generation path and is visible via mosquitto_sub on door/# events).
DOOR_SENSOR_INPUT = "in4"
DOOR_OUTPUT = "out3"  # matches open-gpios in config.json.example-usb


def set_input(hal, name, level):
    in_a, in_b = hal.logic.inputs[name]
    in_a.v, in_b.v = INPUT_LEVELS[level]


def pulse_input(hal, name, hold, level="H"):
    set_input(hal, name, level)
    time.sleep(hold)
    set_input(hal, name, RESTING_LEVEL)


def wait_for_logic_ready(hal):
    while not hal.logic.inputs:
        time.sleep(0.05)


def random_button_presses(hal, buttons, interval_range, pulse_hold):
    """Simulate someone randomly pressing the mode-switch buttons."""
    while True:
        time.sleep(random.uniform(*interval_range))
        name = random.choice(buttons)
        print(f"SIM: button {name} pressed")
        pulse_input(hal, name, pulse_hold)


def door_sensor_responder(hal, malfunction_rate, check_interval):
    """React to an open impulse like a real door position sensor would --
    report the door open shortly after, and closed again once the impulse
    resets -- except sometimes (malfunction_rate) the sensor just doesn't
    respond, to exercise door_manager's handling of a flaky sensor."""
    was_active = False
    while True:
        time.sleep(check_interval)
        active = DOOR_OUTPUT in hal.logic.auto_off
        if active and not was_active:
            if random.random() < malfunction_rate:
                print("SIM: MALFUNCTION -- door sensor failed to report open")
            else:
                print("SIM: door sensor reports open")
                set_input(hal, DOOR_SENSOR_INPUT, "H")
        elif was_active and not active:
            print("SIM: door sensor reports closed")
            set_input(hal, DOOR_SENSOR_INPUT, RESTING_LEVEL)
        was_active = active


def start_random_events(hal, *, button_interval, malfunction_rate, sensor_check_interval, pulse_hold):
    wait_for_logic_ready(hal)
    for name in hal.logic.inputs:
        set_input(hal, name, RESTING_LEVEL)
    buttons = [n for n in BUTTON_INPUTS if n in hal.logic.inputs]
    if buttons:
        threading.Thread(
            target=random_button_presses, args=(hal, buttons, button_interval, pulse_hold), daemon=True
        ).start()
    if DOOR_SENSOR_INPUT in hal.logic.inputs:
        threading.Thread(
            target=door_sensor_responder, args=(hal, malfunction_rate, sensor_check_interval), daemon=True
        ).start()


def main():
    args = docopt(__doc__)
    config_path = args["-c"] or DEFAULT_CONFIG
    with open(config_path) as fd:
        config = loads(fd.read())

    hal = DoorHalUsbSimulatedUc()
    if not args["--no-random-events"]:
        start_random_events(
            hal,
            button_interval=(float(args["--button-min"]), float(args["--button-max"])),
            malfunction_rate=float(args["--malfunction-rate"]),
            sensor_check_interval=float(args["--sensor-check-interval"]),
            pulse_hold=float(args["--pulse-hold"]),
        )

    loop = asyncio.new_event_loop()
    dm = DoorManager(config, hal)
    dm.start(loop)
    loop.run_forever()


if __name__ == '__main__':
    main()
