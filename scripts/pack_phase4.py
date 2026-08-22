#!/usr/bin/env python3
"""Materialize Phase 4 literature 10 + SuperNI 50. Does not rebuild gsm8k/wino/spider."""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any, Callable

import importlib.util

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "make_task_package", ROOT / "scripts" / "make_task_package.py"
)
assert _SPEC and _SPEC.loader
_mtp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mtp)
TASKS_DIR = _mtp.TASKS_DIR
pack_tar = _mtp.pack_tar
sample_indices = _mtp.sample_indices
write_jsonl = _mtp.write_jsonl
write_manifest = _mtp.write_manifest

LOG = logging.getLogger("pack_phase4")
PROTOCOL_PATH = ROOT / "configs" / "protocol_v2.yaml"
NI_DIR = ROOT / "data_cache" / "natural-instructions" / "tasks"
NI_LIST = ROOT / "docs" / "prod_lists" / "superni_50.json"
POOL_REF_LIT = "literature-layer Phase 4; folded MATH500→MATH, MBPP+→MBPP"
POOL_REF_NI = "superni stratified sample seed 20260822"
CHOICE_TAIL = "只答选项字母"
LIT_IDS = [
    "apps",
    "arc_easy",
    "arc_challenge",
    "bird",
    "drop",
    "hellaswag",
    "math",
    "mbpp",
    "piqa",
    "tydiqa",
]
MAX_NEW = {
    "arc_easy": 16,
    "arc_challenge": 16,
    "hellaswag": 16,
    "piqa": 16,
    "math": 512,
    "drop": 128,
    "tydiqa": 128,
    "mbpp": 512,
    "apps": 512,
    "bird": 256,
}

VERIFIER_IMPORT = {
    "choice": "from src.verifiers.choice import verify  # noqa: F401\n",
    "math": "from src.verifiers.math_boxed import verify  # noqa: F401\n",
    "qa": "from src.verifiers.qa_em import verify  # noqa: F401\n",
    "code": "from src.verifiers.code_sandbox import verify  # noqa: F401\n",
    "sql": "from src.verifiers.sql_exec import verify  # noqa: F401\n",
    "em": "from src.verifiers.em_norm import verify  # noqa: F401\n",
}


def load_protocol() -> dict[str, Any]:
    return yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))


def dump_task_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_verifier(task_dir: Path, kind: str) -> None:
    (task_dir / "verifier.py").write_text(VERIFIER_IMPORT[kind], encoding="utf-8")


def finish_task(
    task_id: str,
    task: dict[str, Any],
    train: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    kind: str,
) -> None:
    task_dir = TASKS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(task_dir / "train.jsonl", train)
    write_jsonl(task_dir / "eval.jsonl", eval_rows)
    dump_task_json(task_dir / "task.json", task)
    write_verifier(task_dir, kind)
    write_manifest(task_dir)
    LOG.info("%s train=%s eval=%s", task_id, len(train), len(eval_rows))


def downsample_train(rows: list[dict[str, Any]], cap: int, seed: int) -> list[dict[str, Any]]:
    if len(rows) <= cap:
        return list(rows)
    idx = sample_indices(len(rows), cap, seed)
    return [rows[i] for i in idx]


def pin_dataset(repo_id: str) -> str:
    from huggingface_hub import dataset_info

    info = dataset_info(repo_id)
    sha = getattr(info, "sha", None) or getattr(info, "id", None)
    if not sha:
        raise SystemExit(f"cannot pin {repo_id}")
    LOG.info("pin %s revision=%s", repo_id, sha)
    return str(sha)


def load_hf(repo_id: str, *, name: str | None, split: str, revision: str) -> list[dict[str, Any]]:
    from datasets import load_dataset

    ds = load_dataset(repo_id, name, split=split, revision=revision)
    return [dict(row) for row in ds]


