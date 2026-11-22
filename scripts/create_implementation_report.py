#!/usr/bin/env python3
"""Create an evidence-based CTE 442 implementation report from local artifacts."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/CTE442_Group2_Implementation_Report.pdf"
NAVY = colors.HexColor("#182d63")
GOLD = colors.HexColor("#e5b80b")
TEAL = colors.HexColor("#087a72")
INK = colors.HexColor("#182438")
MUTED = colors.HexColor("#54657a")
PALE = colors.HexColor("#edf3fb")
GREEN = colors.HexColor("#e7f7f0")

MEMBERS = [
    ("1", "AKINKUNLE ADAM<br/>(GROUP LEADER)", "F/HD/24/3410044"),
    ("2", "[name]", "F/HD/24/3410050"),
    ("3", "[name]", "F/HD/24/3410062"),
    ("4", "[name]", "F/HD/24/3410068"),
    ("5", "[name]", "F/HD/24/3410046"),
    ("6", "[name]", "F/HD/24/3410080"),
    ("7", "[name]", "F/HD/24/3410082"),
    ("8", "[name]", "F/HD/24/3410051"),
    ("9", "[name]", "F/HD/24/3410047"),
    ("10", "[name]", "F/HD/24/34100066"),
    ("11", "[name]", "F/HD/24/3410052"),
    ("12", "[name]", "F/HD/24/3410045"),
    ("13", "[name]", "F/HD/24/3410089"),
]


class Rule(Flowable):
    def __init__(self, width=16.5 * cm, color=GOLD, thickness=2):
        super().__init__(); self.width = width; self.color = color; self.thickness = thickness

    def wrap(self, avail_width, avail_height): return min(self.width, avail_width), self.thickness + 4

    def draw(self):
        self.canv.setStrokeColor(self.color); self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.width, 2)


def read_snapshot() -> dict:
    manifest_path = ROOT / "data/public/slr70/manifest.16k.csv"
    splits_path = ROOT / "data/public/slr70/splits_frozen.csv"
    manifest = list(csv.DictReader(manifest_path.open(newline="", encoding="utf-8-sig")))
    splits = {row["utterance_id"]: row["split"] for row in csv.DictReader(splits_path.open(newline="", encoding="utf-8-sig"))}
    counts, hours, speakers = Counter(), defaultdict(float), defaultdict(set)
    for row in manifest:
        split = splits[row["utterance_id"]]; counts[split] += 1
        hours[split] += float(row["duration_seconds"]); speakers[split].add(row["speaker_id"])
    results = []
    for path in sorted((ROOT / "results/slr70/evaluation").glob("*/seed_summary.csv")):
        rows = list(csv.DictReader(path.open(newline="", encoding="utf-8-sig")))
        by_metric = {r["metric"]: r for r in rows if r.get("dimension") == "overall" and r.get("group") == "all"}
        if "wer" in by_metric and "cer" in by_metric:
            wer, cer = by_metric["wer"], by_metric["cer"]
            results.append({"model": wer["model"], "seeds": wer["n_seeds"], "wer": float(wer["mean"]),
                            "cer": float(cer["mean"]), "low": float(wer["ci95_low"]), "high": float(wer["ci95_high"])})
    cnn_path = ROOT / "results/slr70/runs/cnn_bilstm_ctc/run.json"
    cnn = json.loads(cnn_path.read_text(encoding="utf-8")) if cnn_path.exists() else {"status": "not started", "config": {"seeds": []}}
    cnn_done = len(list(cnn_path.parent.glob("seed*/predictions.csv"))) if cnn_path.exists() else 0
    return {"manifest": manifest, "counts": counts, "hours": hours, "speakers": speakers,
            "results": results, "cnn_status": cnn.get("status", "unknown"),
            "cnn_done": cnn_done, "cnn_expected": len(cnn.get("config", {}).get("seeds", []))}


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22,
                                 leading=27, alignment=TA_CENTER, textColor=NAVY, spaceAfter=13),
        "cover": ParagraphStyle("Cover", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=15,
                                 leading=20, alignment=TA_CENTER, textColor=INK, spaceAfter=6),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16,
                              leading=20, textColor=NAVY, spaceBefore=10, spaceAfter=8),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
                              leading=15, textColor=TEAL, spaceBefore=8, spaceAfter=5),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.6,
                                leading=14.2, alignment=TA_JUSTIFY, textColor=INK, spaceAfter=7),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=8.3,
                                 leading=11, textColor=MUTED, spaceAfter=5),
        "table": ParagraphStyle("Table", parent=base["BodyText"], fontName="Helvetica", fontSize=8.1,
                                 leading=10.2, textColor=INK),
        "tablehead": ParagraphStyle("TableHead", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.1,
                                     leading=10, textColor=colors.white, alignment=TA_CENTER),
        "callout": ParagraphStyle("Callout", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9.6,
                                   leading=13.5, textColor=colors.HexColor("#064e46")),
    }


def p(text, style): return Paragraph(text, style)


def page_number(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setStrokeColor(colors.HexColor("#d7e0ec")); canvas.setLineWidth(.5)
        canvas.line(1.8 * cm, 1.35 * cm, A4[0] - 1.8 * cm, 1.35 * cm)
        canvas.setFont("Helvetica", 8); canvas.setFillColor(MUTED)
        canvas.drawString(1.8 * cm, .85 * cm, "CTE 442 Group 2 - Implementation Report")
        canvas.drawRightString(A4[0] - 1.8 * cm, .85 * cm, f"Page {doc.page}")
    canvas.restoreState()


def table(data, widths, styles):
    converted = []
    for row_index, row in enumerate(data):
        style = styles["tablehead"] if row_index == 0 else styles["table"]
        converted.append([cell if isinstance(cell, Flowable) else p(str(cell), style) for cell in row])
    result = Table(converted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#cdd8e7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7faff")]),
    ]))
    return result


def callout(text, styles):
    box = Table([[p(text, styles["callout"])]], colWidths=[16.6 * cm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GREEN), ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#a7dccd")),
                             ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                             ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return box


def section(story, title, styles):
    story.append(p(title, styles["h1"])); story.append(Rule()); story.append(Spacer(1, 5))


def make_report():
    data, styles = read_snapshot(), build_styles()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=1.8 * cm, leftMargin=1.8 * cm,
                            topMargin=1.65 * cm, bottomMargin=1.8 * cm, title="CTE 442 Group 2 Implementation Report")
    story = []

    # Cover: institutional details and member entries faithfully retained from supplied report.
    story += [Spacer(1, .9 * cm), p("YABA COLLEGE OF TECHNOLOGY", styles["title"]),
              p("YABA, LAGOS", styles["cover"]), Spacer(1, .3 * cm), Rule(color=GOLD), Spacer(1, .55 * cm),
              p("DEPARTMENT OF COMPUTER ENGINEERING", styles["cover"]), p("HIGHER NATIONAL DIPLOMA II", styles["cover"]),
              p("ARTIFICIAL INTELLIGENCE", styles["cover"]), p("COURSE CODE: CTE 442", styles["cover"]),
              p("GROUP ASSIGNMENT: GROUP 2", styles["cover"]), Spacer(1, .7 * cm),
              p("IMPLEMENTATION REPORT: NIGERIAN-ENGLISH AUTOMATIC SPEECH RECOGNITION", styles["title"]),
              p("A grounded account of the local dashboard, real SLR70 speech data, completed evaluations, and the voice-recording workflow", styles["body"]), Spacer(1, .4 * cm)]
    member_data = [["S/N", "NAME", "MATRIC NUMBER"]] + [[n, p(name, styles["table"]), matric] for n, name, matric in MEMBERS]
    members_table = table(member_data, [1.2 * cm, 7.5 * cm, 6.9 * cm], styles)
    # The original cover includes thirteen members. Tighten only this table so
    # every institutional detail remains together on one cover page.
    members_table.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [members_table, Spacer(1, .22 * cm),
              p("Course lecturer: [[name of lecturer]]", styles["body"]), p("Submitted: November 2026", styles["body"]),
              Spacer(1, .3 * cm), p("Implementation snapshot generated from local project artifacts on " + date.today().isoformat() + ".", styles["small"]), PageBreak()]

    section(story, "Executive Summary", styles)
    story.append(p("This report replaces proposal-only claims with the work that is currently implemented and verifiable in the CTE 442 project. The system is a local Automatic Speech Recognition (ASR) research console. It imports and validates real Nigerian-English public speech, maintains speaker-disjoint train/dev/test partitions, runs configured ASR models, evaluates transcription quality, and presents the evidence in a local dashboard.", styles["body"]))
    story.append(p("The current data-backed implementation uses the OpenSLR SLR70 Nigerian-English corpus. It contains <b>3,359</b> recordings from <b>31</b> speakers, totaling <b>5.767 hours</b> of audio. The project has completed public-data evaluations for a classical MFCC + GMM-HMM baseline, Wav2Vec2 zero-shot, and Whisper-small zero-shot. A five-seed CNN-BiLSTM CTC run is active and resumable; its completed seed outputs are retained while the remaining seeds are trained.", styles["body"]))
    story.append(callout("The project aim at this stage is to compare ASR approaches on a reproducible Nigerian-English public-speech benchmark and provide a consent-aware workflow for progressively collecting new recordings. The report does not claim completed Yoruba, Igbo, Hausa, noise-condition, 10-hour, or team-collected-corpus experiments because those have not been implemented or measured in the current artifact set.", styles))
    story.append(Spacer(1, 10))
    story.append(table([["What is available now", "Evidence"],
                        ["Real speech data", "OpenSLR SLR70 Nigerian-English recordings, converted to 16 kHz mono and linked to reviewed transcripts."],
                        ["Fair partitioning", "A frozen, speaker-disjoint split is reused across evaluations."],
                        ["Measured results", "Three evaluated model configurations have saved WER/CER summaries."],
                        ["Live dashboard", "Plays real speech samples, shows transcripts/results, monitors model workers, and accepts manual recordings for review."],
                        ["Manual collection", "Consent acknowledgement, pseudonymous IDs, transcripts, preview, and a review queue are implemented."],], [4.3 * cm, 11.3 * cm], styles))

    section(story, "1. Aim, Scope, and Research Question", styles)
    story.append(p("<b>Research question.</b> How do a simple classical ASR baseline and pretrained ASR systems compare when they transcribe the same Nigerian-English speech under a fixed, speaker-disjoint evaluation protocol?", styles["body"]))
    story.append(p("<b>Implemented aim.</b> Build an understandable and reproducible local system that prepares Nigerian-English audio, compares multiple ASR approaches, computes Word Error Rate (WER) and Character Error Rate (CER), makes the supporting evidence visible, and prepares a safe route for collecting additional recordings.", styles["body"]))
    story.append(p("ASR converts spoken audio into text. In this project, each recording has a reviewed reference transcript. A model produces its own transcript, and the evaluation software counts word and character differences. Lower WER/CER values represent more accurate transcription.", styles["body"]))
    story.append(p("The scope is intentionally reported as it exists today: real public Nigerian-English speech plus a local intake path for new consented recordings. The historical proposal scope that named three additional Nigerian languages is retained only as future-work context, not as a claim of completed experiments.", styles["body"]))

    section(story, "2. Data Used and Reproducibility Controls", styles)
    story.append(p("The implemented benchmark is OpenSLR SLR70, a public Nigerian-English corpus. The local import process stores source provenance, validates audio, converts files to 16 kHz mono WAV, and produces a frozen split. Speakers, not individual utterances, are assigned to a single split so that the same speaker cannot appear in both training and test data.", styles["body"]))
    split_rows = [["Split", "Utterances", "Speakers", "Audio hours"]]
    for split in ("train", "dev", "test"):
        split_rows.append([split.title(), str(data["counts"][split]), str(len(data["speakers"][split])), f"{data['hours'][split] / 3600:.3f}"])
    split_rows.append(["Total", str(len(data["manifest"])), str(len({r['speaker_id'] for r in data['manifest']})), f"{sum(data['hours'].values()) / 3600:.3f}"])
    story.append(table(split_rows, [4.3 * cm, 4 * cm, 4 * cm, 4 * cm], styles))
    story.append(Spacer(1, 8))
    story.append(p("The dashboard also includes a small synthetic fixture. Its role is software verification: it checks file flow, audio validation, splitting, scoring, interval calculation, and plot generation. It is not presented as a speech-recognition measurement. Separating that technical check from real speech prevents test tones from being mistaken for ASR evidence.", styles["body"]))
    story.append(p("<b>Progressive collection workflow.</b> The Record voices tab is already available. A contributor acknowledges consent, uses a pseudonymous participant ID, enters a consent reference and exact transcript, records in the browser, listens to the preview, and submits the clip to a local review queue. The system does not automatically train on submitted recordings; review, audio validation, transcript checks, and fixed splits occur first.", styles["body"]))

    section(story, "3. Implemented System and Dashboard", styles)
    story.append(p("The dashboard is served locally at <b>http://127.0.0.1:8765</b>. It is designed for explanation as well as execution: the Overview tab gives the real speech count and results; the Live demo polls saved artifacts and active local workers; Datasets explains the real corpus and the recording workflow; Experiments lists model configurations; Record voices captures consented samples; and System check exercises the local technical pipeline.", styles["body"]))
    story.append(table([["Stage", "What the implementation does", "Visible evidence"],
                        ["Prepare", "Imports SLR70, validates WAV files, converts audio to 16 kHz mono, and creates a frozen split.", "Manifest, validation report, split fingerprint."],
                        ["Train / infer", "Runs configured baselines and pretrained models; interrupted multi-seed runs resume from existing seed predictions.", "Per-seed model and prediction files; live worker state."],
                        ["Evaluate", "Compares hypotheses to the reviewed transcript and computes WER/CER plus seed summaries and intervals.", "Evaluation CSV files and result table."],
                        ["Explain", "Lets a viewer play real speech, read the reference transcript, and understand the model comparison.", "Dashboard real-audio cards and live pipeline."],
                        ["Collect", "Records new consent-cleared samples to a review queue without mixing them into the benchmark automatically.", "Consent-aware manual-recording form."],], [2.8 * cm, 8.3 * cm, 5 * cm], styles))

    section(story, "4. Experiment Design", styles)
    story.append(p("All public-development experiments use the same frozen SLR70 test speakers. The project supports a classical MFCC + GMM-HMM baseline, a CNN-BiLSTM trained with CTC loss, Wav2Vec2, and Whisper-small. The purpose of the comparison is not to declare a universal winner; it is to measure how these approaches behave on the same available speech data and make every result traceable to saved outputs.", styles["body"]))
    story.append(table([["Configuration", "Mode", "Seeds", "Current implementation status"],
                        ["MFCC + GMM-HMM", "Classical acoustic baseline", "5", "Completed and evaluated on SLR70."],
                        ["CNN-BiLSTM CTC", "Neural model trained from scratch", str(data["cnn_expected"]), f"{data['cnn_status'].title()}; {data['cnn_done']}/{data['cnn_expected']} seed outputs saved at report generation."],
                        ["Wav2Vec2", "Pretrained zero-shot transcription", "1", "Completed and evaluated on SLR70."],
                        ["Whisper-small", "Pretrained zero-shot transcription", "1", "Completed and evaluated on SLR70."],
                        ["Wav2Vec2 / Whisper fine-tuning", "Planned local adaptation", "5 planned", "Configuration and study plans exist; no completed public fine-tuning result is reported here."],], [4 * cm, 4.2 * cm, 2.2 * cm, 5.7 * cm], styles))
    story.append(Spacer(1, 8))
    story.append(p("A seed is a controlled random initialization or sampling setting. Multiple seeds help reveal whether a result is stable rather than a one-off. The CNN run uses five seeds. Its resume behavior protects completed seed outputs, so a power interruption or dependency problem does not force the study to restart from seed 1.", styles["body"]))

    section(story, "5. Completed Results on Real SLR70 Speech", styles)
    story.append(p("The following values are read from the saved evaluation summaries in the project folder. They are the measured results currently available for the public Nigerian-English benchmark. WER and CER are error rates, so lower values are better. A WER above 100% can occur when a model inserts many extra words.", styles["body"]))
    result_rows = [["Model", "Seeds", "WER", "CER", "95% t interval (WER)"]]
    for r in data["results"]:
        result_rows.append([r["model"], r["seeds"], f"{r['wer'] * 100:.2f}%", f"{r['cer'] * 100:.2f}%", f"{r['low'] * 100:.2f}% to {r['high'] * 100:.2f}%"])
    story.append(table(result_rows, [4.2 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 5 * cm], styles))
    story.append(Spacer(1, 9))
    story.append(p("<b>Interpretation.</b> Whisper-small zero-shot has the lowest observed error among the completed configurations (11.29% WER and 5.15% CER). Wav2Vec2 zero-shot follows at 23.62% WER and 9.68% CER. The simple MFCC + GMM-HMM baseline has a much higher error rate (101.52% WER), reflecting substantial transcription error and insertions. The CNN-BiLSTM result is intentionally omitted until all five seed outputs are complete and evaluated.", styles["body"]))
    story.append(callout("These numbers demonstrate that the implemented evaluation system can measure real Nigerian-English speech and that the completed pretrained zero-shot systems outperform the simple classical baseline in this public-data comparison. They should be cited as SLR70 public-development findings, with the dataset and split stated alongside them.", styles))

    section(story, "6. Current Training Activity and How to Read the Dashboard", styles)
    story.append(p(f"At report generation, the CNN-BiLSTM CTC run is <b>{data['cnn_status']}</b>, with <b>{data['cnn_done']}/{data['cnn_expected']}</b> complete per-seed prediction outputs. The dashboard distinguishes this from a failure: it checks for a matching local worker and reports an active run when training is actually in progress. A result is not added to the comparison table until the run has all configured seed predictions and is evaluated.", styles["body"]))
    story.append(table([["Dashboard item", "Meaning for a presenter"],
                        ["Real SLR70 speech samples", "Press play to hear a real public Nigerian-English recording. The text shown underneath is its reviewed reference transcript."],
                        ["Measured results", "The result table reads saved WER/CER summaries from completed evaluations. Lower error is better."],
                        ["Saved seed outputs", "Shows how many of the configured repeated runs have written final predictions. For example, 3/5 means three are finished and two are still needed."],
                        ["Live state", "Running means a matching trainer is active. Needs attention means a run record was incomplete but no worker was found."],
                        ["Record voices", "A controlled intake point for new consented samples; recordings enter review before any training use."],
                        ["Run system check", "Checks the local software pathway, not speech-recognition quality."],], [5 * cm, 11.2 * cm], styles))

    section(story, "7. Conclusion and Next Steps", styles)
    story.append(p("The group has implemented a functional local ASR research environment rather than only a written proposal. It handles real public Nigerian-English speech, a reproducible split, model orchestration, saved evaluations, a live explanatory dashboard, and a consent-aware recording intake workflow. The completed results provide an initial, measured comparison: in this data and setup, the completed pretrained zero-shot systems achieved lower error than the simple classical baseline.", styles["body"]))
    story.append(p("The immediate technical next step is to allow the CNN-BiLSTM run to complete its missing seeds, then evaluate and plot its five-seed result. The next research step is to collect additional consent-cleared recordings through the implemented intake path, review them, validate their audio and transcripts, freeze a speaker-disjoint split, and evaluate the same model matrix on that approved corpus. Fine-tuning claims should be added only after those runs and summaries exist.", styles["body"]))
    story.append(table([["Priority", "Action", "Why it matters"],
                        ["1", "Finish CNN seeds 44 and 55; evaluate the combined prediction file.", "Completes the planned five-seed neural comparison."],
                        ["2", "Run the prepared Wav2Vec2 and Whisper fine-tuning studies when suitable compute is available.", "Measures whether local adaptation improves the pretrained systems."],
                        ["3", "Collect and review consented recordings through the dashboard workflow.", "Builds a traceable next-stage dataset without exposing identities."],
                        ["4", "Refresh this report after each completed evaluation.", "Keeps conclusions aligned with saved evidence rather than intentions."],], [1.8 * cm, 8.3 * cm, 6.1 * cm], styles))

    section(story, "References and Evidence Sources", styles)
    story.append(p("OpenSLR. (n.d.). <i>SLR70: Nigerian English speech corpus</i>. https://www.openslr.org/70/", styles["body"]))
    story.append(p("Local project artifacts consulted for this report: <i>data/public/slr70/manifest.16k.csv</i>, <i>data/public/slr70/splits_frozen.csv</i>, saved evaluation summaries under <i>results/slr70/evaluation/</i>, CNN run record under <i>results/slr70/runs/cnn_bilstm_ctc/</i>, project configurations under <i>configs/</i>, and the local dashboard source under <i>dashboard/</i>.", styles["body"]))
    story.append(p("This report is an implementation snapshot. Update its findings tables only from completed, saved evaluation outputs.", styles["small"]))

    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    print(OUT)


if __name__ == "__main__":
    make_report()
