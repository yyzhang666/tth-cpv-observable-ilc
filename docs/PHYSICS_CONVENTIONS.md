# PHYSICS_CONVENTIONS

Frozen conventions for the whole repository. Any change requires supervisor
approval and a dated entry at the bottom.

## 1. Beam helicity labels

```
LR = e-_L e+_R = (P_e-, P_e+) = (-100%, +100%)
RL = e-_R e+_L = (P_e-, P_e+) = (+100%, -100%)
```

## 2. Angle ranges and wrapping

```
theta in [0, pi]
phi   in [-pi, pi)        # frozen from the authoritative implementation
```

`wrap(x) = ((x + pi) mod 2pi) - pi`, mapped into `[-pi, pi)`.

Provenance: `compute_tthcpv_ma2018_observables.py::wrap_phi` (see
CODE_PROVENANCE.md). This half-open range is used by the code, tests, configs,
and Project Note.

## 3. Signed azimuthal difference

$$\Delta\phi(a,b) = \mathrm{wrap}(\phi_a - \phi_b)$$

Pairs are ordered **particle − antiparticle** (theory-study convention).

## 4. Observable definitions (theory-study frozen ordering)

```
O_W    = Delta phi(quark, antiquark)       # light quark - light antiquark, same hadronic W
O_b    = Delta phi(b, bbar)                # b from t  -  bbar from tbar
O_top  = Delta phi(top, antitop)
O_lnu  : CP-ordered same-W lepton-neutrino angle
         W-: Delta phi(l-, anti-nu)        # l- is the particle
         W+: Delta phi(nu, l+)             # nu is the particle
```

These are frozen definitions matching the theory-study "Original Phi"
observable family. The strongest validated generator observable is
`delta_phi_light_quark_antiquark` (our `O_W`) in the Higgs rest frame.

At reco level, the selected W pair is now oriented with Weaver light-flavour
scores and `O_lnu` uses the fitted neutrino plus lepton charge. The top-side
charge orientation for `O_b` and `O_top` is intentionally a separate Chapter 4
implementation and validation task.

## 5. Reference frames and the two basis conventions

Frames (names used in configs and code):

```
lab          measure in the lab frame
higgs_rest   boost into the Higgs rest frame          (theory-study "higgs-rest" / "Rh")
ttbar_rest   boost into the top+antitop rest frame    (theory-study "ttbar-rest" / "Rpsi")
```

The theory study defines two basis conventions; each has its fixed use:

### 5a. Lab-axes basis (`lab_axes`) — PRIMARY, for all delta-phi observables

Boost the four-vector into the frame, then measure against the fixed lab axes:

$$\phi = \operatorname{atan2}(p_y, p_x), \qquad \cos\theta = p_z/|\vec p|$$

After the boost the coordinate axes stay untouched (no rotation). This is
the convention behind every validated `delta_phi_*` result, including the
O_W Higgs-rest numbers. Implementation: `frames.boost_only_angles`.

### 5b. Production-plane basis (`production_plane`) — Ma2018 sign observables

For the Ma2018-style sign observables (`C_phi1`, `C_phi_plus`, ...) the
basis references the production plane:

$$\hat z = \vec p_X^{\,\rm lab}/|\vec p_X^{\,\rm lab}|,\qquad \hat x = \frac{\hat p_{e^-} - (\hat p_{e^-}\cdot\hat z)\hat z}{|\cdot|},\qquad \hat y = \hat z\times\hat x$$

with the electron beam from the parentless PDG 11 particle of highest energy
(fallback +z), and basis orthonormality checked to 1e-9.
Implementation: `frames.make_frame` + `frames.frame_angles`.

The `lab` frame is handled separately with fixed detector axes; applying the
beam-transverse formula when both the beam and lab z axis are the same would
give a zero x axis. For `Rh`/`Rpsi`, `make_frame` returns no frame when the
projected x vector has norm at most `1e-12`. Just above that threshold the
production plane may still be numerically ill-conditioned, so a Ma-style study
must record frame failures and test stability versus the system-to-beam angle.
See PROJECT_NOTE_FULL.md §2.4.

There is no hard-coded beam-crossing-angle correction. The `lab_axes` baseline
uses the event four-momenta in fixed detector coordinates. The authoritative Ma
generator script uses the actual parentless incoming-electron direction from
STDHEP when available, so a crossing angle stored there enters the
production-plane basis; its `+z`/`-z` fallback contains no such information.

The current feature exporter is frozen to `lab_axes` and does not dispatch on
the YAML `basis` label. Ma-style results must explicitly call the
production-plane functions; changing the label alone is not an implementation
change.

Keep each observable family with its own basis; the theory report treats
them as separate conventions. There is exactly ONE implementation of both:
`src/ilc_tth_cpv/frames.py`, shared by gen and reco.

## 6. Signed interference weights and normalisation

- The Physsim CPV samples are importance-sampled on the absolute
  interference: each accepted event carries
  `event_weight_signed = sign * sigma_absint / n_generated` (fb) in the
  per-chunk sidecar CSV. The production sidecar also stores the full
  event-level matrix-element record (`configs/samples.yaml:
  meta.sidecar_columns`).
- Alignment: accepted-event-order matching — sidecar row i is the i-th
  usable LCIO event of the same chunk. The historical validation sample
  additionally needs the JSFHadronizer skip-list from its physsim log.
- Theory-study histograms fill **signed bin contents** with
  `event_weight_signed`; the absolute-interference histogram uses
  `|event_weight_signed|`; `local_signed_fraction = signed/abs` per bin.
