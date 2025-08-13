#!/usr/bin/env -S python3 -u

# This file is part of door_manager.
#
# door_manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# door_manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with door_manager.  If not, see <http://www.gnu.org/licenses/>.

''' door_manager

Usage:
  door_manager.py [-c FILE]
  door_manager.py [-c FILE] (-s | --simulate)

Options:
  -s --simulate     Use console I/O for HAL instead of RPi GPIOs
  -c FILE           Use this config file (json) instead of ./config.json
'''

import logging
from json import loads
from datetime import datetime
import sys
import asyncio
from time import time, sleep
from signal import signal, pause, SIGUSR1, SIGTERM

from docopt import docopt
from decorated_paho_mqtt import GenericMqttEndpoint

from door_hal import DoorHal, DoorHalUSB, DoorHalSim, HalConfig


FORMAT = '%(asctime)s %(processName)s#%(process)d @ %(module)s:%(name)s:%(funcName)s: %(message)s (%(filename)s:%(lineno)s)'
logging.basicConfig(format=FORMAT, handlers=[logging.StreamHandler()], level="INFO")
log = logging.getLogger(__name__)
mqtt_log = logging.getLogger(__name__ + ".mqtt")
mqtt_log.setLevel("DEBUG")


dormakabaMapping = {"in1": "sabotage", "in2": "entriegelt", \
    "in3": "verriegelt", "in4": "druecker", "in5": "steuerfalle", \
    "in6": "daueroffen"}

