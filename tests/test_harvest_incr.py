"""Incremental harvest omits adapters."""

from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


class TestHarvestIncr(unittest.TestCase):
    def test_omits_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "runs" / "toy__pv2__tv4__x"
            (run / "adapters" / "full").mkdir(parents=True)
            (run / "metrics.json").write_text("{}\n", encoding="utf-8")
            (run / "adapters" / "full" / "weights.bin").write_bytes(b"nope")
            out = Path(tmp) / "incr.tar.gz"
            subprocess.check_call(
                [
                    sys.executable,
                    str(_ROOT / "scripts" / "harvest_incr.py"),
                    "--batch",
                    "1",
                    "--run-dir",
                    str(run),
                    "--out",
                    str(out),
                ]
            )
            names = tarfile.open(out).getnames()
            self.assertTrue(any(name.endswith("metrics.json") for name in names))
            self.assertFalse(any("adapters" in name for name in names))


if __name__ == "__main__":
    unittest.main()
