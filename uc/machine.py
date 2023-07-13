
class Pin:
    IN = 0
    OUT = 1

    def __init__(self, ionum, dir):
        self.io = ionum
        self.dir = dir
        self.v = 0

    def value(self, v=None):
        if self.dir == self.OUT:
            self.v = v
            print("DEBUG io", self.io, "=", v)
        if self.dir == self.IN:
            return self.v

