# Original corpus placeholder

No recordings or annotations are included. Store only consent-cleared audio in `audio/`.
Use pseudonymous speaker IDs and keep the re-identification key and consent documents in
an access-controlled location outside this repository. Start from
`data/manifest_template.csv`. Set `corpus_kind=original` for every row.

## Local dashboard recording intake

The local dashboard's **Record voices** tab saves browser recordings only to the ignored
`incoming/` review queue. It requires an explicit consent acknowledgement, a pseudonymous
participant ID, a separate non-identifying consent reference, and an exact transcript.
Incoming recordings are never added automatically to `audio/`, a manifest, a split, or a
training run. A researcher must review the consent record and transcript, validate/convert
the audio, and then add an approved row to the original-corpus manifest.

Do not expose this local intake endpoint publicly as-is. A public deployment needs
authenticated access, HTTPS, encrypted storage, an approved retention policy, and a
separate secure consent-management process.

