
import sys, uselect

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

def read():
    r = uselect.select([sys.stdin], [], [], 0)
    line = ""
    while r[0]:
        line += sys.stdin.read(1)
        if (line[-1] == "\r") or (line[-1] == "\n"):
            break
    return line

def get_unique_id_str():
    return "".join("%02x" % b for b in unique_id())

def get_input(i):
    if i in inputs:
        a = inputs[i][0].value()
        b = inputs[i][1].value()
        if a and not b:
            return "L"
        elif b and not a:
            return "H"
        elif a and b:
            return "Z"
        else:
            return "?"
    else:
        return "E"

def set_output(o, state):
    if o in outputs:
        po = outputs[o]
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

def get_inputs():
    input_status = {}
    for k in cfg["inputs"]:
        while True:
            current_state = get_input(k)
            sleep(0.001)
            if get_input(k) == current_state:
                input_status[k] = current_state
                break
    return input_status

cfg = load(open("config.json", "r"))
ledv = 1

inputs = {}
for k in cfg["inputs"]:
    inputs[k] = [ Pin(cfg["inputs"][k][0], Pin.IN), \
        Pin(cfg["inputs"][k][1], Pin.IN) ]
outputs = {}
set_output_states = {}
for k in cfg["outputs"]:
    outputs[k] = Pin(cfg["outputs"][k], Pin.IN, pull=None)
    set_output(k, "Z")
    set_output_states[k] = "Z"

prev_input_status = get_inputs()

auto_off = {}

while True:
    outputs["led"].value(ledv)

    # if an input changed, print an interrupt message
    input_status = get_inputs()
    if input_status != prev_input_status:
        print("!", dumps(input_status))
    prev_input_status = input_status

    line = read()
    if len(line) > 0:
        line = line.strip()
        elem = line.split()
        if len(elem) < 1:
            continue
        cmd = elem[0]

        if cmd == "*id":
            print(get_unique_id_str())

        elif cmd == "*idn":
            print(cfg["idn"])

        elif cmd == "*read":
            print(dumps(get_inputs()))

        elif (cmd == "*impulse") and (len(elem) >= 3):
            name = elem[1]
            state = elem[2]
            duration = cfg["impulse-time"]
            if len(elem) >= 4:
                duration = int(elem[3])

            ok = set_output(name, state)
            if ok:
                auto_off[name] = time()+duration
                print("ok")
            else:
                print("? invalid output")

        elif (cmd == "*set") and (len(elem) == 3):
            name = elem[1]
            state = elem[2]
            err = set_output(name, state)
            if err:
                set_output_states[name] = state
                auto_off.pop(name, None)
                print("ok")
            else:
                print("? invalid")

        elif cmd == "*version":
            print(PROTOCOL_VERSION)

        else:
            print("?")

        ledv = 1-ledv

    expired = [o for (o,target_time) in auto_off.items() if time() > target_time]
    for o in expired:
        del auto_off[o]
        set_output(o, set_output_states[o])