- Plots in the theory study are line-only, no fill, no error bars, PNG;
  reproductions must use the same style for comparability.
- SM histograms use `weight_sm = xsec/n_written_chunk` in fb per event, then
  receive luminosity and polarization factors at yield evaluation. When a
  cross section is unavailable, `weight_sm_shape=1/n_written_chunk` supports
  shape inspection but not an absolute Fisher result.
- Fisher uses absolute yields: `nu_0 = SM (+bg)`, `nu_1 = signed interference`.
- Stored templates keep raw bin contents; bin edges live in the metadata
  (bin-width division happens only at plot time when needed).

## 7. Polarisation factors

$$a(P_-,P_+) = \tfrac{(1-P_-)(1+P_+)}{4},\qquad b(P_-,P_+) = \tfrac{(1+P_-)(1-P_+)}{4}$$

`a` multiplies pure-LR event weights, `b` pure-RL. `a+b < 1` in general; do
not renormalise. LCF scenario: 8 ab^-1 with fractions (10,40,40,10)% for
(--, -+, +-, ++), see `configs/lcf_polarization.yaml`.

The Physsim convention is resolved for the registered samples: with
`POLE=-1, POLP=+1` or the reversed signs, `functthf.F` selects one initial
helicity with unit weight, and `sgtthf.F` uses `SPIN=1`. Thus the registered
LR/RL cross sections are pure-helicity cross sections. They do not already
contain the quarter factors above.

`a_r, b_r` are later physics-template/yield factors. The current pure-LR and
pure-RL baseline models are trained separately without polarisation
reweighting. These factors stay out of the feature list and out of any score
post-scaling.

## 8. Training vs template weights

- Current production is already importance-sampled on `|w_int|`, and its
  absolute per-event weight is constant within a chunk. Thus the base
  `weight_training = |w_int|` is equivalent to unweighted training here. The
  trainer currently adds class balancing inside the training split and then
  normalises the optimizer weights. This is optimizer bookkeeping, not
  polarisation or yield weighting.
- Interference templates use the signed `weight_template` (initially
  `weight_interference_signed`); SM templates use `weight_sm`. Both receive
  polarisation and luminosity factors later.
- Training-time rescaling is never written into the physics-template column
  (DATA_SCHEMA.md).

## 9. ML observable convention

```
inputs:        RAW variables only (E, theta, phi, masses, scores) — frozen;
               no log/sin/cos or other derived encodings
class labels:  -1 (f1 < 0),  +1 (f1 > 0)     class_order frozen in config
score:         O_ML = P(+) - P(-)            (optional logit variant)
```

The class order and the score definition are stored in `model_metadata.json`
next to every trained model (convention inherited from the ZH CPV analysis).

## 10. Reconstruction-level objects and selected pairs

All reco-level observables use the selected candidate of the standard
kinfit + jet assignment stage (docs/KINFIT_JET_ASSIGNMENT.md):

- events: `accepted = 1` and `fit_success = 1`, one entry per selected event;
- selected candidate: `FinalSelectionMode=logchi2_plus_flavor` with
  `FlavorWeight=0.3`;
- kinfit selects the W pair; the exporter uses opposite q/qbar preferences
  directly, compares `P(q)` for two q-like jets, and compares `P(qbar)` for two
  qbar-like jets, ignoring b scores and recording status plus decision margin;
- reco `O_b` and `O_top` still need lepton-charge-dependent top/antitop side
  ordering, which is a Chapter 4 student checkpoint;
- reco `O_lnu` uses `nu_fit_{E,px,py,pz}` from the selected fit and the frozen
  W-minus/W-plus charge ordering in section 4;
- these distributions include every selected event; truth-signed variants
  (with their smaller denominator) are separate diagnostics;
- single-jet angular residuals/pulls use `theta = atan2(pt, pz)`,
  `phi = atan2(py, px)`, `delta_phi` wrapped into the frozen range, and
  jet-by-jet sigmas projected from the LCIO covariance — not one global sigma;
- collection contract: jet p4/covariance from `OutputErrorFlowJets6`,
  flavor/ymerge (`yth`) from `RefinedJets6`, truth only for validation.

## Change log

- 2026-07-20: initial freeze from the theory-study implementation.
- 2026-07-20: raw-variable ML input policy; kinfit selected-pair conventions
  added after the production kinfit/jet-assignment scheme was frozen.
- 2026-07-20: observable ordering and basis aligned with the theory-study
  observable build report (particle−antiparticle ordering, lab-axes basis for
  delta-phi observables, production-plane basis reserved for Ma2018 sign
  observables).
- 2026-07-20: reco selected-candidate convention updated to the production
  `logchi2_plus_flavor` final selection mode.
- 2026-07-21: clarified fixed-lab-axes versus Ma production-plane usage, the
  separate lab definition, beam-crossing-angle handling, and the near-beam
  degeneracy guard.
- 2026-07-21: clarified sidecar-to-event alignment and separated base training
  weights, signed template weights, and later polarisation/yield factors.
- 2026-07-21: froze the half-open phi range consistently, recorded the
  Physsim pure-helicity normalisation check, and replaced the claimed reco
  W-quark orientation with the then-current implementation status.
- 2026-07-22: froze the conditional Weaver q/qbar orientation within the
  kinfit-selected W pair; persisted the fitted neutrino in the best tree and
  enabled charge-ordered reco `O_lnu`.
- 2026-07-22: wired SM generator/reco feature export and real binned LR `nu0`;
  removed the absolute-interference Fisher fallback.
