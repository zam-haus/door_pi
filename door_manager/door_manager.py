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

import sys
from json import loads
from time import time, sleep
from signal import pause
from docopt import docopt
from decorated_paho_mqtt import GenericMqttEndpoint
from door_hal import DoorHal, DoorHalSim

config = loads(open('config.json').read())

class DoorManager(GenericMqttEndpoint):
    def __init__(self, hal, client_kwargs: dict, password_auth: dict, server_kwargs: dict, tls: bool):
        super().__init__(client_kwargs, password_auth, server_kwargs, tls)
        self.hal = hal
    
    @GenericMqttEndpoint.subscribe_decorator('door/%s/open' % config['door-id'], qos=2)
    def open(self, *, client, userdata, message):
        payload = loads(message.payload)
        assert 'not_after' in payload
        if time() < float(payload['not_after']):
            self.hal.setOutput('key', 1)
            sleep(0.5)
            self.hal.setOutput('key', 0)

if __name__ == '__main__':
    args = docopt(__doc__)
    
    if args['--simulate']:
        hal = DoorHalSim()
    else:
        hal = DoorHal()
        
    dm = DoorManager(
        hal,
        dict(transport='tcp'),
        dict(username=config['mqtt-user'], password=config['mqtt-pass']),
        dict(host=config['mqtt-host'], port=config['mqtt-port'], keepalive=10),
        False
    )
    dm.connect()
    pause()
    dm._mqttc.loop_stop()
    hal.cleanup()

