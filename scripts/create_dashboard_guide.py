"""Generate a concise, printable guide to the CTE 442 local dashboard."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "cte442_dashboard_and_results_guide.pdf"

NAVY = colors.HexColor("#102A43")
BLUE = colors.HexColor("#1E6091")
TEAL = colors.HexColor("#147D78")
PALE = colors.HexColor("#EAF4F9")
AMBER = colors.HexColor("#FEF3C7")
GRAY = colors.HexColor("#52616B")


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def results() -> list[dict[str, str]]:
    rows = []
    for path in sorted((ROOT / "results" / "slr70" / "evaluation").glob("*/seed_summary.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            summary = list(csv.DictReader(handle))
        overall = [row for row in summary if row.get("dimension") == "overall" and row.get("group") == "all"]
        by_metric = {row["metric"]: row for row in overall}
        if "wer" in by_metric and "cer" in by_metric:
            rows.append({
                "model": by_metric["wer"]["model"],
                "seeds": by_metric["wer"]["n_seeds"],
                "wer": f"{100 * float(by_metric['wer']['mean']):.2f}%",
                "cer": f"{100 * float(by_metric['cer']['mean']):.2f}%",
                "interval": (
                    f"{100 * float(by_metric['wer']['ci95_low']):.2f}% - "
                    f"{100 * float(by_metric['wer']['ci95_high']):.2f}%"
                ),
            })
    return rows


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(doc.leftMargin, A4[1] - 1.35 * cm, A4[0] - doc.rightMargin, A4[1] - 1.35 * cm)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(doc.leftMargin, A4[1] - 1.02 * cm, "Group 2 CTE 442 - Dashboard and Results Guide")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.85 * cm, f"Page {doc.page}")
    canvas.restoreState()


def bullet(items: list[str], body: ParagraphStyle):
    return [p(f"<bullet>&bull;</bullet>{item}", body) for item in items]


def section_title(label: str, title: str, styles):
    return [p(label.upper(), styles["eyebrow"]), p(title, styles["h1"]), Spacer(1, 0.18 * cm)]


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=24,
                                leading=29, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10),
        "subtitle": ParagraphStyle("Subtitle", parent=base["BodyText"], fontSize=11, leading=16,
                                   textColor=GRAY, alignment=TA_CENTER),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16,
                              leading=20, textColor=NAVY, spaceBefore=6, spaceAfter=8),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11,
                              leading=14, textColor=BLUE, spaceBefore=9, spaceAfter=4),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.4,
                                leading=13.4, textColor=colors.HexColor("#1F2937"), spaceAfter=5),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=8.2,
                                 leading=11.2, textColor=GRAY),
        "eyebrow": ParagraphStyle("Eyebrow", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8,
                                   leading=10, textColor=TEAL, spaceAfter=2),
        "callout": ParagraphStyle("Callout", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9.2,
                                   leading=13, textColor=NAVY),
        "table": ParagraphStyle("Table", parent=base["BodyText"], fontName="Helvetica", fontSize=8.2,
                                 leading=10.2),
    }

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=1.65 * cm, rightMargin=1.65 * cm,
        topMargin=1.8 * cm, bottomMargin=1.45 * cm,
        title="CTE 442 Dashboard and Results Guide", author="Group 2 CTE 442",
    )
    story = []

    story += [Spacer(1, 2.2 * cm), p("CTE 442 Speech Recognition", styles["title"]),
              p("Dashboard, simulation, testing, and results guide", styles["title"]),
              Spacer(1, 0.3 * cm),
              p("A plain-language guide for explaining the local research console and the work completed so far.", styles["subtitle"]),
              Spacer(1, 1.1 * cm)]
    cover = Table([[p("OPEN THE LIVE DASHBOARD", styles["callout"]), p("http://127.0.0.1:8765", styles["callout"])]],
                  colWidths=[7.1 * cm, 8.5 * cm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story += [cover, Spacer(1, 1.4 * cm), p(f"Prepared {date.today().isoformat()}", styles["subtitle"]),
              Spacer(1, 0.8 * cm),
              p("Important research boundary: the fixture and the public SLR70 corpus are development data. They must not be presented as findings from an original Group 2 corpus.", styles["callout"]), PageBreak()]

    story += section_title("1. Start here", "How to open and test the dashboard", styles)
    story += bullet([
        "Open <b>http://127.0.0.1:8765</b> on this Mac. The address works only while the local dashboard server is running.",
        "Click <b>Refresh status</b> to reload the latest dataset and experiment information from the project folder.",
        "Click <b>Run fixture simulation</b> to test the safe synthetic pipeline. It validates file flow, audio checks, speaker splitting, scoring, confidence intervals, and plot generation.",
        "After the simulation, open the <b>Simulation</b> tab. A successful console message includes <b>validation_failures=0</b> and says that the fixture pipeline is complete.",
        "Do not treat the fixture charts, fixture audio, or fixture scores as speech-recognition findings. The clips are synthetic tones, not human speech.",
    ], styles["body"])
    story += [p("Quick test checklist", styles["h2"])]
    test_data = [[p("Check", styles["table"]), p("Expected result", styles["table"]), p("Meaning", styles["table"])] ]
    for row in [
        ("Dashboard loads", "Top bar says installed tools", "The local server and status endpoint work."),
        ("SLR70 card", "READY; 3,359 utterances", "Public development data is imported and converted."),
        ("Original corpus card", "WAITING", "No consent-cleared Group 2 recordings have been added."),
        ("Run fixture simulation", "validation_failures=0", "The safe plumbing test is working."),
        ("Completed public results", "Three model rows", "The saved evaluation files were found and read."),
    ]:
        test_data.append([p(cell, styles["table"]) for cell in row])
    table = Table(test_data, colWidths=[3.5 * cm, 5.0 * cm, 7.0 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, PageBreak()]

    story += section_title("2. Every dashboard element", "Header, warning, tabs, and overview", styles)
    story += [p("Header and hero area", styles["h2"])]
    story += bullet([
        "<b>G2 / CTE 442 Research Console</b>: the name of the local project dashboard.",
        "<b>Installed: python3.12 - ffmpeg - sox</b>: tool-status line. Python runs the project; FFmpeg and SoX help inspect or convert audio.",
        "<b>Compare classical and pretrained speech models with clean provenance</b>: the study purpose. 'Clean provenance' means keeping fixture, public, and original data separate.",
        "<b>Run fixture simulation</b>: runs only the tiny synthetic test dataset. It never trains real ASR models and never alters the public SLR70 results.",
        "<b>Research boundary</b> warning: reminds viewers that only an approved original Group 2 corpus can support original-corpus conclusions.",
    ], styles["body"])
    story += [p("Navigation tabs", styles["h2"])]
    nav = [[p("Tab", styles["table"]), p("What it contains", styles["table"]), p("How to explain it", styles["table"])] ]
    for row in [
        ("Overview", "Readiness cards, model plan, completed public metrics", "A one-page project summary."),
        ("Datasets", "Fixture, public SLR70, original-corpus cards", "Shows which data lane is ready and which is not."),
        ("Experiments", "Configuration matrix", "Shows every model, mode, seed count, and fine-tuning hours."),
        ("Simulation", "Fixture console, plots, audio", "Demonstrates pipeline operation, not ASR performance."),
    ]:
        nav.append([p(cell, styles["table"]) for cell in row])
    t = Table(nav, colWidths=[3 * cm, 6 * cm, 6.5 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, p("Overview cards and diagrams", styles["h2"])]
    story += bullet([
        "<b>Fixture</b>: 18 synthetic records. It is ready because it exists only to test the workflow.",
        "<b>SLR70 public</b>: 3,359 utterances and about 5.767 hours. It is imported public Nigerian-English development data.",
        "<b>Original corpus</b>: recordings needed. This is correctly waiting because approved Group 2 recordings are absent.",
        "<b>Experiments</b>: six configurations. The card is a count of configured studies, not six completed studies.",
        "<b>Study comparison</b>: MFCC-GMM-HMM, CNN-BiLSTM CTC, Wav2Vec2, and Whisper-small are the four planned systems.",
        "<b>Fine-tuning ladder</b>: the original design lists 1 h, 2 h, 5 h, and 10 h. Public SLR70 has only 3.86 train hours after held-out splits, so public fine-tuning is limited to 1 h and 2 h.",
    ], styles["body"])
    story += [PageBreak()]

    story += section_title("3. Data and experiment tabs", "What each card, archive check, and configuration means", styles)
    story += [p("Datasets", styles["h2"])]
    story += bullet([
        "<b>Tiny fixture - READY</b>: 18 non-speech records. Use it for testing the app only.",
        "<b>OpenSLR SLR70 - READY</b>: public Nigerian-English audio imported, converted to 16 kHz mono, and speaker-split. It supports public-development comparisons.",
        "<b>Group 2 recordings - WAITING</b>: this is the primary research lane. It remains empty until your team obtains approval, consent-cleared recordings, transcripts, and pseudonymous speaker IDs.",
        "<b>SLR70 archive checklist</b>: en_ng_female.zip and en_ng_male.zip show 'found' when the official source archives are stored locally. Their presence verifies the source files, not model quality.",
    ], styles["body"])
    story += [p("Experiments", styles["h2"])]
    exp = [[p("Experiment", styles["table"]), p("Meaning", styles["table"]), p("Current state", styles["table"])] ]
    for row in [
        ("mfcc_gmm_hmm", "Classical, non-pretrained acoustic baseline; five random seeds.", "Complete on public SLR70."),
        ("cnn_bilstm_ctc", "Neural model trained from scratch; five seeds.", "Still running on CPU."),
        ("wav2vec2_zeroshot", "Pretrained Wav2Vec2 used without SLR70 training.", "Complete on public SLR70."),
        ("whisper_small_zeroshot", "Pretrained Whisper-small used without SLR70 training.", "Complete on public SLR70."),
        ("wav2vec2_finetune", "Pretrained Wav2Vec2 adapted to local training audio.", "Not run; public plan uses 1 h and 2 h."),
        ("whisper_small_finetune", "Pretrained Whisper-small adapted to local training audio.", "Not run; public plan uses 1 h and 2 h."),
    ]:
        exp.append([p(cell, styles["table"]) for cell in row])
    t = Table(exp, colWidths=[4.2 * cm, 7.7 * cm, 3.6 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [t, PageBreak()]

    story += section_title("4. Simulation and metrics", "How to explain the charts, audio, WER, CER, and intervals", styles)
    story += [p("Simulation tab", styles["h2"])]
    story += bullet([
        "<b>Safe simulation / NOT ASR RESULTS</b>: this label prevents accidental reporting of synthetic fixture numbers as research findings.",
        "<b>Console output</b>: lists pipeline steps and provides operational evidence. 'validation_failures=0' means the fixture audio passed the validation rules.",
        "<b>Fixture plots</b>: WER by accent region, gender, noise condition, and sentence length. They prove that plot generation and group slicing work. The labels are fixture metadata, not observed demographics.",
        "<b>Fixture audio</b>: playable synthetic wave files. It proves local audio delivery works. It is deliberately non-speech.",
    ], styles["body"])
    story += [p("Metric definitions", styles["h2"])]
    metric = [[p("Item", styles["table"]), p("Meaning", styles["table"]), p("How to interpret", styles["table"])] ]
    for row in [
        ("WER", "Word Error Rate: substitutions + deletions + insertions divided by reference words.", "Lower is better. It can exceed 100% when a model inserts many extra words."),
        ("CER", "Character Error Rate: analogous error calculation at character level.", "Lower is better. It is useful when spelling detail matters."),
        ("Seed", "A random initialization or sampling setting for a model run.", "Five seeds provide a more stable average than one run."),
        ("95% interval", "A range expressing uncertainty around an estimate.", "For one zero-shot run, a t interval is just the same value; speaker-bootstrap intervals are more informative."),
        ("Training hours", "How much train-split audio was used for fine-tuning.", "Zero-shot means no SLR70 training audio was used."),
    ]:
        metric.append([p(cell, styles["table"]) for cell in row])
    t = Table(metric, colWidths=[3 * cm, 7.1 * cm, 5.4 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, PageBreak()]

    story += section_title("5. Completed public results", "What has been measured so far", styles)
    story += [p("These are public SLR70 development results only. They answer a preliminary version of the comparison question, not the final original-corpus research question.", styles["callout"]), Spacer(1, 0.2 * cm)]
    data = [[p("Model", styles["table"]), p("Seeds", styles["table"]), p("Mean WER", styles["table"]), p("Mean CER", styles["table"]), p("95% t interval for WER", styles["table"])] ]
    for row in results():
        data.append([p(row["model"], styles["table"]), p(row["seeds"], styles["table"]), p(row["wer"], styles["table"]),
                     p(row["cer"], styles["table"]), p(row["interval"], styles["table"])])
    t = Table(data, colWidths=[4.1 * cm, 1.8 * cm, 2.5 * cm, 2.5 * cm, 4.0 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [t, p("Interpretation", styles["h2"])]
    story += bullet([
        "Whisper-small zero-shot currently has the lowest observed public-test error among the completed systems.",
        "Wav2Vec2 zero-shot also substantially outperforms the classical baseline.",
        "The classical baseline is intentionally simple and performs poorly. Its WER above 100% reflects many extra predicted words; it is not a percentage of correct speech.",
        "The CNN result must wait until its complete five-seed run and evaluation are available. It must not be inferred from a partial run.",
    ], styles["body"])
    story += [PageBreak()]

    story += section_title("6. What remains", "What is required to achieve the full project aim", styles)
    story += [p("Current conclusion", styles["h2"]), p("The team has achieved a working public-data development study and preliminary evidence that pretrained models outperform the simple classical baseline on SLR70. The full project aim has not yet been achieved because original Group 2 data and fine-tuning results are missing.", styles["body"])]
    story += [p("Remaining actions", styles["h2"])]
    remaining = [
        [p("1", styles["table"]), p("Finish CNN-BiLSTM training, evaluation, and plots. The current CPU run is active but slow.", styles["table"])],
        [p("2", styles["table"]), p("Run 1-hour and 2-hour Whisper and Wav2Vec2 fine-tuning on public SLR70, preferably on a GPU.", styles["table"])],
        [p("3", styles["table"]), p("Create the final paired comparison tables using the same frozen test speakers and compatible seeds.", styles["table"])],
        [p("4", styles["table"]), p("Obtain ethics/department approval, informed consent, recordings, reviewed transcripts, and pseudonymous speaker IDs for the original Group 2 corpus.", styles["table"])],
        [p("5", styles["table"]), p("Validate original audio, freeze speaker-disjoint train/dev/test splits, then rerun the same model matrix on the original corpus.", styles["table"])],
        [p("6", styles["table"]), p("Write the report with a strict distinction between public-development outcomes and original-corpus findings.", styles["table"])],
    ]
    t = Table(remaining, colWidths=[1 * cm, 14.1 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), AMBER), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [t, Spacer(1, 0.4 * cm), p("Suggested explanation in a presentation", styles["h2"]),
              p("'We first verified the entire ASR research pipeline with a synthetic fixture. We then imported the public SLR70 Nigerian-English corpus, used frozen speaker-disjoint splits, and evaluated three systems. The pretrained zero-shot models outperformed the simple classical baseline. These are public-development results only. Our next stage is to collect and evaluate a consent-cleared Group 2 corpus and measure the effect of fine-tuning.'", styles["body"])]

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
