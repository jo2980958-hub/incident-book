# Incident Book

A violent incident log for one small premises, built on the Ring API. Staff
tap one button when something happens; the app pulls the ninety seconds
either side from the shop's camera and drafts the record California Labor
Code 6401.9 requires, plus a pack for the police or the insurer.

Full product spec, the design rationale, and the honest case against
building this at all: [`SPEC.md`](SPEC.md).

## This is a fixture-boundary build. Read this before you run it.

**No real Ring device was used anywhere in this build or these tests.** Ring
documents no reachable sandbox, and every developer path needs a real,
US-located, registered device on a paid Ring Protect plan (continuous
recording specifically, or clip retrieval returns `416
TIMESTAMP_NOT_FOUND`). Neither was available. See `SPEC.md`, "The fixture
boundary, stated plainly," for the full detail.

What that means concretely:

- `app/ring_client.py` is the only file that speaks the Ring HTTP shapes.
  Everything else in the app only ever sees its typed return values
  (`RingDevice`, `RingEvent`, `RingClip`, `RingSnapshot`), never raw JSON.
- Every demo run in this build uses `FixtureTransport`, which reads recorded
  JSON from `fixtures/` and a small, clearly labelled placeholder clip
  (`fixtures/clip_placeholder.bin`, containing the literal text
  `FIXTURE_CLIP_NOT_REAL_RING_FOOTAGE...`, not a real recording). Every
  incident and every exported pack carries `"source": "fixture"` so this is
  never silently presented as real footage.
- `tools/replay_webhook.py` signs a fixture webhook payload with the same
  HMAC-SHA256 scheme the app verifies and posts it to the running server,
  exactly the way a real Ring webhook would arrive. This is what drives the
  demo.
- `HttpTransport` in the same file is written against the documented real
  API shapes and is a one-line swap in `ring_client.build_client()` if a
  real device becomes available. It has never been exercised against a live
  account.

## Run it

Requires Python 3.11 or newer.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.server        # serves http://localhost:5057
```

Port 5057 is hard-coded (`app/server.py`); if something else already holds it, stop
that process first — there is currently no environment override.

`requirements.txt` deliberately does **not** install WeasyPrint, so the app and
its test suite install cleanly with nothing beyond a plain `pip install`. PDF
export is optional and lives in `requirements-pdf.txt`:

```bash
pip install -r requirements-pdf.txt
```

WeasyPrint needs system Cairo and Pango to build on a machine that does not
already have them (on Debian/Ubuntu: `apt install libpango-1.0-0
libpangocairo-1.0-0 libcairo2`; on macOS: `brew install pango cairo`). Skip
this install entirely if you don't need PDFs — the `.pdf` export routes then
return a named 503 and the same document is served as HTML instead, which
prints fine from any browser. Nothing else in this README depends on it.

## Amazon Bedrock

`app/bedrock.py` is a real Bedrock boundary: a model preference chain, a read
timeout, and one exception (`BedrockUnavailable`) that every caller treats the same
way. `app/drafting.py` uses it to turn a staff member's own few words into the two
free-text fields of the incident record (what happened, and how it was handled) —
and nothing else; it is never used for anything that classifies or accuses. If
Bedrock is unreachable, the staff member's own words are kept exactly as typed
instead, and the page says so.

| Variable | Default | Effect |
|---|---|---|
| `INCIDENT_BOOK_BEDROCK` | unset | `off`/`0`/`false`/`no` runs the whole app with no AWS account — this is how the demo survives a conference wifi network |
| `INCIDENT_BOOK_BEDROCK_MODEL` | unset | pins one model id instead of walking the preference chain |
| `INCIDENT_BOOK_BEDROCK_TIMEOUT` | `20` (seconds) | read timeout on the Bedrock client |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | your AWS CLI/env default | region Bedrock is called in |
| `RING_WEBHOOK_SECRET` | `demo-shared-secret` | HMAC secret the webhook signature is checked against; the default lets the replay demo work with no setup |

In a second terminal, drive the demo the way a real Ring device would, by
sending a signed webhook and then tapping the button:

```bash
source venv/bin/activate
python tools/replay_webhook.py motion_human
curl -X POST http://localhost:5057/incidents/tap -d "device_id=dev_counter_cam_01"
```

Or just open `http://localhost:5057` in a browser, replay the webhook from a
terminal, then tap the on-screen button. The capture confirmation page, the
incident list, the nine-field form and every export are all reachable from
there. The export routes are per record — `/incidents/<id>/export/log` as
JSON, `.../export/log.html` and `.../export/pack` as documents,
`.../export/pack.json` as a hash manifest — plus `/export/log.json` and
`/export/log.csv` for the whole book.

## Test

```bash
source venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

263 tests and 23 skipped, all real assertions: HMAC signature verification (valid, tampered,
wrong secret, missing), the documented `416 TIMESTAMP_NOT_FOUND` behaviour
for a device without continuous recording, the consent time-gate that keeps
pre-consent events out of history, the nine 6401.9(d)(2) fields mapped one
to one, the no-accusation language guard, SHA-256 manifest hashes matching
the actual evidence bytes, and a full capture-to-export integration test
through the real Flask routes. One test
(`tests/test_store_threading.py`) exists specifically because it caught a
real concurrency bug the rest of the suite did not (two requests racing to
append to the same incident's history).

## What it deliberately does not do

See `SPEC.md` for the full list and the reasoning. In short: it never names
or accuses a person, it does not build a cross-shop suspect list (Ring's
content policy bans this outright), it does not replace Ring's own
dashboard, and it does not silently hide a missing clip.

## Licence

MIT. See below. Third-party font credits: see [`ATTRIBUTION.md`](ATTRIBUTION.md).

```
MIT License

Copyright (c) 2026 Incident Book

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
```
