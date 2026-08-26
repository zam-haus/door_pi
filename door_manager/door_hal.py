import json
import os
from io import StringIO
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
from pathlib import Path
from signal import SIGTERM
from time import sleep
from json import load, loads, JSONDecodeError
import queue
from threading import Lock, Thread
import abc
import functools
from typing import override, Literal
from select import select


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


class GPIOHAL(abc.ABC):
    def __init__(self, _cfg):
        pass

    @abc.abstractmethod
    def impulse(self, name, val, duration=2.0):
        pass

    @abc.abstractmethod
    def setOutput(self, name, val):
        pass

    @abc.abstractmethod
    def getInput(self, name):
        pass

    @abc.abstractmethod
    def getEvent(self):
        pass

    def cleanup(self):
        pass


class DoorHalRaspi(GPIOHAL):
    def __init__(self, cfg):
        import RPi.GPIO as gpio
        self.cfg = cfg
        self.gpio = gpio
        self.gpio.setmode(gpio.BCM)
        self.gpio.setwarnings(False)
        self.eventq = queue.Queue()
        self.callbacks = {}

        for i in self.cfg.inputs:
            self.gpio.setup(self.cfg.inputs[i], self.gpio.IN)
        for o in self.cfg.outputs:
            self.gpio.setup(self.cfg.outputs[o], self.gpio.OUT, initial=0)
        self.outputStates = {}
        for input in self.cfg.inputs:
            self.gpio.add_event_detect(
                self.cfg.inputs[input],
                self.gpio.BOTH,
                callback=functools.partial(self._event_callback, input),
                bouncetime=50)

    def _event_callback(self, input, *_args):
        pinval = self.gpio.input(self.cfg.inputs[input])
        if pinval:
            x = "H"
        else:
            x = "L"
        self.eventq.put({input: x})
        for cb in self.callbacks.get((input, x), ()):
            cb()

    def registerInputCallback(self, input, callback, falling=True):
        if falling is True:
            x = "L"
        elif falling is False:
            x = "H"
        else:
            raise TypeError("parameter falling should be True or False")
        if (input, x) not in self.callbacks:
            self.callbacks[(input, x)] = []
        self.callbacks[(input, x)].append(callback)

    def exist(self, name):
        return name in self.cfg.inputs

    def impulse(self, name, val, duration=2.0):
        reset = self.outputStates.get(name, "L")
        self.setOutput(name, val)
        sleep(duration)
        self.setOutput(name, reset)

    def setOutput(self, name, val):
        # TODO: ValueError instead of assert
        if val not in "HL":
            raise ValueError("GPIO value must be H or L. Unsupported value: %r" % val)
        assert (name in self.cfg.outputs)
        print('output', val, 'on', name)
        self.gpio.output(self.cfg.outputs[name], {"H": True, "L": False}[val])
        self.outputStates[name] = val

    def getInput(self, name):
        assert name in self.cfg.inputs
        return self.gpio.input(self.cfg.inputs[name]) == self.gpio.HIGH

    def getEvent(self):
        try:
            return self.eventq.get(block=False)
        except queue.Empty:
            return None

    def cleanup(self):
        self.gpio.cleanup()


class DoorHalUSB(GPIOHAL):
    def __init__(self, cfg):
        self.cfg = cfg
        self.s = self._get_serial()
        self.slock = Lock()
        self.eventq = queue.Queue()

        iv = self.getInputAll()
        for i in iv:
            self.cfg.inputs[i] = i

    def _get_serial(self):
        import serial
        return serial.Serial(self.cfg.usbpath, timeout=10)

    def __readline(self, event_only=False):
        l = self.s.readline().strip().decode()
        while l.startswith("!"):
            self.eventq.put(l)
            if event_only:
                return None
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
        return None  # no event pending

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


class DoorHalSim(GPIOHAL):
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
        reset = self.outputStates.get(name, "Z")
        self.setOutput(name, val)
        sleep(duration)
        self.setOutput(name, reset)

    def setOutput(self, name, val):
        assert (name in self.cfg.outputs) and (val in "HLZ")
        self.outputStates[name] = val
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


class DoorHalUsbSimulatedUc(DoorHalUSB):
    class FakeSerialIo:
        def __init__(self):
            class FakeIo():
                def __init__(self, parent):
                    self.parent : DoorHalUsbSimulatedUc.FakeSerialIo = parent

                def read(self) -> str:
                    fd = self.parent.to_uc[0]
                    r, _, _ = select([fd], [], [], 0)
                    line = ""
                    while r:
                        line += os.read(fd, 1).decode()
                        if line[-1] in ("\r", "\n"):
                            break
                    return line

                def write(self, *value: str):
                    line = " ".join(str(v) for v in value) + "\n"
                    os.write(self.parent.from_uc[1], line.encode())

            class FakeSerial():
                def __init__(self, parent):
                    self.parent : DoorHalUsbSimulatedUc.FakeSerialIo = parent

                def readline(self) -> bytes:
                    fd = self.parent.from_uc[0]
                    line = b""
                    while True:
                        c = os.read(fd, 1)
                        if not c:
                            break
                        line += c
                        if c in (b"\r", b"\n"):
                            break
                    return line

                def write(self, *value: bytes):
                    for v in value:
                        if isinstance(v, str):
                            v = v.encode()
                        os.write(self.parent.to_uc[1], v)

                @property
                def in_waiting(self) -> int:
                    r, _, _ = select([self.parent.from_uc[0]], [], [], 0)
                    return 1 if r else 0

            self.io = FakeIo(self)
            self.serial = FakeSerial(self)
            # pipefd[0] refers to the read end of the pipe.  pipefd[1] refers to the write end of the pipe.
            self.to_uc = os.pipe()
            self.from_uc = os.pipe()

    def __init__(self):
        self.uc = Path(__file__).parent / ".." / "uc"
        from logic import Logic
        self.fake = DoorHalUsbSimulatedUc.FakeSerialIo()
        self.logic = Logic(self.fake.io)
        self.cancel = False
        self.thread = Thread(target=self.run_logic, daemon=True)
        self.thread.start()
        super().__init__(HalConfig())

    @override
    def _get_serial(self):
        return self.fake.serial

    def run_logic(self):
        self.logic.cfg = json.loads((self.uc / "config.json").read_text(encoding="ascii"))
        self.logic.run_initialize()
        while not self.cancel:
            self.logic.loop()


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
        hal = DoorHalRaspi(cfg)

    if args.input:
        print('input', args.name, 'is', hal.getInput(args.name))
        # hal.registerInputCallback(args.name,
        #    lambda v: print("input", args.name, "falling"), falling=True)
        # hal.registerInputCallback(args.name,
        #    lambda v: print("input", args.name, "rising"), falling=False)
    elif args.output is not None:
        val = args.output == 1
        hal.setOutput(args.name, val)
        if args.time > 0:
            sleep(args.time / 1000)
            hal.setOutput(args.name, False)
