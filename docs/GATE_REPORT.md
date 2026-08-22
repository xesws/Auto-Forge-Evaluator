# Gate 0 / Gate 1 报告

pod: `forge-or-not` (NVIDIA A40). protocol `pv2`, tasks `tv3`.
本地产物: `runs/`（gitignore）与 `runs/forge_runs.tar.gz`
sha256 `f34668737c2653e2c221237df5e66b7a2a40a38b0b4772fbfd372e0cbe3b8552`（403MB，与 pod `/tmp/forge_runs.tar.gz` 一致）。

## 三行主表

| task | base_p1 | Δ_pilot | Δ_full | 目录 |
|---|---|---|---|---|
| gsm8k | 0.69 | −0.335 | −0.230 | `runs/gsm8k__pv2__tv3__20260821-1038/` |
| winogrande | 0.56 | −0.055 | +0.190 | `runs/winogrande__pv2__tv3__20260821-2105/` |
| spider | 0.495 | −0.155 | +0.150 | `runs/spider__pv2__tv3__20260821-2137/` |

逐条对错: 各目录 `eval_*_greedy.jsonl`。LoRA: `adapters/pilot/`、`adapters/full/`。总表: `metrics.json`。

## 五眼

| | gsm8k | winogrande | spider |
|---|---|---|---|
| unparseable | 0/200 = 0% | 0/200 = 0% | 1/200 = 0.5% |
| extract_div 行数 | 0（无文件） | 0（无文件） | 0（无文件） |
| S2 pilot loss | 0.449 → 3.67e-05 | 0.733 → 2.41e-05 | 0.482 → 9.52e-05 |
| base pass@1（40–75 带） | 0.69 | 0.56 | 0.495 |
| systems | 三套均齐: torch 2.11.0+cu128, transformers 5.15.1, CUDA 12.8, driver 570.195.03, NVIDIA A40, revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, dry_run false | | |
| greedy 复跑 mismatch | 0/200 | 0/200 | 0/200 |

Gate 0 通过（五眼+确定性全绿）。gsm8k 负 Δ 判定为格式覆盖伴随推理退化。

## format_compliance（派生，未升协议）

- gsm8k base: `####` 58 / last-number 142 / none 0 / diverge 0；pilot 与 full 均为 `####` 200
- winogrande base: A 119 / B 81 / unparseable 0；full: A 105 / B 95
- spider base: parsed 199 / unparseable 1；full: parsed 200。SQL `OperationalError` base 34 / full 30

## 墙钟（S0 start → S6 done）

- gsm8k ≈ 2.16 h（S1 56 min 为主）
- winogrande ≈ 0.51 h（S4 27 min 为主）
- spider 有效 GPU ≈ 2.22 h（含 S4 重训 84 min；另有中途被杀的半截 S4 ≈ 0.9 h）
- 有效合计 ≈ 4.9 GPU·h。A40 TDP 300 W × 4.9 h ≈ 1.5 kWh 上限。

## 停点

等协议评审: pilot 10×100 练到 loss ~1e-5 = 背诵，要不要进 protocol_v3。量产前定死。