class DoorManager(GenericMqttEndpoint):
    def __init__(self, config, hal: DoorHal):
        # super().__init__ accesses self.door_id to build the endpoint.
        self.door_id=config['door-id']
        super().__init__(
            config['mqtt']['client_kwargs'],
            config['mqtt']['password_auth'],
            config['mqtt']['server_kwargs'],
            config['mqtt']['tls'])
        self.config = config
        self.hal = hal
        self.program = "closed"


    @GenericMqttEndpoint.subscribe_decorator(lambda self: f'door/{self.door_id}/+', qos=2)
    def msg(self, cmd, *, client, userdata, message):
        if cmd == "open":
            self.open(client, userdata, message)
        else:
            log.error("Unknown command: " + cmd)

    def open(self, client, userdata, message):
        log.info("Received request to open door")
        # noinspection PyBroadException
        try:
            payload = loads(message.payload)
            assert 'not_after' in payload
            not_after = payload['not_after']
            now = time()
            if now < float(not_after):
                self.open_door()
            else:
                time_str = datetime.utcfromtimestamp(not_after).strftime('%Y-%m-%dT%H:%M:%SZ')
                log.warning(f"Ignored delayed request, is only valid until {time_str}")
        except:
            log.error("Failed to parse request", exc_info=True)

    def _on_log(self, client, userdata, level, buf):
        mqtt_log.log(level, buf, extra=dict(client=client, userdata=userdata))
    def set_program(self, program):
        if program not in self.config["programs"]:
            log.error("Requested unknown door program: " + program)
        self.output_program(program)
        self.program = program
    def cycle_program(self, direction=1):
        """cycle forward (direction=1) or backward through the states (direction=-1)"""
        # when in a not-cycleable state, initialize to first
        if self.program not in self.config["cycle-programs"]:
            self.set_program(self.config["cycle-programs"][0])
            return
        ind = self.config["cycle-programs"].index(self.program)
        ind = (ind + direction) % len(self.config["cycle-programs"])
        self.set_program(self.config["cycle-programs"][ind])

    def open_door(self):
        for (pin, state) in self.config['open-gpios'].items():
            self.hal.impulse(pin, state, self.config['open-time'])

    def output_program(self, program):
        # turn everything off
        s = set()
        for gpios in self.config["programs"].values():
            s.update(gpios.keys())
        for gpio in s:
            val = "Z"
            if "inactive-outputs" in self.config:
                val = self.config["inactive-outputs"].get(gpio, self.config["inactive-outputs"].get("others","Z"))
            self.hal.setOutput(gpio, val)
        # enable the gpios for the program
        for (gpio, val) in self.config["programs"][program].items():
            self.hal.setOutput(gpio, val)


    async def cycle_loop(self):
        self.output_program(self.program)
        f = self.config["cycle-forward-input"]
        b = self.config["cycle-backward-input"]
        inputs = {f: '?', b: '?'}
        while asyncio.get_running_loop().is_running():
            event = self.hal.getEvent()
            if event is None:
                await asyncio.sleep(0.5)
                continue
            prev_inputs = inputs
            inputs = loads(event)

            if inputs[f] == "H" and not prev_inputs[f] == "H":
                self.cycle_program(1)
            if inputs[b] == "H" and not prev_inputs[b] == "H":
                self.cycle_program(-1)

    async def switch_loop(self):
        while asyncio.get_running_loop().is_running():
            val = self.hal.getInput(config['switch-input'])
            program = self.config['switch-programs'][val]
            self.set_program(program)
            await asyncio.sleep(1)


    async def presence_loop(self):
        gpioPresence = self.config["presence-gpio"]
        gpioPresenceInv = self.config["presence-gpio-inverted"]
        while asyncio.get_running_loop().is_running():
            try:
                presence = self.hal.getInput(gpioPresence)
                if gpioPresenceInv:
                    presence = not presence
                self.publish("door/+/presence", self.door_id, qos=2, retain=True, payload=str(presence).lower())
            except:
                log.error("Failed to retrieve or publish inputs", exc_info=True)
            await asyncio.sleep(5)


    async def dormakaba_open_loop(self):
        while asyncio.get_running_loop().is_running():
            try:
                isOpen = (not self.hal.getInput("in2")) or self.hal.getInput("in5")
                self.publish("door/+/is_open", self.door_id, qos=2, retain=True, payload=str(isOpen).lower())
                log.info("door status is_open=" + str(isOpen))

                for k in dormakabaMapping.keys():
                    name = dormakabaMapping[k]
                    if self.hal.exist(k):
                        val = self.hal.getInput(k)
                        self.publish("door/+/input_%s" % name, \
                            self.door_id, qos=2, retain=True, \
                                payload=str(val).lower())
            except:
                log.error("Failed to retrieve or publish inputs for dormakaba_open_loop", exc_info=True)
            await asyncio.sleep(5)

    async def usb_push_pinstatus(self):
        ev = self.hal.getEvent()
        if ev is not None:
            log.info("usb_push_instatus: got %s" % ev)
        await asyncio.sleep(0.2)

    def gong_handler(self, v):
        try:
            self.publish("door/+/gong", self.door_id, qos=2, retain=False)
        except:
            log.error("Failed publishing gong", exc_info=True)


    def start(self, loop):
        self.connect()
        if self.config.get("program-change", None) == "cycle":
            loop.create_task(self.cycle_loop())
        if self.config.get("program-change", None) == "switch":
            loop.create_task(self.switch_loop())

        if "input-type" in self.config:
            if self.config["input-type"] == "gildor":
                self.hal.registerInputCallback("gong", gong_handler, falling=False)
                loop.create_task(self.presence_loop())
            elif self.config["input-type"] == "dormakaba":
                loop.create_task(self.dormakaba_open_loop())
            elif self.config["input-type"] == "dormakaba_ed_100_250":
                loop.create_task(self.usb_push_pinstatus())

def main():
    args = docopt(__doc__)
    print(args)
    config_path = args["-c"]
    if config_path is None: config_path = "./config.json"
    with open(config_path) as fd:
        config = loads(fd.read())
    if "loglevel" in config:
        mqtt_log.setLevel(config["loglevel"])

    def sigterm_handler(signum, frame):
        dm._mqttc.loop_stop()
        hal.cleanup()
        sys.exit(0)

    def sigusr1_handler(signum, frame):
        dm.open_door()

    signal(SIGUSR1, sigusr1_handler)
    signal(SIGTERM, sigterm_handler)


    if config["gpio-config"] == "usb":
        halcfg = HalConfig()
        halcfg.usbpath = config["usb-path"]
    else:
        halcfg = HalConfig(config["gpio-config"])

    if args['--simulate']:
        log.warning("Running in simulation mode")
        hal = DoorHalSim(halcfg)
    else:
        if config["gpio-config"] == "usb":
            hal = DoorHalUSB(halcfg)
        else:
            hal = DoorHal(halcfg)

    loop = asyncio.new_event_loop()
    dm = DoorManager(config, hal)
    dm.start(loop)
    loop.run_forever()

if __name__ == '__main__':
    main()
