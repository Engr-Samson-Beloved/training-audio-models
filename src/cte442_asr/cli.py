"""Command-line interface for the research pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="cte442")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("make-fixture")
    slr70 = sub.add_parser("import-slr70")
    slr70.add_argument("--root", default="data/public/slr70")
    slr70.add_argument("--no-download", action="store_true")
    slr70.add_argument("--no-extract", action="store_true")
    slr70.add_argument("--limit", type=int)
    slr70.add_argument("--allow-partial", action="store_true")
    original = sub.add_parser("import-original")
    original.add_argument("--source-manifest", required=True)
    original.add_argument("--destination", default="data/original/manifest.csv")
    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8765)
    validate = sub.add_parser("validate"); validate.add_argument("--manifest", required=True)
    validate.add_argument("--converted-dir", required=True); validate.add_argument("--report")
    validate.add_argument("--converted-manifest")
    split = sub.add_parser("split"); split.add_argument("--manifest", required=True); split.add_argument("--output", required=True); split.add_argument("--seed", type=int, default=442)
    review = sub.add_parser("review"); review.add_argument("--manifest", required=True); review.add_argument("--output", required=True)
    smoke = sub.add_parser("smoke-predictions"); smoke.add_argument("--manifest", required=True); smoke.add_argument("--splits", required=True); smoke.add_argument("--output", required=True)
    evaluate = sub.add_parser("evaluate"); evaluate.add_argument("--manifest", required=True); evaluate.add_argument("--splits", required=True); evaluate.add_argument("--predictions", required=True); evaluate.add_argument("--output-dir", required=True); evaluate.add_argument("--bootstrap-samples", type=int, default=2000); evaluate.add_argument("--seed", type=int, default=442)
    plot = sub.add_parser("plot"); plot.add_argument("--metrics", required=True); plot.add_argument("--output-dir", required=True)
    train = sub.add_parser("train"); train.add_argument("--config", required=True); train.add_argument("--manifest", required=True); train.add_argument("--splits", required=True); train.add_argument("--output-dir", default="results/runs"); train.add_argument("--execute", action="store_true")
    study = sub.add_parser("study-plan"); study.add_argument("--config", required=True); study.add_argument("--manifest", required=True); study.add_argument("--splits", required=True); study.add_argument("--output-dir", required=True)
    rescore = sub.add_parser("rescore"); rescore.add_argument("--nbest", required=True); rescore.add_argument("--output", required=True); rescore.add_argument("--lm-weight", type=float, default=0.3)
    return root


def main(argv=None) -> int:
    ns = parser().parse_args(argv)
    try:
        if ns.command == "make-fixture":
            from .fixture import make_fixture; print(make_fixture())
        elif ns.command == "import-slr70":
            from .datasets.slr70 import import_slr70
            print(import_slr70(ns.root, not ns.no_download, not ns.no_extract, ns.limit,
                               not ns.allow_partial))
        elif ns.command == "import-original":
            from .datasets.original import import_original
            print(import_original(ns.source_manifest, ns.destination))
        elif ns.command == "dashboard":
            from .webapp import main as dashboard_main
            dashboard_main(["--host", ns.host, "--port", str(ns.port)])
        elif ns.command == "validate":
            from .audio import validate_and_convert
            report = ns.report or str(Path(ns.converted_dir) / "validation.csv")
            converted_manifest = ns.converted_manifest or str(Path(ns.converted_dir) / "manifest.csv")
            failures = validate_and_convert(ns.manifest, ns.converted_dir, report, converted_manifest)
            print(f"validation_failures={failures} report={report} converted_manifest={converted_manifest}")
            if failures: return 2
        elif ns.command == "split":
            from .split import split_fingerprint, write_splits
            write_splits(ns.manifest, ns.output, ns.seed); print(f"split_fingerprint={split_fingerprint(ns.output)}")
        elif ns.command == "review":
            from .review import review_manifest; review_manifest(ns.manifest, ns.output)
        elif ns.command == "smoke-predictions":
            from .fixture import smoke_predictions; smoke_predictions(ns.manifest, ns.splits, ns.output)
        elif ns.command == "evaluate":
            from .evaluation import evaluate_files
            evaluate_files(ns.manifest, ns.splits, ns.predictions, ns.output_dir, ns.bootstrap_samples, ns.seed)
        elif ns.command == "plot":
            from .plots import plot_metrics; plot_metrics(ns.metrics, ns.output_dir)
        elif ns.command == "train":
            from .training import prepare_run; print(prepare_run(ns.config, ns.manifest, ns.splits, ns.output_dir, ns.execute))
        elif ns.command == "study-plan":
            from .studies import build_study_plan; print(build_study_plan(ns.config, ns.manifest, ns.splits, ns.output_dir))
        elif ns.command == "rescore":
            from .studies import rescore_nbest; rescore_nbest(ns.nbest, ns.output, ns.lm_weight)
        return 0
    except (ValueError, OSError, ModuleNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())

