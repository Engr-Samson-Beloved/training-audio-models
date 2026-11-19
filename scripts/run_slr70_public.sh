#!/usr/bin/env bash
set -euo pipefail

SLR70_ROOT="${SLR70_ROOT:-data/public/slr70}"
RUN_MODE="${CTE442_RUN_MODE:-prepare}"
OFFLINE="${SLR70_OFFLINE:-0}"
if [[ -n "${CTE442_PYTHON:-}" ]]; then
  PYTHON_BIN="$CTE442_PYTHON"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
else
  PYTHON_BIN="python3"
fi
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "$OFFLINE" == "1" ]]; then
  "$PYTHON_BIN" -m cte442_asr.cli import-slr70 --root "$SLR70_ROOT" --no-download
else
  "$PYTHON_BIN" -m cte442_asr.cli import-slr70 --root "$SLR70_ROOT"
fi
"$PYTHON_BIN" -m cte442_asr.cli validate \
  --manifest "$SLR70_ROOT/manifest.csv" \
  --converted-dir "$SLR70_ROOT/audio_16k" \
  --converted-manifest "$SLR70_ROOT/manifest.16k.csv" \
  --report "reports/slr70_audio_validation.csv"
"$PYTHON_BIN" -m cte442_asr.cli split \
  --manifest "$SLR70_ROOT/manifest.16k.csv" \
  --output "$SLR70_ROOT/splits_frozen.csv" --seed 442

for cfg in configs/*.toml; do
  "$PYTHON_BIN" -m cte442_asr.cli train --config "$cfg" \
    --manifest "$SLR70_ROOT/manifest.16k.csv" \
    --splits "$SLR70_ROOT/splits_frozen.csv" \
    --output-dir results/slr70/plans
done

if [[ "$RUN_MODE" == "full" ]]; then
  for cfg in configs/*.toml; do
    "$PYTHON_BIN" -m cte442_asr.cli train --execute --config "$cfg" \
      --manifest "$SLR70_ROOT/manifest.16k.csv" \
      --splits "$SLR70_ROOT/splits_frozen.csv" \
      --output-dir results/slr70/runs
    experiment="$(basename "$cfg" .toml)"
    "$PYTHON_BIN" -m cte442_asr.cli evaluate \
      --manifest "$SLR70_ROOT/manifest.16k.csv" \
      --splits "$SLR70_ROOT/splits_frozen.csv" \
      --predictions "results/slr70/runs/$experiment/predictions.csv" \
      --output-dir "results/slr70/evaluation/$experiment" \
      --bootstrap-samples 10000 --seed 442
    "$PYTHON_BIN" -m cte442_asr.cli plot \
      --metrics "results/slr70/evaluation/$experiment/utterance_metrics.csv" \
      --output-dir "results/slr70/evaluation/$experiment/plots"
  done
else
  echo "SLR70 prepared and plans verified. Set CTE442_RUN_MODE=full after installing model extras."
fi

echo "All SLR70 outputs are PUBLIC DEVELOPMENT results, never original-corpus results."