def choice_user(stem: str, options: list[tuple[str, str]]) -> str:
    lines = [stem.rstrip(), ""]
    for letter, text in options:
        lines.append(f"{letter}. {text}")
    lines.append(CHOICE_TAIL)
    return "\n".join(lines)


def letters_for(n: int) -> list[str]:
    return [chr(ord("A") + i) for i in range(n)]


def _task_shell(
    task_id: str,
    source: dict[str, Any],
    train_n: int,
    eval_n: int,
    seeds: dict[str, int],
    prompt_style: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "source": source,
        "prior_label": None,
        "pool_ref": POOL_REF_LIT if not task_id.startswith("task") else POOL_REF_NI,
        "splits": {"train_n": train_n, "eval_n": eval_n, "seeds": seeds},
        "max_new_tokens": MAX_NEW.get(task_id, 128),
        "prompt_style": prompt_style,
    }


def build_arc(protocol: dict[str, Any], task_id: str, config: str) -> None:
    repo = "allenai/ai2_arc"
    rev = pin_dataset(repo)
    train_raw = load_hf(repo, name=config, split="train", revision=rev)
    eval_pool = load_hf(repo, name=config, split="test", revision=rev)
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), eval_n, eval_seed)

    def _row(prefix: str, i: int, rec: dict[str, Any]) -> dict[str, Any]:
        labels = [str(x) for x in rec["choices"]["label"]]
        texts = [str(x) for x in rec["choices"]["text"]]
        options = list(zip(labels, texts))
        gold = str(rec["answerKey"]).strip().upper()
        if gold.isdigit():
            gold = labels[int(gold) - 1] if gold != "0" else labels[0]
        return {
            "id": f"{task_id}-{prefix}-{i:05d}",
            "messages": [
                {
                    "role": "user",
                    "content": choice_user(str(rec["question"]), options),
                }
            ],
            "reference": {
                "gold": gold,
                "n_choices": len(options),
                "completion": gold,
            },
        }

    train = downsample_train(
        [_row("train", i, rec) for i, rec in enumerate(train_raw)], cap, train_seed
    )
    eval_rows = [_row("test", i, eval_pool[i]) for i in eval_idx]
    for row in eval_rows:
        row["reference"].pop("completion", None)
    finish_task(
        task_id,
        _task_shell(
            task_id,
            {"dataset": task_id, "hf_path": repo, "config": config, "revision": rev},
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "question plus N lettered options; last line: 只答选项字母",
        ),
        train,
        eval_rows,
        "choice",
    )


def build_hellaswag(protocol: dict[str, Any]) -> None:
    repo = "Rowan/hellaswag"
    rev = pin_dataset(repo)
    train_raw = load_hf(repo, name=None, split="train", revision=rev)
    eval_pool = load_hf(repo, name=None, split="validation", revision=rev)
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), eval_n, eval_seed)
    lets = letters_for(4)

    def _row(prefix: str, i: int, rec: dict[str, Any]) -> dict[str, Any]:
        endings = [str(x) for x in rec["endings"]]
        options = list(zip(lets, endings))
        gold = lets[int(rec["label"])]
        stem = f"{rec['ctx']}\nWhich ending is most plausible?"
        return {
            "id": f"hellaswag-{prefix}-{i:05d}",
            "messages": [{"role": "user", "content": choice_user(stem, options)}],
            "reference": {"gold": gold, "n_choices": 4, "completion": gold},
        }

    train = downsample_train(
        [_row("train", i, rec) for i, rec in enumerate(train_raw)], cap, train_seed
    )
    eval_rows = [_row("val", i, eval_pool[i]) for i in eval_idx]
    for row in eval_rows:
        row["reference"].pop("completion", None)
    finish_task(
        "hellaswag",
        _task_shell(
            "hellaswag",
            {"dataset": "hellaswag", "hf_path": repo, "config": None, "revision": rev},
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "HellaSwag context plus 4 endings; last line: 只答选项字母",
        ),
        train,
        eval_rows,
        "choice",
    )


