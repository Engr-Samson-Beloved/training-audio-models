# Group 2 CTE 442 — Speech Recognition Study

Research question: **How much do pretrained speech models outperform a classical
pipeline on Nigerian-accented English or a selected Nigerian language, and how much
does fine-tuning on a small original corpus close the gap?**

This repository implements the study protocol and its data pipeline. It contains no
original recordings, consent records, transcripts, experiment metrics, or research
conclusions. The generated `data/fixture/` material is labelled synthetic and exists
only to smoke-test plumbing; it is not intelligible speech and must never be reported
as corpus/model performance.

## Quick start: tiny synthetic fixture

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cte442 make-fixture
cte442 validate --manifest data/fixture/manifest.csv --converted-dir data/fixture/audio_16k
cte442 split --manifest data/fixture/manifest.csv --output data/fixture/splits.csv --seed 442
cte442 smoke-predictions --manifest data/fixture/manifest.csv --splits data/fixture/splits.csv --output data/fixture/predictions.csv
cte442 evaluate --manifest data/fixture/manifest.csv --splits data/fixture/splits.csv --predictions data/fixture/predictions.csv --output-dir results/fixture_smoke --bootstrap-samples 200 --seed 442
cte442 plot --metrics results/fixture_smoke/utterance_metrics.csv --output-dir results/fixture_smoke/plots
```

Or run the same sequence with `./scripts/run_fixture.sh`. The fixture predictions are
deliberately perturbed plumbing inputs, not the output of any ASR model.

## Visual research console

The local dashboard has no third-party Python dependencies and keeps all data on this
computer. It displays dataset readiness, experiment configurations, fixture plots/audio,
and can rerun the safe fixture simulation.

```bash
./scripts/launch_dashboard.sh
# Open http://127.0.0.1:8765

# Or open this directly without a server:
open dist/standalone.html
```

FFmpeg and SoX are recommended for inspecting and converting real recordings. The core
dashboard and fixture pipeline remain available without Streamlit or PyPI access.
The standalone view is read-only; use `./scripts/run_fixture.sh` to rerun the simulation.

## Original-corpus workflow

1. Obtain ethics/departmental approval and informed consent outside this repository.
2. Copy consent-cleared recordings under `data/original/audio/` and populate a manifest
   from `data/manifest_template.csv`. Do not put names or direct identifiers in it.
3. Review transcriptions with `cte442 review --manifest ... --output ...`.
4. Validate/convert, then create one frozen speaker-disjoint split file. Every model and
   every seed must use that exact split file and test-speaker list.
5. Install only the backend needed for an experiment, e.g. `pip install -e '.[classical]'`
   or `pip install -e '.[neural,transformers]'`.
6. Run `cte442 train --config configs/<experiment>.toml --manifest ... --splits ...` and
   then `cte442 infer`, `cte442 evaluate`, and `cte442 plot`.

See [STATUS.md](STATUS.md) for exact next-stage commands, limitations, and the distinction
between implemented orchestration and compute/data-dependent training.

## OpenSLR SLR70 public development workflow

SLR70 is imported only under `data/public/slr70/`. It is useful for integration checks and
public-development comparisons, but it is not a substitute for the Group 2 original corpus.

```bash
# Downloads about 1.21 GB, verifies archive hashes, extracts, converts and freezes splits.
./scripts/run_slr70_public.sh

# If the two official ZIPs were downloaded manually into data/public/slr70/raw/:
SLR70_OFFLINE=1 ./scripts/run_slr70_public.sh

# After installing all model extras and allocating suitable compute:
CTE442_RUN_MODE=full ./scripts/run_slr70_public.sh
```

The official source describes SLR70 as manually quality-checked Nigerian-English sentence
recordings from volunteers in Lagos and London. Its index does not expose a per-utterance
Lagos/London label, recording device, age, proficiency, or noise condition, so the importer
stores those fields as `unspecified` instead of inventing them.

## Study safeguards

- `corpus_kind` is mandatory and must be `fixture`, `public`, or `original`.
- Public imports and original-corpus ingress use separate commands and directories:
  `import-slr70` writes only public provenance; `import-original` rejects non-original rows.
- Speaker IDs, not utterances, are assigned to train/dev/test; overlap is rejected.
- The split artifact is reused across all comparisons.
- Fine-tuning hour subsets are nested and speaker-aware; they are drawn only from train.
- Five-seed aggregation reports mean, sample standard deviation, and 95% t confidence
  intervals. Paired speaker bootstrap intervals are supported for WER/CER comparisons.
- Timing and model-size fields are carried in every run record.
- Empty/missing demographic values are reported as `unspecified`, never inferred.

## Modules

`manifest`, `audio`, `review`, `split`, `training`, `inference`, `evaluation`, `plots`,
and `studies` are separate modules under `src/cte442_asr/`. Model adapters live under
`src/cte442_asr/models/`; the Streamlit app is `src/cte442_asr/demo.py`.

