# Detection Specification

Auto-detect narrows the catalog choice for a user who has not picked a
modem. It sends one credential-free request to each catalog address,
reads the single reply (headers, redirect chain and body), compares it
with what each catalog entry's own configuration says its login surface
looks like, and reports the entries the device could be. It never
selects a modem, a variant or an auth strategy; the user confirms the
result.

**Invariant.** When the device probed is a registered modem, that modem
is among the candidates. Names, signals and `Server` only order
candidates; the one rule that removes an entry is § Narrowing's
contradiction rule, and the accuracy report fails when it removes a
real modem
([INTAKE_PIPELINE.md § Detection Accuracy](../../cable_modem_monitor_catalog_tools/docs/INTAKE_PIPELINE.md#detection-accuracy)).

Governing decision:
[ARCHITECTURE_DECISIONS.md § Detection narrows, never decides](ARCHITECTURE_DECISIONS.md#detection-narrows-never-decides).
Consumer flow: [CONFIG_FLOW_SPEC.md § Auto-detect](../../../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md#auto-detect).

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
class Reply:
    paths: list[str]               # paths the reply points at, see § Reply evidence
    cookies: list[str]             # cookie names the reply sets
    server: str | None             # the Server product, the text before "/"


@dataclass(frozen=True)
class Candidate:
    summary: ModemSummary
    tier: int                      # 1, 2 or 3, see § Narrowing
    signals: list[str]             # the config signals found in the reply
    named: bool                    # the page names the entry's model or alias


@dataclass(frozen=True)
class Detection:
    host: str                      # an address that answered
    observation: Observation
    match: PageMatch
    reply: Reply
    candidates: list[Candidate]    # the entries kept, best first


def detect(summaries: list[ModemSummary], *, timeout: float = 3.0) -> list[Detection]: ...


def match_page(text: str, summaries: list[ModemSummary]) -> PageMatch: ...


def read_reply(hops: Sequence[tuple[str, Mapping[str, str], bytes]]) -> Reply: ...


def narrow(
    summaries: list[ModemSummary], match: PageMatch, reply: Reply, observation: Observation
) -> list[Candidate]: ...


def describe_response(
    url: str, status: int, headers: Mapping[str, str], body: bytes
) -> tuple[Observation, str]: ...
```

`detect()` returns one `Detection` per address that answered. An empty
list means nothing answered. `match_page()`, `read_reply()` and
`narrow()` are the pure steps: `detect()` calls them on each probed
host, and the accuracy report calls them on captured replies, so
runtime and report cannot drift. `describe_response()` turns a landing
response into its `Observation` and the text `match_page()` reads, with
the text of § Matching: the `Server` header, then the body decoded as
UTF-8 with replacement and cut at the § Sweep body limit.
`read_reply()` takes each response of a redirect chain as `(url,
headers, body)`.

`ModemSummary.landing_signals` and `ModemSummary.server_headers` are
filled by `list_modems()` from the entry's configuration, see
§ Signals. `ModemSummary.auth_strategies` lists the `auth.strategy` of
every variant of the entry.

## Sweep

Hosts are the distinct `default_host` values of `summaries`, most
frequent first, then lexical. All are probed concurrently.

Per host, one credential-free `GET /`:

- `https://` first, then `http://` when `https://` yields no HTTP
  response. The first response wins. A listener that completes a TLS
  handshake is preferred, as in
  [CONFIG_FLOW_SPEC.md § Step 4](../../../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md#step-4-validate).
- Redirects are followed (limit 5), across schemes. TLS verification is
  off, as everywhere in Core (`connectivity.create_session`).
- A fresh session per host; no credentials, no cookies carried over.
- The body is read up to 256 KiB.

A host that refuses, times out or errors is not an answering host. That
request, and its redirects, is all a probe sends.

## Matching

Text is the landing response's `Server` header followed by its body. It
is lowercased and split into runs of `[a-z0-9]`. A name matches when its
own tokens appear as a consecutive run in the page's tokens, so `CM600`
does not match `CM6000`.

| Result | A name matches when |
|--------|---------------------|
| `models` | an entry's `model` or any `model_aliases` entry matches |
| `buckets` | an entry's `manufacturer` or any `brands` entry matches |

`PageMatch.models` lists every matching entry. `buckets` lists each
matching name once, as the catalog spells it. Both are computed
independently: a page can name a maker and no model. There is no
scoring, weighting or threshold.

## Reply evidence

`read_reply()` reduces the reply to three things:

- **Paths.** From the HTML body of each response in the redirect chain,
  the values of `src`, `href`, `action` and `data` attributes and the
  target of a `<meta http-equiv="refresh">`. A redirect's own `Location`
  is not collected: where it points is a correlation, and the page it
  leads to carries the evidence. Each value is resolved against its
  response's URL; values on another host are dropped; what remains is
  the path without query string or fragment, with `/` dropped. Each path
  appears once.
- **Cookies.** The names of cookies set by any response in the chain.
- **Server.** The `Server` header's product, the text before `/`.

No value is fetched.

## Signals

Each entry's configuration already says what its login surface looks
like. The auth strategy owns that knowledge
([ARCHITECTURE_DECISIONS.md § Strategy knowledge lives with the strategy](ARCHITECTURE_DECISIONS.md#strategy-knowledge-lives-with-the-strategy)):
it reports, from its config, the paths and cookie names its login
surface carries. Examples are `action`, `login_page` and
`login_endpoint`, `cookie_name`, and for a protocol-locked transport
such as HNAP its client script. `parser.yaml` adds the paths of the data
pages the entry reads. Field names such as `username` are not signals:
many entries share them.

`list_modems()` collects an entry's signals across all its variants into
`ModemSummary.landing_signals`. An entry with none carries an empty list.
A signal is found when a path signal equals a path in `Reply.paths` or a
cookie signal equals a name in `Reply.cookies`.

`ModemSummary.server_headers` holds the `Server` products the entry's
landing replies showed, from `modem.yaml`
([MODEM_YAML_SPEC.md § Detection](MODEM_YAML_SPEC.md#detection)).

## Narrowing

`narrow()` starts from the whole catalog.

| Tier | An entry is in the tier when |
|------|------------------------------|
| 1 | the page names its model or alias, or one of its signals is found in the reply |
| 2 | the page names its manufacturer or a brand, or `Reply.server` is among its `server_headers` |
| 3 | neither |

The candidates are tier 1, then tier 2, then tier 3. Within tier 1 the
entries the page names come first; every other group is in catalog order.
A name is stronger evidence than a signal: several entries can declare the
same cookie, but a page that spells a model names it.

**Contradiction rule.** When the reply holds a password field, a tier 3
or tier 2 entry whose every variant has `auth.strategy: none` is removed:
a no-auth modem does not present a login form. An entry the page names or
whose signal is found stays. This is the only removal. Whether it
holds is measured on the fleet
([INTAKE_PIPELINE.md § Detection Accuracy](../../cable_modem_monitor_catalog_tools/docs/INTAKE_PIPELINE.md#detection-accuracy));
another contradiction is added only when that report shows it removing
no real modem.

A name never removes an entry: a page can name another maker, so a
missing name removes nothing. Missing signals remove nothing either: a
login driven by script may reference nothing its config declares.

## Observation

The `Observation` is evidence for the user, the log and the accuracy
report. Beyond the password field the contradiction rule reads, neither
the matcher nor `narrow()` reads it. The other landing response markers
(scheme, `WWW-Authenticate`) are used at runtime only as
[INTAKE_PIPELINE.md § Marker accuracy](../../cable_modem_monitor_catalog_tools/docs/INTAKE_PIPELINE.md#marker-accuracy)
permits.

## Bounds

- Detection never authenticates and never retries. The request is a
  credential-free `GET`, so a probe cannot lock out a modem or collide
  with a session on single-session firmware. No strategy is inferred.
- One request per distinct address, plus its redirects. Nothing is
  fetched for any entry or path.
- Nothing is persisted at runtime. Names, signals and servers come from
  `summaries` at call time.
