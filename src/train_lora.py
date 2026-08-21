"""LoRA training (MANUAL §2, §6). Machine-agnostic; dry-run uses a tiny random Qwen2."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

from src.data import completion_from_reference

LOG = logging.getLogger("forge.train")
DRY_RUN_MODEL = "yujiepan/qwen2-tiny-random"
DRY_RUN_MAX_SEQ = 512


class CompletionDataset(Dataset):
    def __init__(
        self,
        rows: list[dict[str, Any]],
        tokenizer: Any,
        task_id: str,
        max_seq_len: int,
    ) -> None:
        self.examples: list[dict[str, list[int]]] = []
        for row in rows:
            prompt = tokenizer.apply_chat_template(
                row["messages"],
                tokenize=False,
                add_generation_prompt=True,
            )
            completion = completion_from_reference(task_id, row["reference"])
            full = tokenizer.apply_chat_template(
                row["messages"] + [{"role": "assistant", "content": completion}],
                tokenize=False,
                add_generation_prompt=False,
            )
            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
            if full_ids[: len(prompt_ids)] != prompt_ids:
                prompt_len = min(len(prompt_ids), len(full_ids) - 1)
            else:
                prompt_len = len(prompt_ids)
            if len(full_ids) > max_seq_len:
                full_ids = full_ids[:max_seq_len]
                prompt_len = min(prompt_len, max_seq_len - 1)
            labels = [-100] * prompt_len + full_ids[prompt_len:]
            if all(x == -100 for x in labels):
                labels[-1] = full_ids[-1]
            self.examples.append(
                {
                    "input_ids": full_ids,
                    "labels": labels,
                    "attention_mask": [1] * len(full_ids),
                }
            )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, list[int]]:
        return self.examples[index]


def _collate(batch: list[dict[str, list[int]]], pad_id: int) -> dict[str, torch.Tensor]:
    max_len = max(len(item["input_ids"]) for item in batch)
    input_ids, labels, mask = [], [], []
    for item in batch:
        pad = max_len - len(item["input_ids"])
        input_ids.append(item["input_ids"] + [pad_id] * pad)
        labels.append(item["labels"] + [-100] * pad)
        mask.append(item["attention_mask"] + [0] * pad)
    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "labels": torch.tensor(labels, dtype=torch.long),
        "attention_mask": torch.tensor(mask, dtype=torch.long),
    }


def resolve_device(dry_run: bool) -> torch.device:
    if dry_run:
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def resolve_revision(protocol: dict[str, Any], dry_run: bool) -> str | None:
    if dry_run:
        return None
    rev = protocol.get("base_revision")
    if rev in (None, "PIN_AT_ENV_SETUP"):
        return None
    return str(rev)


def load_tokenizer(model_name: str, revision: str | None) -> Any:
    kwargs: dict[str, Any] = {}
    if revision:
        kwargs["revision"] = revision
    tokenizer = AutoTokenizer.from_pretrained(model_name, **kwargs)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if not tokenizer.chat_template:
        tokenizer.chat_template = (
            "{% for message in messages %}"
            "{{ '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>\n' }}"
            "{% endfor %}"
            "{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
        )
    return tokenizer


def load_base_model(
    protocol: dict[str, Any],
    dry_run: bool,
    device: torch.device,
) -> tuple[Any, Any, str, str | None]:
    if dry_run:
        model_name = DRY_RUN_MODEL
        revision = None
        dtype = torch.float32
    else:
        model_name = str(protocol["base_model"])
        revision = resolve_revision(protocol, dry_run=False)
        dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    kwargs: dict[str, Any] = {"torch_dtype": dtype}
    if revision:
        kwargs["revision"] = revision
    tokenizer = load_tokenizer(model_name, revision)
    model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)
    model.to(device)
    resolved = getattr(getattr(model, "config", None), "_name_or_path", model_name)
    try:
        from huggingface_hub import model_info

        info = model_info(model_name, revision=revision)
        resolved_rev = info.sha
    except Exception as exc:  # noqa: BLE001
        LOG.warning("could not resolve hub sha for %s: %s", model_name, exc)
        resolved_rev = revision
    LOG.info("loaded model=%s revision=%s params~device=%s", model_name, resolved_rev, device)
    model.config.pad_token_id = tokenizer.pad_token_id
    return model, tokenizer, resolved, resolved_rev


def attach_lora(model: Any, protocol: dict[str, Any], dry_run: bool) -> Any:
    spec = protocol["lora"]
    wanted = list(spec["target_modules"])
    present = {name.split(".")[-1] for name, _ in model.named_modules()}
    targets = [name for name in wanted if name in present]
    missing = [name for name in wanted if name not in present]
    if missing:
        if dry_run:
            LOG.warning("dry-run missing LoRA targets %s; using %s", missing, targets)
        else:
            raise SystemExit(f"missing LoRA target_modules: {missing}")
    if not targets:
        raise SystemExit("no LoRA target_modules present on the model")
    config = LoraConfig(
        r=int(spec["r"]),
        lora_alpha=int(spec["alpha"]),
        lora_dropout=float(spec["dropout"]),
        target_modules=targets,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    return get_peft_model(model, config)


def load_adapter(base_model: Any, adapter_dir: Path) -> Any:
    return PeftModel.from_pretrained(base_model, str(adapter_dir))


def train_lora(
    model: Any,
    tokenizer: Any,
    rows: list[dict[str, Any]],
    task_id: str,
    protocol: dict[str, Any],
    device: torch.device,
    steps: int,
    out_dir: Path,
    dry_run: bool,
    seed: int,
) -> None:
    torch.manual_seed(seed)
    max_seq_len = DRY_RUN_MAX_SEQ if dry_run else int(protocol["max_seq_len"])
    dataset = CompletionDataset(rows, tokenizer, task_id, max_seq_len=max_seq_len)
    if len(dataset) == 0:
        raise SystemExit("empty train split")
    train_cfg = protocol["train"]
    batch_size = int(train_cfg["per_device_batch"])
    grad_accum = 1 if dry_run else int(train_cfg["grad_accum"])
    pad_id = tokenizer.pad_token_id
    loader = DataLoader(
        dataset,
        batch_size=min(batch_size, len(dataset)),
        shuffle=True,
        collate_fn=lambda batch: _collate(batch, pad_id),
        num_workers=0,
    )
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(train_cfg["lr"]))
    warmup = max(0, int(steps * float(train_cfg["warmup_ratio"])))
    scheduler = get_cosine_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup, num_training_steps=max(steps, 1)
    )
    updates = 0
    micro = 0
    optimizer.zero_grad(set_to_none=True)
    while updates < steps:
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            loss = model(**batch).loss
            (loss / grad_accum).backward()
            micro += 1
            if micro % grad_accum == 0:
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                updates += 1
                LOG.info(
                    "train step %s/%s loss=%s", updates, steps, float(loss.detach())
                )
            if updates >= steps:
                break
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
