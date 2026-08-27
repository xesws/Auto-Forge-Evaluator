#!/bin/bash
# Build an anonymized supplementary zip for anonymous.4open.science.
# Operator uploads by hand. No usernames, no .git, no ledger hosts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%MZ)"
OUT="${ROOT}/paper/supplementary/anonymous_supp_${STAMP}.zip"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/analysis" "$STAGE/metrics" "$STAGE/eval" "$STAGE/prereg" "$STAGE/protocol"

cp "$ROOT/scripts/analysis.py" "$STAGE/analysis/"
cp "$ROOT/scripts/analysis_v2.py" "$STAGE/analysis/"
cp "$ROOT/scripts/plot_v2_figures.py" "$STAGE/analysis/"
cp "$ROOT/docs/ANALYSIS_RESULTS_v2.md" "$STAGE/analysis/"
python3 - "$ROOT/docs/ANALYSIS_RESULTS_v2.json" "$STAGE/analysis/ANALYSIS_RESULTS_v2.json" <<'PY'
import json, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
d = json.loads(src.read_text())
d["run_dirs"] = ["metrics/" + t for t in d["task_ids"]]
dst.write_text(json.dumps(d, indent=2) + "\n")
PY
cp "$ROOT/docs/ANALYSIS_RESULTS.md" "$STAGE/analysis/"
cp "$ROOT/paper/supplementary/ANALYSIS_PREREG_en.md" "$STAGE/prereg/"
cp "$ROOT/docs/ANALYSIS_PREREG.md" "$STAGE/prereg/ANALYSIS_PREREG.zh.md"
cp "$ROOT/docs/ANALYSIS_PREREG_V2.md" "$STAGE/prereg/"
cp "$ROOT/configs/protocol_v2.yaml" "$STAGE/protocol/"

python3 - "$ROOT" "$STAGE" <<'PY'
import json, shutil, sys
from pathlib import Path
root, stage = Path(sys.argv[1]), Path(sys.argv[2])
blob = json.loads((root / "docs" / "ANALYSIS_RESULTS_v2.json").read_text())
for i, d in enumerate(blob["run_dirs"]):
    src = Path(d)
    tid = blob["task_ids"][i]
    dest = stage / "metrics" / tid
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("metrics.json", "STATUS", "journal.jsonl"):
        p = src / name
        if p.is_file():
            shutil.copy2(p, dest / name)
    ev = stage / "eval" / tid
    ev.mkdir(parents=True, exist_ok=True)
    for name in ("eval_base_greedy.jsonl", "eval_full_greedy.jsonl", "eval_pilot_greedy.jsonl"):
        p = src / name
        if p.is_file():
            shutil.copy2(p, ev / name)
print("copied", len(blob["task_ids"]), "tasks")
PY

cat > "$STAGE/README.md" <<'EOF'
# Anonymous supplementary archive

- `analysis/` — registered analysis.py, revision analysis_v2.py, RESULTS_v2
- `metrics/` — per-task metrics.json + journal + STATUS
- `eval/` — paired greedy jsonl used for McNemar
- `prereg/` — English translation + Chinese originals (Chinese wins)
- `protocol/` — frozen protocol_v2.yaml

No author names, hosts, or repository URLs.
Run on CPU: `python analysis/analysis_v2.py` from a checkout that has `runs/`.
EOF

(cd "$STAGE" && zip -qr "$OUT" .)
echo "wrote $OUT"
ls -lh "$OUT"
