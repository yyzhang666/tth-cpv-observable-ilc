# Summer Student Project Note

## Validation and stability study of ML-learned CP observables in semileptonic $e^+e^- \to t\bar tH$

**Status:** working project note  
**Analysis energy:** $\sqrt{s}=550~\mathrm{GeV}$  
**Core channel:** semileptonic $t\bar tH$, with $H\to b\bar b$  
**Available initial states:** $e^-_Le^+_R$ and $e^-_Re^+_L$, corresponding to $(-100\%,+100\%)$ and $(+100\%,-100\%)$

> This project starts from a developing analysis. There is no completed angular–ML baseline to reproduce. The first scientific result is therefore the construction, validation, and documentation of that baseline.

# Chapter 1 — Project overview

## 1.1 Motivation

The top-Higgs interaction can be written as

$$
\mathcal L_{t\bar tH}
=
-\frac{m_t}{v}H\,
\bar t\left(\kappa_t+i\widetilde\kappa_t\gamma_5\right)t.
$$

In the Standard Model,

$$
\kappa_t=1,\qquad \widetilde\kappa_t=0.
$$

A non-zero pseudoscalar component introduces CP-violating structure into $t\bar tH$ production and top-decay correlations. At a linear $e^+e^-$ collider, the clean initial state, beam polarisation, charge-aware flavour tagging, and full event reconstruction provide several complementary probes.

Traditional studies compress each event into one angular observable. An ML-learned CP observable can instead combine several correlated kinematic quantities. The central question is:

> How much CP-interference information is retained by an angular observable and by its corresponding ML observable when moving from generator level to reconstruction level, and how should several physically distinct information sources be combined?

## 1.2 Current status and responsibilities

The project begins with the following conditions.

1. Generator-level CP samples and signed interference weights are available, but final generator validation remains the supervisor's responsibility.
2. Reconstructed semileptonic signal samples and a ParT-assisted jet assignment are available.
3. The ILC Particle Transformer provides charge-aware flavour information, including signed quark/antiquark probabilities.
4. No complete angular–ML baseline currently exists.
5. The final signal-versus-background event-selection MVA is under development and is expected after approximately one to two weeks.
6. Apart from the isolated-lepton multiplicity requirement and technical validity requirements, the final physics selection will be MVA-based.
7. The student is not responsible for validating the generator, producing every missing MC sample, or finishing the whole $t\bar tH$ analysis.

## 1.3 Required scientific questions

The required programme addresses five questions.

1. For one physical object pair, how much information is captured by a signed angular observable and how much additional information is captured by an ML model using the same objects?
2. How much information is lost when truth-level objects are replaced by reconstructed objects?
3. How do hadronic-$W$, top-decay $b/\bar b$, lepton-neutrino, and reconstructed-top observables compare?
4. Is the best combination strategy an all-feature model, separated physical branches, late fusion, or a multidimensional likelihood?
5. How should fully polarised $LR/RL$ samples be converted into the physical LCF running configuration?

## 1.4 Required project scope

The required scope is:

1. establish a complete generator/reconstruction angular–ML baseline for $O_W$;
2. add the supervisor-provided event-selection MVA and obtain a first selected-signal and signal-plus-background result;
3. establish faster baselines for $O_b$, $O_{\ell\nu}$, and $O_{\rm top}$;
4. combine $O_W$ with one selected secondary observable;
5. produce the physical LCF polarisation combination;
6. provide a minimal supervisor-approved conversion from the generator coupling convention to a SMEFT convention.

## 1.5 Optional extensions

These extensions are not required. Completing none of them is acceptable. Normally, at most one should be opened.

1. Add the hadronic-$\tau$ semileptonic channel as an extra statistical category.
2. Investigate an improvement of the existing ParT-assisted hadronic-$W$ pairing.
3. Add the quadratic EFT contribution.
4. Extend fusion beyond $O_W$ plus one secondary observable.

## 1.6 Scope-control principle

A negative result is valid. Examples include:

