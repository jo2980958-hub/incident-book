# Friction log — Incident Book (Ring)

Rows added as they happened, in build order. Severity: Blocker / High / Medium / Low.

The first three rows are the ones that matter to anyone who owns the Ring developer
programme. They are also the three that were true before a line of this app was written
and will be true for the next entrant, so they are first rather than in the order we hit
them.

---

### 1. Onboarding cannot be completed at all without a paid, US-located, subscribed device
- **Task**: Get from zero to one authenticated Ring API call.
- **Steps**: Worked through the Ring developer pages in order — get started, develop,
  certify, publish — looking for the step where a developer without hardware joins.
- **Expected**: A sandbox tenant, a demo account, a fixture set, or a device-free
  read-only tier. Any one of them.
- **Actual**: Every documented path terminates at a real Ring device, registered to a
  US-located address, on an active Ring Protection subscription, with staging capped at
  ten users. There is no step for a developer who does not already own one.
- **Severity**: Blocker. Not for this app, which was built against fixtures, but for the
  question the feedback form actually asks. We cannot answer "how was onboarding" with
  anything except "we did not complete it."
- **Workaround**: None available. Everything below is what building without completing
  onboarding looks like.
- **Suggestion**: This is upstream of every other item in this log and fixing it would
  remove most of them. A read-only demo tenant with a handful of synthetic devices and a
  week of canned event history would let a developer see real JSON, real error shapes and
  real auth failures before committing a design. That is the difference between an
  integration built against documented prose and one built against the thing.

### 2. The sandbox is named in two places and documented in none
- **Task**: Decide how to exercise the Ring client code before demo day.
- **Steps**: The glossary names a sandbox with synthetic devices. The FAQ repeats it. The
  Test section of the same reference says, in full, to use your personal Ring account and
  devices. Two independent research passes over `developer.ring.com` and
  `developer.amazon.com/docs/ring` grepped for `simulator`, `mock`, `virtual device`,
  `emulat` and `sandbox`, and found the word used but never defined: no base URL, no auth
  flow, no way to request access.
- **Expected**: A sandbox base URL, or no mention of a sandbox.
- **Actual**: Neither. A term of art appears twice in the documentation with nothing
  behind it, which costs more time than an honest absence would, because a developer
  reasonably assumes they have failed to find the page rather than that the page does not
  exist.
- **Severity**: Blocker for anything that needs a live call.
- **Worth saying against ourselves**: the hackathon Resources page also states that
  "Creating a free Ring account gets you access to the Ring (Amazon Vision) APIs." Nobody
  on this project created one. We concluded from Ring's own docs that no device-free path
  exists and stopped there rather than making the free account and seeing what an
  authenticated session returns with no doorbell attached. That was the wrong stopping
  point and the gap is ours, not Ring's.
- **Workaround**: Built a fixture and replay boundary at the HTTP client layer
  (`app/ring_client.py`). Every code path that would hit `api.amazonvision.com` is
  reachable, typed and unit-tested against recorded JSON in `fixtures/`, but no request
  has ever left this machine.
- **Suggestion**: Either publish the sandbox host and its auth flow, or take the word out
  of the glossary and the FAQ. The hackathon page's claim that a physical Ring device is
  not required needs to be reconciled with the developer documentation, which says the
  opposite in the one section where it matters.

### 3. Clip retrieval requires a paid plan, and the failure is a 416 on a documented endpoint
- **Task**: Design the "pull the ninety seconds either side of the incident" feature,
  which is this product's whole reason to exist.
- **Steps**: Read `POST /v1/devices/{id}/media/video/download` in the API reference.
- **Expected**: Any registered device returning a clip for a valid timestamp inside its
  retention window.
- **Actual**: *"If the camera was not recording at the requested timestamp, you will
  receive a 416 TIMESTAMP_NOT_FOUND error."* Continuous recording is a paid tier.
  Event-only recording, which is what a device without that tier does, will miss the
  requested window almost every time, because the point of the feature is footage from
  before the event that triggered it. So the documented success path for this endpoint
  requires a subscription, and the documented failure is `416 TIMESTAMP_NOT_FOUND`.
