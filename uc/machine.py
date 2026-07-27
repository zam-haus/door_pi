# from uc.logic import IO


class Pin:
    IN = 0
    OUT = 1

    def __init__(self, ionum, mode, pull=None):
        self.ionum = ionum
        self.v = 0
        self.dir = None
        self.pull = None
        self.init(mode, pull)

    def init(self, mode=-1, pull=-1, *, value=None, drive=0, alt=-1):
        self.dir = mode
        if value is not None:
            self.v = value
        self.pull = pull
        print("Initializing Pin", self.ionum, "as", "IN" if self.dir == self.IN else "OUT", "with pull", self.pull,
              " and value", self.v)

    def value(self, v=None):
        if self.dir == self.OUT:
            if self.v != v:
                print("DEBUG io", self.ionum, "=", v)
            self.v = v
            return None
        if self.dir == self.IN:
            return self.v
        raise Exception("Unknown pin direction")


def unique_id():
    return b"BOARD #1337"
