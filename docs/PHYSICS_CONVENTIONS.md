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
CODE_PROVENANCE.md). The project note writes `(-pi, pi]`; the boundary
difference is documented as KNOWN_ISSUES #2 and the code convention wins.

## 3. Signed azimuthal difference

$$\Delta\phi(a,b) = \operatorname{wrap}(\phi_a - \phi_b)$$

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

These match the theory-study "Original Phi" observable family; the strongest
validated observable is `delta_phi_light_quark_antiquark` (our `O_W`) in the
Higgs rest frame. At reconstruction level the selected kinfit slots `W1/W2`
map onto quark/antiquark via the signed flavor information; that mapping is
confirmed with the supervisor (KNOWN_ISSUES #1).

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
- SM histograms (once the SM samples exist): unit weight
  `xsec * lumi / n_generated` per event; unit-area normalisation only for
  shape display, absolute yield for Fisher.
- Fisher uses absolute yields: `nu_0 = SM (+bg)`, `nu_1 = signed interference`.
- Stored templates keep raw bin contents; bin edges live in the metadata
  (bin-width division happens only at plot time when needed).

## 7. Polarisation factors

$$a(P_-,P_+) = \tfrac{(1-P_-)(1+P_+)}{4},\qquad b(P_-,P_+) = \tfrac{(1+P_-)(1-P_+)}{4}$$

`a` multiplies pure-LR event weights, `b` pure-RL. `a+b < 1` in general; do
not renormalise. LCF scenario: 8 ab^-1 with fractions (10,40,40,10)% for
(--, -+, +-, ++), see `configs/lcf_polarization.yaml`. Check the generator
spin-averaging convention before using yields (KNOWN_ISSUES #7).

`a_r, b_r` act exclusively as event weights for training and templates; they
stay out of the feature list and out of any score post-scaling.

## 8. Training vs template weights

- Training: `weight_training ∝ |w_int|`, class balancing allowed.
- Physics templates: `weight_interference_signed` (signed) and `weight_sm`,
  luminosity included, always with the physical (class-unbalanced) weights.
- The two live in separate columns of every feature table (DATA_SCHEMA.md).

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
- `O_W` from selected slots `W1 - W2`; `O_b` from `b_had - b_lep`;
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
