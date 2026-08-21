"""Greedy (and sampled) generation + verifier (MANUAL §5-6)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch

LOG = logging.getLogger("forge.eval")


def _generate_one(
    model: Any,
    tokenizer: Any,
    messages: list[dict[str, str]],
    max_new_tokens: int,
    device: torch.device,
    do_sample: bool,
    temperature: float,
    top_p: float,
    num_return: int,
) -> list[str]:
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    encoded = tokenizer(prompt, return_tensors="pt")
    encoded = {key: value.to(device) for key, value in encoded.items()}
    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "num_return_sequences": num_return,
    }
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = top_p
    model.eval()
    with torch.no_grad():
        out = model.generate(**encoded, **gen_kwargs)
    prompt_len = encoded["input_ids"].shape[1]
    texts = []
    for seq in out:
        texts.append(
            tokenizer.decode(seq[prompt_len:], skip_special_tokens=True)
        )
    return texts


def eval_split(
    model: Any,
    tokenizer: Any,
    rows: list[dict[str, Any]],
    verifier: Any,
    max_new_tokens: int,
    device: torch.device,
    do_sample: bool = False,
    temperature: float = 0.0,
    top_p: float = 1.0,
    num_return: int = 1,
    extract_div_path: Path | None = None,
) -> list[dict[str, Any]]:
    results = []
    for row in rows:
        texts = _generate_one(
            model,
            tokenizer,
            row["messages"],
            max_new_tokens=max_new_tokens,
            device=device,
            do_sample=do_sample,
            temperature=temperature,
            top_p=top_p,
            num_return=num_return,
        )
        per_seq = []
        for text in texts:
            verdict = verifier.verify(text, row["reference"])
            per_seq.append(
                {
                    "output": text,
                    "pass": bool(verdict["pass"]),
                    "parsed": verdict.get("parsed"),
                    "note": verdict.get("note"),
                }
            )
            if extract_div_path is not None:
                try:
                    note = json.loads(verdict.get("note") or "{}")
                except json.JSONDecodeError:
                    note = {}
                if note.get("diverge"):
                    with extract_div_path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            json.dumps(
                                {"id": row["id"], "output": text, "note": note},
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
        results.append({"id": row["id"], "samples": per_seq})
    return results