- an angle retaining almost as much information as the corresponding ML model;
- an all-feature model performing no better than separated branches;
- the present assignment already being close to an oracle assignment;
- a reference frame providing no useful gain;
- an optional extension not being justified by available statistics.

# Chapter 2 — Physics, ML, and statistical concepts

## 2.1 Scalar–pseudoscalar interference

A one-parameter convention is

$$
\mathcal L_{t\bar tH}
=
-\frac{m_t}{v}H\,
\bar t\left(\cos\xi+i\sin\xi\,\gamma_5\right)t.
$$

The amplitude is

$$
\mathcal M(\xi)=\cos\xi\,\mathcal M_S+\sin\xi\,\mathcal M_P.
$$

Near the Standard Model point, use a local parameter $c$:

$$
\frac{d\sigma}{dx}=f_0(x)+c f_1(x)+c^2 f_2(x),
$$

where

$$
f_0=\frac{d\sigma_{\rm SM}}{dx},
$$

$$
f_1=\frac{d\sigma_{\rm int}}{dx}
=
2\operatorname{Re}\left(\mathcal M_{\rm SM}^{\ast}\mathcal M_{\rm CPV}\right)d\Phi,
$$

and

$$
f_2=\frac{d\sigma_{\rm CPV^2}}{dx}.
$$

The required study begins with $f_0+c f_1$. The quadratic term is optional.

## 2.2 Signed interference samples

The interference contribution is signed and is not a probability density. A classifier may separate

$$
y=
\begin{cases}
+1,& f_1(x)>0,\\
-1,& f_1(x)<0,
\end{cases}
$$

using training weights proportional to $|f_1|$. Final physics templates must use the signed interference weight,

$$
w_{\rm int}
=
\operatorname{sign}(f_1)|w_{\rm int}|.
$$

Training weights and physics-template weights must remain separate. Class balancing may be used in training but never in final yield templates.

## 2.3 Angular observables

Define a signed azimuthal difference

$$
\Delta\phi(a,b)
=
\operatorname{wrap}(\phi_a-\phi_b)
\in(-\pi,\pi].
$$

The object ordering matters. The current analysis uses charge-aware ParT information and the reconstructed decay assignment.

Initial observable families are

$$
O_W=\Delta\phi(j_{W,\mathrm{up}},j_{W,\mathrm{down}}),
$$

$$
O_b=\Delta\phi(b_t,b_{\bar t}),
$$

$$
O_{\ell\nu}=\Delta\phi(\ell,\nu_W),
$$

and a supervisor-approved $O_{\rm top}$ based on reconstructed $t,\bar t$ systems.

Exact definitions, charge conventions, and axis conventions must be frozen in one configuration file.

## 2.4 Reference frames

The $O_W$ pilot study uses:

- laboratory or collider centre-of-mass frame;
- Higgs rest frame;
- $t\bar t$ rest frame.

Four-vectors remain the internal representation for Lorentz boosts. After boosting, angular features are evaluated.

A production-plane basis for a system $X$ may be defined as

$$
\hat z=\frac{\vec p_X^{\,\rm lab}}{|\vec p_X^{\,\rm lab}|},
$$

$$
\hat x=
\frac{\hat p_{e^-}-(\hat p_{e^-}\cdot\hat z)\hat z}
{\left|\hat p_{e^-}-(\hat p_{e^-}\cdot\hat z)\hat z\right|},
$$

$$
\hat y=\hat z\times\hat x.
$$

Then

$$
\phi_i=\operatorname{atan2}(\vec p_i\cdot\hat y,\vec p_i\cdot\hat x).
$$

The approved convention must be implemented once in a shared frame library.

## 2.5 Why use $(E,\theta,\phi)$ as ML inputs?

A four-vector is

$$
p^\mu=(E,p_x,p_y,p_z),
$$

with

$$
p_x=|\vec p|\sin\theta\cos\phi,\qquad
p_y=|\vec p|\sin\theta\sin\phi,\qquad
p_z=|\vec p|\cos\theta.
$$

