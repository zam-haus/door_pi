
from minimalmodbus import Instrument, MODE_RTU

class DPS:
    Uset = 0
    Iset = 1
    Uout = 2
    Iout = 3
    Pout = 4
    Uin = 5
    Lock = 6
    Protect = 7
    CC = 8
    On = 9
    Disp = 10

    def __init__(self, path):
        self.psu = Instrument(path, 1)
        self.psu.serial.baudrate = 9600
        self.psu.serial.bytesize = 8
        self.psu.serial.timeout = 2
        self.psu.mode = MODE_RTU

    def read(self):
        self.data = self.psu.read_registers(0,11)

    def get_u_set(self):
        return self.data[self.Uset]/100
    def get_i_set(self):
        return self.data[self.Iset]/1000
    def get_u_out(self):
        return self.data[self.Uout]/100
    def get_i_out(self):
        return self.data[self.Iout]/1000
    def get_p_out(self):
        return self.data[self.Pout]/100
    def get_u_in(self):
        return self.data[self.Uin]/100
    def get_lock(self):
        return self.data[self.Lock] == 1
    def get_protected(self):
        return self.data[self.Protect] == 1
    def get_mode_cc(self):
        return self.data[self.CC] == 1
    def get_on(self):
        return self.data[self.On] == 1
    def get_disp_intensity(self):
        return self.data[self.Disp]

    def set_u_set(self, uset):
        val = int(uset*100)
        self.psu.write_register(self.Uset, val)
        self.read()
        assert val == self.data[self.Uset]
    def set_i_set(self, iset):
        val = int(iset*1000)
        self.psu.write_register(self.Iset, val)
        self.read()
        assert val == self.data[self.Iset]
    def set_lock(self, lock):
        val = 1 if lock else 0
        self.psu.write_register(self.Lock, val)
        self.read()
        assert val == self.data[self.Lock]
    def set_on(self, on):
        val = 1 if on else 0
        self.psu.write_register(self.On, val)
        self.read()
        assert val == self.data[self.On]
    def set_disp_intensity(self, disp):
        val = disp
        self.psu.write_register(self.Disp, val)
        self.read()
        assert val == self.data[self.Disp]

    def __str__(self):
        s = ""
        s += "Uset=%.2f " % self.get_u_set()
        s += "Iset=%.2f " % self.get_i_set()
        s += "Uout=%.2f " % self.get_u_out()
        s += "Iout=%.2f " % self.get_i_out()
        s += "Pout=%.2f " % self.get_p_out()
        s += "Uin=%.2f " % self.get_u_in()
        if self.get_lock():
            s += "LOCKED "
        if self.get_protected():
            s += "PROTECTED "
        if self.get_mode_cc():
            s += "CC "
        else:
            s += "CV "
        if self.get_on():
            s += "ON "
        s += "disp=%d " % self.get_disp_intensity()
        return s
