
from json import loads, dumps
from serial import Serial
from time import sleep
from os.path import isfile

class IF:
    def __init__(self, port):
        self.s = Serial(port)
        self.uid = 0
    
    def cmd(self, c):
        self.s.write((c + "\n").encode())
        ans = self.s.readline().decode().strip()
        return ans

    def get_id(self):
        self.uid = self.cmd("*id")
        return self.uid

    def get_state(self):
        r = self.cmd("*read")
        return loads(r)

    def get_state_str(self):
        state = self.get_state()
        s = ""
        for k in sorted(state.keys()):
            s += k + "=" + state[k] + " "
        return s

    def set_output(self, onum, state):
        assert state in ("Z","L","H")
        self.cmd("*set out%d %s" % (onum, state))

class ProtoFile:
    def __init__(self, uid):
        self.data = {}
        self.fname = "protos/%s.json" % uid
        if isfile(self.fname):
            self.data = loads(open(self.fname, "r").read())
    
    def save(self):
        f = open(self.fname, "wt")
        f.write(dumps(self.data, indent=4))

    def set(self, *args):
        if len(args) < 2:
            raise Exception("set requires > 2 arguments")
        val = args[-1]
        path = args[:-1]
        top = self.data
        for p in path[:-1]:
            if p not in top:
                top[p] = {}
            top = top[p]
        top[path[-1]] = val

class InpTest:
    def __init__(self, dps, ctl, vsys):
        self.dps = dps
        self.ctl = ctl
        self.vsys = vsys
    
    def find_thr(self, sv, st, lo, hi):
        sv(lo)
        sleep(5)
        s_lo = st()
        sv(hi)
        s_hi = st()
        print("lo", s_lo, "hi", s_hi)
        if not((s_lo == "L" and s_hi == "Z") or (s_lo == "Z" and s_hi == "H")):
            return -1,True

        err = False
        for i in range(0,10):
            mid = lo+(hi-lo)/2
            print("lo=%.2f, mid=%.2f, hi=%.2f" % (lo,mid,hi))
            sv(mid)
            sleep(5)
            s_mid = st()
            print("got", s_mid)
            if s_mid != s_lo:
                if hi < mid:
                    print("inconsistent, abort")
                    err = True
                    break
                hi = mid
            else:
                if lo > mid:
                    print("inconsistent, abort")
                    err = True
                    break
                lo = mid
        return mid, err

    def test(self, i):
        st = lambda: self.ctl.get_state()["in%d"%i]
        sv = lambda v: self.dps.set_u_set(v)

        tL, errL = self.find_thr(sv,st,0,self.vsys/2)
        tH, errH = self.find_thr(sv,st,self.vsys/2,self.vsys)
        print("tL %.2f V, tH %.2f" % (tL, tH))
        return tL, tH, errL or errH

class OutpTest:
    def __init__(self, dps, ctl, vsys):
        self.dps = dps
        self.ctl = ctl
        self.vsys = vsys

    def test(self, i):
        # low only
        self.ctl.set_output(i, "Z")
        self.dps.set_i_set(1)
        self.dps.set_u_set(self.vsys)
        self.dps.set_on(True)
        self.ctl.set_output(i, "L")
        sleep(3)
        vout = self.dps.get_u_out()
        iout = self.dps.get_i_out()
        self.dps.set_on(False)
        self.ctl.set_output(i, "Z")
        return vout,iout