For a nearly massless jet, $(E,\theta,\phi)$ contains almost the same independent information as the four-vector. It separates:

- energy scale $E$;
- polar direction $\theta$;
- azimuthal direction $\phi$.

This is physically aligned with CP-sensitive azimuthal observables and gives a transparent gen/reco comparison through

$$
\Delta E,\qquad \Delta\theta,\qquad \Delta\phi.
$$

However, raw $\phi$ is discontinuous at $-\pi$ and $+\pi$. A robust ML representation is

$$
\left(
\log\frac{E}{E_0},
\cos\theta,
\sin\phi,
\cos\phi
\right),
$$

optionally with

$$
m_j/E_j
\quad\text{or}\quad
m_j.
$$

Four-vectors must still be preserved internally for boosts and invariant-mass calculations.

## 2.6 Corresponding ML observables

Each angle is paired first with an ML model using the same physical objects.

For the hadronic-$W$ branch,

$$
M_W:F_W\rightarrow s_W.
$$

A minimal feature set is

$$
F_W^{\rm min}
=
\left\{
E,\theta,\phi
\right\}_{j_{W,\mathrm{up}},j_{W,\mathrm{down}}}
+
\text{frame-defining information}.
$$

An extended set may include

$$
F_W^{\rm ext}
=
F_W^{\rm min}
+
\left\{
m_{jj},
P_{\rm pair},
P_{\rm orientation},
\text{signed ParT probabilities}
\right\}.
$$

Analogous branches are $M_b$, $M_{\ell\nu}$, and $M_{\rm top}$.

A binary ML observable may be

$$
O_{\rm ML}=P(+)-P(-),
$$

or

$$
O_{\rm logit}=\log\frac{P(+)}{P(-)}.
$$

The output convention must be stored in model metadata.

## 2.7 Feature subsets as information projections

Let $x$ be the full event and

$$
t(x)=
\left.\frac{\partial\log p(x|c)}{\partial c}\right|_{c=0}
$$

the ideal local score. If only $z=g(x)$ is retained, the best possible observable in that feature space is

$$
t_z(z)=\mathbb E[t(x)\mid z].
$$

Different feature groups are therefore different projections of the same CP-interference information. For a single coupling, they do not normally correspond to different CP phases.

This motivates comparing:

- separate physical branches;
- all-feature early fusion;
- branch-output late fusion;
- multidimensional likelihoods.

## 2.8 Generator-to-reconstruction comparison

All gen/reco comparisons must use identical event IDs. Define

$$
S_{\rm common}
=
\{
\text{events with required reconstructed objects and valid assignment}
\}.
$$

For these events, evaluate both

$$
O_i^{\rm gen}
\quad\text{and}\quad
O_i^{\rm reco}.
$$

An inclusive gen-level curve may be shown as an upper reference, but it must not enter a gen/reco retention ratio unless the event populations match.

A single global bookkeeping table should record

$$
N_{\rm generated}
\rightarrow
N_{\rm isolated\ lepton}
\rightarrow
N_{\rm valid\ reconstruction}
\rightarrow
N_{\rm MVA\ selected}.
$$

## 2.9 Event-selection MVA and backgrounds

For signal,

$$
f_{\rm sig}(x;c)=f_0(x)+c f_1(x).
$$

A fixed selection $a(x)$ gives

$$
f_{\rm selected}(x;c)=a(x)\left[f_0(x)+c f_1(x)\right].
$$

For accepted signal events, the local score remains $f_1/f_0$. Selection changes the retained event population and total information, but does not invalidate the signal-only study.

With parameter-independent background $b(x)$,

$$
t_{\rm sig+bg}(x)
=
\frac{f_1(x)}{f_0(x)+b(x)}
=
\frac{f_0(x)}{f_0(x)+b(x)}
\frac{f_1(x)}{f_0(x)}.
$$

This motivates a two-dimensional observable

$$
(q_{SB},O_{\rm CP}),
$$