def _http_download(url: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file():
        import urllib.request

        LOG.info("download %s -> %s", url, dest)
        urllib.request.urlretrieve(url, dest)
    digest = _mtp.sha256_file(dest)
    LOG.info("sha256 %s %s", dest.name, digest)
    return digest


def build_piqa(protocol: dict[str, Any]) -> None:
    base = "https://yonatanbisk.com/piqa/data/"
    cache = ROOT / "data_cache" / "piqa"
    train_path = cache / "train.jsonl"
    val_path = cache / "valid.jsonl"
    train_lab = cache / "train-labels.lst"
    val_lab = cache / "valid-labels.lst"
    hashes = {
        "train.jsonl": _http_download(base + "train.jsonl", train_path),
        "valid.jsonl": _http_download(base + "valid.jsonl", val_path),
        "train-labels.lst": _http_download(base + "train-labels.lst", train_lab),
        "valid-labels.lst": _http_download(base + "valid-labels.lst", val_lab),
    }
    rev = hashes["train.jsonl"]

    def _load(jsonl: Path, labels: Path) -> list[dict[str, Any]]:
        labs = [int(x.strip()) for x in labels.read_text().splitlines() if x.strip()]
        rows = []
        for i, line in enumerate(jsonl.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            rec = json.loads(line)
            rec["label"] = labs[i]
            rows.append(rec)
        return rows

    train_raw = _load(train_path, train_lab)
    eval_pool = _load(val_path, val_lab)
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), eval_n, eval_seed)

    def _row(prefix: str, i: int, rec: dict[str, Any]) -> dict[str, Any]:
        options = [("A", str(rec["sol1"])), ("B", str(rec["sol2"]))]
        gold = "A" if int(rec["label"]) == 0 else "B"
        return {
            "id": f"piqa-{prefix}-{i:05d}",
            "messages": [
                {"role": "user", "content": choice_user(str(rec["goal"]), options)}
            ],
            "reference": {"gold": gold, "n_choices": 2, "completion": gold},
        }

    train = downsample_train(
        [_row("train", i, rec) for i, rec in enumerate(train_raw)], cap, train_seed
    )
    eval_rows = [_row("val", i, eval_pool[i]) for i in eval_idx]
    for row in eval_rows:
        row["reference"].pop("completion", None)
    finish_task(
        "piqa",
        _task_shell(
            "piqa",
            {
                "dataset": "piqa",
                "hf_path": None,
                "url": "https://yonatanbisk.com/piqa/data/",
                "revision": rev,
                "sha256": hashes,
            },
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "PIQA goal plus two solutions; last line: 只答选项字母",
        ),
        train,
        eval_rows,
        "choice",
    )


def _extract_boxed_from_solution(solution: str) -> str:
    from src.verifiers.math_boxed import _extract_boxed_raw, normalize_math

    boxed = _extract_boxed_raw(solution)
    if boxed:
        return boxed
    lines = [ln.strip() for ln in solution.splitlines() if ln.strip()]
    return lines[-1] if lines else solution.strip()


