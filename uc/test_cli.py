#!/usr/bin/env python3

import sys
import serial
import json

def cmd(c):
    s.write((c + "\n").encode())
    ans = s.readline().decode().strip()
    return ans

port = sys.argv[1]
s = serial.Serial(port)


uid = cmd("*id")
r = cmd("*read")
inp = json.loads(r)

print("unique id: " + uid)
for k in sorted(inp.keys()):
    print(k + "=" + inp[k], end=" ")
print()