rather than treating $q_{SB}$ only as a hard cut.

## 2.10 Fisher information

For independent Poisson bins with

$$
\nu_i(c)=\nu_{0,i}+c\nu_{1,i},
$$

the likelihood is

$$
\mathcal L(c)=
\prod_i \operatorname{Pois}(n_i\mid\nu_i(c)).
$$

At $c=0$,

$$
I(0)
=
\sum_i
\frac{
\left(\partial\nu_i/\partial c\right)^2
}{
\nu_i
}
=
\sum_i
\frac{\nu_{1,i}^2}{\nu_{0,i}}.
$$

The per-bin information is

$$
I_i=\frac{\nu_{1,i}^2}{\nu_{0,i}}.
$$

With parameter-independent background,

$$
\nu_{0,i}=s_{0,i}+b_i,\qquad
\nu_{1,i}=s_{1,i},
$$

so

$$
I=\sum_i\frac{s_{1,i}^2}{s_{0,i}+b_i}.
$$

High purity alone is not enough; a useful bin must have large interference relative to the square root of the SM-plus-background yield.

Absolute-yield Fisher includes rate and shape. If the total normalisation is removed or profiled,

$$
I_{\rm shape}
=
\sum_i\frac{\nu_{1,i}^2}{\nu_{0,i}}
-
\frac{\left(\sum_i\nu_{1,i}\right)^2}{\sum_i\nu_{0,i}}.
$$

## 2.11 From Fisher information to limits

Near the reference point,

$$
-2\Delta\log\mathcal L(c)\simeq I c^2.
$$

Therefore,

$$
\sigma_c\simeq\frac{1}{\sqrt I}.
$$

For one approximately Gaussian parameter,

$$
|c|_{68\%}\simeq\frac{1}{\sqrt I},
$$

and the two-sided $95\%$ interval is approximately

$$
|c|_{95\%}\simeq\frac{1.96}{\sqrt I}.
$$

Fisher information is primarily a local ranking metric. A final interval must come from an explicit likelihood scan if:

- the quadratic term matters;
- linear templates become negative;
- the likelihood is asymmetric;
- bins are sparse;
- nuisance parameters are included;
- the expected interval is not local.

With nuisance parameters $\theta$,

$$
I_{\rm prof}
=
I_{cc}
-
I_{c\theta}I_{\theta\theta}^{-1}I_{\theta c}.
$$

## 2.12 Retention and gain metrics

For observable $z$, define

$$
I_{\rm gen}(z),\quad
I_{\rm reco}(z),\quad
I_{\rm selected}(z),\quad
I_{\rm sig+bg}(z).
$$

Then

$$
R_{\rm reco}(z)=\frac{I_{\rm reco}(z)}{I_{\rm gen}(z)},
$$

$$
R_{\rm selection}(z)=\frac{I_{\rm selected}(z)}{I_{\rm reco}(z)},
$$

$$
R_{\rm background}(z)=\frac{I_{\rm sig+bg}(z)}{I_{\rm selected}(z)},
$$

and

$$
G_{\rm ML/angle}=\frac{I_{\rm ML}}{I_{\rm angle}}.
$$

All ratios require the same luminosity, coupling convention, event pool, and binning.

## 2.13 Beam polarisation

For longitudinal polarisations $P_-$ and $P_+$,

$$
d\sigma(P_-,P_+)
=
a(P_-,P_+)\,d\sigma_{LR}
+
b(P_-,P_+)\,d\sigma_{RL},
$$

where

$$
a(P_-,P_+)=\frac{(1-P_-)(1+P_+)}{4},
$$

$$
b(P_-,P_+)=\frac{(1+P_-)(1-P_+)}{4}.
$$

For $80\%/60\%$ beams:

| $(P_-,P_+)$ | $a_{LR}$ | $b_{RL}$ |
|---|---:|---:|
| $(-0.8,-0.6)$ | 0.18 | 0.08 |
| $(-0.8,+0.6)$ | 0.72 | 0.02 |
| $(+0.8,-0.6)$ | 0.02 | 0.72 |
| $(+0.8,+0.6)$ | 0.08 | 0.18 |