def build_math(protocol: dict[str, Any]) -> None:
    repo = "EleutherAI/hendrycks_math"
    rev = pin_dataset(repo)
    subjects = [
        "algebra",
        "counting_and_probability",
        "geometry",
        "intermediate_algebra",
        "number_theory",
        "prealgebra",
        "precalculus",
    ]
    train_raw: list[dict[str, Any]] = []
    eval_pool: list[dict[str, Any]] = []
    for subj in subjects:
        train_raw.extend(load_hf(repo, name=subj, split="train", revision=rev))
        eval_pool.extend(load_hf(repo, name=subj, split="test", revision=rev))
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), eval_n, eval_seed)
    instr = "Put the final answer in \\boxed{}."

    def _row(prefix: str, i: int, rec: dict[str, Any], with_completion: bool) -> dict[str, Any]:
        solution = str(rec.get("solution") or "")
        gold = _extract_boxed_from_solution(solution)
        ref: dict[str, Any] = {"gold": gold}
        if with_completion:
            ref["completion"] = solution.strip() or gold
        return {
            "id": f"math-{prefix}-{i:05d}",
            "messages": [
                {
                    "role": "user",
                    "content": f"{rec['problem']}\n{instr}",
                }
            ],
            "reference": ref,
        }

    train = downsample_train(
        [_row("train", i, rec, True) for i, rec in enumerate(train_raw)],
        cap,
        train_seed,
    )
    eval_rows = [_row("test", i, eval_pool[i], False) for i in eval_idx]
    finish_task(
        "math",
        _task_shell(
            "math",
            {
                "dataset": "math",
                "hf_path": repo,
                "config": "all_subjects",
                "revision": rev,
            },
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "Hendrycks MATH problem; final answer in \\boxed{}",
        ),
        train,
        eval_rows,
        "math",
    )


def _drop_golds(rec: dict[str, Any]) -> tuple[list[str], str]:
    block = rec.get("answers_spans") or rec.get("answers") or rec.get("answer") or {}
    if not isinstance(block, dict):
        return ([str(block)], "span") if block else ([], "span")
    spans = [str(x) for x in (block.get("spans") or []) if str(x).strip()]
    types = [str(x) for x in (block.get("types") or [])]
    numbers = [str(x) for x in (block.get("number") or []) if str(x).strip() != ""]
    dates = block.get("date") or []
    date_s = []
    for item in dates:
        if isinstance(item, dict):
            date_s.append(
                " ".join(
                    str(item.get(k, "")).strip()
                    for k in ("month", "day", "year")
                    if str(item.get(k, "")).strip()
                )
            )
        else:
            date_s.append(str(item))
    golds = []
    seen: set[str] = set()
    for item in spans + numbers + date_s:
        if item not in seen:
            seen.add(item)
            golds.append(item)
    if "number" in types or numbers:
        atype = "number"
    elif "date" in types or date_s:
        atype = "date"
    else:
        atype = "span"
    return golds, atype


def build_drop(protocol: dict[str, Any]) -> None:
    repo = "ucinlp/drop"
    rev = pin_dataset(repo)
    train_raw = load_hf(repo, name=None, split="train", revision=rev)
    eval_pool = load_hf(repo, name=None, split="validation", revision=rev)
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), eval_n, eval_seed)

    def _row(prefix: str, i: int, rec: dict[str, Any], with_completion: bool) -> dict[str, Any] | None:
        golds, atype = _drop_golds(rec)
        if not golds:
            return None
        passage = rec.get("passage") or rec.get("context") or ""
        question = rec.get("question") or ""
        content = f"{passage}\n\nQuestion: {question}\nShort answer:"
        ref: dict[str, Any] = {"golds": golds, "answer_type": atype}
        if with_completion:
            ref["completion"] = golds[0]
        return {
            "id": f"drop-{prefix}-{i:05d}",
            "messages": [{"role": "user", "content": content}],
            "reference": ref,
        }

    train_all = [
        row
        for i, rec in enumerate(train_raw)
        if (row := _row("train", i, rec, True)) is not None
    ]
    train = downsample_train(train_all, cap, train_seed)
    eval_rows = []
    for i in eval_idx:
        row = _row("val", i, eval_pool[i], False)
        if row is not None:
            eval_rows.append(row)
    if len(eval_rows) < eval_n:
        raise SystemExit(f"drop eval after empty-gold filter {len(eval_rows)} < {eval_n}")
    eval_rows = eval_rows[:eval_n]
    finish_task(
        "drop",
        _task_shell(
            "drop",
            {"dataset": "drop", "hf_path": repo, "config": None, "revision": rev},
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "DROP passage + question; short answer (number/span/date)",
        ),
        train,
        eval_rows,
        "qa",
    )


