# Local O_W ordering diagnostics

Status: **tracked WIP NAF diagnostic**, not a formal physics result. The
scripts and compact diagnostic outputs are versioned for provenance; they do
not modify or rerun the production workflow.

## Comparison contract

- Repository:
  `/data/dust/user/zhangyuy/tth-cpv-observable-ilc`
- Inputs: the existing chunk-0 LR CPV and SM gen/reco feature CSVs under
  `outputs/ow_lr/features/`
- Frame: the already-exported `higgs_rest` Ma-style basis
- Binning: 36 uniform bins in `[-pi, pi)`
- Luminosity scale: `8000 fb^-1`
- CPV numerator: `weight_template`
- SM denominator: `weight_sm`
- Fisher: `sum_i nu1_i^2 / nu0_i`
- No event-ID intersection
- No kinfit rerun and no offline pair reranking

Run:

```bash
bash diagnostics/o_w/run_all.sh
```

Outputs are written below `diagnostics/o_w/results/`.

## Cases

### `opposite_preferences_reco`

Uses the current exported `O_W`, but keeps only rows with
`w_orientation_status=opposite_preferences`. The same category selection is
applied independently to CPV and SM. This is a category diagnostic, not the
headline full-reco retention.

### `eta_ordered_gen`

Uses the exported generator W-daughter pair. The object with larger
pseudorapidity

```text
eta = -log(tan(theta/2))
```

is placed first, following the old ZH angular-observable convention. Theta,
phi and eta are all evaluated in the already-exported Higgs-rest frame.

### `eta_ordered_reco`

Uses the current production kinfit-selected pair. It does not change the pair
or rerank candidates. It only orders the two selected jets by larger
same-frame eta first.

The script also reproduces the existing gen/reco baselines as a numerical
cross-check. Each case includes a deterministic sign-shuffle reference. A raw
Fisher value near the shuffle distribution should not be interpreted as
resolved CP information. The summary also records the signed-template odd-power
fraction and bin-wise cosine similarity to the relevant generator template.

## Main files

- `run_o_w_diagnostics.py`: builds all templates, plots, Fisher values and
  sign-shuffle references.
- `results/summary.csv`: compact comparison table.
- `results/fisher_summary.png`: observed Fisher and the 95% shuffle level.
- `results/<case>/distribution.png`: signed CPV and SM panels on separate axes.
- `TRUTH_QQBAR_TODO.md`: reserved truth-orientation diagnostic.