The LCF $550~\mathrm{GeV}$ scenario uses

$$
8~\mathrm{ab}^{-1}
$$

with

$$
(--,-+,+-,++)=(10\%,40\%,40\%,10\%).
$$

The generator cross-section convention must be checked before using these factors.

### Polarisation in training

The coefficients $a$ and $b$ are not input features and must not multiply the final classifier score.

For physical running configuration $r$:

1. combine $LR$ and $RL$ events;
2. assign mixture weights
   $$
   w_{e,r}^{\rm phys}
   =
   \begin{cases}
   a_r w_e^{LR},&e\in LR,\\
   b_r w_e^{RL},&e\in RL;
   \end{cases}
   $$
3. preserve the physical $LR/RL$ mixture inside each class;
4. optionally equalise the total positive and negative class weights for training stability;
5. use unbalanced physical yield weights, including luminosity, for final templates.

For final templates,

$$
w_{e,r}^{\rm template}
=
\mathcal L_r a_r w_e^{LR}
$$

or

$$
w_{e,r}^{\rm template}
=
\mathcal L_r b_r w_e^{RL}.
$$

Dedicated mixed-polarisation classifiers may be trained for the four running categories. Their likelihoods are combined as

$$
\mathcal L_{\rm LCF}(c)=\prod_r\mathcal L_r(c).
$$

The initial physics study should still keep pure $LR$ and $RL$ separate.

## 2.14 Generator-to-SMEFT conversion

If

$$
c_{\rm gen}=K\frac{C}{\Lambda^2},
$$

then

$$
I_{C/\Lambda^2}=K^2 I_{c_{\rm gen}},
$$

and

$$
\Delta\left(\frac{C}{\Lambda^2}\right)
=
\frac{\Delta c_{\rm gen}}{|K|}.
$$

The factor $K$ depends on conventions and must be supplied or approved by the supervisor. A one-parameter conversion is not a multi-operator SMEFT fit.

# Chapter 3 — Common analysis baseline

**Suggested completion:** finish the data contract, weight checks, event matching, and first angular distribution before broad model scans.

## 3.1 Objective

Build one common layer used by all angles and ML models.

## 3.2 Standard event schema

The table should contain:

- unique event ID;
- `LR` or `RL` label;
- generator and reconstruction validity flags;
- isolated-lepton flavour and charge;
- SM event weight;
- signed interference weight;
- optional quadratic weight;
- event-selection MVA score when available;
- generator and reconstructed four-vectors;
- current ParT-assisted assignments;
- signed ParT probabilities;
- reconstruction-quality variables;
- deterministic train/validation/test split.

## 3.3 Shared software

Implement reusable functions for:

1. table reading and validation;
2. event-ID matching;
3. Lorentz boosts;
4. frame axes;
5. $\theta,\phi,\Delta\phi$;
6. feature construction;
7. deterministic splitting;
8. angular and ML templates;
9. Fisher calculation;
10. likelihood scanning;
11. polarisation weights;
12. metadata and plots.

## 3.4 Validation

Required checks:

- no train/validation/test overlap;
- exact event-ID closure;
- correct SM and interference normalisation;
- stable signed-weight sums;
- correct $\phi$ wrapping;
- one central frame implementation;
- SM CP closure within statistics;
- complete output metadata.

## 3.5 Deliverable

A frozen baseline configuration, schema documentation, validated common event table, and first gen/reco $O_W$ plot.

# Chapter 4 — Full $O_W$ angular–ML baseline

**Suggested completion:** this is the main development milestone; allow roughly two to three effective project weeks including debugging.

## 4.1 Observable

Construct

$$
O_W=\Delta\phi(j_{W,\mathrm{up}},j_{W,\mathrm{down}})
$$

at generator and reconstruction levels using the current ParT-assisted assignment.

