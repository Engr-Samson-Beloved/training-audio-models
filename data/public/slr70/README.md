# OpenSLR SLR70 public development corpus

This path is reserved for **public development data only**. SLR70 is not the Group 2
original corpus and its measurements must not be described as original-corpus results.

Source: https://www.openslr.org/70/

License: Creative Commons Attribution-ShareAlike 4.0 International.

The importer downloads the official female and male archives, checks their published
SHA-256 values, safely extracts them, and writes a `corpus_kind=public` manifest. Audio,
archives, generated manifests, and evaluation results are intentionally gitignored.

```bash
cte442 import-slr70 --root data/public/slr70
```

Per-utterance recording device, noise condition, age, proficiency, and Lagos/London
location are not provided by the source index. The importer records these as
`unspecified`; it does not infer them from gender, file names, or audio.

