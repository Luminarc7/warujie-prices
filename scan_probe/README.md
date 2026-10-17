# Card scan probe (test branch only)

Phase 1 of the card scan plan: before anything is built into warujie.jp, measure how reliably a
phone photo of a card can be matched to the right card by its artwork.

- `build_index.py` chooses one picture per distinct look of every artwork (English where there
  is one, Japanese for Japanese-only art and for sagas/split/flip cards), downloads Scryfall's
  small pictures (10 a second at most; kept in the Actions cache) and fingerprints them.
- `common.py` is the fingerprint: the art region of the flattened card as a 256-bit DCT hash, a
  64-bit one, and a 4x4 colour grid; `export_model.py` adds two small image models (MobileNetV3,
  ONNX) to compare against.
- `synth.py` makes believable phone photos (angle, light, glare, sleeve, blur, JPEG);
  `detect.py` finds the card's edges near the on-screen guide.
- `evaluate.py` matches every test photo and writes `out/results.md`.

Workflow: `.github/workflows/scan-probe.yml`, on push to this branch. Nothing here is used by
the site or the daily price workflow, and this branch is never merged as it is.