- **Severity**: High. It is the load-bearing feature, and the constraint that governs it
  appears once, in passing, in a different section from the endpoint.
- **Workaround**: `ring_client.fetch_clip()` treats `416` as a named outcome rather than
  an exception bolted on afterwards. The incident record is still created and still
  exports, carrying a field that says "clip unavailable, continuous recording not
  enabled" instead of silently producing a pack with a hole in it. Pinned by
  `tests/test_ring_client.py::test_fetch_clip_416_produces_explicit_gap_not_a_crash`.
- **Suggestion**: Put the plan-tier requirement in the endpoint's own description, above
  the parameters, not in a section a developer reads later. A capability that depends on
  a subscription should say so where the capability is documented. As it stands, an
  integrator designs a feature, builds it, and finds out at the first real call — and on
  this track the first real call comes after the demo is scripted.

### 4. No starter project reachable from this machine
- **Task**: Find `AmazonAppDev/ring-api-helloworld` to start from, per the build brief.
- **Steps**: `find / -iname "*ring-api-helloworld*"` across the filesystem.
- **Expected**: A cloned starter to build from.
- **Actual**: Not present anywhere on this machine, and the brief gives a repo name with
  no clone URL. No GitHub token was configured for this session either.
- **Severity**: Medium.
- **Workaround**: Built from the documented API shapes in `research/PLATFORM-FACTS.md`
  and the topic files instead of the starter's own file layout. The request and response
  shapes match what those files record from
  `developer.amazon.com/docs/ring/api-documentation.html`, but I never saw the starter's
  error handling or retry conventions, so mine may diverge from Amazon's reference style.
- **Suggestion**: Vendor the starter alongside the hackathon materials, or give a working
  clone URL rather than a repo name.

### 5. The HMAC header is named and the signing scheme is not
- **Task**: Build `verify_webhook_signature()` to check `X-Signature`.
- **Steps**: The reference says "Signed webhooks (HMAC-SHA256 in `X-Signature`)" and
  nothing more. No canonicalisation rule — raw body or re-serialised JSON — no timestamp
  or nonce header, no worked example.
- **Expected**: A worked signing example, the way Stripe and GitHub webhook docs give
  you one.
- **Actual**: One sentence. No sample payload, no sample secret, no resulting header
  value.
- **Severity**: Medium, and it is a security item rather than a convenience one. An
  integrator guessing at canonicalisation will get it wrong in a way that still passes
  their own tests, because they generate the fixtures with the same guess.
- **Workaround**: Implemented the conservative common-case reading,
  `hex(hmac_sha256(shared_secret, raw_request_body))`, constant-time compared, isolated in
  `app/webhooks.py::verify_signature()` so it is a one-function change if Ring's actual
  scheme differs. No replay protection, because no nonce or timestamp header is
  documented; written down in `SPEC.md` as a known gap rather than left silent.
- **Suggestion**: Publish one worked example: a sample body, a sample secret, the
  resulting header. Three lines of documentation that remove a guess from every
  integration. And if there is a timestamp header, name it, because without one every
  correct implementation of this scheme is replayable.

### 6. The consent time-gate has no API shape, and its practical effect is that there is no backfill
- **Task**: Enforce "events before the consent date are not accessible", so the demo
  cannot accidentally show history it should not have.
- **Steps**: Looked for a `consent_granted_at` field on the device or account object.
- **Expected**: A field, since the behaviour is documented.
- **Actual**: The behaviour is stated — older events are filtered server-side — and the
  timestamp it filters on is not exposed anywhere a client can read. The consequence,
  stated plainly because the reference itself does not: `GET /v1/history/devices/{id}/events`
  has no backfill window and no way to request one. A shop that links its account the
  morning after a serious incident gets a record that starts the morning after — nothing
  server-side will ever produce that incident's motion or ding event, and there is no
  parameter, no plan tier and no support request that reaches back before the link.
  For a violence log specifically, that is not a cosmetic gap: it means the one incident
  most likely to be the reason a shop signs up for this product is, by construction, the
  one incident the Ring side of the app can never corroborate.