## 4.2 Full frame study

Test:

- laboratory frame;
- Higgs rest frame;
- $t\bar t$ rest frame.

## 4.3 Feature schemes

Minimal:

$$
F_W^{\rm min}
=
\left\{
\log(E/E_0),
\cos\theta,
\sin\phi,
\cos\phi
\right\}
$$

for both W jets.

Extended:

$$
F_W^{\rm ext}
=
F_W^{\rm min}
+
\left\{
m_{jj},
P_{\rm pair},
P_{\rm orientation},
\text{signed ParT probabilities}
\right\}.
$$

## 4.4 Models

Use:

1. BDT or CatBoost baseline;
2. small MLP cross-check.

This is a stability study, not a large architecture search.

## 4.5 Required comparisons

Calculate

$$
I_{\rm angle}^{\rm gen},
\quad
I_{\rm angle}^{\rm reco},
\quad
I_{\rm ML}^{\rm gen},
\quad
I_{\rm ML}^{\rm reco},
$$

and the corresponding retention and gain ratios.

Repeat separately for pure $LR$ and $RL$.

## 4.6 Deliverable

A matrix showing:

- frame dependence;
- angle versus ML;
- BDT versus MLP;
- minimal versus extended features;
- gen-to-reco retention;
- $LR$ versus $RL$.

# Chapter 5 — Secondary-observable baselines

**Suggested completion:** start after the $O_W$ framework is stable. Reuse the selected default frame and model configuration.

## 5.1 $O_b$

$$
O_b=\Delta\phi(b_t,b_{\bar t}).
$$

Use signed ParT $b/\bar b$ information, top-side assignment, and lepton-charge consistency.

## 5.2 $O_{\ell\nu}$

Use the supervisor-approved lepton-neutrino angle,

$$
O_{\ell\nu}=\Delta\phi(\ell,\nu_W)
$$

or its approved equivalent. Document the reconstruction-level neutrino estimator and validity flag.

## 5.3 $O_{\rm top}$

Use a supervisor-approved top-level angle constructed from reconstructed $t,\bar t$ systems. Freeze the exact definition before implementation.

## 5.4 Required comparison

For each:

- gen/reco angle;
- one fixed BDT;
- Fisher at gen/reco level;
- retention;
- correlation with $s_W$.

## 5.5 Deliverable

A compact table identifying the strongest and most complementary secondary observable.

# Chapter 6 — Event-selection MVA and backgrounds

**Suggested completion:** integrate the MVA score as soon as the supervisor provides a frozen version. Earlier chapters must remain runnable without it.

## 6.1 Interface

The supervisor supplies:

```text
event_id
mva_score
pass_nominal_mva
```

plus score convention, threshold, model version, and provenance.

## 6.2 Selected signal

Compare

$$
I_{\rm reco}^{\rm signal}
\quad\text{and}\quad
I_{\rm selected}^{\rm signal}.
$$

Calculate

$$
R_{\rm selection}
=
\frac{I_{\rm selected}^{\rm signal}}
{I_{\rm reco}^{\rm signal}}.
$$

## 6.3 Signal plus background

Use

$$
\nu_{0,i}=s_{0,i}+b_i,
\qquad
\nu_{1,i}=s_{1,i}.
$$

Compare angular and ML observables after the nominal MVA cut.

## 6.4 Two-dimensional diagnostic

Compare, where statistics permit:

- a loose/common pool with $(q_{SB},O_{\rm CP})$;
- nominal MVA cut with one-dimensional $O_{\rm CP}$;
- nominal cut with two-dimensional $(q_{SB},O_{\rm CP})$.

The nominal cut remains the event-selection baseline. The loose-pool result measures information loss.

## 6.5 Deliverable

A first background-aware comparison and a quantitative measurement of selection-induced CP-information loss.

# Chapter 7 — Fusion of $O_W$ with one secondary observable

**Suggested completion:** start after $O_W$ and at least one secondary branch are stable.

