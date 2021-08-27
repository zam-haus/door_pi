
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

inputs = { # mapping to GPIO ids
    'gong': 22,
    'light': 23,
    'sw1': 24,
    'sw2': 25,
    'sw3': 26,
}

outputs = { # mapping to GPIO ids
    'led': 21,
    'exit': 7,
    'night': 8,
    'emerg': 9,
    'key': 10,
    'out1': 11
}

class DoorHal:
    def __init__(self):
        import RPi.GPIO as gpio
        self.gpio = gpio
        self.gpio.setmode(gpio.BCM)
        self.gpio.setwarnings(False)
        
        for i in inputs:
            self.gpio.setup(inputs[i], self.gpio.IN)
        for o in outputs:
            self.gpio.setup(outputs[o], self.gpio.OUT, initial=0)
    
    def setOutput(self, name, val):
        assert (name in outputs) and (val in (True,False))
        self.gpio.output(outputs[name], val)
        
    def getInput(self, name):
        assert name in inputs
        return self.gpio.input(inputs[name]) == self.gpio.HIGH
        
    def registerInputCallback(self, name, callback, falling=True):
        assert name in inputs
        self.gpio.add_event_detect(
            self.gpio.FALLING if falling else self.gpio.RISING,
            callback=callback
        )

if __name__ == '__main__':
    from argparse import ArgumentParser
    from time import sleep
    
    p = ArgumentParser(description='Test DoorHal')
    p.add_argument('name', help='name of gpio')
    p.add_argument('-i', dest='input', action='store_true', help='get input')
    p.add_argument('-o', dest='output', type=int, metavar='value')
    p.add_argument('-t', dest='time', type=int, metavar='millisecs', default=0)
    args = p.parse_args()

    hal = DoorHal()
    
    if args.input:
        print('input', args.name, 'is', hal.getInput(args.name))
    elif args.output is not None:
        val = args.output == 1
        print('output', val, 'on', args.name)
        hal.setOutput(args.name, val)
        if args.time > 0:
            sleep(args.time/1000)
            hal.setOutput(args.name, False)
            hal.setOutput(args.name, val)
            print('output', False, 'on', args.name)
    
    
