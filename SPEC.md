# Incident Book — spec

## What it does

One small premises, one Ring camera pointed at the counter or the floor. When
something happens (a theft, a threat, abuse across the counter, a refused sale
that turns nasty), whoever is on the floor taps one large button. Incident Book
pulls the ninety seconds either side of that tap from the Ring event stream,
opens a violent incident record with the date, time, location and event
timeline already filled in, and asks the person completing it only the plain
questions California Labor Code 6401.9(d)(2) actually requires. It keeps the
record for five years and exports two things: the statutory violent incident
log, and an evidence pack for the police or the insurer.

## Who it's for

The owner or the one staff member on shift at a corner shop, a barber, a
takeaway, a small workshop. Not a chain with a security manager. Not a
warehouse. One till, one or two people, no loss-prevention department.

## The one screen that carries the demo

The capture screen is the whole product for the person it is built for: one
button, filling most of the screen, on a page with nothing else on it. No
form, no fields, no choice to make. The capture must work for someone with a
shaking hand a few seconds after being threatened, so it cannot be allowed to
depend on them also being ready to answer nine legal questions in that same
moment. Capture and completion are two different screens on purpose:

1. A webhook (replayed from a fixture, signed the way Ring signs them) has
   already arrived: `motion_detected`, `sub_type: human`, at the counter
   camera.
2. Staff taps the one button. The app records the tap time, calls Ring's clip
   endpoint for [tap − 90s, tap + 90s], and saves a draft incident with the
   date, time, location and evidence already attached. This is the only step
   that cannot be redone later; a clip not fetched now is a clip that may no
   longer be reachable by the time anyone comes back to it.
3. A confirmation screen, just as plain, says what was captured and returns
   to the one-button screen so the next tap is never blocked. "Add details
   now" and "finish later from the incident list" are both offered here,
   equally, with no pressure toward either.
4. Whenever someone does sit down with it, the half-written form asks only
   the plain-English versions of the remaining 6401.9(d)(2) questions (who
   did it, was the worker alone, what kind of incident, what happened next,
   who is filling this in), with the auto-filled fields already in place.
5. Save (or re-save later) produces two exports: the five-year violent
   incident log entry in the exact nine-field shape of 6401.9(d)(2), and a
   pack (HTML report plus a JSON manifest with SHA-256 hashes of the clip and
   stills) that a police officer or an insurer can be handed.

The demo shows steps 1-3 as the dramatic run, and 4-5 as the calm follow-up.
They are deliberately not the same moment.

## The fixture boundary, stated plainly

**No real Ring device was used to build or test this.** Three platform
constraints, verified independently before this pass started, make that
impossible in the time given:

- Ring documents no reachable sandbox. A sandbox is named in the glossary and
  the FAQ, but the Test section of the same reference page says only "use your
  personal Ring account and devices," and no page explains how to reach it.
- Every developer path needs a real, US-located, registered device on an
  active Ring Protect base plan, and clip retrieval specifically needs the
  paid continuous-recording tier or it returns `416 TIMESTAMP_NOT_FOUND`.
- The hackathon page says a physical device is not required and lists
  simulators under Resources; Ring's own documentation does not support
  that, and the question is with the organisers, unresolved, as of this
  writing.

So this app is built and demoed against **recorded fixtures replayed through
the real client code**, never above it. Concretely:

- `app/ring_client.py` is the only file that knows the Ring HTTP shapes
  (`GET /v1/devices`, `GET /v1/history/devices/{id}/events`,
  `POST /v1/devices/{id}/media/video/download`,
  `POST /v1/devices/{id}/media/image/download`). It takes a `transport`
  object. In demo and test mode that transport is `FixtureTransport`, which
  reads JSON files from `fixtures/` and returns them in the exact response
  shape Ring's reference documents. If a real Ring OAuth token and base URL
  are ever set in the environment, the same client can be pointed at
  `HttpTransport` instead, and nothing above `ring_client.py` changes.
- `fixtures/` contains: a device list, an event-history page, two signed
  webhook payloads (`motion_detected` and `button_press`), and a placeholder
  clip. The placeholder clip is not a real recording; it is a small,
  deterministic byte string clearly labelled `FIXTURE_CLIP`, used to prove the
  storage, hashing and packaging pipeline actually runs end to end. The UI
  never claims it is real footage; the incident record and the exported pack
  both carry a `"source": "fixture"` field verbatim.
- `tools/replay_webhook.py` signs a fixture payload with the same HMAC-SHA256
  scheme the app verifies, exactly as Ring's real webhook would arrive, and
  posts it to the running app's `/webhooks/ring` endpoint. This is what
  drives the demo: nothing in the Flask app knows or cares that the webhook
  came from a replay script instead of Ring's servers.

### What would change with a real device

If a US-located Ring Protect device on the continuous-recording tier became
available: set `RING_CLIENT_ID`, `RING_CLIENT_SECRET`, `RING_WEBHOOK_SECRET`
and `RING_BASE_URL` in the environment, complete the OAuth authorization-code
flow once (there is no code for this yet; it is one HTTP redirect handler,
not built, because there is nothing to authorize against), and switch
`ring_client.build_client()` from `FixtureTransport` to `HttpTransport`. No
other file changes. The incident form, the log export and the pack export are
identical either way, because they only ever see the `RingEvent` and
`RingClip` dataclasses that both transports return.

## What it deliberately does not do

- **It never names or accuses a person.** Ring's own classifier has been
  documented labelling a motorised wheelchair a package. The app records "an
  event was detected" and "no arrival was recorded," never "the thief" or
  "he stole." The classification questions in the form (customer, stranger,
  coworker, and so on, per 6401.9(d)(2)(D)) are filled in by a human who was
  there, not inferred from the video. `app/incident.py` and its tests enforce
  this: a banned-phrase check runs on every generated document.