def build_tydiqa(protocol: dict[str, Any]) -> None:
    repo = "google-research-datasets/tydiqa"
    rev = pin_dataset(repo)
    config = "secondary_task"
    train_raw = load_hf(repo, name=config, split="train", revision=rev)
    eval_pool = load_hf(repo, name=config, split="validation", revision=rev)
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), eval_n, eval_seed)

    def _row(prefix: str, i: int, rec: dict[str, Any], with_completion: bool) -> dict[str, Any]:
        golds = [str(x) for x in rec.get("answers", {}).get("text") or [] if str(x)]
        if not golds and rec.get("answer"):
            golds = [str(rec["answer"])]
        passage = rec.get("context") or rec.get("passage") or ""
        question = rec.get("question") or rec.get("question_text") or ""
        ref: dict[str, Any] = {"golds": golds or [""], "answer_type": "span"}
        if with_completion and golds:
            ref["completion"] = golds[0]
        return {
            "id": f"tydiqa-{prefix}-{i:05d}",
            "messages": [
                {
                    "role": "user",
                    "content": f"{passage}\n\nQuestion: {question}\nShort answer:",
                }
            ],
            "reference": ref,
        }

    train = downsample_train(
        [_row("train", i, rec, True) for i, rec in enumerate(train_raw)],
        cap,
        train_seed,
    )
    eval_rows = [_row("val", i, eval_pool[i], False) for i in eval_idx]
    finish_task(
        "tydiqa",
        _task_shell(
            "tydiqa",
            {"dataset": "tydiqa", "hf_path": repo, "config": config, "revision": rev},
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "TyDiQA-GoldP passage + question; short span answer",
        ),
        train,
        eval_rows,
        "qa",
    )


def build_mbpp(protocol: dict[str, Any]) -> None:
    repo = "google-research-datasets/mbpp"
    rev = pin_dataset(repo)
    config = "sanitized"
    train_raw = load_hf(repo, name=config, split="train", revision=rev)
    extra = []
    for split in ("prompt", "validation"):
        try:
            extra.extend(load_hf(repo, name=config, split=split, revision=rev))
        except Exception:  # noqa: BLE001
            LOG.warning("mbpp split %s missing", split)
    train_raw = train_raw + extra
    eval_pool = load_hf(repo, name=config, split="test", revision=rev)
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), min(eval_n, len(eval_pool)), eval_seed)
    if len(eval_pool) < eval_n:
        LOG.warning("mbpp test n=%s < 200; using all test rows", len(eval_pool))

    def _row(prefix: str, i: int, rec: dict[str, Any], with_completion: bool) -> dict[str, Any]:
        tests = rec.get("test_list") or rec.get("test") or []
        if isinstance(tests, list):
            tests_s = "\n".join(str(t) for t in tests)
        else:
            tests_s = str(tests)
        prompt = rec.get("text") or rec.get("prompt") or rec.get("description") or ""
        code = rec.get("code") or rec.get("source_code") or ""
        ref: dict[str, Any] = {"kind": "mbpp", "tests": tests_s}
        if with_completion:
            ref["completion"] = str(code)
        return {
            "id": f"mbpp-{prefix}-{i:05d}",
            "messages": [
                {
                    "role": "user",
                    "content": f"{prompt}\nWrite a Python function. Return only code.",
                }
            ],
            "reference": ref,
        }

    train = downsample_train(
        [_row("train", i, rec, True) for i, rec in enumerate(train_raw)],
        cap,
        train_seed,
    )
    eval_rows = [_row("test", i, eval_pool[i], False) for i in eval_idx]
    finish_task(
        "mbpp",
        _task_shell(
            "mbpp",
            {"dataset": "mbpp", "hf_path": repo, "config": config, "revision": rev},
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "MBPP sanitized prompt; official asserts in reference.tests",
        ),
        train,
        eval_rows,
        "code",
    )


