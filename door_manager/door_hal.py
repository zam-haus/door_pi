
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

from os import kill, getpid
from signal import SIGTERM
from time import sleep

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
        print('output', val, 'on', name)
        self.gpio.output(outputs[name], val)
        
    def getInput(self, name):
        assert name in inputs
        return self.gpio.input(inputs[name]) == self.gpio.HIGH
        
    def registerInputCallback(self, name, callback, falling=True):
        assert name in inputs
        self.gpio.add_event_detect(inputs[name],
            self.gpio.FALLING if falling else self.gpio.RISING,
            callback=callback
        )

    def cleanup(self):
        self.gpio.cleanup()
        
class DoorHalSim:
    def __init__(self):
        import readline
        from threading import Thread        
        self.worker = Thread(target=self.__inputLoop)
        self.worker.start()
        self.inputStates = {}
        self.inputCallbacksFalling = {}
        self.inputCallbacksRising = {}
        for i in inputs:
            self.inputStates[i] = 1
            self.inputCallbacksFalling[i] = []
            self.inputCallbacksRising[i] = []
        
    def __inputLoop(self):
        try:
            while True:
                inp = input("> ")
                if inp in inputs:
                    self.inputStates[inp] = 0
                    for cb in self.inputCallbacksFalling[inp]:
                        cb(0)
                    sleep(0.5)
                    self.inputStates[inp] = 1
                    for cb in self.inputCallbacksRising[inp]:
                        cb(1)
        except EOFError:
            print()
            kill(getpid(), SIGTERM)
            return
        
    def setOutput(self, name, val):
        assert (name in outputs) and (val in (True,False))
        print("output", name, "=", val)

    def getInput(self, name):
        assert name in inputs
        return self.inputStates[name]

    def registerInputCallback(self, name, callback, falling=True):
        assert name in inputs
        if falling:
            self.inputCallbacksFalling[name].append(callback)
        else:
            self.inputCallbacksRising[name].append(callback)

    def cleanup(self):
        pass

if __name__ == '__main__':
    from argparse import ArgumentParser
    
    p = ArgumentParser(description='Test DoorHal')
    p.add_argument('name', help='name of gpio')
    p.add_argument('-s', dest='sim', action='store_true', help='simulation mode')
    p.add_argument('-i', dest='input', action='store_true', help='get input')
    p.add_argument('-o', dest='output', type=int, metavar='value')
    p.add_argument('-t', dest='time', type=int, metavar='millisecs', default=500)
    args = p.parse_args()

    if args.sim:
        hal = DoorHalSim()
    else:
        hal = DoorHal()
    
    if args.input:
        print('input', args.name, 'is', hal.getInput(args.name))
        #hal.registerInputCallback(args.name, 
        #    lambda v: print("input", args.name, "falling"), falling=True)
        #hal.registerInputCallback(args.name, 
        #    lambda v: print("input", args.name, "rising"), falling=False)
    elif args.output is not None:
        val = args.output == 1
        hal.setOutput(args.name, val)
        if args.time > 0:
            sleep(args.time/1000)
            hal.setOutput(args.name, False)
    
    
