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

| column | description |
|---|---|
| `weight_sm` | SM yield weight `xsec*lumi/n_gen` (pending SM samples, KNOWN_ISSUES #5) |
| `weight_interference_signed` | signed interference weight (fb-scaled), physics templates only |
| `weight_interference_abs` | `abs(weight_interference_signed)` |
| `weight_quadratic` | optional `c^2` term weight (Optional extension 3) |
| `weight_training` | training-only weight, may be class-balanced |
| `weight_polarization` | `a_r` or `b_r` factor for a running configuration |
| `weight_luminosity` | luminosity scale of the running configuration |
| `weight_template` | final template weight = product of physics factors (always the physical, class-unbalanced weights) |

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

Pairs follow the particle−antiparticle ordering (PHYSICS_CONVENTIONS §3–§4).
Reco-level tables use the kinfit selected-candidate slots and record the
mapping `W1, W2 -> wjet_quark/antiquark` (via signed flavor), `b_had, b_lep`,
`H_b1, H_b2`.

## Kinfit stage columns (reco level)

From the `TTHSemiLepKinFit` selected candidate (docs/KINFIT_JET_ASSIGNMENT.md):

```
accepted  fit_success  fit_status  fitchi2  ndof  fitprob
final_selection_mode  flavor_weight
final_selection_score  final_fit_score  final_flavor_score
best_combo_id
idx_W1  idx_W2  idx_bhad  idx_blep  idx_H1  idx_H2
mW_had_prefit  mt_had_prefit  mt_lep_prefit  mH_prefit
mW_had_postfit mt_had_postfit mt_lep_postfit mH_postfit
```

The canonical selected candidate minimizes
`final_selection_score = log(1 + fit_chi2) + 0.3*signed_flavor_NLL` after
preferring successful fits. Physics selections require `accepted = 1` and
`fit_success = 1`.

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
