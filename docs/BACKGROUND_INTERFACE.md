# BACKGROUND_INTERFACE

Contract for background samples (prepared by the supervisor in parallel).
All analysis scripts must run with `background.enabled: false` today and pick
up backgrounds via this interface without pipeline changes.

## Manifest entries

Backgrounds are registered in `configs/samples.yaml` under `backgrounds:`
(`ttZ` reco production directories exist; `ttbb` and `other_6f` pending).

## Required background event table (CSV)

Minimum columns:

```
event_id
process            # ttZ / ttbb / other_6f / ...
helicity           # LR / RL
weight_sm          # absolute yield weight: xsec * lumi / n_generated
mva_score
pass_nominal_mva
```

Recommended additions:

```
cross_section
n_generated
luminosity_weight
```

plus the observable columns needed for the CP templates (same object naming
as DATA_SCHEMA.md) whenever the background enters an observable histogram
rather than only a yield.

## Config switch

```yaml
background:
  enabled: false
```

later:

```yaml
background:
  enabled: true
  manifest: configs/samples.yaml
```

## Physics usage

Backgrounds are parameter-independent at leading order in `c`:

```
nu_0,i = s_0,i + b_i        nu_1,i = s_1,i
```

so `evaluate_fisher.py --mode signal-plus-background` only needs the binned
`b_i` per template. No CP weights are expected for background samples.
