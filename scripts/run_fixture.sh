#!/usr/bin/env bash
set -euo pipefail

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

"$PYTHON_BIN" -m cte442_asr.cli make-fixture
"$PYTHON_BIN" -m cte442_asr.cli validate --manifest data/fixture/manifest.csv --converted-dir data/fixture/audio_16k
"$PYTHON_BIN" -m cte442_asr.cli split --manifest data/fixture/manifest.csv --output data/fixture/splits.csv --seed 442
"$PYTHON_BIN" -m cte442_asr.cli smoke-predictions --manifest data/fixture/manifest.csv --splits data/fixture/splits.csv --output data/fixture/predictions.csv
"$PYTHON_BIN" -m cte442_asr.cli evaluate --manifest data/fixture/manifest.csv --splits data/fixture/splits.csv --predictions data/fixture/predictions.csv --output-dir results/fixture_smoke --bootstrap-samples 200 --seed 442
"$PYTHON_BIN" -m cte442_asr.cli plot --metrics results/fixture_smoke/utterance_metrics.csv --output-dir results/fixture_smoke/plots
echo "Fixture pipeline complete. Outputs are plumbing tests, NOT ASR research results."

