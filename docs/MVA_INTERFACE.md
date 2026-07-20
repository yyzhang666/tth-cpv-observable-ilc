# MVA_INTERFACE

Contract between this repository and the supervisor-provided event-selection
MVA. Frozen so that all student code runs before the MVA exists and picks it
up without changes when it arrives.

## Input file format (CSV)

```
event_id, mva_score, pass_nominal_mva, model_version
```

- `event_id`: must match the `event_id` convention of DATA_SCHEMA.md.
- `mva_score`: float; direction convention (larger = more signal-like) must be
  stated by the provider in the accompanying metadata.
- `pass_nominal_mva`: 0/1 at the provider's nominal threshold.
- `model_version`: string, stored into all downstream metadata.

Optional extra columns are ignored by the joiner.

## Config switch

```yaml
selection:
  enabled: false
```

when delivered:

```yaml
selection:
  enabled: true
  score_file: outputs/mva/scores.csv
  threshold: null      # null -> use pass_nominal_mva; number -> cut on score
```

## Joining

`scripts/join_selection_mva.py` left-joins the score file onto a feature table
by `event_id` and reports:

- number of unmatched feature-table events (must be justified);
- number of score rows not in the table;
- duplicated `event_id`s (error).

## Physics usage

- Nominal analysis: cut on `pass_nominal_mva` (selection baseline).
- Diagnostic: keep a loose pool and use the two-dimensional observable
  `(q_SB, O_CP)` (project note §2.9, §6.4) to measure selection-induced
  CP-information loss.
