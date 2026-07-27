import json
import re
from typing import Callable

ERROR_REPONSE = re.compile(r"^\?")
import unittest
from unittest.mock import MagicMock
from parameterized import parameterized

import logic
from logic import IO

CFG = {
    "idn": "IDENTIFIER #1337",
    "impulse-time": 5,
    "inputs": {
        "in1": [0, 1],
        "in2": [2, 3],
        "in3": [4, 5],
        "in4": [6, 7],
        "in5": [8, 9],
        "in6": [10, 11],
        "in7": [12, 13],
        "in8": [14, 15]
    },
    "outputs": {
        "led": 22,
        "out1": 21,
        "out2": 20,
        "out3": 19,
        "out4": 18,
        "out5": 17,
        "out6": 16
    }
}


class MyTestCase(unittest.TestCase):
    def _write(self, *values):
        print("WRITE", *values)
        self.last_write = " ".join(values)

    def setUp(self):
        self.last_write = None
        self.mock_io: IO = MagicMock()
        self.mock_io.write = MagicMock(side_effect=self._write)
        self.mock_io.read = MagicMock(return_value="")
        self.logic = logic.Logic(self.mock_io)
        self.logic.cfg = CFG  # replacement for load_cfg()
        self.logic.run_initialize()

    def test_cmd_id(self):
        self.simulate("*id", b"BOARD #1337".hex())

    def test_cmd_idn(self):
        self.simulate("*idn", "IDENTIFIER #1337")

    @parameterized.expand([
        ["in1", "H"],
        ["in1", "L"],
        ["in1", "Z"],
        ["in42", "H"],
        ["in42", "L"],
        ["in42", "Z"],
    ])
    def test_cmd_set(self, input, value):
        self.simulate(f"*set {input} {value}", ERROR_REPONSE)

    @parameterized.expand([
        ["out42", "H"],
        ["out42", "L"],
        ["out42", "Z"],
        ["out1", "A"],
        ["out1", "ZZ"],
        ["out1", "HH"],
        ["out1", "LL"],
        ["out1", ""],
        ["", ""],
        ["", "H"],
    ])
    def test_cmd_set_out_invalid(self, output, value):
        self.simulate(f"*set {output} {value}", ERROR_REPONSE)

    @parameterized.expand([
        ["out1", "H"],
        ["out1", "L"],
        ["out1", "Z"],
    ])
    def test_cmd_set_out(self, output, value):
        self.simulate(f"*set {output} {value}", "ok")

    @parameterized.expand([
        ["out1", "H"],
        ["out1", "L"],
        ["out1", "Z"],
        ["out1", "Z", 10],
        ["out1", "H", 20],
        ["out1", "L", 30],
    ])
    def test_cmd_set_impulse(self, output, value, duration=None):
        self.simulate(f"*impulse {output} {value}" + (f" {duration}" if duration is not None else ""), "ok")

    @parameterized.expand([
        ["out1", ""],
        ["out1", "", "A"],
        ["out1", "H", "A"],
        ["out1", "A"],
    ])
    def test_cmd_set_impulse_invalid(self, output, value, duration=None):
        self.simulate(f"*impulse {output} {value}" + (f" {duration}" if duration is not None else ""), ERROR_REPONSE)

    def test_read(self):
        self.simulate("*read", lambda x: json.loads(x))

    def test_cmd_version(self):
        self.simulate("*version", "2.0")

    def simulate(self, command: str, expected_response: str | re.Pattern | Callable[[str],bool]):
        self.mock_io.read = MagicMock(side_effect=[command] + [""] * 20)
        print("WRITING", command)
        for i in range(5):
            self.logic.loop()
        if isinstance(expected_response, re.Pattern):
            self.assertRegex(self.last_write, expected_response)
        elif isinstance(expected_response, Callable):
            self.assertTrue(expected_response(self.last_write))
        else:
            self.assertEqual(self.last_write, expected_response)


if __name__ == '__main__':
    unittest.main()
