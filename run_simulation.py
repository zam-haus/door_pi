#!/usr/bin/env -S uv run
''' run_simulation

Runs door_manager exactly as it would run against real hardware -- including
connecting to MQTT per the given config -- but backs the GPIO/serial HAL with
DoorHalUsbSimulatedUc, which runs the uc firmware's Logic in-process and talks
to it over a pair of os.pipe()s instead of a real USB-serial microcontroller.

Usage:
  run_simulation.py [-c FILE]

Options:
  -c FILE  Config file for door_manager [default: door_manager/config.json.example-usb]
'''

import asyncio
import sys
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


def main():
    args = docopt(__doc__)
    config_path = args["-c"] or DEFAULT_CONFIG
    with open(config_path) as fd:
        config = loads(fd.read())

    hal = DoorHalUsbSimulatedUc()

    loop = asyncio.new_event_loop()
    dm = DoorManager(config, hal)
    dm.start(loop)
    loop.run_forever()


if __name__ == '__main__':
    main()
