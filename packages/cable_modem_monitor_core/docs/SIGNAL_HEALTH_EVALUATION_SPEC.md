# Signal Health Evaluation Specification

> Parent specs: [ORCHESTRATION_SPEC.md](ORCHESTRATION_SPEC.md) —
> runtime data models and snapshot contract,
> [RUNTIME_POLLING_SPEC.md](RUNTIME_POLLING_SPEC.md) — poll cadence and
> `docsis_status` derivation,
> [PARSING_SPEC.md](PARSING_SPEC.md) — normalized channel fields and
> aggregate system_info fields

This specification governs how Core evaluates normalized modem telemetry
into a compact signal-health result. The evaluation is platform-agnostic:
it does not know about Home Assistant entities, options flows,
translations, or icons. Consumers provide the current snapshot,
user-selected thresholds, and optional prior-sample context; Core
returns typed result data only.

## Contents

| Section | What it covers |
|---------|----------------|
| [Purpose](#purpose) | What this evaluator is for and what it is not for |
| [Design principles](#design-principles) | Platform boundaries and invariants |
| [Public API](#public-api) | Evaluator inputs and outputs |
| [Threshold model](#threshold-model) | Typed threshold input contract |
| [Result model](#result-model) | Typed result payload returned by Core |
| [DOCSIS trust rule](#docsis-trust-rule) | Locked-only trust model for RF grading |
| [Metric groups](#metric-groups) | Evaluated groups and comparison semantics |
| [Evaluation flow](#evaluation-flow) | Ordered evaluation steps |
| [Tie-breaking](#tie-breaking) | Deterministic decisive-metric selection |
| [Baseline-dependent metrics](#baseline-dependent-metrics) | Error-rate initialization and provisional values |
| [Consumer responsibilities](#consumer-responsibilities) | What the platform layer must do |

---

## Purpose

The signal-health evaluator answers one question:

```text
Given the current normalized modem snapshot and a threshold profile,
what is the current signal-health grade and which metric group decided it?
```

The evaluator produces a compact, machine-readable result suitable for:

- Home Assistant sensor attributes
- automations
- diagnostics output
- other non-HA consumers

It does not produce:

- translated display strings
- icon names
- entity availability decisions
- persisted baseline storage
- Home Assistant-specific metadata

Those belong to the consumer layer.

---

## Design principles

1. **Core is data-first.** Return typed values and machine-readable
   reason codes, not UI phrasing.
2. **Core does not read platform storage.** Thresholds and baselines
   are passed in by the consumer.
3. **Only trusted DOCSIS state may be graded.** Anything less than
   locked forces `poor`.
4. **Metric groups are independent.** Each group yields one grade and
   one observed value summary.
5. **The worst group wins.** The final grade is determined by the most
   severe metric group, subject to the DOCSIS trust rule.
6. **Unsupported and provisional are different.** Unsupported means the
   modem does not expose the data. Provisional means the metric exists
   but one more sample is needed.
7. **Results must be deterministic.** The same inputs always produce
   the same decisive metric and same channel selection.

---

## Public API

Core-facing contract:

```python
@dataclass(frozen=True)
class SignalHealthBaseline:
    total_uncorrected: int
    sampled_at: datetime


@dataclass(frozen=True)
class SignalHealthEvaluationInput:
    snapshot: ModemSnapshot
    thresholds: SignalHealthThresholds
    baseline: SignalHealthBaseline | None = None


def evaluate_signal_health(
    evaluation: SignalHealthEvaluationInput,
) -> SignalHealthResult:
    """Evaluate normalized modem telemetry into a signal-health result."""
```

Notes:

- `snapshot` is the current normalized Core snapshot
- `thresholds` is a typed profile built by the consumer from user
  options and fixed limits
- `baseline` is optional prior-sample context for error-rate
  evaluation

The function is pure with respect to consumer state:

- no Home Assistant imports
- no I/O
- no logging side effects required for correctness
- no mutation of the provided snapshot

---

## Threshold model

Thresholds are consumer-supplied, but the model is owned by Core.

```python
@dataclass(frozen=True)
class SignalHealthThresholds:
    downstream_power_fair_max: float
    downstream_power_poor_max: float
    upstream_power_good_min: float
    upstream_power_good_max: float
    upstream_power_poor_min: float
    upstream_power_poor_max: float
    snr_fair_min: float
    snr_poor_min: float
    downstream_power_delta_fair_max: float
    downstream_power_delta_poor_max: float
    error_rate_fair_max: float
    error_rate_poor_max: float
```

Rules:

- fixed physical or standards-backed limits may still be represented in
  this model even when the consumer does not expose them in the UI
- the evaluator uses only the values it was passed, not hidden
  fallback constants in evaluation logic
- the consumer decides which values are user-configurable and which are
  fixed constants

---

## Result model

Core returns a typed, compact result designed for structured consumers.

```python
class SignalHealthGrade(StrEnum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass(frozen=True)
class SignalHealthMetricResult:
    grade: SignalHealthGrade
    observed: float | str | None
    unit: str | None
    comparison: str
    thresholds: dict[str, float | str | list[str]]
    worst_channel: str | None = None
    baseline_established: bool | None = None
    provisional: bool | None = None
    window_seconds: int | None = None
    omitted: bool = False


@dataclass(frozen=True)
class SignalHealthResult:
    grade: SignalHealthGrade
    decisive_metric: str
    non_good_metrics: dict[str, SignalHealthGrade]
    channel_counts: dict[str, int]
    metrics: dict[str, SignalHealthMetricResult]
    evaluated_at: datetime
```

Contract rules:

- `grade` is the final evaluator output
- `decisive_metric` names the metric group that decided the result
- `non_good_metrics` contains only metric groups currently graded
  `fair` or `poor`
- `metrics` contains one entry per supported metric group, plus
  DOCSIS status
- omitted metrics may still appear in `metrics` with `omitted=True` if
  the consumer wants one stable schema; alternatively the consumer may
  choose to drop omitted groups after evaluation

Keep omitted groups explicit in the typed result so consumers do not have to
infer why a group is missing.

---

## DOCSIS trust rule

DOCSIS status is a first-class metric group, but it is also a trust
boundary for the rest of RF grading.

Evaluation rule:

- only fully locked / operational DOCSIS state is trustworthy
- any state less than locked forces final grade `poor`

Expected canonical behavior:

| Observed `docsis_status` | Metric grade | Effect |
|--------------------------|--------------|--------|
| `Operational` | `good` | Continue normal metric grading |
| `locked` | `good` | Continue normal metric grading |
| `partial_lock` | `poor` | Final grade forced to `poor` |
| `not_locked` | `poor` | Final grade forced to `poor` |
| `unknown` | `poor` | Final grade forced to `poor` unless the consumer proves it is a locked synonym before evaluation |

Rationale:

- if DOCSIS is not fully locked, RF values cannot be trusted
- partial lock is not a warning tier for signal health; it is already a
  failed trust state

The evaluator still computes other metric groups when useful for
diagnostics, but `decisive_metric` remains `docsis_status` and the final
grade remains `poor`.

---

## Metric groups

The evaluator operates over these metric groups:

| Metric group | Observed value | Comparison | Channel-scoped |
|--------------|----------------|------------|----------------|
| `docsis_status` | enum string | `enum_status` | No |
| `downstream_power` | worst absolute dBmV deviation | `absolute_distance_from_zero` | Yes |
| `upstream_power` | worst transmit power | `inclusive_range` | Yes |
| `snr` | worst downstream SNR | `minimum_floor` | Yes |
| `downstream_power_delta` | downstream max-min spread | `spread` | No |
| `error_rate` | uncorrectables per minute | `rate` | No |

### Channel-scoped metric rules

For channel-scoped groups, the evaluator reports one `worst_channel`.

Selection rules:

- evaluate only active channels for the metric
- pick the worst-performing channel for that metric
- if multiple channels tie, choose the lowest channel number
- if channel number is unavailable for tie-break, choose the earliest
  stable ordering from the normalized channel list

### Comparison semantics

`comparison` is a machine-readable hint for consumers and diagnostics.

Canonical values:

- `enum_status`
- `absolute_distance_from_zero`
- `inclusive_range`
- `minimum_floor`
- `spread`
- `rate`

Consumers treat these as stable identifiers, not translated UI
strings.

---

## Evaluation flow

The evaluator runs in this order:

1. Read `snapshot.docsis_status` and evaluate the DOCSIS trust rule.
2. Count active downstream and upstream channels for reporting.
3. Evaluate each supported metric group independently.
4. Build `non_good_metrics` from all metric groups graded `fair` or
   `poor`.
5. Select `decisive_metric` using severity first, then deterministic
   ordering.
6. Produce the final `SignalHealthResult`.

Severity order:

- `poor` beats `fair`
- `fair` beats `good`

If DOCSIS status is `poor`, final grade is `poor` regardless of all
other metric grades.

---

## Tie-breaking

Two kinds of tie-breaking must be deterministic.

### Tied channels within one metric group

Rule:

- choose the lower channel number

If the normalized data does not expose a comparable channel number,
fall back to stable list order.

### Tied metric groups across the final result

If multiple metric groups share the same worst grade, choose
`decisive_metric` by this stable precedence order:

1. `docsis_status`
2. `error_rate`
3. `downstream_power_delta`
4. `downstream_power`
5. `upstream_power`
6. `snr`

Why this order:

- DOCSIS trust failures invalidate all RF interpretation
- error-rate is closest to user-facing service impact
- downstream delta is a fleet-level imbalance signal, not one bad row
- downstream and upstream power precede SNR because they represent the
  primary hardware operating window in this design

If this precedence changes, it must change here first.

---

## Baseline-dependent metrics

`error_rate` depends on a previous successful sample.

Rules:

- if no baseline is provided, evaluate `error_rate` as `0.0` with
  `provisional=True` and `baseline_established=False`
- if a valid baseline is provided, compute delta over elapsed time and
  convert to per-minute rate
- if the total uncorrectables counter decreases, treat the metric as a
  reset/restart case: `observed=0.0`, `provisional=True`,
  `baseline_established=False`
- if elapsed time is zero or negative, treat the metric as provisional

This keeps the result stable and avoids making the whole signal-health
entity unavailable just because one rate-based metric needs one more
sample.

---

## Consumer responsibilities

The consumer layer is responsible for:

- building `SignalHealthThresholds` from user options and fixed
  constants
- deciding when evaluation runs
- persisting and re-supplying the optional baseline
- translating `SignalHealthResult` into entity state and attributes
- adding any display summaries, translations, or icons

The consumer layer is not allowed to:

- reimplement grading math already specified here
- reinterpret DOCSIS trust rules differently per platform
- replace omitted or provisional Core results with platform-specific
  heuristics

That split is the architectural point of this spec: Core answers the
cable-modem question, consumers decide how to present the answer.
