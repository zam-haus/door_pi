
import sys, uselect

from time import sleep, time
from machine import Pin
from json import load, dumps

cfg = load(open("config.json", "r"))
ledv = 1

inputs = {}
for k in cfg["inputs"]:
    inputs[k] = Pin(cfg["inputs"][k], Pin.IN)
outputs = {}
for k in cfg["outputs"]:
    outputs[k] = Pin(cfg["outputs"][k], Pin.OUT)

def read():
    r = uselect.select([sys.stdin], [], [], 0)
    line = ""
    while r[0]:
        line += sys.stdin.read(1)
        if (line[-1] == "\r") or (line[-1] == "\n"):
            break
    return line

auto_off = []

while True:
    outputs["led"].value(ledv)

    line = read()
    if len(line) > 0:
        line = line.strip()
        elem = line.split()
        if len(elem) < 1:
            continue
        cmd = elem[0]

        if cmd == "*idn":
            print(cfg["idn"])
        elif cmd == "*read":
            r = {}
            for k in inputs:
                r[k] = inputs[k].value()
            print(dumps(r))
        elif (cmd == "*click") and (len(elem) >= 2):
            name = elem[1]
            duration = cfg["open-time"] 
            if len(elem) >= 3:
                duration = int(elem[2])

            if name in outputs:
                outputs[name].value(1)
                auto_off.append((name, time()+duration))
                print("ok")
            else:
                print("? invalid output")
        elif (cmd == "*on") and (len(elem) == 2):
            name = elem[1]
            if name in outputs:
                outputs[name].value(1)
                print("ok")
            else:
                print("? invalid output")
        elif (cmd == "*off") and (len(elem) == 2):
            name = elem[1]
            if name in outputs:
                outputs[name].value(0)
                print("ok")
            else:
                print("? invalid output")
        else:
            print("?")
        
        ledv = 1-ledv

    for i in range(0,len(auto_off)):
        if time() > auto_off[i][1]:
            outputs[auto_off[i][0]].value(0)
            del auto_off[i]
            break

