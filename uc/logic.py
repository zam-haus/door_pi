import abc
import sys

from time import sleep, time
from machine import Pin, unique_id
from json import load, dumps

# Changelog:
# 2.0:
# - added *version
# - drop active/idle states:
#   this is to make all boards interchangable, preventing short circuits due to missing configuration.
#   The board initializes with all outputs as Z.
#   - removed *on/*off commands.
#   - add an explicit state parameter to the  *impulse command. The syntax is now
#     *impulse NAME H/L/Z [DURATION]
PROTOCOL_VERSION = "2.0"


class IO(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def read(self) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def write(self, *value: str):
        raise NotImplementedError()


class PipeIO(IO):
    def __init__(self):
        super().__init__()
        try:
            import uselect
            self.select = uselect.select
        except ModuleNotFoundError:
            from select import select
            self.select = select

    def read(self):
        r = self.select([sys.stdin], [], [], 0)
        line = ""
        while r[0]:
            line += sys.stdin.read(1)
            if (line[-1] == "\r") or (line[-1] == "\n"):
                break
        return line

    def write(self, *value):
        print(*value)


class Logic():
    def __init__(self, io: IO):
        self.io = io
        self.set_output_states = {}
        self.auto_off: dict[str, float] = {}
        self.outputs: dict[str, Pin] = {}
        self.inputs: dict[str, tuple[Pin, Pin]] = {}
        self.ledv = 1
        self.prev_input_status = None

    def run(self):
        self.load_cfg()

        self.run_initialize()

        while True:
            self.loop()

    def load_cfg(self):
        self.cfg = load(open("config.json", "r"))

    def run_initialize(self):
        for k in self.cfg["inputs"]:
            self.inputs[k] = (
                Pin(self.cfg["inputs"][k][0], Pin.IN),
                Pin(self.cfg["inputs"][k][1], Pin.IN),
            )
        for k in self.cfg["outputs"]:
            self.outputs[k] = Pin(self.cfg["outputs"][k], Pin.IN, pull=None)
            self.set_output(k, "Z")
            self.set_output_states[k] = "Z"

        if "led" in self.outputs:
            self.outputs["led"].init(Pin.OUT, value=self.ledv)

        self.prev_input_status = self.get_inputs()

    def loop(self):
        # set output of LED
        self.outputs["led"].value(self.ledv)

        self.generate_interrupts()

        line = self.io.read()

        if len(line) > 0:
            line = line.strip()
            elem = line.split()

            if len(elem) < 1:
                return

            cmd = elem[0]

            if cmd == "*id":
                self.cmd_id()

            elif cmd == "*idn":
                self.cmd_idn()

            elif cmd == "*read":
                self.cmd_read()

            elif (cmd == "*impulse") and (len(elem) >= 3):
                name = elem[1]
                state = elem[2]
                if len(elem) >= 4:
                    try:
                        duration = int(elem[3])
                    except ValueError:
                        self.io.write("? invalid duration")
                    else:
                        self.cmd_impulse(duration, name, state)
                else:
                    duration = None
                    self.cmd_impulse(duration, name, state)

            elif (cmd == "*set") and (len(elem) == 3):
                name = elem[1]
                state = elem[2]
                self.cmd_set(name, state)

            elif cmd == "*version":
                self.cmd_version()

            else:
                self.io.write("?")

            self.ledv = 1 - self.ledv

            expired = [
                o
                for (o, target_time)
                in self.auto_off.items()
                if time() > target_time
            ]

            for o in expired:
                self.auto_off.pop(o, None)
                self.set_output(o, self.set_output_states[o])

    def generate_interrupts(self):
        # if an input changed, print an interrupt message
        input_status = self.get_inputs()
        if input_status != self.prev_input_status:
            self.io.write("!", dumps(input_status))
        self.prev_input_status = input_status

    def cmd_version(self):
        self.io.write(PROTOCOL_VERSION)

    def cmd_set(self, name: str, state: str):
        err = self.set_output(name, state)
        if err:
            self.set_output_states[name] = state
            self.auto_off.pop(name, None)
            self.io.write("ok")
        else:
            self.io.write("? invalid")

    def cmd_impulse(self, duration: int | None, name: str, state: str):
        duration = duration or self.cfg["impulse-time"]

        ok = self.set_output(name, state)
        if ok:
            self.auto_off[name] = time() + duration
            self.io.write("ok")
        else:
            self.io.write("? invalid output")

    def cmd_read(self):
        self.io.write(dumps(self.get_inputs()))

    def cmd_idn(self):
        self.io.write(self.cfg["idn"])

    def cmd_id(self):
        self.io.write(self.get_unique_id_str())

    def get_unique_id_str(self):
        return "".join("%02x" % b for b in unique_id())

    def get_input(self, i):
        if i in self.inputs:
            in_a, in_b = self.inputs[i]
            a = in_a.value()
            b = in_b.value()
            if a and not b:
                return "L"
            elif b and not a:
                return "H"
            elif a and b:
                return "Z"
            else:
                return "?"
        else:
            raise ValueError("invalid parameter i specifying unknown input")

    def set_output(self, o, state):
        if o in self.outputs:
            po = self.outputs[o]
            if state == "H":
                po.init(Pin.OUT, value=1)
            elif state == "L":
                po.init(Pin.OUT, value=0)
            elif state == "Z":
                po.init(Pin.IN, pull=None)
            else:
                return False
        else:
            return False
        return True

    def get_inputs(self):
        input_status = {}
        for k in self.cfg["inputs"]:
            while True:
                current_state = self.get_input(k)
                sleep(0.001) # TODO move debounce to self.generate_interrupts()
                if self.get_input(k) == current_state:
                    input_status[k] = current_state
                    break
        return input_status
