"""prod_serial.txt merge invariants."""

from __future__ import annotations

import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _ids(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.split()[0])
    return out


class TestProdSerial(unittest.TestCase):
    def test_order(self) -> None:
        serial = _ids(_ROOT / "docs" / "prod_lists" / "prod_serial.txt")
        self.assertEqual(serial[-1], "bird")
        self.assertEqual(len(serial), 60)
        lit = [
            "apps",
            "math",
            "mbpp",
            "drop",
            "tydiqa",
            "arc_easy",
            "arc_challenge",
            "hellaswag",
            "piqa",
        ]
        self.assertEqual(serial[:9], lit)
        self.assertNotIn("bird", serial[:-1])
        a = _ids(_ROOT / "docs" / "prod_lists" / "pod_a.txt")
        b = _ids(_ROOT / "docs" / "prod_lists" / "pod_b.txt")
        self.assertEqual(serial[9:34], [x for x in a if x.startswith("task")])
        self.assertEqual(serial[34:59], [x for x in b if x.startswith("task")])


if __name__ == "__main__":
    unittest.main()
