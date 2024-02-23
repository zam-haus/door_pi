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
  door_manager.py
  door_manager.py (-s | --simulate)

Options:
  -s --simulate     Use console I/O for HAL instead of RPi GPIOs
'''

import logging
from json import loads
from datetime import datetime

with open('config.json') as fd:
    config = loads(fd.read())

FORMAT = '%(asctime)s %(processName)s#%(process)d @ %(module)s:%(name)s:%(funcName)s: %(message)s (%(filename)s:%(lineno)s)'
logging.basicConfig(format=FORMAT, handlers=[logging.StreamHandler()], level="INFO")
log = logging.getLogger(__name__)
mqtt_log = logging.getLogger(__name__ + ".mqtt")
if "loglevel" in config:
    mqtt_log.setLevel(config["loglevel"])    
else:
    mqtt_log.setLevel("DEBUG")

import sys
import asyncio
from time import time, sleep
from signal import signal, pause, SIGUSR1, SIGTERM
from docopt import docopt
from decorated_paho_mqtt import GenericMqttEndpoint
from door_hal import DoorHal, DoorHalUSB, DoorHalSim, HalConfig

def open_door():
    hal.impulse(config['open-gpio'], config['open-time'])

def set_day(en):
    if config['input-type'] == "dormakaba_ed_100_250":
        hal.setOutput(config['day-gpio'], en)
        hal.setOutput(config['night-gpio'], not en)
    else:
        hal.setOutput(config['day-gpio'], en)

class DoorManager(GenericMqttEndpoint):
    def __init__(self, client_kwargs: dict, password_auth: dict, server_kwargs: dict, tls: bool):
        super().__init__(client_kwargs, password_auth, server_kwargs, tls)

    @GenericMqttEndpoint.subscribe_decorator('door/%s/+' % config['door-id'], qos=2)
    def msg(self, cmd, *, client, userdata, message):
        if cmd == "open":
            self.open(client, userdata, message)
        elif cmd == "day":
            self.day(client, userdata, message)
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
                open_door()
            else:
                time_str = datetime.utcfromtimestamp(not_after).strftime('%Y-%m-%dT%H:%M:%SZ')
                log.warning(f"Ignored delayed request, is only valid until {time_str}")
        except:
            log.error("Failed to parse request", exc_info=True)

    def day(self, client, userdata, message):
        log.info("Received request to set day mode")
        # noinspection PyBroadException
        try:
            payload = loads(message.payload)
            assert 'enabled' in payload
            set_day(payload['enabled'])
        except:
            log.error("Failed to parse request", exc_info=True)

    def _on_log(self, client, userdata, level, buf):
        mqtt_log.log(level, buf, extra=dict(client=client, userdata=userdata))

async def presence_loop(doorman: DoorManager, hal: DoorHal):
    gpioPresence = config["presence-gpio"]
    gpioPresenceInv = config["presence-gpio-inverted"]
    while asyncio.get_event_loop().is_running():
        try:
            presence = hal.getInput(gpioPresence)
            if gpioPresenceInv:
                presence = not presence
            doorman.publish("door/+/presence", config["door-id"], qos=2, retain=True, payload=str(presence).lower())
        except:
            log.error("Failed to retrieve or publish inputs", exc_info=True)
        await asyncio.sleep(5)

dormakabaMapping = {"in1": "sabotage", "in2": "entriegelt", \
    "in3": "verriegelt", "in4": "druecker", "in5": "steuerfalle", \
    "in6": "daueroffen"}

async def dormakaba_open_loop(doorman: DoorManager, hal: DoorHal):
    while asyncio.get_event_loop().is_running():
        try:
            isOpen = (not hal.getInput("in2")) or hal.getInput("in5")
            doorman.publish("door/+/is_open", config["door-id"], qos=2, retain=True, payload=str(isOpen).lower())
            log.info("door status is_open=" + str(isOpen))

            for k in dormakabaMapping.keys():
                name = dormakabaMapping[k]
                if hal.exist(k):
                    val = hal.getInput(k)
                    doorman.publish("door/+/input_%s" % name, \
                        config["door-id"], qos=2, retain=True, \
                            payload=str(val).lower())
        except:
            log.error("Failed to retrieve or publish inputs for dormakaba_open_loop", exc_info=True)
        await asyncio.sleep(5)

async def usb_permaopen_loop(doorman: DoorManager, hal: DoorHal):
    last = None
    while asyncio.get_event_loop().is_running():
        po = hal.getInput(config['permaopen-input'])
        if po == 'H':
            set_day(True)
            if po != last:
                log.info("setting day")
        else:
            set_day(False)
            if po != last:
                log.info("setting night")
        last = po
        await asyncio.sleep(5)

async def usb_push_pinstatus(doorman: DoorManager, hal: DoorHal):
    ev = hal.getEvent()
    if ev is not None:
        log.info("usb_push_instatus: got %s" % ev)
    await asyncio.sleep(0.2)

def gong_handler(v):
    try:
        dm.publish("door/+/gong", config["door-id"], qos=2, retain=False)
    except:
        log.error("Failed publishing gong", exc_info=True)

def sigterm_handler(signum, frame):
    dm._mqttc.loop_stop()
    hal.cleanup()
    sys.exit(0)

def sigusr1_handler(signum, frame):
    open_door()

if __name__ == '__main__':
    args = docopt(__doc__)
    loop = asyncio.get_event_loop()

    signal(SIGUSR1, sigusr1_handler)
    signal(SIGTERM, sigterm_handler)

    dm = DoorManager(
        config['mqtt']['client_kwargs'],
        config['mqtt']['password_auth'],
        config['mqtt']['server_kwargs'],
        config['mqtt']['tls']
    )
    dm.connect()

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

    if "input-type" in config:
        if config["input-type"] == "gildor":
            hal.registerInputCallback("gong", gong_handler, falling=False)
            loop.create_task(presence_loop(dm, hal))
        elif config["input-type"] == "dormakaba":
            loop.create_task(dormakaba_open_loop(dm, hal))
        elif config["input-type"] == "dormakaba_ed_100_250":
            set_day(False)
            loop.create_task(usb_permaopen_loop(dm, hal))
            loop.create_task(usb_push_pinstatus(dm, hal))

    loop.run_forever()