- **It does not build a cross-shop suspect database.** Ring content policy
  1.2.5 and 1.2.7 ban community watchlists and suspect registries outright.
  This app is one premises' own record of its own incidents, full stop.
- **It does not do industrial safety detection** (slips, spills, fire).
  That space already has a Ring Marketplace listing (Visionify). This product
  is record-keeping, not monitoring.
- **It does not replace Ring's own dashboard** for live view or video search.
  Ring for Business already sells that. This product's value is the one thing
  Ring does not sell: turning a tap into a completed statutory record with the
  evidence already attached.
- **It does not claim the clip will always be there.** If the shop is on
  event-only recording, or the timestamp falls outside what was recorded, the
  client surfaces `416 TIMESTAMP_NOT_FOUND` as a named, visible state on the
  incident record ("clip unavailable: continuous recording not enabled"), not
  a silent gap or a crash.
- **It does not implement webhook replay protection** (no nonce or timestamp
  window), because Ring's docs do not specify a scheme for one. Written down
  here, not hidden: see friction log row 4.
- **It does not handle the five-year deletion schedule automatically.**
  Records are timestamped and flagged `retain_until`, but nothing purges them;
  that is a real product's job, not a hackathon demo's.

## Honesty about demand

Two things pull against this product and are stated here rather than in a
pitch deck footnote:

- No Cal/OSHA citation issued under Labor Code 6401.9 was findable. The
  statute is real, in force since 1 July 2024, and carries citation power
  under subdivision (g), but a search of the DIR news index and an attempted
  OSHA citation-record query turned up nothing specific to workplace violence
  at a shop. The compliance case is legally sound and empirically unproven.
- In a hand-read sample of 100 consecutive r/smallbusiness posts on one day,
  zero mentioned crime at the premises or evidence of anything that happened
  there. The pain shows up clearly in Home Office and ONS statistics; it does
  not show up in what small business owners spontaneously write about. Demand
  would need to be created, not just met.

Full detail on both points was verified independently before this pass
started. This app is built anyway because it is the only one of the five
scored Ring ideas that clears the "technology is load-bearing" test: fetching
an MP4 for an arbitrary past timestamp from a third party's premises is a
genuine platform capability nothing else substitutes for, and every
alternative was either a phone app with a camera bolted on or a feature Ring
already ships itself.

## The nine 6401.9(d)(2) fields, as implemented

Each is a named field on `Incident` in `app/incident.py`, not a paraphrase:

| Statute | Field | Source in this app |
|---|---|---|
| (A) date, time, location | `occurred_at`, `location` | Filled from the Ring event automatically |
| (B) workplace violence type | `violence_type` | Human-selected: customer/client, stranger with criminal intent, worker-on-worker, personal relationship |
| (C) detailed description | `description` | Human-written, free text |
| (D) classification of who committed it | `perpetrator_class` | Human-selected: client or customer, stranger, coworker, supervisor, other, unknown |
| (E) circumstances at the time | `circumstances` | Checkboxes: alone, low staffing, poorly lit, rushed, isolated, unable to get help, other, matching the statute's own list |
| (F) where it occurred | `location_detail` | Human-written, defaults to camera's registered location |
| (G) type of incident | `incident_type` | Human-selected: physical attack without weapon, physical attack with weapon, threat, sexual assault or threat |
| (H) consequences | `consequences` | Human-written: was security or law enforcement contacted, and their response |
| (I) name and job title of person completing the log | `completed_by`, `completed_by_title` | Human-entered at save time |

`created_at` and `retain_until` (created_at + 5 years) are stored alongside
but are not statute fields; they implement subdivision (f)(3)'s five-year
retention requirement.

## Design

Checked against this hackathon's existing palette inventory before choosing
anything. Taken already: cartridge pink, mint, coral, magenta, yellow, apricot, orange,
navy and purple accents; ultramarine, dusk purple, plum-black, pale grey,
cream, warm sand, blush, pale green and pale lilac grounds; left sidebar,
top nav with a metrics strip, centred hero with cards, and left rail
shells. Incident Book uses none of them.

**Ground: charcoal, near-black and neutral, no purple or blue cast**, so it
sits apart from the two other dark projects in the inventory (dusk purple,
plum-black) and reads calmly under ordinary shop lighting rather than
looking like a lit-up device. **Accent: signal red, reserved for exactly one
element, the capture button**, chosen because it is the one colour in this
product that has to mean "press this now" and nothing else, and because
nobody else in the inventory has claimed it. It is used flat and solid, no
gradient, no pulse or flash, so it reads as a control, not an alarm going
off.

**Shell: a full-bleed single-control surface**, not any of the four already
listed. The capture screen has no chrome, no navigation, no header at all;
the button is close to the full viewport so a shaking hand cannot miss it or
need to aim. Everything else the app does (the incident list, the
statutory form, the exports) lives one level down, reachable only from a
small, deliberately unhurried link, because the person filling in nine
legal fields is not the same person, or the same moment, as the person who
just tapped the button.

Large tap targets throughout, a single clean sans-serif, and no camera-feed
chrome or siren iconography anywhere outside the one capture button itself:
the rest of the product is closer to "paperwork that writes itself" than to
a security dashboard.

## Stack

Python 3.14, Flask for the web UI (server-rendered, kiosk-appropriate: one
button, one form, no client-side framework needed), SQLite for storage,
stdlib `hmac`/`hashlib` for webhook verification. No Ring Partner SDK exists
("There is no official Ring Partner SDK. Use standard HTTP libraries"), so
`ring_client.py` is a hand-written HTTP client against the documented REST
shapes, with a fixture transport substituted at the boundary for this build.