def _load_jsonl_file(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_apps(protocol: dict[str, Any]) -> None:
    repo = "codeparrot/apps"
    rev = pin_dataset(repo)
    from huggingface_hub import hf_hub_download

    train_path = Path(
        hf_hub_download(
            repo, "train.jsonl", repo_type="dataset", revision=rev,
            cache_dir=str(ROOT / "data_cache" / "hf"),
        )
    )
    test_path = Path(
        hf_hub_download(
            repo, "test.jsonl", repo_type="dataset", revision=rev,
            cache_dir=str(ROOT / "data_cache" / "hf"),
        )
    )
    train_raw = [
        rec
        for rec in _load_jsonl_file(train_path)
        if str(rec.get("difficulty") or "").lower() == "introductory"
    ]
    eval_pool = [
        rec
        for rec in _load_jsonl_file(test_path)
        if str(rec.get("difficulty") or "").lower() == "introductory"
    ]
    if len(eval_pool) < 200:
        raise SystemExit(f"APPS introductory test n={len(eval_pool)} < 200")
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = sample_indices(len(eval_pool), eval_n, eval_seed)

    def _io(rec: dict[str, Any]) -> list[dict[str, str]]:
        raw = rec.get("input_output") or ""
        if isinstance(raw, dict):
            payload = raw
        else:
            try:
                sys.set_int_max_str_digits(0)
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {}
        inputs = payload.get("inputs") or []
        outputs = payload.get("outputs") or []
        return [
            {"input": str(inp), "output": str(out).strip()}
            for inp, out in zip(inputs, outputs)
        ]

    def _row(prefix: str, i: int, rec: dict[str, Any], with_completion: bool) -> dict[str, Any]:
        q = rec.get("question") or rec.get("problem") or ""
        sols = rec.get("solutions") or "[]"
        try:
            sol_list = json.loads(sols) if isinstance(sols, str) else list(sols)
        except json.JSONDecodeError:
            sol_list = []
        code = str(sol_list[0]) if sol_list else ""
        ref: dict[str, Any] = {"kind": "apps", "io": _io(rec)}
        if with_completion:
            ref["completion"] = code
        return {
            "id": f"apps-{prefix}-{i:05d}",
            "messages": [
                {
                    "role": "user",
                    "content": f"{q}\nWrite a Python solution. Return only code.",
                }
            ],
            "reference": ref,
        }

    train = downsample_train(
        [_row("train", i, rec, True) for i, rec in enumerate(train_raw)],
        cap,
        train_seed,
    )
    eval_rows = [_row("test", i, eval_pool[i], False) for i in eval_idx]
    finish_task(
        "apps",
        _task_shell(
            "apps",
            {
                "dataset": "apps",
                "hf_path": repo,
                "config": None,
                "revision": rev,
                "difficulty": "introductory",
            },
            len(train),
            len(eval_rows),
            {"eval_slice_seed": eval_seed, "train_sample_seed": train_seed},
            "APPS introductory only; IO tests in reference.io",
        ),
        train,
        eval_rows,
        "code",
    )


def build_bird(_protocol: dict[str, Any]) -> None:
    raise SystemExit(
        "BIRD pack is a separate boxed download (33.4GB / 1h / 40GB). "
        "Call --task bird after the zip is present."
    )


def build_superni_one(task_id: str, protocol: dict[str, Any], sha: str) -> None:
    path = NI_DIR / f"{task_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    definition = payload.get("Definition") or [""]
    defn = definition[0] if isinstance(definition, list) else str(definition)
    instances = payload.get("Instances") or []
    eval_n = int(protocol["eval"]["slice_n"])
    eval_seed = int(protocol["eval"]["slice_seed"])
    cap = int(protocol["full"]["cap"])
    train_seed = int(protocol["full"]["sample_seed"])
    eval_idx = set(sample_indices(len(instances), eval_n, eval_seed))
    eval_rows = []
    train_pool = []
    for i, inst in enumerate(instances):
        inst_id = str(inst.get("id") or f"{task_id}-{i:05d}")
        outputs = inst.get("output") or []
        if isinstance(outputs, str):
            outputs = [outputs]
        golds = [str(x) for x in outputs if str(x)]
        row = {
            "id": inst_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"{defn}\n\n{inst.get('input','')}".strip(),
                }
            ],
            "reference": {"golds": golds or [""]},
        }
        if i in eval_idx:
            eval_rows.append(row)
        else:
            if golds:
                row = {
                    **row,
                    "reference": {"golds": golds, "completion": golds[0]},
                }
            train_pool.append(row)
    train = downsample_train(train_pool, cap, train_seed)
    cats = payload.get("Categories") or ["unknown"]
    sources = payload.get("Source") or ["unknown"]
    finish_task(
        task_id,
        {
            "task_id": task_id,
            "source": {
                "dataset": "natural-instructions",
                "hf_path": None,
                "repo": "allenai/natural-instructions",
                "revision": sha,
                "filename": f"tasks/{task_id}.json",
                "category": cats[0] if isinstance(cats, list) else str(cats),
                "source_dataset": sources[0] if isinstance(sources, list) else str(sources),
            },
            "prior_label": None,
            "pool_ref": POOL_REF_NI,
            "splits": {
                "train_n": len(train),
                "eval_n": len(eval_rows),
                "seeds": {
                    "eval_slice_seed": eval_seed,
                    "train_sample_seed": train_seed,
                    "task_sample_seed": 20260822,
                },
            },
            "max_new_tokens": 128,
            "prompt_style": "SuperNI definition + instance input; normalized EM",
        },
        train,
        eval_rows,
        "em",
    )


