
""" pcb-test

Usage:
  pcb-test.py
  pcb-test.py inptest <vsys> [--input=<i>]
  pcb-test.py outptest <vsys> [--output=<o>]

Options:
  --input=<i>   Limit test to input #i
  --output=<o>  Limit test to output #o
"""

from sys import exit
from dps import DPS
from glob import glob
from if4test import IF, InpTest, OutpTest, ProtoFile
from docopt import docopt


if __name__ == "__main__":
    args = docopt(__doc__)

    dps = DPS("/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0")
    dps.read()
    print(dps)

    mods = glob("/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_*")
    for m in mods:
        print(m)

        if args["inptest"]:
            vsys = int(args["<vsys>"])
            inp = args["--input"]
            i = IF(m)
            mod_id = i.get_id()
            state = i.get_state_str()
            print("id:", mod_id)
            print("state:", state)

            pf = ProtoFile(mod_id)

            t = InpTest(dps, i, vsys)
            nums = range(1,9)
            if inp is not None:
                nums = [int(inp)]
            for inum in nums:
                input("setup input %d: " % inum)
                tL,tH,err = t.test(inum)
                pf.set("%dv" % vsys,"in",str(inum),{"low": tL, "high": tH, "err": err})
                pf.save()

        elif args["outptest"]:
            vsys = int(args["<vsys>"])
            outp = args["--output"]
            i = IF(m)
            mod_id = i.get_id()
            state = i.get_state_str()
            print("id:", mod_id)
            print("state:", state)

            pf = ProtoFile(mod_id)
            
            t = OutpTest(dps, i, vsys)
            nums = range(1,7)
            if outp is not None:
                nums = [int(outp)]
            for onum in nums:
                input("setup output %d: " % onum)
                vout,iout = t.test(onum)
                pf.set("%dv" % vsys,"out",str(onum),{"vout": vout, "iout": iout})
                pf.save()


