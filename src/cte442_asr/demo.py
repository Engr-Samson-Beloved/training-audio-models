"""Streamlit demonstration UI. Predictions are visibly labelled by corpus provenance."""

from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st

from .evaluation import score


st.set_page_config(page_title="CTE 442 ASR", layout="wide")
st.title("Group 2 CTE 442 — ASR comparison")
st.warning("Fixture and public-dataset outputs are not original-corpus research results.")
manifest_file = st.file_uploader("Manifest CSV", type="csv")
predictions_file = st.file_uploader("Predictions CSV", type="csv")
if manifest_file and predictions_file:
    manifest = {row["utterance_id"]: row for row in csv.DictReader(line.decode() for line in manifest_file.readlines())}
    predictions = list(csv.DictReader(line.decode() for line in predictions_file.readlines()))
    kinds = sorted({row.get("corpus_kind", "missing") for row in manifest.values()})
    st.subheader(f"Corpus provenance: {', '.join(kinds)}")
    if kinds != ["original"]: st.error("NON-ORIGINAL DATA — smoke/demo inspection only")
    uid = st.selectbox("Utterance", [row["utterance_id"] for row in predictions])
    pred = next(row for row in predictions if row["utterance_id"] == uid); ref = manifest[uid]
    audio_path = Path(ref["audio_path"])
    if audio_path.exists(): st.audio(str(audio_path))
    left, right = st.columns(2)
    left.metric("WER", f"{float(score(ref['transcript'], pred['hypothesis'])['error_rate']):.3f}")
    right.metric("CER", f"{float(score(ref['transcript'], pred['hypothesis'], 'char')['error_rate']):.3f}")
    st.write("Reference:", ref["transcript"]); st.write("Hypothesis:", pred["hypothesis"])
else:
    st.info("Upload a manifest and matching predictions CSV. The app does not create or infer results.")