Select one $X\in\{b,\ell\nu,\mathrm{top}\}$.

## 7.1 Early fusion

$$
M_{\rm early}(F_W,F_X).
$$

## 7.2 Late fusion

$$
s_W=M_W(F_W),
\qquad
s_X=M_X(F_X),
$$

$$
s_{\rm late}=M_{\rm fusion}(s_W,s_X).
$$

## 7.3 Multidimensional likelihood

Use

$$
(s_W,s_X)
$$

as a two-dimensional observable.

## 7.4 Metrics

Compare

$$
I(s_W),\quad
I(s_X),\quad
I(M_{\rm early}),\quad
I(s_{\rm late}),\quad
I(s_W,s_X).
$$

Define

$$
\Delta I_{X|W}=I(W+X)-I(W).
$$

## 7.5 Deliverable

A justified answer to whether one all-feature model, separated branches, or a multidimensional likelihood is preferable.

# Chapter 8 — Physical LCF polarisation combination

**Suggested completion:** perform after observable definitions and models are frozen.

## 8.1 Pure-helicity study

First compare pure $LR$ and $RL$ rates, shapes, interference, and Fisher information.

## 8.2 Weighted physical training

For each physical run category, combine $LR/RL$ events using $a_r,b_r$ as event weights.

Do not:

- use $a_r,b_r$ as features;
- multiply the final score by them;
- average independently trained scores without a calibrated common coordinate.

## 8.3 Templates and likelihood

Use

$$
\mathcal L_r=f_r^{\rm run}\times 8~\mathrm{ab}^{-1}
$$

and build one template category per configuration.

Combine through

$$
\mathcal L_{\rm total}(c)=\prod_r\mathcal L_r(c).
$$

## 8.4 Deliverable

Pure $LR/RL$, four running-category, and combined LCF sensitivities, with a rate-versus-shape interpretation where possible.

# Chapter 9 — Minimal BSM interpretation

**Suggested completion:** only after the final likelihood is stable.

Use a supervisor-approved mapping

$$
c_{\rm gen}=K\frac{C}{\Lambda^2}.
$$

Record conventions, sign, units, and the local nature of the conversion. Do not claim a multi-operator fit.

# Chapter 10 — Optional extensions

**Suggested completion:** open only after the required results are frozen. Completing none is acceptable.

## Option 1 — Hadronic-$\tau$ category

Restricted scope:

- use a frozen tau tagger;
- add semitau events as a separate category;
- retain the hadronic-$W$, $b/\bar b$, and top observables;
- do not build a tau polarimeter.

Proceed only if the tagger team supplies a frozen model/interface, efficiency and fake rates, constituent links, and a usable charge convention.

Deliverable: sensitivity change from adding the tau category.

## Option 2 — W-pair optimisation

The present assignment is already ParT-assisted. First compare current assignment with a truth-matched reconstructed-jet oracle:

$$
\Delta I_{\rm pairing}
=
I_{\rm oracle}-I_{\rm current}.
$$

Proceed only if the gap is relevant.

Possible methods:

- probability calibration;
- global assignment;
- top-$K$ candidates;
- soft assignment;
- posterior-weighted observables.

Deliverable: increased CP information, not only higher pairing accuracy.

## Option 3 — Quadratic EFT term

Use

$$
\nu_i(c)=\nu_{0,i}+c\nu_{1,i}+c^2\nu_{2,i}.
$$

Proceed if linear templates become negative, the interval is non-local, or a quadratic template is required for a physical finite-coupling scan.

Deliverable: comparison of linear and quadratic intervals, with EFT-truncation caveats.

## Option 4 — Additional-observable fusion

Extend the required $W+X$ fusion to a larger controlled set, for example

$$
W+b+\mathrm{top}
$$

or

$$
W+b+\ell\nu+\mathrm{top}.
$$

Proceed only if the two-branch result is stable and additional branches have non-negligible conditional information.

Deliverable: an information-gain matrix for each added branch.

