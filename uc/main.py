
import sys, uselect

from time import sleep, time
from machine import Pin, unique_id
from json import load, dumps

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

def set_output_idle(o):
    return set_output(o, cfg["outputs"][o][1])

def set_output_active(o):
    return set_output(o, cfg["outputs"][o][2])

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
for k in cfg["outputs"]:
    outputs[k] = Pin(cfg["outputs"][k][0], Pin.IN, pull=None)
    set_output_idle(k)

prev_input_status = get_inputs()

auto_off = []

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

        elif (cmd == "*impulse") and (len(elem) >= 2):
            name = elem[1]
            duration = cfg["impulse-time"] 
            if len(elem) >= 3:
                duration = int(elem[2])

            err = set_output_active(name)
            if err:
                auto_off.append((name, time()+duration))
                print("ok")
            else:
                print("? invalid output")

        elif (cmd == "*on") and (len(elem) == 2):
            name = elem[1]
            err = set_output_active(name)
            if err:
                print("ok")
            else:
                print("? invalid output")

        elif (cmd == "*off") and (len(elem) == 2):
            name = elem[1]
            err = set_output_idle(name)
            if err:
                print("ok")
            else:
                print("? invalid output")
            
        elif (cmd == "*set") and (len(elem) == 3):
            name = elem[1]
            state = elem[2]
            err = set_output(name, state)
            if err:
                print("ok")
            else:
                print("? invalid")

        else:
            print("?")
        
        ledv = 1-ledv

    for i in range(0,len(auto_off)):
        if time() > auto_off[i][1]:
            set_output_idle(auto_off[i][0])
            del auto_off[i]
            break

