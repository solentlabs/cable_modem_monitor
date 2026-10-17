# Detection Specification

Auto-detect narrows the catalog choice for a user who has not picked a
modem. It reads a device's landing page and reports which catalog
entries the page names. It never selects a modem, a variant or an auth
strategy; the user confirms the result.

Governing decision:
[ARCHITECTURE_DECISIONS.md § Detection narrows, never decides](ARCHITECTURE_DECISIONS.md#detection-narrows-never-decides).
Consumer flow: [CONFIG_FLOW_SPEC.md § Auto-detect](../../../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md#auto-detect).
Accuracy report: [INTAKE_PIPELINE.md § Detection Accuracy](../../cable_modem_monitor_catalog_tools/docs/INTAKE_PIPELINE.md#detection-accuracy).

## API

Module `solentlabs.cable_modem_monitor_core.detection`. Synchronous and
blocking; async consumers call it in an executor.

```python
@dataclass(frozen=True)
class Observation:
    scheme: str                    # "http" or "https" of the final response
    status: int
    final_path: str                # path after redirects
    server: str | None
    title: str | None
    www_authenticate: str | None
    password_field: bool           # body holds an input of type password


@dataclass(frozen=True)
class PageMatch:
    models: list[ModemSummary]     # entries whose model or alias the page names
    buckets: list[str]             # manufacturer and brand names the page names
    matched: list[str]             # the catalog names found on the page, as spelled there


@dataclass(frozen=True)
class Detection:
    host: str                      # an address that answered
    observation: Observation
    match: PageMatch


def detect(summaries: list[ModemSummary], *, timeout: float = 3.0) -> list[Detection]: ...


def match_page(text: str, summaries: list[ModemSummary]) -> PageMatch: ...


def describe_response(
    url: str, status: int, headers: Mapping[str, str], body: bytes
) -> tuple[Observation, str]: ...
```

`detect()` returns one `Detection` per address that answered, including
those with no hit. An empty list means nothing answered. `match_page()`
is the pure matcher: `detect()` calls it on each probed page and pairs
the result with the host and observation, and the accuracy report calls
it on captured landing responses, so runtime and report cannot drift.
`describe_response()` is the other shared step: it turns a landing
response into its `Observation` and the text `match_page()` reads, with
the text of § Matching: the `Server` header, then the body decoded as
UTF-8 with replacement and cut at the § Sweep body limit.

## Sweep

Hosts are the distinct `default_host` values of `summaries`, most
frequent first, then lexical. All are probed concurrently.

Per host, one credential-free `GET /`:

- `http://` first, then `https://` when `http://` yields no HTTP
  response. The first response wins.
- Redirects are followed (limit 5), across schemes. TLS verification is
  off, as everywhere in Core (`connectivity.create_session`).
- A fresh session per host; no credentials, no cookies carried over.
- The body is read up to 256 KiB.

A host that refuses, times out or errors is not an answering host.

## Matching

Text is the response's `Server` header followed by its body. It is
lowercased and split into runs of `[a-z0-9]`. A name matches when its
own tokens appear as a consecutive run in the page's tokens, so `CM600`
does not match `CM6000`.

| Result | A name matches when |
|--------|---------------------|
| `models` | an entry's `model` or any `model_aliases` entry matches |
| `buckets` | an entry's `manufacturer` or any `brands` entry matches |

The observation is evidence for the user, the log and the accuracy
report. The matcher never reads it; narrowing on scheme, `Server` or
login shape would infer a modem from an ambiguous signal.

`PageMatch.models` lists every matching entry. `buckets` lists each matching name
once, as the catalog spells it. Both are computed independently: a page
can name a maker and no model. There is no scoring, weighting or
threshold.

## Bounds

- Detection never authenticates and never retries. No credentials are
  sent, so a probe cannot lock out a modem or collide with a session on
  single-session firmware. No strategy is inferred from the page.
- Nothing is persisted. No index or signature file exists; the names
  come from `summaries` at call time.
- A signal beyond page text is added only for a gap the detection
  accuracy report measures. It orders candidates and removes none until
  the report shows no entry wrongly removed by it across the fleet
  ([INTAKE_PIPELINE.md § Marker accuracy](../../cable_modem_monitor_catalog_tools/docs/INTAKE_PIPELINE.md#marker-accuracy)).
  The change that adds one specifies where its per-modem values live.