# Chapter 11 — Deliverables and success criteria

## 11.1 Required scientific outputs

1. Validated $O_W$ angular baseline at gen/reco level.
2. Corresponding BDT/CatBoost and MLP baselines.
3. Controlled frame study for $O_W$.
4. Gen-to-reco information-retention result.
5. Fast $O_b,O_{\ell\nu},O_{\rm top}$ baselines.
6. Event-selection MVA integration.
7. First signal-plus-background result when available.
8. Fusion of $O_W$ with one secondary observable.
9. Physical LCF polarisation combination.
10. Minimal generator-to-SMEFT conversion.

## 11.2 Required technical outputs

- documented schema;
- reproducible configs;
- deterministic splits;
- model metadata and seeds;
- validation plots;
- tested Fisher and likelihood code;
- polarisation closure test;
- runnable README;
- short report;
- internal presentation.

## 11.3 Central summary result

Aim for one figure or table comparing

$$
I_{\rm gen},\qquad
I_{\rm reco},\qquad
I_{\rm selected},\qquad
I_{\rm sig+bg}
$$

for:

- $O_W$;
- $M_W$;
- one fused observable.

## 11.4 Quote-readiness conditions

A quoted result requires:

- no training/test overlap;
- stable event and weight bookkeeping;
- stable binning;
- no negative expected yields in the quoted scan;
- adequate MC statistics in high-information bins;
- documented gen/reco conventions;
- checked polarisation weights;
- stated background assumptions;
- model-seed stability.

## 11.5 Non-goals

The student is not required to:

- finish the complete $t\bar tH$ analysis independently;
- validate the generator;
- produce all missing MC samples;
- derive a full optimal observable;
- derive SMEFT matching from first principles;
- rewrite the ParT tagger;
- develop a full neutrino-correction Marlin processor;
- complete any optional extension.

# Chapter 12 — Suggested reading

1. Project $t\bar tH$ generator-level CP-observable theory report.
2. Ma et al. on frame-dependent $e^+e^-\to t\bar tH$ CP observables.
3. CLIC $t\bar tH$ CP reconstruction study.
4. Qu et al., Particle Transformer.
5. ILC charge-aware ParticleTransformer material.
6. arXiv:2401.02474, on optimal-observable ideas and detector-level ML.
7. A Linear Collider Vision for the Future of Particle Physics, arXiv:2503.19983.
8. Project ZH CPV WORKLOG.
9. Current hadronic-$\tau$ ParticleTransformer report.
10. DESY Summer Student 2026 supervisor guidelines.

# Appendix A — Recommended result table

| Family | Level | Frame | Representation | Model | Polarisation | $I$ | $R_{\rm reco}$ | $G_{\rm ML/angle}$ | Status |
|---|---|---|---|---|---|---:|---:|---:|---|
| $W$ | gen | Higgs rest | angle | — | LR |  | — | — |  |
| $W$ | reco | Higgs rest | angle | — | LR |  |  | — |  |
| $W$ | gen | Higgs rest | ML-min | BDT | LR |  | — |  |  |
| $W$ | reco | Higgs rest | ML-min | BDT | LR |  |  |  |  |
| $b$ | reco | default | angle | — | LR |  |  | — |  |
| $b$ | reco | default | ML | BDT | LR |  |  |  |  |
| fusion | reco | default | $(s_W,s_X)$ | 2D | LCF |  |  |  |  |

# Appendix B — Polarisation closure test

For each physical configuration:

1. calculate $a_r,b_r$;
2. construct weighted $LR+RL$ SM yields;
3. compare with a partially polarised sample if available;
4. compare total cross sections;
5. compare at least one angular distribution;
6. document any generator factor-of-four or spin-average convention.

# Appendix C — Decision log template

```text
date:
decision:
alternatives considered:
physics reason:
technical reason:
validation performed:
person responsible:
```

Use this for axis conventions, object ordering, feature sets, model output, binning, MVA threshold, background set, polarisation convention, and SMEFT conversion.
