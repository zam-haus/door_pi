
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
from json import load, loads, JSONDecodeError
from queue import Queue
from threading import Lock

class HalConfig:
    def __init__(self, fname=None):
        if fname is None:
            self.inputs = {}
            self.outputs = {}
        else:
            with open(fname, "r") as f:
                cfgGpio = load(f)
            self.inputs = cfgGpio["inputs"]
            self.outputs = cfgGpio["outputs"]

class DoorHal:
    def __init__(self, cfg):
        import RPi.GPIO as gpio
        self.cfg = cfg
        self.gpio = gpio
        self.gpio.setmode(gpio.BCM)
        self.gpio.setwarnings(False)
        
        for i in self.cfg.inputs:
            self.gpio.setup(self.cfg.inputs[i], self.gpio.IN)
        for o in self.cfg.outputs:
            self.gpio.setup(self.cfg.outputs[o], self.gpio.OUT, initial=0)
        self.outputStates = {}

    def exist(self, name):
        return name in self.cfg.inputs

    def impulse(self, name, val, duration=2.0):
        reset=self.outputStates.get(name, "Z")
        setOutput(name, val)
        sleep(duration)
        setOutput(name, reset)
    
    def setOutput(self, name, val):
        assert val in "HL"
        assert (name in self.cfg.outputs)
        print('output', val, 'on', name)
        self.gpio.output(self.cfg.outputs[name], {"H":True, "L":False}[val])
        self.outputStates[name]=val
        
    def getInput(self, name):
        assert name in self.cfg.inputs
        return self.gpio.input(self.cfg.inputs[name]) == self.gpio.HIGH
        
    def registerInputCallback(self, name, callback, falling=True):
        assert name in self.cfg.inputs
        self.gpio.add_event_detect(self.cfg.inputs[name],
            self.gpio.FALLING if falling else self.gpio.RISING,
            callback=callback
        )

    def cleanup(self):
        self.gpio.cleanup()

class DoorHalUSB:
    def __init__(self, cfg):
        import serial
        self.cfg = cfg
        self.s = serial.Serial(cfg.usbpath, timeout=10)
        self.slock = Lock()
        self.eventq = Queue()

        iv = self.getInputAll()
        for i in iv:
            self.cfg.inputs[i] = i

    def __readline(self, event_only=False):
        l = self.s.readline().strip().decode()
        while l.startswith("!"):
            self.eventq.put(l)
            if event_only: return
            l = self.s.readline().strip().decode()
        return l

    def __checkok(self):
        l = self.__readline()
        assert l == "ok"

    def getEvent(self):
        with self.slock:
            if self.s.in_waiting > 0:
                self.__readline(event_only=True)
            if not self.eventq.empty():
                return self.eventq.get()[1:]

    def exist(self, name):
        return name in self.cfg.inputs
    
    def impulse(self, name, val, duration=None):
        assert val in "HLZ"
        with self.slock:
            cmd = "*impulse {name} {val}".format(name=name, val=val)
            if duration is not None:
                cmd += " {}".format(duration)
            self.s.write((cmd + "\r").encode())
            self.__checkok()
        
    def getInput(self, name):
        iv = self.getInputAll()
        assert name in iv
        return iv[name]
    
    def getInputAll(self):
        with self.slock:
            self.s.write("*read\r".encode())
            try:
                d = self.__readline()
                j = loads(d)
                return j
            except JSONDecodeError:
                print("JSONDecodeError")
            except TimeoutError:
                print("TimeoutError")
            except Exception as e:
                print("Exception:", str(e))

    def setOutput(self, name, val):
        assert val in "HLZ"
        with self.slock:
            self.s.write(("*set " + name + " " + val + "\r").encode())
            self.__checkok()
        
    def registerInputCallback(self, name, callback, falling=True):
        pass

    def cleanup(self):
        pass
   
class DoorHalSim:
    def __init__(self, cfg):
        self.cfg = cfg

        import readline
        from threading import Thread        
        self.worker = Thread(target=self.__inputLoop)
        self.worker.start()
        self.outputStates = {}
        self.inputStates = {}
        self.inputCallbacksFalling = {}
        self.inputCallbacksRising = {}
        for i in self.cfg.inputs:
            self.inputStates[i] = 1
            self.inputCallbacksFalling[i] = []
            self.inputCallbacksRising[i] = []
        
    def __inputLoop(self):
        try:
            while True:
                inp = input("> ")
                if inp in self.cfg.inputs:
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

    def exist(self, name):
        return name in self.cfg.inputs
      
    def impulse(self, name, val, duration=2.0):
        reset=self.outputStates.get(name, "Z")
        setOutput(name, val)
        sleep(duration)
        setOutput(name, reset)
      
    def setOutput(self, name, val):
        assert (name in self.cfg.outputs) and (val in "HLZ")
        self.outputStates[name]=val
        print("output", name, "=", val)

    def getInput(self, name):
        assert name in self.cfg.inputs
        return self.inputStates[name]

    def registerInputCallback(self, name, callback, falling=True):
        assert name in self.cfg.inputs
        if falling:
            self.inputCallbacksFalling[name].append(callback)
        else:
            self.inputCallbacksRising[name].append(callback)

    def cleanup(self):
        pass

if __name__ == '__main__':
    from argparse import ArgumentParser
    
    p = ArgumentParser(description='Test DoorHal')
    p.add_argument('confFile', help='gpio configuration file')
    p.add_argument('name', help='name of gpio')
    p.add_argument('-s', dest='sim', action='store_true', help='simulation mode')
    p.add_argument('-i', dest='input', action='store_true', help='get input')
    p.add_argument('-o', dest='output', type=int, metavar='value')
    p.add_argument('-t', dest='time', type=int, metavar='millisecs', default=500)
    args = p.parse_args()

    cfg = HalConfig(args.confFile)

    if args.sim:
        hal = DoorHalSim(cfg)
    else:
        hal = DoorHal(cfg)
    
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
    
    
