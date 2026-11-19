# Project status — 19 November 2026

## What runs now

- A dependency-free, synthetic **non-speech** fixture exercises manifest parsing,
  WAV inspection, 16 kHz mono conversion, speaker-disjoint splitting, deliberately
  supplied smoke hypotheses, WER/CER, group slices, speaker-cluster bootstrap intervals,
  five-seed summaries, and SVG plots.
- Manifest review, provenance checks, split leakage checks/fingerprints, nested 1/2/5/10
  hour subset planning, timing/model-size capture, and n-best LM-score rescoring are wired.
- Executable optional backends exist for a word-segmental MFCC+GMM-HMM baseline, a
  CNN-BiLSTM CTC model, Hugging Face wav2vec 2.0, and Whisper-small. Zero-shot and
  fine-tune modes use separate configurations.
- The Streamlit UI inspects a manifest/predictions pair and prominently warns whenever
  provenance is not `original`.
- A zero-dependency local dashboard at `http://127.0.0.1:8765` shows dataset readiness,
  installed tools, configurations, plots, fixture audio, and a safe simulation control.
- `dist/standalone.html` provides the same visual overview without a server. It is read-only
  and can be opened directly in a browser.
- The SLR70 importer downloads the official archives sequentially with resumable partial
  files, verifies published SHA-256 values, blocks ZIP path traversal, derives and audits
  speaker IDs, records only source-supported metadata, and labels every row `public`.
- Original recordings have a separate `import-original` command which rejects public and
  fixture manifests and requires original-corpus consent references.

No model experiment has been run and this repository contains **no observed ASR metric**.
Generated fixture metrics only verify arithmetic and file flow. They are not estimates of
accuracy and must not appear in the report as findings.

The SLR70 importer and the full convert/split/evaluate/plot plumbing were verified with a
local archive-layout test whose hypotheses are explicitly labelled `NOT_ASR`. The official
1.21 GB corpus could not be downloaded in this execution
environment because terminal, browser, and JavaScript network paths were blocked. Therefore
there are no SLR70 audio-validation or model results in this repository yet.

## Needs real recordings / project decisions

- Ethics/consent approval, consent records, language choice, prompt list, recording
  protocol, pseudonymous speaker recruitment, and the original recordings/transcripts.
- Enough consent-cleared training audio for each requested 1/2/5/10 h subset. The study
  planner refuses an hour target that the training split cannot meet.
- Review/adjudication of transcripts, including a written orthography and text
  normalization policy for the chosen local language.
- A pronunciation lexicon and an externally trained or train-only language model for the
  GMM-HMM/CTC rescoring ablation. LM training must not see dev/test transcripts.
- GPU/compute selection and actual runs. Inspect learning curves and errors before setting
  final epochs; preserve the frozen test speakers.
- The included classical recipe is a deliberately simple, closed-vocabulary word
  GMM-HMM with equal-duration boundary initialization. Document that limitation. For a
  publication-strength phone system, supply the pronunciation lexicon named in the
  config and replace the initializer with train-only forced alignments.

## Exact next-stage commands

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,audio]'

# Public development data (kept separate from the original corpus):
cte442 import-slr70 --root data/public/slr70
./scripts/run_slr70_public.sh
# If browser-downloaded official ZIPs are placed under data/public/slr70/raw/:
SLR70_OFFLINE=1 ./scripts/run_slr70_public.sh
# Full five-seed/model matrix after installing all extras and allocating compute:
python -m pip install -e '.[all]'
CTE442_RUN_MODE=full ./scripts/run_slr70_public.sh

# After approved recordings + initial annotations have been added:
cp data/manifest_template.csv data/original/manifest.csv
# Populate it; do not put names/direct identifiers in the manifest.
cte442 import-original --source-manifest data/original/manifest.csv \
  --destination data/original/manifest.checked.csv
cte442 review --manifest data/original/manifest.checked.csv --output data/original/manifest.reviewed.csv
cte442 validate --manifest data/original/manifest.reviewed.csv \
  --converted-dir data/original/audio_16k \
  --converted-manifest data/original/manifest.16k.csv \
  --report reports/audio_validation.csv
cte442 split --manifest data/original/manifest.16k.csv \
  --output data/original/splits_frozen.csv --seed 442

# Validate all plans before spending compute:
for cfg in configs/*.toml; do
  cte442 train --config "$cfg" --manifest data/original/manifest.16k.csv \
    --splits data/original/splits_frozen.csv --output-dir results/plans
done
cte442 study-plan --config configs/wav2vec2_finetune.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv \
  --output-dir results/study_plans/wav2vec2
cte442 study-plan --config configs/whisper_small_finetune.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv \
  --output-dir results/study_plans/whisper

# Install each required backend, then execute one experiment at a time:
python -m pip install -e '.[classical]'
cte442 train --execute --config configs/mfcc_gmm_hmm.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv

python -m pip install -e '.[neural]'
cte442 train --execute --config configs/cnn_bilstm_ctc.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv

python -m pip install -e '.[transformers,audio]'
cte442 train --execute --config configs/wav2vec2_zeroshot.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv
cte442 train --execute --config configs/wav2vec2_finetune.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv
cte442 train --execute --config configs/whisper_small_zeroshot.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv
cte442 train --execute --config configs/whisper_small_finetune.toml \
  --manifest data/original/manifest.16k.csv --splits data/original/splits_frozen.csv

# For each predictions.csv produced:
cte442 evaluate --manifest data/original/manifest.16k.csv \
  --splits data/original/splits_frozen.csv --predictions PATH/TO/predictions.csv \
  --output-dir PATH/TO/evaluation --bootstrap-samples 10000 --seed 442
cte442 plot --metrics PATH/TO/evaluation/utterance_metrics.csv \
  --output-dir PATH/TO/evaluation/plots

# LM ablation after a decoder has exported n-best rows containing the normal prediction
# columns plus rank, acoustic_logprob, and train-only-LM lm_logprob:
cte442 rescore --nbest PATH/TO/nbest.csv \
  --output PATH/TO/predictions.lm_rescored.csv --lm-weight 0.3
cte442 evaluate --manifest data/original/manifest.16k.csv \
  --splits data/original/splits_frozen.csv \
  --predictions PATH/TO/predictions.lm_rescored.csv \
  --output-dir PATH/TO/evaluation_lm --bootstrap-samples 10000 --seed 442

# Demo (inspection only):
python -m pip install -e '.[demo]'
streamlit run src/cte442_asr/demo.py
```

## Method note

Use the same frozen split artifact for every run. Treat speaker as the resampling unit.
Report both per-seed values and mean ± sample SD with 95% t intervals. Compare systems
with paired test-speaker bootstrap intervals, not by overlapping/unpaired utterance
intervals. Slice estimates with very few speakers should be labelled exploratory.

