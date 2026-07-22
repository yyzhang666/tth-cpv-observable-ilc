# DATA_SCHEMA

Contract for every event table (CSV) produced in this repository. Scripts must
validate against this schema (`src/ilc_tth_cpv/io.py::validate_table`).

## Event-level fields

| column | type | description |
|---|---|---|
| `event_id` | int | unique across the sample: `chunk * 1e6 + sidecar event number` |
| `sample_name` | str | key from `configs/samples.yaml` |
| `chunk` | str | production chunk id |
| `process` | str | e.g. `ttH_SM`, `ttH_CPVint` |
| `level` | str | `gen` or `reco` |
| `helicity` | str | `LR` or `RL` |
| `split` | str | `train` / `validation` / `test` (deterministic, from `event_id` hash + seed) |

## Weight fields

All weight columns exist in every table; unavailable ones carry `NaN` and a
note in the metadata, so missing weights stay visible.

`export_features.py --component interference` writes the CPV derivative table;
`--component sm` writes a separate SM denominator table. One production chunk
is a full-cross-section MC estimate. Average multiple per-chunk templates, or
renormalize concatenated rows to the total written-event count; never sum
full-cross-section chunk estimates.

| column | description |
|---|---|
| `weight_sm` | SM base cross-section weight `xsec/n_written_chunk` in fb; finite for the registered LR and RL SM samples |
| `weight_sm_shape` | unit-area SM shape weight `1/n_written_chunk`; available even when the absolute cross section is unknown |
| `weight_interference_signed` | signed interference weight (fb-scaled), physics templates only |
| `weight_interference_abs` | `abs(weight_interference_signed)` |
| `weight_quadratic` | optional `c^2` term weight (Optional extension 3) |
| `weight_training` | non-negative base optimizer weight; any class balancing is applied only inside the trainer and is not written back here |
| `weight_polarization` | `a_r` or `b_r` factor for a running configuration |
| `weight_luminosity` | luminosity scale of the running configuration |
| `weight_template` | active component's base template weight: signed interference weight on CPV rows or `weight_sm` on normalized SM rows; later includes polarisation and luminosity factors |

## Object kinematics

Per object `<obj>`:

```
<obj>_E  <obj>_theta  <obj>_phi  <obj>_mass  <obj>_valid
```

**Feature policy (frozen, supervisor decision 2026-07-20): ML inputs are the
RAW variables above**, used exactly as exported. A transformed-input study,
if ever approved, enters as an explicit config option.

Four-vectors remain the internal representation for boosts; tables store the
frame-evaluated `(E, theta, phi)` plus the frame name in the table metadata.

## Object names

```
wjet_quark  wjet_antiquark   light quark / antiquark from the hadronic W
top_b       antitop_bbar     top-side and antitop-side b jets
lepton      neutrino         isolated lepton and neutrino estimator
top         antitop  higgs   composite systems
```

Generator-level pairs follow the particle-antiparticle ordering in
`PHYSICS_CONVENTIONS.md` sections 3 and 4. At reco level, kinfit supplies the
selected slots `W1, W2, b_had, b_lep, H_b1, H_b2`. The exporter orients the
selected W pair with Weaver light-flavour probabilities, uses the fitted
neutrino for `O_lnu`, and records the details below. The `b_had/b_lep` and
hadronic/leptonic top aliases are not yet charge-oriented; Chapter 4 makes
that a separate student validation task before `O_b` or `O_top` is quoted.

## Kinfit stage columns (reco level)

From the `TTHSemiLepKinFit` selected candidate (docs/KINFIT_JET_ASSIGNMENT.md):

```
accepted  fit_success  fit_status  fitchi2  ndof  fitprob
final_selection_mode  flavor_weight
final_selection_score  final_fit_score  final_flavor_score
best_combo_id
idx_W1  idx_W2  idx_bhad  idx_blep  idx_H1  idx_H2
nu_fit_E  nu_fit_px  nu_fit_py  nu_fit_pz  lepton_charge
mW_had_prefit  mt_had_prefit  mt_lep_prefit  mH_prefit
mW_had_postfit mt_had_postfit mt_lep_postfit mH_postfit
```

The canonical selected candidate minimizes
`final_selection_score = log(1 + fit_chi2) + 0.3*signed_flavor_NLL` after
preferring successful fits. Physics selections require `accepted = 1` and
`fit_success = 1`.

The fitted neutrino branches are required. Old kinfit ROOT files without them
are rejected and must be regenerated with the 2026-07-22 processor build.

## Reco W orientation columns

For each selected W jet, the exporter defines

```math
P(q)=P(u)+P(d)+P(s)+P(c),
\qquad
P(\bar q)=P(\bar u)+P(\bar d)+P(\bar s)+P(\bar c),
```

Opposite q/qbar preferences are used directly. If both jets are q-like, the
one with larger `P(q)` is q; if both are qbar-like, the one with larger
`P(qbar)` is qbar. Exact decision-score ties keep W1 as q only as a
deterministic fallback and are explicitly labelled. The highest Weaver class
may be b; b scores are deliberately irrelevant here.

```text
idx_W_quark  idx_W_antiquark
w_orientation_status  w_orientation_margin
W1_weaver_pq  W1_weaver_pqbar  W1_weaver_qminusqbar
W2_weaver_pq  W2_weaver_pqbar  W2_weaver_qminusqbar
```

Reco feature export reads selected indices/status/score from this ROOT tree and
the selected jet four-vectors from the matching `complete_reco_kinfit_ready`
SLCIO event. If the kinfit ROOT for the requested config/chunk is missing,
`export_features.py --level reco` stops with an explicit error asking the user
to run `scripts/run_kinfit_assignment.sh` first.

## Missing values

- Missing kinematics: `NaN` + `<obj>_valid = 0`, keeping missing objects
  visible in every table.
- Rows are only dropped at analysis time by explicit validity cuts, and the
  cut flow is recorded (`N_generated -> N_isolep -> N_valid_reco -> N_MVA`).

## Per-observable extras

| column | description |
|---|---|
| `O_W`, `O_b`, `O_lnu`, `O_top` | signed angular observables in the table's frame |
| `mva_score`, `pass_nominal_mva` | joined from the selection MVA (MVA_INTERFACE.md) |
| `part_*` | Weaver/ParT scores from `RefinedJets6` (PID algorithm `weaver`) |
| `y45`, `y56`, `y67` | ymerge from `RefinedJets6` (PID algorithm `yth`) — the flavour collection is the single source for these |

## File-level metadata

Every exported CSV is accompanied by `<name>.meta.json` containing at least:
config path + hash, sample keys, frame, level, n_events read/kept, skip list
source, git describe of this repo, and creation timestamp.