def pack_v4(task_ids: list[str]) -> None:
    pack_tar(task_ids, version=4)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="comma task ids, or superni, or literature")
    parser.add_argument("--pack", action="store_true")
    args = parser.parse_args()
    protocol = load_protocol()
    ni_doc = json.loads(NI_LIST.read_text(encoding="utf-8"))
    ni_sha = str(ni_doc["sha"])
    ni_ids = [t["task_id"] for t in ni_doc["tasks"]]
    builders: dict[str, Callable[[], None]] = {
        "arc_easy": lambda: build_arc(protocol, "arc_easy", "ARC-Easy"),
        "arc_challenge": lambda: build_arc(protocol, "arc_challenge", "ARC-Challenge"),
        "hellaswag": lambda: build_hellaswag(protocol),
        "piqa": lambda: build_piqa(protocol),
        "math": lambda: build_math(protocol),
        "drop": lambda: build_drop(protocol),
        "tydiqa": lambda: build_tydiqa(protocol),
        "mbpp": lambda: build_mbpp(protocol),
        "apps": lambda: build_apps(protocol),
        "bird": lambda: build_bird(protocol),
    }
    wanted: list[str]
    if args.only == "superni":
        wanted = ni_ids
    elif args.only == "literature":
        wanted = list(LIT_IDS)
    elif args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
    elif args.pack:
        wanted = []
    else:
        wanted = list(LIT_IDS) + ni_ids
    for task_id in wanted:
        if task_id in builders:
            builders[task_id]()
        elif task_id in ni_ids:
            build_superni_one(task_id, protocol, ni_sha)
        else:
            raise SystemExit(f"unknown task {task_id}")
    if args.pack:
        present = [
            tid
            for tid in (LIT_IDS + ni_ids)
            if tid != "bird" and (TASKS_DIR / tid / "task.json").is_file()
        ]
        if len(present) != 59:
            raise SystemExit(f"refusing to pack v4: have {len(present)}/59 (bird is v5)")
        pack_tar(present, version=4)


if __name__ == "__main__":
    main()
