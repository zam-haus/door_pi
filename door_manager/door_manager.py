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
from datetime import datetime

FORMAT = '%(asctime)s %(processName)s#%(process)d @ %(module)s:%(name)s:%(funcName)s: %(message)s (%(filename)s:%(lineno)s)'
logging.basicConfig(format=FORMAT, handlers=[logging.StreamHandler()], level="INFO")
log = logging.getLogger(__name__)
mqtt_log = logging.getLogger(__name__ + ".mqtt")
mqtt_log.setLevel("DEBUG")

import sys
from json import loads
from time import time, sleep
from signal import pause
from docopt import docopt
from decorated_paho_mqtt import GenericMqttEndpoint
from door_hal import DoorHal, DoorHalSim

with open('config.json') as fd:
    config = loads(fd.read())


class DoorManager(GenericMqttEndpoint):
    def __init__(self, hal, client_kwargs: dict, password_auth: dict, server_kwargs: dict, tls: bool):
        super().__init__(client_kwargs, password_auth, server_kwargs, tls)
        self.hal = hal

    @GenericMqttEndpoint.subscribe_decorator('door/%s/open' % config['door-id'], qos=2)
    def open(self, *, client, userdata, message):
        log.info("Received request to open door")
        # noinspection PyBroadException
        try:
            payload = loads(message.payload)
            assert 'not_after' in payload
            not_after = payload['not_after']
            now = time()
            if now < float(not_after):
                self.hal.setOutput('key', 1)
                sleep(0.5)
                self.hal.setOutput('key', 0)
            else:
                time_str = datetime.utcfromtimestamp(not_after).strftime('%Y-%m-%dT%H:%M:%SZ')
                log.warning(f"Ignored delayed request, is only valid until {time_str}")
        except:
            log.error("Failed to parse request", exc_info=True)

    def _on_log(self, client, userdata, level, buf):
        mqtt_log.log(level, buf, extra=dict(client=client, userdata=userdata))


if __name__ == '__main__':
    args = docopt(__doc__)

    if args['--simulate']:
        log.warning("Running in simulation mode")
        hal = DoorHalSim()
    else:
        hal = DoorHal()

    dm = DoorManager(
        hal,
        config['mqtt']['client_kwargs'],
        config['mqtt']['password_auth'],
        config['mqtt']['server_kwargs'],
        config['mqtt']['tls']
    )
    dm.connect()
    pause()
    dm._mqttc.loop_stop()
    hal.cleanup()