- **Severity**: Low for the API contract, since the server enforces it regardless and
  consistently. Medium for the product, because it sets an expectation ("the record
  pulls the footage") that has a real, silent exception on day one of any deployment.
- **Workaround**: Stored the value ourselves at the moment account linking completes
  (`store.py::record_consent_grant()`), and the fixture loader filters history against it
  so the demo mirrors server behaviour. Pinned by
  `tests/test_ring_client.py::test_event_history_consent_gate_excludes_pre_consent_events`.
  There is no workaround for the underlying gap — a staff-completed incident record
  never depends on Ring footage existing, precisely because it cannot be guaranteed to.
- **Suggestion**: Expose the consent timestamp on `GET /v1/devices/{id}`. Then a client
  can tell a user *why* their history starts where it does, instead of showing a short
  list and letting them assume the camera was off. Separately, a documented backfill
  window — even 24 to 48 hours — would close the exact gap described above for any Ring
  integrator building on day-of-signup history, not just this one.

### 7. The model our own brief called verified cannot be invoked by this account
- **Task**: Add the Bedrock drafting step, using `anthropic.claude-sonnet-5` on
  us-east-1, which the build brief described as live and verified.
- **Steps**:
  - `aws bedrock list-foundation-models --region us-east-1` lists
    `anthropic.claude-sonnet-5` and `anthropic.claude-opus-5`.
  - `aws bedrock list-inference-profiles --region us-east-1` also lists
    `us.anthropic.claude-sonnet-5`.
  - `aws bedrock-runtime converse --model-id anthropic.claude-sonnet-5`.
- **Expected**: An inference call, since the model is in the account's own catalogue.
- **Actual**: `AccessDeniedException: anthropic.claude-sonnet-5 is not available for this
  account.` The `us.`-prefixed profile fails the same way, and the error message drops
  the prefix you typed, so it reads as though the CLI ignored your argument. A third
  shape fails differently again: the bare `anthropic.claude-sonnet-4-6` returns
  `ValidationException: Invocation of model ID ... with on-demand throughput isn't
  supported.` `us.anthropic.claude-sonnet-4-6` and
  `us.anthropic.claude-sonnet-4-5-20250929-v1:0` both answer in about 1.5s.
- **Severity**: Medium for time. The part worth reporting is that four agents on this
  project lost time to it independently, from the same listing output, on the same day.
- **Workaround**: `app/bedrock.py` ships a preference chain rather than a constant. It
  tries the brief's model first so the build upgrades itself the day access lands, treats
  `AccessDeniedException`, `ValidationException` and `ResourceNotFoundException` as "not
  this one, try the next", and caches the first id that answers for the life of the
  process. A throttle or a timeout is a real failure and goes to the caller as
  `BedrockUnavailable`.
- **Suggestion**: `ListFoundationModels` and `ListInferenceProfiles` both return models
  the calling account cannot invoke, with nothing in either response distinguishing them.
  Add an `accessStatus` field. Today the only method available is to invoke every
  candidate and read the exception, which costs one call per model and gives an answer
  that is only valid for that account in that region. And echo the model id the caller
  actually sent in the `AccessDeniedException` message, because dropping the `us.` prefix
  sends people round the loop a second time doubting the CLI.

### 8. Bedrock will write a legal characterisation into a statutory record, and a denylist will not stop it
- **When**: after the drafting step worked, re-reading what it produced rather than what
  the tests asserted.
- **Task**: Let a model draft the narrative fields of a Cal/OSHA workplace violence
  record while the statutory classifications stay human-chosen, and guarantee the draft
  never concludes, accuses or judges.
- **Steps**: The system prompt says exactly that, in rule 4. The enforcement is
  `app/incident_language.py`'s `BANNED_ACCUSATIONS`, thirteen phrases. We ported the
  denylist out and ran real sentences through it.
- **Expected**: Accusatory drafts blocked.
- **Actual**: Two of four got through.

  ```
  PASSES GUARD  :: The individual attempted to rob the register and threatened to kill the clerk.
  PASSES GUARD  :: A man in his forties in a red jacket with a neck tattoo came over the counter.
  blocked       :: The suspect was seen on camera.
  blocked       :: The offender was intoxicated and assaulted the clerk.
  ```

  `the attacker`, `the thief` and `he stole` are on the list. `attempted to rob`,
  `threatened to kill` and `assaulted` are not. The second sentence violates a different
  prompt rule — no physical description, no clothing — which has no validator at all. Both
  reach the unredacted evidence pack that goes to a police officer, under a gutter note
  reading "Drafted by software, accepted unchanged."
- **Severity**: High. The record has a five-year retention duty and an audience with
  powers.
- **Workaround, and its limits**: the human gate is real and is the reason this is not
  worse. Nothing is filed until a person saves it, the amendment trail records edited
  against accepted, and the document says which fields software drafted. That mitigates
  and does not close it, because the failure mode of a fluent draft is that a shaken
  person accepts it. The real fix is the one the free-text audit landed on across the
  whole repository: a model string is either a span of the source or a value from a
  closed set, and there is no third kind. A denylist is a fourth kind and it is the one
  that looks like a control.
- **Suggestion**: This is feedback about Bedrock rather than about Ring. The Converse
  API's `toolConfig` gives you a JSON schema, and a JSON schema constrains shape and
  never content. There is no way to say "this string must be a span of the input I gave
  you", which is the single constraint that would make grounded extraction safe by
  construction rather than by a validator every developer writes again. Constrained
  decoding against a source document, or even a documented pattern for it in the Bedrock
  guides, would close a class of defect that is currently everybody's homework. We've
  seen the same shape elsewhere: a prompt forbidding exactly the sentence the model then
  produced, with nothing stopping the model from producing it anyway.

### 9. Three fields the guard never saw, in the app that guards best
- **When**: an audit pass over every place a model's words reach a person.
- **Actual**: three findings in this app, all the same shape.
  - `DRAFTED_FIELDS` is a hand-maintained tuple of three field names. The tool schema
    returns a fourth, `not_said[]`, an optional model-authored array of prose capped at
    six items and at nothing else. It is never length-capped per item, never passed to
    the safety assertion, never passed to the PII scan, and it renders to the person
    completing the form styled as the app's own checklist. A hand-maintained list of
    fields to check, sitting next to a schema that grew a new one.
  - The PII guard reads `if finding.certain and finding.text not in words`. `certain` is
    true only for regex shapes — SSN, email, phone, street address, title plus surname.
    It is false for the capitalised-run name heuristic. So a model that invents a plain
    name passes the guard, and the redaction that would catch it downstream runs only on
    the statutory log, never on the evidence pack, which is the document with the police
    officer at the end of it. One boolean.
  - The statutory purge never touches the `drafts` table, and the form renders the draft
    block above the `is_purged` branch, so model text and the worker's raw unredacted
    words survive a purge the statute requires.
- **Severity**: High, and instructive rather than embarrassing: this app's test suite is
  the best in our set, with tests written to pin fixes and name the old broken behaviour
  in their docstrings. None of these three was found by a test. All three were found by
  reading the schema against the guard list, and by rendering the page.
- **Suggestion to ourselves**: walk the parsed object, reject on an unknown key, and make
  it structural so the list cannot go stale.

### 10. A bug the test suite passed clean and the live server did not
- **Task**: Run the app for real after all 45 tests were green, to check the demo works
  rather than that the units do.
- **Steps**: Started the Flask dev server, replayed a signed webhook, tapped the capture
  button.
- **Expected**: A saved incident, the same as in every integration test.
- **Actual**: `500 Internal Server Error`. Flask's dev server runs each request on its
  own thread; the app's single shared `sqlite3.Connection` was opened on the startup
  thread, and sqlite3 refuses to touch a connection from another thread by default.
  Flask's test client, which all 45 passing tests used, does not spawn threads, so the
  bug was invisible to the entire suite.
- **Severity**: High. It would have failed live, in front of judges, after a fully green
  test run.
- **Workaround**: `check_same_thread=False` in `app/store.py`, with a comment saying why,
  and `tests/test_store_threading.py` saving and reading an incident from a spawned
  thread so this class of bug cannot come back quietly.
- **Suggestion for future me, not for Ring**: "all tests pass" is not "the app runs". The
  instruction to build the thing and then run it is what caught this, and it is the same
  instruction that caught row 9.

### 11. WeasyPrint 70 changed the `url_fetcher` contract and the old shape fails at render time
- **Task**: Render the statutory log and the evidence pack to PDF, resolving the
  document's own `/static/...` references to files in the package so a rendered record
  never touches the network.
- **Steps**: Passed `url_fetcher=` a plain function returning the documented
  `{"string": ..., "mime_type": ...}` dict, which is what the examples still show.
- **Expected**: The fetcher is called for the stylesheet and the four font files.
- **Actual**: `'function' object has no attribute '_fail_on_errors'`. In 70 the fetcher
  must be a `URLFetcher` instance with private attributes and must return a
  `URLFetcherResponse`, and `weasyprint/urls.py` asserts on the return type. The error
  names a private attribute rather than the contract, so it reads as an internal bug
  rather than an API change. A second failure in the same hour: `Relative URI reference
  without a base URI: /static/record.css`. A root-relative href in a `string=` document is
  silently dropped unless `base_url` is set, and the only symptom is a PDF with no
  stylesheet, which looks like a CSS problem rather than a fetch that never happened.
- **Severity**: Medium, about forty minutes.
- **Workaround**: Dropped the custom fetcher. `app/export_pdf.py` rewrites `/static/` to
  an absolute `file://` URL before rendering, sets `base_url` to the package's static
  directory so the stylesheet's own relative font URLs resolve, and passes
  `URLFetcher(allowed_protocols=["file", "data"])`, which keeps the "a record is built
  only from files that shipped with the software" guarantee without depending on a
  private attribute.
- **Suggestion**: Raise a named error when a `url_fetcher` is not a `URLFetcher`, and warn
  rather than silently ignore a relative URI in a `string=` document.

### 12. Google Fonts serves one variable file per family and bills it as several
- **Task**: Vendor two faces locally, because the kiosk sits on a shop counter and the
  app has to render identically with no network.
- **Steps**: Requested `Public Sans:wght@400;600;700` from the css2 endpoint and
  downloaded the `woff2` from each `/* latin */` block.
- **Expected**: Three files, or one file and one block.
- **Actual**: Three `@font-face` blocks with three weights and the same URL in all three,
  so a naive download writes the same 26,832-byte variable font to disk three times under
  three names. Same for Source Serif 4.
- **Severity**: Low, and the kind of thing that silently triples an asset budget.
- **Workaround**: One file per family, declared `font-weight: 100 900`.
- **Suggestion**: The css2 response gives no hint that a file is variable. A comment
  naming the axis would be enough.

### 13. The statutory detail that changes the product was not in our own research file
- **Task**: Build the log export.
- **Steps**: The topic file summarises California Labor Code 6401.9(d)(2) accurately and
  I nearly built from the summary. Fetched the section text from leginfo to check the
  option lists word for word.
- **Actual**: Four things the summary did not carry, each of which changes the build.
  (d)(1)(B) requires the employer to "omit any element of personal identifying
  information sufficient to allow identification of any person involved", which makes
  de-identification a duty on the log and forces two separate documents. (B) is "the
  workplace violence type **or types**" and (G) is "whether it involved **any** of the
  following", so both are multi-select and the first build modelled both as single
  values. (D) lists eight classifications, not five. (I) requires "name, job title, **and
  the date completed**", which the first build did not store.
- **Severity**: High, in that the first build shipped a form that did not match the
  statute it cited.
- **Workaround**: `app/statute.py` transcribes every option list verbatim with its
  statutory wording, both documents print that wording under the plain-English question,
  and `store_serialize.py` migrates records written against the old vocabulary.
- **Suggestion for us, not for Amazon**: when a product's whole claim is that it produces
  the document a statute asks for, read the statute rather than a summary of it. A
  paraphrase of a legal list is a different list.

### 14. Two Jinja mistakes whose error messages point somewhere else
- **Actual**: A macro named `history` shadowed a context variable named `history`, and
  the failure surfaced as `'jinja2.runtime.Macro object' has no attribute 'get'`, five
  lines from the cause. Separately, `selectattr("provenance", "startswith", "Drafted")`
  raises `No test named 'startswith'` — Jinja has no such test, and the natural-looking
  filter chain is unavailable.
- **Severity**: Low each.
- **Workaround**: Renamed the macro to `amendment_trail`, and moved the "which fields did
  the software draft" computation into `document.py` where it can be tested.

### 15. `sub_type: human` cannot be trusted as testimony, and the guard treats it as a device's guess, not a witness

- **Task**: Decide whether `compose_event_summary()` could write a plain sentence like "a
  person was at the counter" when a tap arrives, since that is the trigger for the whole
  capture flow.
- **Steps**: Cross-checked the Ring event vocabulary against what two research passes
  found and `research/PLATFORM-FACTS.md` records independently: Ring's own classifier has
  been documented labelling a motorised wheelchair user a package rather than a person.
- **Expected**: Not a bug report. A design constraint forced by evidence.
- **Actual**: Writing `sub_type` as a fact would put a documented misclassification into a
  five-year statutory record with a police officer at the end of it, which is a worse
  failure here than in an arrival log: this app's whole second half asks a human being to
  characterise what a camera saw, and a camera that calls a wheelchair a package is not a
  source, it is a hint.
- **Severity**: High for the product's honesty, not for build time.
- **Workaround**: `compose_event_summary()` phrases the device's classification as the
  device's own assertion, never as a fact: "The device classified the event `human`. That
  classification is the manufacturer's automatic one, it has not been checked by a
  person, and it is not a statement that a person was present." `incident_language.py`'s
  no-accusation rule (row 8) sits on top of this and reaches every sentence the app
  composes for itself, not only this one. `tests/test_documents.py` names the wheelchair
  case directly in its own docstring so the reasoning survives a refactor without the
  citation getting lost.
- **Suggestion**: Publish a confidence score alongside `sub_type` so an integrator can
  pick a threshold, instead of
  a binary label known to misclassify mobility-aid users going straight into a legal
  record with nothing beside it to weigh.

### 16. Two things stop a judge before the first incident is even captured, neither a bug in this app's own logic

- **When**: audit pass, following the README's install and run block exactly on a scratch
  checkout, rather than the venv already set up from writing the app.
- **Task**: Run `pip install -r requirements.txt` then `python -m app.server`, the way a
  judge would, and reach the point of tapping "Capture" for the first time.
- **Steps**: `requirements.txt` line 8 is `weasyprint>=66`, unconditional, three lines
  below a comment on the same block that reads "Optional. Without it the .pdf routes
  return a named 503 and the same document is served as HTML." The install resolved
  clean here (WeasyPrint 70 came from a prebuilt wheel on this machine), but the package
  needs system Cairo and Pango at import time, which a clean machine, especially a fresh
  container or a locked-down laptop, is not guaranteed to have; there it fails `pip
  install` before the app has run once. Separately, started the server with something
  else already bound to 5057:
  ```
  Address already in use
  Port 5057 is in use by another program. Either identify and stop that program,
  or start the server with a different port.
  ```
  `app/server.py`'s `application.run(debug=False, port=5057)` is hard-coded with no env
  override anywhere in the file, so the error's own second sentence describes an action
  the reader has no way to take.
- **Expected**: A dependency the comment calls optional installing as optional, and a
  port a judge can change without editing source.
- **Actual**: Both gaps are real and neither is hidden. The comment on `weasyprint` is
  honest about what it is, it is just not backed by the file's own unconditional listing;
  the port error is Werkzeug's stock message, accurate about the problem and wrong about
  the remedy on this specific install.
- **Severity**: Medium for each. Neither stopped this machine's run, since the wheel
  installed and 5057 was free, which is exactly why both are easy to miss reviewing a
  working checkout rather than a clean one.
- **Workaround**: None shipped yet; recorded here rather than silently patched, since both
  are one-line fixes and this log is where the next person should find them before
  rediscovering them the same way. The fix for the first is a `requirements-pdf.txt` (or
  an install extra) so the base install genuinely matches its own comment. The fix for the
  second is `port=int(os.environ.get("INCIDENT_BOOK_PORT", 5057))`.
- **Suggestion**: Nothing Amazon-specific — this is Flask/Werkzeug and a Python packaging
  choice, not a platform constraint. Recorded because a judge stopped at either one never
  reaches anything else in this log.

---

## Product feedback (for the required submission answer)

**Tools, APIs and SDKs used.** Python 3.14 standard library (`hmac`, `hashlib`,
`sqlite3`, `json`), Flask 3.1, pytest 9.1, WeasyPrint 70 for the PDFs, and
`@aws-sdk`-equivalent `boto3` for Bedrock Converse. There is no official Ring Partner
SDK — the reference says so plainly, "use standard HTTP libraries" — so
`app/ring_client.py` is hand-written against the documented REST shapes.

**Onboarding, zero to hello world.** Not completed, and that is the headline. Every
developer path terminates at a real, paid, US-located, Ring Protect-subscribed device.
The documentation is readable and the shapes are clear; the problem is entirely that
there is no way to exercise them. Bedrock's onboarding, by contrast, took one CLI call,
and the only stumble there was the model id.

**What worked.** The webhook event vocabulary and the media endpoints are well specified
once found: clear field names, clear verbs, documented rate limits with `X-RateLimit-*`
headers. The JSON:API envelope is consistent. Bedrock's `Converse` with a forced
`toolConfig` is the right shape for structured drafting and removes JSON-parsing-of-prose
entirely.

**What needs work.** In order of what it cost: no reachable sandbox despite the word
appearing twice in the documentation; no worked webhook-signing example, which leaves
every integrator guessing at canonicalisation; the `416 TIMESTAMP_NOT_FOUND` plan-tier
constraint documented in a different section from the endpoint it governs; no starter
repo reachable without a GitHub fetch; no consent timestamp exposed on the device record.
On the AWS side, `ListFoundationModels` returning models the account cannot invoke, and
no way to constrain a model string to a span of the source document.

**Amazon Devices Builder Tools.** Not used. It is the first item under "Start here" on
the Resources page for this track and we went to the API reference instead. What would
have changed that: a line saying it can answer questions the reference does not, such as
the webhook signing recipe or which endpoints are plan-gated. "Documentation search" reads
like a search box over pages we had already opened.

**Would we build with it again?** The API shape is good enough to build something honest
on, and for a log-shaped product it is a good fit. The developer experience of reaching a
first real call is not, for anyone without an existing Ring Protect subscription at a US
address. That gap is the organisers' first fix before the next event, because it is the
reason a Ring integration built without one ends up demonstrating replayed fixtures
instead of a live device.

## One thing we would tell the next team

The most dangerous field in a statutory record is the one nobody listed. Our guard list
had three field names in it and the tool schema had four, and the fourth rendered to the
user in the app's own voice. Walk the parsed object instead of naming the fields, reject
on an unknown key, and then open the page and read what the model actually wrote, because
the test suite is only going to check the sentences you already thought of.
