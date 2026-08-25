"""Wave-1 wrap-up: list, wall map, oom allowlist, isolate."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_LIST = _load("run_pod_list_mod", _ROOT / "scripts" / "run_pod_list.py")
_TASK = _load("run_task_mod", _ROOT / "scripts" / "run_task.py")
_ISO = _load("isolate_run_mod", _ROOT / "scripts" / "isolate_run.py")


def _ids(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.split()[0])
    return out


class TestRerunWave1(unittest.TestCase):
    def test_list_order(self) -> None:
        ids = _ids(_ROOT / "docs" / "prod_lists" / "rerun_wave1.txt")
        self.assertEqual(
            ids,
            [
                "bird",
                "tydiqa",
                "task419_persent_answer_generation",
                "apps",
            ],
        )

    def test_wall_map(self) -> None:
        self.assertEqual(_LIST.parse_wall_map(""), {})
        self.assertEqual(_LIST.parse_wall_map("apps=28800"), {"apps": 28800})
        self.assertEqual(_LIST.APPS_WALL_SEC, 8 * 60 * 60)
        self.assertEqual(_LIST.WALL_SEC, 3 * 60 * 60)

    def test_oom_allowlist_ok(self) -> None:
        proto = {
            "train": {"per_device_batch": 2, "grad_accum": 8, "lr": 1.0e-4}
        }
        out = _TASK.apply_oom_fallback(proto, "tydiqa")
        self.assertEqual(out["train"]["per_device_batch"], 1)
        self.assertEqual(out["train"]["grad_accum"], 16)
        self.assertEqual(proto["train"]["per_device_batch"], 2)
        out2 = _TASK.apply_oom_fallback(proto, "task419_persent_answer_generation")
        self.assertEqual(out2["train"]["per_device_batch"] * out2["train"]["grad_accum"], 16)

    def test_oom_allowlist_rejects_other(self) -> None:
        proto = {"train": {"per_device_batch": 2, "grad_accum": 8}}
        with self.assertRaises(SystemExit):
            _TASK.apply_oom_fallback(proto, "apps")

    def test_oom_cli_set_rejects_extra(self) -> None:
        extra = _LIST.parse_oom_tasks("apps,tydiqa") - _LIST.OOM_FALLBACK_TASKS
        self.assertEqual(extra, {"apps"})

    def test_isolate_moves_not_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            src = runs / "bird__pv2__tv4__x"
            src.mkdir(parents=True)
            (src / "STATUS").write_text("PARTIAL\n", encoding="utf-8")
            dest = _ISO.isolate_run(src)
            self.assertFalse(src.exists())
            self.assertTrue((dest / "STATUS").is_file())
            self.assertEqual(dest.parent.name, "_isolated")

    def test_protocol_v2_untouched_batch(self) -> None:
        from src.data import load_protocol

        v2 = load_protocol(_ROOT / "configs" / "protocol_v2.yaml")
        self.assertEqual(v2["train"]["per_device_batch"], 2)
        self.assertEqual(v2["train"]["grad_accum"], 8)


if __name__ == "__main__":
    unittest.main()
