
from time import sleep
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

while True:
    outputs["led"].value(ledv)

    line = input().strip()
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
    elif (cmd == "*click") and (len(elem) == 2):
        name = elem[1]
        if name in outputs:
            outputs[name].value(1)
            sleep(cfg["open-time"])
            outputs[name].value(0)
            print("ok")
        else:
            print("? invalid output")
    else:
        print("?")

    ledv = 1-ledv
