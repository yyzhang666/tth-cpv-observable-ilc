# Summer Student Project Guide

## Validation and stability study of ML-learned CP observables in semileptonic $e^+e^- \to t\bar{t}H$

**Status:** student-facing full project guide. This file is the repository's
main project note.

**Analysis energy:** $\sqrt{s}=550~\mathrm{GeV}$
**Core channel:** semileptonic $t\bar{t}H$ with $H\to b\bar{b}$
**Available samples:** two fully polarised beam configurations, $e^-_Le^+_R$ ("LR") and $e^-_Re^+_L$ ("RL")

> **Read this first.** This project starts from an analysis that is still being developed. There is *no* finished "angular vs. ML" baseline that you reproduce. Building, validating, and documenting that baseline **is** the first scientific result of the project. That also means: if you find that something simple works as well as something complicated, that is a real, publishable-quality finding — not a failure (see §1.6).

The short navigation page [PROJECT_NOTE.md](PROJECT_NOTE.md) follows the same
chapter structure and points to the relevant repository files.

---

## How this guide is organised

| Part | What it gives you |
|---|---|
| Chapter 1 | The physics motivation and exactly what you are (and are not) responsible for |
| Chapter 2 | Every concept you need, explained: interference weights, angles, frames, ML inputs, Fisher information, polarisation |
| Chapters 3–10 | The actual work plan, step by step |
| Chapter 11 | The checklist of what "done" means |
| Chapter 12 + Appendices | Reading list, result-table template, closure test, decision log |

Where the repository already has code or documentation for a topic, this guide links to it. Start with [../README.md](../README.md) and [NAF_STUDENT_SETUP.md](NAF_STUDENT_SETUP.md) for the technical setup.

---

# Chapter 1 — Project overview

## 1.1 Motivation: why measure CP structure in $t\bar{t}H$?

The Higgs boson couples to the top quark more strongly than to any other fermion, so the top–Higgs coupling is the natural place to look for deviations from the Standard Model (SM). The most general way to write this coupling with one Higgs field is

```math
\mathcal{L}_{t\bar{t}H}
=
-\frac{m_t}{v}H\,
\bar{t}\left(\kappa_t+i\widetilde{\kappa}_t\gamma_5\right)t .
```

Read this term by term:

- $m_t/v$ — the SM Yukawa strength ($m_t$ = top mass, $v \approx 246~\mathrm{GeV}$ = Higgs vacuum expectation value). It sets the overall scale.
- $\kappa_t$ — the **scalar** (CP-even) coupling. In the SM, $\kappa_t = 1$.
- $\widetilde{\kappa}_t$ — the **pseudoscalar** (CP-odd) coupling, entering through $i\gamma_5$. In the SM, $\widetilde{\kappa}_t = 0$.

If $\widetilde{\kappa}_t \neq 0$, the Higgs is not a pure scalar: the top–Higgs interaction violates CP. That would be new physics, and CP violation beyond the SM is one of the ingredients needed to explain the matter–antimatter asymmetry of the universe.

**Why a linear $e^+e^-$ collider?** Compared to the LHC:

- the initial state is clean and fully known (no parton distribution functions);
- the beams can be polarised, which changes production in a controlled way;
- charge-aware flavour tagging (ParT, §1.2) can tell quark jets from antiquark jets;
- the full event, including both tops and the Higgs, can be reconstructed.

**Why machine learning?** Traditional CP studies compress each event into *one* cleverly chosen angle. But the CP-violating interference (§2.1) leaves traces in several correlated kinematic quantities at once. An ML model can use all of them together. The central question of this project is:

> How much CP-interference information does a single angular observable capture, how much more does an ML model using the *same* physical objects capture, how much of either survives the step from generator level (truth) to reconstruction level (detector), and what is the best way to combine several physically distinct sources of information?

## 1.2 Starting conditions — what exists, and what is *your* job

Vocabulary you will meet immediately:

- **Generator level ("gen")** — the Monte-Carlo truth: the actual four-momenta of the quarks, leptons, W's, tops, Higgs, before any detector simulation.
- **Reconstruction level ("reco")** — what an analysis would actually measure: jets, an isolated lepton, missing momentum, after detector simulation and reconstruction.
- **ParT** — the ILC **Par**ticle **T**ransformer, a charge-aware flavour tagger. For each jet it provides probabilities such as "this is a $b$ jet" vs. "this is a $\bar{b}$ jet" (signed quark/antiquark probabilities).
- **Jet assignment** — deciding which reconstructed jet plays which role ($W$ jet 1, $W$ jet 2, hadronic-top $b$, leptonic-top $b$, Higgs $b$'s). Here this is done with a kinematic fit helped by ParT scores; see [KINFIT_JET_ASSIGNMENT.md](KINFIT_JET_ASSIGNMENT.md).
- **Semileptonic channel** — one top decays hadronically ($t\to bW,\ W\to q\bar q'$), the other leptonically ($t\to bW,\ W\to \ell\nu$). One isolated lepton, six jets (2 from $W$, 2 top $b$'s, 2 Higgs $b$'s), one neutrino.

Starting conditions:

1. Generator-level CP samples with **signed interference weights** (§2.2) exist. Final validation of the generator itself is the **supervisor's** job, not yours.
2. Reconstructed semileptonic signal samples with a ParT-assisted jet assignment exist.
3. ParT provides charge-aware flavour information, including signed quark/antiquark probabilities.
4. **No complete angular–ML baseline exists yet.** Building it is your first milestone.
5. The final signal-vs-background event-selection MVA (§2.9, Chapter 6) is being developed by the supervisor and should arrive after roughly one to two weeks. Everything before Chapter 6 must work without it.
6. Apart from requiring exactly one isolated lepton and basic technical validity, the final physics selection will be MVA-based — you will *receive* that MVA, not build it.
7. You are **not** responsible for validating the generator, producing missing MC samples, or finishing the entire $t\bar{t}H$ analysis (full list of non-goals: §11.5).

## 1.3 The five scientific questions

Everything in this project answers one of these:

1. **Angle vs. ML, same objects.** For one pair of physical objects (e.g. the two $W$ jets), how much CP information is in the signed angle, and how much *extra* does an ML model using the same objects capture?
2. **Truth vs. detector.** How much information is lost when truth-level objects are replaced by reconstructed ones?
3. **Which branch is strongest?** How do the hadronic W, top-decay $b/\bar{b}$, lepton–neutrino, and reconstructed-top observables compare with each other?
4. **How to combine?** Is it better to train one model on all features, keep separate physical branches, fuse branch outputs at the end, or use a multidimensional likelihood? (Definitions in §2.7 and Chapter 7.)
5. **Realistic beams.** How do you convert results from the idealised 100%-polarised LR/RL samples into the realistic LCF running scenario? (§2.13, Chapter 8.)

## 1.4 Required scope — the six deliverables

In order (this is also roughly the timeline):

1. A complete gen + reco **angular–ML baseline for $O_W$** (the hadronic W angle) — Chapters 3–4. This is the main milestone.
2. Integrate the supervisor's **event-selection MVA**; first selected-signal and signal-plus-background result — Chapter 6.
3. **Faster baselines** for the secondary observables $O_b$, $O_{\ell\nu}$, $O_{\mathrm{top}}$ — Chapter 5 (reuse the $O_W$ machinery; do not rebuild anything).
4. **Fusion** of $O_W$ with *one* chosen secondary observable — Chapter 7.
5. The **physical LCF polarisation combination** — Chapter 8.
6. A minimal, supervisor-approved **generator → SMEFT coupling conversion** — Chapter 9.

## 1.5 Optional extensions

Not required. Completing **none** of them is perfectly fine; normally at most **one** is opened, and only after the required results are frozen (Chapter 10):

1. add the hadronic tau semileptonic channel as an extra category;
2. try to improve the ParT-assisted hadronic W jet pairing;
3. add the quadratic ($c^2$) EFT term;
4. extend fusion beyond the required $O_W$ plus one secondary observable.

## 1.6 Negative results are valid results

This is a *validation and stability* study. All of the following are useful, reportable outcomes:

- the plain angle retains almost as much information as the ML model → "a simple angle suffices" is a real conclusion;
- one all-feature model is no better than separate branches;
- the existing jet assignment is already close to a perfect ("oracle") assignment;
- a fancier reference frame gives no gain;
- an optional extension is not justified by the available statistics.

You are measuring *how much information survives and where*, not trying to force the ML number to be bigger.

---

# Chapter 2 — Concepts: physics, ML, and statistics

This chapter is the toolbox. Read it once fully, then come back to individual sections as you need them.

## 2.1 Scalar–pseudoscalar interference: where the signal lives

### From $(\kappa_t,\widetilde{\kappa}_t)$ to the mixing angle $\xi$

Section 1.1 wrote the vertex with two real couplings $(\kappa_t,\widetilde{\kappa}_t)$. An equivalent one-parameter convention uses a single **CP mixing angle** $\xi$:

```math
\mathcal{L}_{t\bar{t}H}
=
-\frac{m_t}{v}H\,
\bar{t}\left(\cos\xi+i\sin\xi\,\gamma_5\right)t .
```

The corresponding couplings are

```math
\kappa_t=\cos\xi,\quad
\widetilde{\kappa}_t=\sin\xi .
```

This convention fixes the total Yukawa strength ($\kappa_t^2+\widetilde{\kappa}_t^2=1$) and keeps the scalar–pseudoscalar mixing as the only free parameter. The SM is $\xi=0$. Near the SM point $\widetilde{\kappa}_t=\sin\xi\approx\xi$, so the small "local" parameter $c$ introduced below can be read as $c\propto\widetilde{\kappa}_t\approx\xi$; the exact proportionality constant is a generator convention, fixed once in §2.14.

### CP transformations: CP-even vs CP-odd at the Lagrangian level

CP is the combination of charge conjugation C (particle $\leftrightarrow$ antiparticle) and parity P (space inversion: momenta flip, $\vec p\to-\vec p$, while spins do not). A Lagrangian term is **CP-even** if CP maps it onto itself, and **CP-odd** if CP maps it onto minus itself. Taking the Higgs field as a CP-even scalar, the two top bilinears transform oppositely:

- $H\,\bar{t} t$ — the scalar ($\kappa_t$) term — is **CP-even**;
- $H\,i\bar{t}\gamma_5 t$ — the pseudoscalar ($\widetilde{\kappa}_t$) term — is **CP-odd**.

Note that either term *alone* does not violate CP: if only the pseudoscalar term were present, one could simply declare $H$ to be a CP-odd particle and CP would again be conserved. CP violation requires **both terms simultaneously** ($\kappa_t\widetilde{\kappa}_t\neq0$, i.e. $\sin\xi\cos\xi\neq0$) — then no consistent CP assignment for $H$ leaves the Lagrangian invariant, and it is precisely the *interference* between the two terms that exposes this.

### CP-even vs CP-odd at the amplitude and observable level

The total amplitude for an event configuration $x$ is the superposition

```math
\mathcal{M}(\xi)=\cos\xi\,\mathcal{M}_S+\sin\xi\,\mathcal{M}_P .
```

Let $\bar x$ denote the **CP image** of the configuration $x$ (all momenta reflected, particles exchanged with antiparticles). Because the two vertices transform oppositely under CP, so do the two amplitudes (up to absorptive phases, negligible here):

```math
\mathcal{M}_S(\bar x)=\mathcal{M}_S(x),
\qquad
\mathcal{M}_P(\bar x)=-\mathcal{M}_P(x).
```

Squaring the superposition gives **three** pieces with definite CP character:

| Piece | Coupling factor | Under $x\to\bar x$ | CP character |
|---|---|---|---|
| $\lvert\mathcal{M}_S\rvert^2$ | $\cos^2\xi$ | unchanged | CP-even |
| $2\,\mathrm{Re}(\mathcal{M}_S^{*}\mathcal{M}_P)$ | $\sin\xi\cos\xi$ | **flips sign** | **CP-odd** |
| $\lvert\mathcal{M}_P\rvert^2$ | $\sin^2\xi$ | unchanged | CP-even |

Near the SM point, with the small local parameter $c$, the differential cross section over the event configuration $x$ is

```math
\frac{d\sigma}{dx}=f_0(x)+c\,f_1(x)+c^2 f_2(x),
```

where

- $f_0 = d\sigma_{\mathrm{SM}}/dx$ is the SM prediction and is CP-even:
  $f_0(\bar x)=f_0(x)$.
- $f_2 = d\sigma_{\mathrm{CPV}^2}/dx$ is the pure-CPV quadratic term and is
  also CP-even.

The interference term is

```math
f_1(x)
=
\frac{d\sigma_{\mathrm{int}}}{dx}
=
2\,\mathrm{Re}\left[
\mathcal{M}_{\mathrm{SM}}^{*}
\mathcal{M}_{\mathrm{CPV}}
\right]d\Phi .
```

It is linear in $c$ and CP-odd: $f_1(\bar x)=-f_1(x)$.

The same classification applies to observables: $O$ is **CP-even** if $O(\bar x)=O(x)$ and **CP-odd** if $O(\bar x)=-O(x)$. Two consequences drive the entire analysis strategy:

1. In a CP-symmetric sample (the SM part $f_0$ alone), any CP-odd observable has a distribution **symmetric around zero**, so $\langle O\rangle=0$. This becomes the SM CP-closure check once the required SM template is available.
2. Only the CP-odd part of an observable is *linearly* sensitive to $c$: since $f_1$ is CP-odd, $\int O\,f_1\,dx=0$ for any CP-even $O$, while for a CP-odd $O$

```math
\langle O\rangle
=
\frac{c\int O(x)\,f_1(x)\,dx}{\sigma_{\mathrm{SM}}}
+\mathcal{O}(c^2)
\;\propto\; c .
```

> **In plain words:** for small $c$ the interference term $c\,f_1$ dominates the deviation from the SM. $f_1(x)$ is **not positive everywhere** — CP-oddness forces it to be positive in some regions of phase space and negative in the CP-mirrored regions, integrating to zero over any CP-even variable. "Finding the CP signal" = "finding a CP-odd variable in which the positive and negative regions of $f_1$ separate cleanly", so that the interference shows up as an **asymmetry** of the distribution instead of cancelling inside each bin.

The required programme uses only $f_0 + c f_1$. The quadratic term is Optional Extension 3.

## 2.2 Attach each sidecar weight to the correct event

The important bookkeeping problem is not event generation. The event
kinematics are stored in STDHEP/SLCIO, while the sign and normalisation of the
CP-odd interference are stored in a separate per-chunk sidecar CSV. A sidecar
row has physics meaning only when it is attached to the correct event.

For the current production samples, sidecar row $i$ belongs to the $i$-th
usable STDHEP event in the same chunk. `weights.py` enforces sequential sidecar
event numbers and checks

```math
s_{\mathrm{sidecar}}=\mathrm{sign}(w_{\mathrm{int}}),
\qquad
|w_{\mathrm{int}}|
=
\frac{\sigma_{|\mathrm{int}|}}{N_{\mathrm{generated}}}.
```

The older historical validation sample has an additional complication:
JSFHadronizer skipped some numbered events. Its skipped event numbers are read
from the Physsim log and removed from the sidecar before row-by-row alignment.
The current production chunks do not use that skip-log correction.

At reconstruction level, the kinfit tree stores `event_index`, the input SLCIO
record index. `export_features.py` uses that index both to retrieve the reco
objects and to retrieve the corresponding row of the already aligned sidecar.
If this alignment is shifted by even one event, a perfectly plausible angle is
assigned another event's interference sign. The resulting asymmetry or ML
label is then meaningless even though every individual input file still looks
valid. This is why Chapter 3 asks for sidecar counts, event-index checks, and
`n_event_number_mismatch=0` before any plot is interpreted.

### What the weight columns actually mean

The CPV sidecar supplies the signed interference weight used for $f_1$.
Separate SM generator/reco tables supply $f_0$ and are evaluated with the same
angle or trained model. For one independent SM chunk, the base physical weight
is $\sigma_{\mathrm{SM}}/N_{\mathrm{written,chunk}}$; luminosity and
polarisation are applied when yields are built. The polarization-matched LR
and RL cross sections are both audited. The relevant columns are:

| Column | Current meaning | Where it is used |
|---|---|---|
| `label` | $+1$ or $-1$ from the sign of $w_{\mathrm{int}}$ | classifier target only |
| `weight_training` | non-negative base optimizer weight, currently $\lvert w_{\mathrm{int}}\rvert$ | `train_cpv_model.py` only |
| `weight_interference_signed` | signed MC estimate of the interference derivative $f_1$ | provenance and physics checks |
| `weight_template` | active component's base weight: signed interference on CPV rows, physical SM weight on normalized SM rows | angular/ML templates |
| `weight_sm` | $\sigma_{\mathrm{SM}}/N_{\mathrm{written,chunk}}$ in fb on normalized SM rows | physical SM denominator |
| `weight_sm_shape` | $1/N_{\mathrm{written,chunk}}$ | SM shape checks when an absolute cross section is unavailable |

The official samples were already generated by importance sampling
$|f_1|$. Within each current production chunk, $|w_{\mathrm{int}}|$ is constant.
Therefore this base weight is equivalent to an unweighted fit for the present
samples; normalising it to mean one does not change that. The only non-uniform
training rescaling currently introduced is that the trainer equalises the
total positive- and negative-class weight in the training split. That is an
optimizer choice, not a physics weight, and it is unrelated to beam
polarisation.

Polarisation enters later: `apply_polarization_weights.py` multiplies the
signed template weight by the LR/RL mixture coefficient and luminosity. It does
not turn $|w_{\mathrm{int}}|$ into a physics yield and it does not alter the
sign label.

The distinction that must be preserved is therefore simple:
`weight_training` controls how the classifier is fitted;
`weight_template` controls how the already evaluated score or angle contributes
to the signed $f_1$ histogram. Class balancing changes only the loss used to
learn the score. When building the physics template, the code fills each event
with its original signed `weight_template`, not the class-balanced optimizer
weight. Class balancing may still change the learned score and must be
validated, but it does not directly replace the physical event weight. The
error would be to fill an interference template with the non-negative or
class-balanced training weights: that would estimate $|f_1|$, not the signed
derivative $f_1$ needed in $\nu(c)=\nu_0+c\nu_1$.

Code: [../src/ilc_tth_cpv/weights.py](../src/ilc_tth_cpv/weights.py),
[../scripts/export_features.py](../scripts/export_features.py),
[../scripts/train_cpv_model.py](../scripts/train_cpv_model.py), and
[../scripts/apply_polarization_weights.py](../scripts/apply_polarization_weights.py).

## 2.3 Angular observables

**Why azimuthal angles? (following on from §2.1.)** The interference term $f_1$ is CP-odd, so to pick it up at first order we need observables that are themselves CP-odd (§2.1, consequence 2): quantities that flip sign when all momenta are reflected and particles are exchanged with antiparticles. Signed azimuthal differences are the classic construction. The sign of a signed $\Delta\phi(a,b)$ is the sign of the triple product

```math
\mathrm{sign}\bigl(\sin\Delta\phi(a,b)\bigr)
=
\mathrm{sign}\bigl(\hat z\cdot(\hat p_a\times\hat p_b)\bigr),
```

and a triple product of momenta flips sign under P (every vector in it is reversed). With a **charge-aware ordering** of $a$ and $b$ (so that C maps the ordered pair onto itself, for example particle before antiparticle), the full CP operation gives

```math
\Delta\phi \;\xrightarrow{\;CP\;}\; -\Delta\phi ,
```

i.e. $\Delta\phi$ is CP-odd. Consequently the SM part $f_0$ produces a $\Delta\phi$ distribution **symmetric** under $\Delta\phi\to-\Delta\phi$, while the interference $c\,f_1$ produces the **antisymmetric** component: the CP signal is the asymmetry between $\Delta\phi>0$ and $\Delta\phi<0$.

The basic building block is therefore a **signed azimuthal difference** between two objects $a$ and $b$:

```math
\Delta\phi(a,b)
=
\mathrm{wrap}(\phi_a-\phi_b)
\in[-\pi,\pi),
```

where "wrap" folds the raw difference back into $[-\pi,\pi)$ (e.g. $350°$ becomes $-10°$). Two things students often get wrong:

- **Order matters.** $\Delta\phi(a,b) = -\Delta\phi(b,a)$. Since the sign *is* the CP information, you must fix which object is first (e.g. light quark before light antiquark; $b_t$ before $b_{\bar{t}}$) and never deviate. Generator truth supplies this identity directly; a reco result needs an explicitly implemented and validated orientation rule.
- **Wrapping matters.** Compute $\Delta\phi$ with a proper wrap function, never a naive subtraction.

For the two hadronic W jets, the observable is

```math
O_W=\Delta\phi(j_{W,q},\,j_{W,\bar q}).
```

For the two top-decay $b$ jets, it is

```math
O_b=\Delta\phi(b_t,\,b_{\bar{t}}).
```

For the lepton and neutrino from the leptonic $W$, use the charge-dependent
CP ordering

```math
O_{\ell\nu}(W^-)=\Delta\phi(\ell^-,\,\bar\nu),
```

```math
O_{\ell\nu}(W^+)=\Delta\phi(\nu,\,\ell^+),
```

and $O_{\mathrm{top}}=\Delta\phi(t,\bar t)$.

At reco level, kinfit first selects the W pair. For each of those two jets the
exporter sums the signed Weaver light-flavour probabilities,

```math
P(q)=P(u)+P(d)+P(s)+P(c),
\qquad
P(\bar q)=P(\bar u)+P(\bar d)+P(\bar s)+P(\bar c).
```

An opposite-preference pair is assigned directly. If both jets are q-like, the
jet with larger $P(q)$ is q; if both are qbar-like, the jet with larger
$P(\bar q)$ is qbar. The highest Weaver class may be b and is ignored for this
decision because the task is only to orient the already selected W pair. The
table stores the two scores, assignment status, and decision margin; an exact
tie uses W1 as q only as a labelled deterministic fallback.

The 2026-07-22 kinfit best tree also stores the fitted neutrino four-vector, so
reco $O_{\ell\nu}$ uses the charge ordering above. The remaining unfinished
signed-object step is the lepton-charge-dependent top/antitop orientation for
$O_b$ and $O_{\mathrm{top}}$; Chapter 4 asks the student to derive, implement,
and validate it before those observables are used.

> **Freeze conventions early.** Exact definitions, charge conventions, and axis conventions must be written down **once**, in a configuration file, and used everywhere (see the decision log, Appendix C). Silent convention changes are the classic way to waste two weeks.

Code: [../src/ilc_tth_cpv/angles.py](../src/ilc_tth_cpv/angles.py); conventions: [PHYSICS_CONVENTIONS.md](PHYSICS_CONVENTIONS.md).

## 2.4 Reference frames

An azimuthal angle needs two separate choices:

1. **which rest frame** supplies the particle four-momenta;
2. **which coordinate axes** define $\theta$ and $\phi$ in that frame.

The repository keeps two axis conventions because they reproduce two different, already existing generator studies. Do not mix them or call them interchangeable.

### The current $O_W$ baseline: fixed lab axes after the boost

The production configs freeze `basis: lab_axes`. This is the convention used by `export_features.py`, `inspect_generator_event.py`, and the original signed $\Delta\phi$ generator study. It compares three momentum frames:

- the **laboratory** frame: no boost;
- the **Higgs rest frame** (use $p_H$ to construct the Lorentz boost to rest);
- the **$t\bar{t}$ rest frame** (use $p_t+p_{\bar t}$ to construct the Lorentz boost to rest).

In all three cases the axes remain the fixed detector/lab axes

```math
\hat x_{\mathrm{lab}}=(1,0,0),\qquad
\hat y_{\mathrm{lab}}=(0,1,0),\qquad
\hat z_{\mathrm{lab}}=(0,0,1),
```

with $\hat z_{\mathrm{lab}}$ along the nominal beam direction. After a Higgs-rest or $t\bar t$-rest boost, **no coordinate rotation is applied**. Thus

```math
\phi_i
=
\mathrm{atan2}(p_{i,y}^{\mathrm{boosted}},p_{i,x}^{\mathrm{boosted}}).
```

This fixed-axis convention is reference-axis dependent, but it is the convention behind the validated original $O_W$ result and is therefore the required starting baseline in Chapter 4.

### Ma2018: a production-plane basis for $R_h$ and $R_\psi$

The Ma2018 observables use two rest frames, each with its own production-plane axes:

- $R_h$: the Higgs rest frame;
- $R_\psi$: the $t\bar t$ rest frame.

For the corresponding system $X=H$ or $t\bar t$, save its lab-frame momentum
**before** the boost. The $z$ axis follows the system direction:

```math
\hat z=\frac{\vec p_X^{\,\mathrm{lab}}}{|\vec p_X^{\,\mathrm{lab}}|}
```

The $x$ axis is the incoming-electron direction projected perpendicular to
$\hat z$:

```math
\hat x=
\frac{\hat p_{e^-}-(\hat p_{e^-}\cdot\hat z)\hat z}
{\left|\hat p_{e^-}-(\hat p_{e^-}\cdot\hat z)\hat z\right|}
```

The $y$ axis completes the right-handed basis:

```math
\hat y=\hat z\times\hat x .
```

Then the azimuth of any particle $i$ is

```math
\phi_i=\mathrm{atan2}(\vec p_i\cdot\hat y,\;\vec p_i\cdot\hat x).
```

This is the Fig. 1 convention of [Ma2018](https://arxiv.org/abs/1809.07127): $\hat z_{R_\psi}$ follows the lab flight direction of the $t\bar t$ system, while $\hat z_{R_h}$ follows the lab flight direction of the Higgs. In an ideal collider centre-of-mass event,

```math
\vec p_{t\bar t}^{\,\mathrm{lab}}
=
-\vec p_H^{\,\mathrm{lab}},
```

so $\hat z_{R_\psi}=-\hat z_{R_h}$, the projected $\hat x$ axes are equal, and $\hat y_{R_\psi}=-\hat y_{R_h}$. A sign change in a signed $\phi$ observable between these frames can therefore be a direct consequence of the convention rather than a bug.

The laboratory frame is handled separately. If $\hat z_{\mathrm{lab}}$ is the beam axis, it is invalid to reuse the Ma projection formula with the same beam vector: the projected $\hat x$ would be exactly zero. The code correctly uses fixed detector axes for `lab`.

### Beam crossing angle

There is no hard-coded crossing-angle correction in the repository. In the
fixed-`lab_axes` baseline, the stored particle four-momenta are used in detector
coordinates and the axes remain exactly $(\hat x_{\mathrm{lab}},\hat
y_{\mathrm{lab}},\hat z_{\mathrm{lab}})$ above. Therefore any crossing-angle
effect already present in the event momenta remains in the event kinematics,
but the analysis does not rotate or boost the event into an ideal head-on beam
frame.

The authoritative generator-level Ma script instead takes $\hat p_{e^-}$ from
the highest-energy parentless PDG-11 particle in each STDHEP event. Thus a
crossing angle encoded in that incoming-electron momentum is automatically used
when the production-plane $\hat x$ axis is constructed. If that particle is
missing, the script falls back to the configured $+z$ or $-z$ direction and no
crossing-angle information is recovered. The helper functions in `frames.py`
support the same rule, but the current feature exporter does not call the Ma
path (§2.4, final note below).

### Near-beam degeneracy in the Ma basis

If the Higgs or $t\bar t$ system travels almost parallel to the electron beam, the production plane becomes ill-defined:

```math
\vec x_{\mathrm{raw}}
=
\hat p_{e^-}-(\hat p_{e^-}\cdot\hat z)\hat z
\longrightarrow 0.
```

The current implementation treats $|\vec x_{\mathrm{raw}}|\leq10^{-12}$ as an invalid frame and returns no angle. Numerical toy probes give an invalid frame for $\sin\theta_X=0$ and $5\times10^{-13}$, but accept $\sin\theta_X=2\times10^{-12}$. Just above the threshold the normalized $\hat x$ can still be sensitive to tiny momentum perturbations; `BasisQuality` checks the orthonormality of the already normalized axes and therefore cannot diagnose this conditioning problem. Any Ma-style study must record the frame-failure count and inspect stability versus the system-to-beam angle. Do not invent an arbitrary fallback axis and interpret its $\phi$ as physical.

### How the signed cross-object angle is formed

The shared code first computes one azimuth per object in the chosen basis and then forms

```math
\Delta\phi(a,b)
=
\mathrm{wrap}(\phi_a-\phi_b)
\in[-\pi,\pi).
```

The cross product appears only in constructing the right-handed Ma axis $\hat y=\hat z\times\hat x$; the production $\Delta\phi$ implementation uses the explicit signed difference above. Argument order fixes the sign: quark minus antiquark for $O_W$, $b$ minus $\bar b$ for $O_b$, and top minus antitop for $O_{\mathrm{top}}$. The lepton-neutrino observable uses the CP-ordered convention of §2.3.

> **One shared implementation.** Boosts and both axis conventions live in [../src/ilc_tth_cpv/frames.py](../src/ilc_tth_cpv/frames.py); wrapping and signed differences live in [../src/ilc_tth_cpv/angles.py](../src/ilc_tth_cpv/angles.py). The current feature exporter always follows the frozen `lab_axes` path. Ma-style observables must call the dedicated production-plane functions explicitly; changing a YAML label alone does not switch the implementation.

## 2.5 ML input representation: why $(E,\theta,\phi)$?

A four-vector is $p^\mu=(E,p_x,p_y,p_z)$ with

```math
p_x=|\vec p|\sin\theta\cos\phi,\qquad
p_y=|\vec p|\sin\theta\sin\phi,\qquad
p_z=|\vec p|\cos\theta .
```

For a (nearly) massless jet, $(E,\theta,\phi)$ carries essentially the same information as the four-vector, but factorised into physically meaningful pieces:

- $E$ — energy scale;
- $\theta$ — polar direction (relative to the beam);
- $\phi$ — azimuthal direction, which is where the CP signal predominantly sits (§2.3).

This factorisation also makes the gen-vs-reco comparison transparent: you can look at resolution in $\Delta E$, $\Delta\theta$, $\Delta\phi$ separately.

**Default choice: start from the raw variables** ($E$, $\theta$, $\phi$, masses, scores), with no transformation. See [DATA_SCHEMA.md](DATA_SCHEMA.md) and [../KNOWN_ISSUES.md](../KNOWN_ISSUES.md).

**Optional variant:** raw $\phi$ jumps discontinuously between $+\pi$ and $-\pi$, and events near the wrap point may be handled poorly by some ML models. If such a problem is actually observed (e.g. artefacts in the learned score near $\phi=\pm\pi$), an optional smooth representation to try is

```math
\left(\log\frac{E}{E_0},\ \cos\theta,\ \sin\phi,\ \cos\phi\right),
```

optionally adding $m_j$ or $m_j/E_j$ for massive jets. Either way, four-vectors are always preserved internally for boosts and invariant masses.

Code: [../src/ilc_tth_cpv/features.py](../src/ilc_tth_cpv/features.py).

## 2.6 The ML observable paired with each angle

The comparison in question 1 (§1.3) is only fair if the ML model uses **the same physical objects** as the angle. For the hadronic W branch, the model is a map

```math
M_W:\ F_W\ \rightarrow\ s_W
```

from a feature set $F_W$ to a score $s_W$.

The **minimal** feature set contains the kinematics of the two $W$ jets and
the quantities required to define the frame:

```math
F_W^{\mathrm{min}}
=
\{E,\theta,\phi\}_{j_{W,q}}
\cup
\{E,\theta,\phi\}_{j_{W,\bar q}}
\cup
F_{\mathrm{frame}} .
```

Here $F_{\mathrm{frame}}$ denotes the frame-defining information. The
**extended** set adds pair quality and signed flavour information:

```math
F_W^{\mathrm{ext}}
=
F_W^{\mathrm{min}}
\cup
\{m_{jj},P_{\mathrm{pair}},P_{\mathrm{orientation}},P_{\mathrm{ParT,signed}}\} .
```

$P_{\mathrm{ParT,signed}}$ collectively denotes the signed ParT
quark-antiquark probabilities.

Analogous branches: $M_b$, $M_{\ell\nu}$, $M_{\mathrm{top}}$.

For a binary classifier the **default** ML observable is the difference of class probabilities,

```math
O_{\mathrm{ML}}=P(+)-P(-)\ \in[-1,1] .
```

An **optional** alternative is the logit,

```math
O_{\mathrm{logit}}=\log\frac{P(+)}{P(-)} ,
```

a monotonic transform of the same score that can be useful if the information concentrates in the tails ($P(\pm)\to1$). Use the subtraction definition unless there is a demonstrated reason to switch — and record whichever convention is used in the model metadata, because downstream binning and Fisher calculations depend on it.

Training script: [../scripts/train_cpv_model.py](../scripts/train_cpv_model.py); model policy: [DEPENDENCY_AND_MODEL_POLICY.md](DEPENDENCY_AND_MODEL_POLICY.md).

## 2.7 Why compare feature subsets at all? (information projections)

Here is the theoretical picture that makes questions 1, 3, 4 (§1.3) precise. For the full event $x$, the ideal CP observable is the **local score**

```math
t(x)=
\left.\frac{\partial\log p(x|c)}{\partial c}\right|_{c=0}
=\frac{f_1(x)}{f_0(x)},
```

i.e. the relative size of the interference at that phase-space point. No observable can beat it. If you only keep part of the event, $z=g(x)$ (e.g. only the two $W$ jets), the best you can possibly do in that reduced space is the conditional average

```math
t_z(z)=\mathrm{E}\left[t(x)\mid z\right].
```

> **In plain words:** every feature group (W jets only, b jets only, everything, …) is a different *projection* of one and the same underlying CP-interference information. A "W-branch model" and a "b-branch model" are not measuring different physics parameters — they are partial views of the same $c$. (For a single coupling, they do **not** correspond to different CP phases.)

### What makes the projections physically different?

The CP structure of the $t\bar{t}H$ vertex is imprinted in the **production spin-density matrix** of the $t\bar{t}(H)$ system. Because the top decays before hadronising, its decay products act as **spin analysers**: each decay product reads out the parent top's spin through its own decay matrix, with its own analysing power, so the *same* spin-density matrix is projected into *different* angular distributions depending on which objects you use (see arXiv:1809.07127 for the formalism). Concretely:

- **Single-side objects** (decay products of only one top) mainly project out the **polarization of that single top**.
- **Objects from both sides** (one from $t$, one from $\bar{t}$ — as in $O_b$) directly access the **$t\bar{t}$ spin-correlation matrix**, where much of the CP-odd interference information sits.
- The **two hadronic W daughter jets** additionally encode the **$W$ helicity and decay-plane orientation** — an extra handle beyond the parent-top spin direction.
- The **reconstructed-top observable** $O_{\mathrm{top}}$ works at production level: it probes the kinematics of the $t$, $\bar{t}$, $H$ systems themselves, in particular the interference between Higgs emission off the top line (the $t\bar{t}H$ vertex being measured) and the Higgsstrahlung-like contribution where the Higgs is radiated off the intermediate $Z$ (the "ZH"-type diagram).

The projections also differ in **reconstruction quality**, not only in physics content: the isolated lepton is tagged with high efficiency, carries an unambiguous charge, and has no jet-assignment problem; a $b/\bar{b}$ ordering instead relies on flavour tagging (lower efficiency, mis-tag rates) *plus* jet assignment. A reco-level branch comparison therefore mixes analysing power with reconstruction quality — comparing gen level (physics only) against reco level (physics × detector) disentangles the two, which is exactly the $R_{\mathrm{reco}}$ logic of §2.12.

This is exactly why Chapter 7 compares:

- separate physical branches ($s_W$, $s_b$, …);
- **early fusion** — one model trained on all features at once;
- **late fusion** — a small model combining the branch scores $(s_W, s_X)$;
- a **multidimensional likelihood** — using $(s_W, s_X)$ directly as a 2D histogram.

If the branches are nearly independent projections, late fusion ≈ early fusion; if they are strongly overlapping, adding a branch gains little. Both outcomes are informative.

## 2.8 Comparing gen and reco correctly: total retention first

The main reconstruction metric in this project is the **total Fisher-information retention**

```math
R_{\mathrm{reco}}^{\mathrm{total}}
=
\frac{I_{\mathrm{reco}}^{\mathrm{baseline}}}
{I_{\mathrm{gen}}^{\mathrm{inclusive}}}.
```

The denominator uses the inclusive generated population for which the chosen gen observable is defined; the numerator uses the full reconstructed baseline. Do **not** intersect event IDs for this headline ratio. Missing reco events, failed reconstruction, invalid assignments, smearing, and mis-assignment are all part of the loss, while the original generated-sample weight normalisation is retained.

> **Optional matched-event diagnostic:** students who are interested in separating the sources of information loss may also define $S_{\mathrm{common}}=S_{\mathrm{gen}}\cap S_{\mathrm{reco}}$ and evaluate $R_{\mathrm{migration}}=I_{\mathrm{reco}}(S_{\mathrm{common}})/I_{\mathrm{gen}}(S_{\mathrm{common}})$. This matched-event ratio isolates migration, resolution, and mis-assignment among successfully reconstructed events. It excludes acceptance and reconstruction-efficiency losses, so never call it the total retention. This study is optional and is not required for the main result.

The practical bookkeeping and pass/fail checks are introduced step by step in Chapter 3; the actual $I_{\mathrm{reco}}/I_{\mathrm{gen}}$ comparison belongs to Chapter 4.5. Schema and optional matching diagnostic: [DATA_SCHEMA.md](DATA_SCHEMA.md), [../tests/test_event_matching.py](../tests/test_event_matching.py).

## 2.9 Event-selection MVA and backgrounds

The signal density is $f_{\mathrm{sig}}(x;c)=f_0(x)+c f_1(x)$. A fixed selection (a cut on the supervisor's MVA score) is an acceptance function $a(x)\in\{0,1\}$:

```math
f_{\mathrm{selected}}(x;c)=a(x)\left[f_0(x)+c f_1(x)\right].
```

Because $a(x)$ does not depend on $c$, the local score of **accepted** events is still $f_1/f_0$ — so selection *removes events* (and thus information) but does not bias the shape logic of the signal-only study. That is why Chapters 3–5 can proceed before the MVA arrives.

With a background $b(x)$ that does not depend on $c$, the ideal observable becomes

```math
t_{\mathrm{sig+bg}}(x)
=
\frac{f_1(x)}{f_0(x)+b(x)}
=
\frac{f_0(x)}{f_0(x)+b(x)}
\frac{f_1(x)}{f_0(x)} .
```

The first factor is the signal purity and the second is the signal-only CP
score.

> **In plain words:** in the presence of background, the best observable is (purity) × (CP score). This motivates using the selection-MVA score $q_{SB}$ **as a second dimension** $(q_{SB}, O_{\mathrm{CP}})$ rather than only as a hard cut — a hard cut throws away the purity information of the events it keeps. Chapter 6 quantifies the difference.

Interfaces: [MVA_INTERFACE.md](MVA_INTERFACE.md), [BACKGROUND_INTERFACE.md](BACKGROUND_INTERFACE.md).

## 2.10 Fisher information: the project's common currency

Every comparison in this project ("angle vs ML", "gen vs reco", "frame A vs frame B") is expressed as a ratio of **Fisher information**. Intuition first:

> The Fisher information $I$ measures how fast your expected histogram changes with the physics parameter $c$, relative to the statistical noise. Large $I$ = the data constrain $c$ tightly. Its practical meaning is the achievable uncertainty: $\sigma_c \approx 1/\sqrt{I}$ (§2.11).

For a histogram of independent Poisson bins with expectations

```math
\nu_i(c)=\nu_{0,i}+c\,\nu_{1,i}
```

($\nu_{0,i}$ = SM yield in bin $i$, $\nu_{1,i}$ = interference yield, both from your weighted templates), the likelihood is $\mathcal{L}(c)=\prod_i \mathrm{Pois}(n_i\mid\nu_i(c))$ and the Fisher information at $c=0$ is

```math
I(0)
=
\sum_i
\frac{\nu_{1,i}^2}{\nu_{0,i}} .
```

The contribution from bin $i$ is

```math
I_i=\frac{\nu_{1,i}^2}{\nu_{0,i}} .
```

The per-bin form tells you *where* the information sits: a bin is valuable when its interference yield is large **relative to the square root of its SM yield** ($I_i = (\nu_{1,i}/\sqrt{\nu_{0,i}})^2$).

With a $c$-independent background,

```math
\nu_{0,i}=s_{0,i}+b_i,\qquad
\nu_{1,i}=s_{1,i}
\quad\Longrightarrow\quad
I=\sum_i\frac{s_{1,i}^2}{s_{0,i}+b_i} .
```

> Note: high purity alone is not enough — a useful bin needs a large interference yield relative to $\sqrt{s_{0}+b}$.

The **absolute-yield Fisher** above includes both rate and shape information.
If the overall normalisation is removed or profiled away, use the
**shape-only Fisher**:

```math
I_{\mathrm{shape}}
=
\sum_i\frac{\nu_{1,i}^2}{\nu_{0,i}}
-
\frac{\left(\sum_i\nu_{1,i}\right)^2}{\sum_i\nu_{0,i}} .
```

For a purely CP-odd observable, $\sum_i\nu_{1,i}\approx0$, and the two
variants coincide.

Code: [../src/ilc_tth_cpv/fisher.py](../src/ilc_tth_cpv/fisher.py), driver [../scripts/evaluate_fisher.py](../scripts/evaluate_fisher.py).

## 2.11 From Fisher information to limits

Near the reference point the log-likelihood is approximately parabolic:

```math
-2\Delta\log\mathcal{L}(c)\simeq I c^2
\quad\Longrightarrow\quad
\sigma_c\simeq\frac{1}{\sqrt I},
\qquad
|c|_{68\%}\simeq\frac{1}{\sqrt I},
\qquad
|c|_{95\%}\simeq\frac{1.96}{\sqrt I}.
```

> **Use Fisher as a ranking tool, not as the final answer.** It is exact only in the Gaussian/local limit. Run an explicit likelihood scan ([../src/ilc_tth_cpv/likelihood.py](../src/ilc_tth_cpv/likelihood.py)) before *quoting* an interval whenever any of these hold:
> - the quadratic ($c^2$) term matters;
> - linear templates $\nu_0 + c\nu_1$ go negative somewhere in the scan range;
> - the likelihood is visibly asymmetric;
> - bins are sparsely populated;
> - nuisance parameters are included;
> - the expected interval is large enough that "local" no longer applies.

With nuisance parameters $\theta$, the effective (profiled) information is reduced:

```math
I_{\mathrm{prof}}
=
I_{cc}
-
I_{c\theta}I_{\theta\theta}^{-1}I_{\theta c} .
```

## 2.12 Retention and gain metrics — the headline numbers

For any observable $z$, evaluate the Fisher information at each analysis stage:

```math
I_{\mathrm{gen}}(z),\quad
I_{\mathrm{reco}}(z),\quad
I_{\mathrm{selected}}(z),\quad
I_{\mathrm{sig+bg}}(z),
```

and form the ratios that answer the project questions directly:

```math
R_{\mathrm{reco}}
\equiv
R_{\mathrm{reco}}^{\mathrm{total}}
=
\frac{I_{\mathrm{reco}}^{\mathrm{baseline}}}
{I_{\mathrm{gen}}^{\mathrm{inclusive}}} .
```

This is the fraction of information that survives reconstruction.

```math
R_{\mathrm{selection}}=\frac{I_{\mathrm{selected}}}{I_{\mathrm{reco}}} .
```

This measures the cost of the MVA selection.

```math
R_{\mathrm{background}}=\frac{I_{\mathrm{sig+bg}}}{I_{\mathrm{selected}}} .
```

This measures background dilution.

```math
G_{\mathrm{ML/angle}}=\frac{I_{\mathrm{ML}}}{I_{\mathrm{angle}}} .
```

This measures the gain from ML over the plain angle.

> **Fair-comparison rule:** every ratio requires the *same* luminosity, coupling convention, sample/chunk scope, weight normalisation, and binning strategy. For the primary gen-to-reco total retention, the event populations are intentionally not identical (§2.8); identical event IDs are required only for the optional matched-event migration diagnostic.

## 2.13 Beam polarisation: from ideal LR/RL to the real machine

The MC samples are 100% polarised: $LR$ means $e^-$ fully left-handed + $e^+$ fully right-handed; $RL$ is the reverse. A real machine has partial longitudinal polarisations $(P_-, P_+)$, and its cross section is a **fixed linear mixture** of the two pure samples:

```math
d\sigma(P_-,P_+)
=
a(P_-,P_+)\,d\sigma_{LR}
+
b(P_-,P_+)\,d\sigma_{RL},
```
```math
a=\frac{(1-P_-)(1+P_+)}{4},
\qquad
b=\frac{(1+P_-)(1-P_+)}{4}.
```

For the ILC-like $80\%/60\%$ beams:

| $(P_-,P_+)$ | $a_{LR}$ | $b_{RL}$ |
|---|---:|---:|
| $(-0.8,\,-0.6)$ | 0.18 | 0.08 |
| $(-0.8,\,+0.6)$ | 0.72 | 0.02 |
| $(+0.8,\,-0.6)$ | 0.02 | 0.72 |
| $(+0.8,\,+0.6)$ | 0.08 | 0.18 |

(E.g. the $(-0.8,+0.6)$ run is dominated by the LR configuration with weight 0.72.)

The **LCF 550 GeV scenario** assumed here: total $8~\mathrm{ab}^{-1}$, shared among the four sign configurations as $(--,-+,+-,++)=(10\%,40\%,40\%,10\%)$.

The Physsim source convention has been checked for these productions. At
`POLE=-1, POLP=+1` and `POLE=+1, POLP=-1`, `functthf.F` selects a single
initial helicity with unit weight, while `sgtthf.F` uses `SPIN=1`. The stored
LR/RL cross sections are therefore pure-helicity cross sections, not values
that already contain an initial-state factor of four. Apply the factors above
once, without renormalising $a+b$.

**Polarisation in ML training — three rules:**

1. $a_r,b_r$ are **event weights**, never input features, and must never
   multiply the final classifier score.
2. To train for physical run configuration $r$, pool LR and RL events. For an
   LR event use

```math
w_{e,r}^{\mathrm{phys}}=a_r\,w_e^{LR},\qquad e\in LR .
```

For an RL event use

```math
w_{e,r}^{\mathrm{phys}}=b_r\,w_e^{RL},\qquad e\in RL .
```

This preserves the physical LR/RL mixture inside each class. Equalising total
positive and negative class weight for training stability is allowed.

3. Final templates use the physical yield weights including luminosity. For
   an LR event,

```math
w_{e,r}^{\mathrm{template}}
=
\mathcal{L}_r\,a_r\,w_e^{LR} .
```

For an RL event,

```math
w_{e,r}^{\mathrm{template}}
=
\mathcal{L}_r\,b_r\,w_e^{RL} .
```

Per-run likelihoods are combined by multiplication: $\mathcal{L}_{\mathrm{LCF}}(c)=\prod_r\mathcal{L}_r(c)$.

The initial physics study nevertheless keeps pure $LR$ and $RL$ separate — mix only in Chapter 8.

Code: [../src/ilc_tth_cpv/polarization.py](../src/ilc_tth_cpv/polarization.py), config [../configs/lcf_polarization.yaml](../configs/lcf_polarization.yaml).

## 2.14 Generator convention → SMEFT convention

The CPV generator sample should not be read as a physical finite $\alpha$
sample. It provides the signed scalar-pseudoscalar interference basis
$f_1(x)$. The small parameter $c_{\mathrm{gen}}$ is applied later in the
likelihood as the coefficient multiplying that signed template:

```math
\frac{d\sigma}{dx}
=
f_0(x)+c_{\mathrm{gen}}f_1(x)+\mathcal{O}(c_{\mathrm{gen}}^2).
```

Connect this to the coupling convention of §1.1 and §2.1 by writing

```math
\kappa_t=\kappa\cos\alpha,
\qquad
\widetilde{\kappa}_t=\kappa\sin\alpha .
```

For a one-parameter Warsaw-basis reinterpretation of the CP-odd top-Yukawa
operator $O_{t\varphi}$, in a fixed input scheme, the linear dimension-6
relations are

```math
\kappa\cos\alpha
=
1-\frac{v^3}{\sqrt{2}m_t}\frac{C^R_{t\varphi}}{\Lambda^2},
\qquad
\kappa\sin\alpha
=
-\frac{v^3}{\sqrt{2}m_t}\frac{C^I_{t\varphi}}{\Lambda^2}.
```

The coefficient of the scalar-pseudoscalar interference template is

```math
c_{\mathrm{gen}}
=
\kappa_t\widetilde{\kappa}_t
=
(\kappa\cos\alpha)(\kappa\sin\alpha).
```

Near the SM point, keeping only the linear SMEFT term,

```math
\kappa_t\simeq 1,
\qquad
c_{\mathrm{gen}}
\simeq
\widetilde{\kappa}_t
=
-\frac{v^3}{\sqrt{2}m_t}\frac{C^I_{t\varphi}}{\Lambda^2}.
```

The real scalar coefficient $C^R_{t\varphi}$ changes $\kappa_t$, but its
product with $C^I_{t\varphi}$ enters the CP-odd interference only beyond the
linear dimension-6 reinterpretation. That is why the first result can quote a
one-parameter constraint on $C^I_{t\varphi}/\Lambda^2$ without fitting
$C^R_{t\varphi}$.

Using $v\simeq246~\mathrm{GeV}$ and $m_t\simeq172.5~\mathrm{GeV}$, and quoting
$C^I_{t\varphi}/\Lambda^2$ in $\mathrm{TeV}^{-2}$,

```math
c_{\mathrm{gen}}
\simeq
-0.061
\left[
\frac{C^I_{t\varphi}/\Lambda^2}{\mathrm{TeV}^{-2}}
\right],
```

or equivalently

```math
\frac{C^I_{t\varphi}}{\Lambda^2}
\simeq
-16.4\,c_{\mathrm{gen}}\ \mathrm{TeV}^{-2}.
```

Define the dimensionless numeric parameter

```math
x^I_{t\varphi}
\equiv
\frac{C^I_{t\varphi}/\Lambda^2}{\mathrm{TeV}^{-2}},
\qquad
c_{\mathrm{gen}}=Kx^I_{t\varphi},
\qquad
K\simeq -0.061 .
```

Then the Fisher-information conversion is

```math
I_{x^I_{t\varphi}}
=
K^2 I_{c_{\mathrm{gen}}},
\qquad
\Delta\left(\frac{C^I_{t\varphi}}{\Lambda^2}\right)
=
\frac{\Delta c_{\mathrm{gen}}}{|K|}\ \mathrm{TeV}^{-2}.
```

The numerical factor and the sign convention must still be supervisor-approved
before quoting a result. This is a one-parameter reinterpretation, not a
multi-operator SMEFT fit.

---

# Chapter 3 — First end-to-end validation (do this first)

**Goal:** learn what one real event looks like, run every required stage once, and produce one trustworthy generator table plus one trustworthy reconstruction table before attempting the Chapter 4 physics comparison. Follow the steps in order. A command finishing without an error is not enough; each step below says what evidence must be checked.

## 3.1 What this chapter is for

This chapter is the bridge between the README Quick Start and the first physics result. It is not a request to redesign the data format. [DATA_SCHEMA.md](DATA_SCHEMA.md) already defines the columns; here it is used as an **acceptance contract** for tables produced by the scripts.

By the end of the chapter, the student should be able to answer, without guessing:

- Which generator STDHEP, sidecar, reco SLCIO, and kinfit ROOT file entered the run?
- Which objects and collections were read from one event?
- Which frame, axis convention, object ordering, and weight column were used?
- How many events entered, failed reconstruction, passed kinfit, and filled $O_W$?
- Where are the event table, metadata, validation JSON, histogram CSV, and plot?

## 3.2 Step 0–2: environment, source, and event inspection

### Step 0 — check the environment and registered data

```bash
cd /data/dust/user/$USER/analysis/tth-cpv-observable-ilc
source env/setup.sh
bash env/check_environment.sh
bash env/check_environment.sh --data
```

**Pass condition:** the required software checks report `OK`, the analysis config parses, `outputs/` is writable, and the LR/RL generator and reco sample paths are found. Stop and resolve any `FAIL`, `MISS`, or unexpected `NOFI` before running the analysis.

Before executing the Quick Start, read these four files in this order:

```bash
less configs/analysis_ow_lr.yaml
less configs/samples.yaml
less scripts/run_baseline.sh
less scripts/export_features.py
```

You do not need to understand every Python line. Confirm the CPV and SM sample
keys, `basis: lab_axes`, default frame, number of bins, output base directory,
and the nine stages called by `run_baseline.sh`. In particular, verify that the
Fisher stage receives a separately built SM template and never substitutes
$|f_1|$ for $f_0$.

### Step 1 — inspect generator and reconstructed events

```bash
python3 scripts/inspect_generator_event.py \
  --config configs/analysis_ow_lr.yaml \
  --chunk 0 \
  --max-events 3

python3 scripts/inspect_reco_event.py \
  --config configs/analysis_ow_lr.yaml \
  --max-events 1
```

For the generator output, record the printed STDHEP and sidecar paths, sidecar/alignment counts, positive and negative weight counts, and one event's $t$, $\bar t$, Higgs, $b/\bar b$, and hadronic W daughter identities. `O_W` should be finite whenever both light daughters are found, but its value may differ among frames because the particle momenta are boosted.

For the reco output, record the input SLCIO path and confirm that the expected collections exist. Inspect in particular `OutputErrorFlowJets6`, `RefinedJets6`, `ISOElectrons`, and `ISOMuons`; check the jet multiplicities and that the printed Weaver probabilities are present and non-constant. An unusual event is something to understand and record, not something to hide.

### Step 2 — inspect the underlying LCIO records directly

Use the paths printed in Step 1:

```bash
anajob <reco-slcio-path>

LCIO_READ_COL_NAMES="MCParticle RefinedJets6 OutputErrorFlowJets6 ISOElectrons ISOMuons" \
  dumpevent <reco-slcio-path> 0

stdhepjob_new <generator-stdhep-path> /tmp/tthcpv_chunk0_first100.slcio 100
anajob /tmp/tthcpv_chunk0_first100.slcio
dumpevent /tmp/tthcpv_chunk0_first100.slcio 0
```

From one generator event, note the incoming electron direction, the parent/daughter chain for $t$, $\bar t$, $H$, and the two hadronic W daughters. From one reco event, note the run/event number, collection names and sizes, the six-jet collections, isolated-lepton collection, and any PID parameters visible for the jets. These notes establish intuition for what the later CSV columns actually mean; `dumpevent` itself is not a selection or physics-result tool.

## 3.3 Step 3: run the local generator example and inspect its table

Run the README generator smoke chain:

```bash
bash scripts/run_baseline.sh configs/analysis_ow_lr.yaml --max-events 500
```

This executes generator inspection; separate CPV and SM feature exports;
separate angular templates; a small XGBoost training on CPV signs; evaluation
of the same score on CPV and SM events; and Fisher calculations with the real
binned LR SM denominator. With `--max-events 500` it is an integration test,
not a physics result, because the event and test-split scope is deliberately
limited. The denominator identity itself is no longer a placeholder.

The important Chapter 3 outputs are:

| Output | Location | What to inspect |
|---|---|---|
| event feature table | `outputs/ow_lr/features/features_gen_higgs_rest_chunk0.csv` | header, first rows, event IDs, validity flags, signed weights, $O_W$ |
| table metadata | `outputs/ow_lr/features/features_gen_higgs_rest_chunk0.meta.json` | sample, chunk, level, frame, `lab_axes`, row count, schema and weight reports |
| SM feature table | `outputs/ow_lr/features/features_sm_gen_higgs_rest_chunk0.csv` | SM sample identity, finite LR `weight_sm`, validity flags, $O_W$ |
| angular bins | `outputs/ow_lr/angular/O_W/O_W_test_bins.csv` | bin edges, signed and absolute bin weights, entries |
| SM angular bins | `outputs/ow_lr/angular/O_W/O_W_test_sm_bins.csv` | same edges, positive SM yields from `weight_sm` |
| angular metadata | `outputs/ow_lr/angular/O_W/O_W_test_bins.meta.json` | filled/invalid counts, out-of-range count, signed/absolute integrals |
| first plot | `outputs/ow_lr/angular/O_W/O_W_test.png` | correct range, non-empty content, positive and negative signed bins |

Useful inspection commands are

```bash
head -n 2 outputs/ow_lr/features/features_gen_higgs_rest_chunk0.csv
python3 -m json.tool outputs/ow_lr/features/features_gen_higgs_rest_chunk0.meta.json
python3 -m json.tool outputs/ow_lr/angular/O_W/O_W_test_bins.meta.json
```

**Pass condition:** both feature tables report `schema check: ok=True`; their
metadata identify CPV interference versus SM; the SM table has finite positive
`weight_sm`; both interference signs are present; event IDs are unique within
each sample; all valid $O_W$ values are in $[-\pi,\pi)$; both angular templates
use identical edges with `n_out_of_range=0`; and the Fisher JSON names the SM
bin CSV as its `nu0_source`. Do not quote the smoke numbers because only 500
events and the test split were evaluated, not because the denominator is fake.

## 3.4 Step 4–6: kinfit smoke, one complete chunk, then HTCondor

### Step 4 — run a 50-event kinfit smoke in a separate directory

First read [KINFIT_JET_ASSIGNMENT.md](KINFIT_JET_ASSIGNMENT.md), `scripts/run_kinfit_assignment.sh`, and `scripts/validate_kinfit_root.py`. Then run

```bash
bash scripts/run_kinfit_assignment.sh \
  --config configs/analysis_ow_lr.yaml \
  --chunk 0 \
  --max-events 50 \
  --out-dir outputs/ow_lr/kinfit_smoke

python3 -m json.tool \
  outputs/ow_lr/kinfit_smoke/kinfit_tthcpv_reco_elpr_chunk0.validation.json
```

This separate output directory prevents a partial 50-event ROOT file from occupying the canonical full-chunk filename. It is only a processor smoke test and is not read by the standard reco exporter.

**Pass condition:** the validation JSON has `ok: true`, a non-zero `entries` count, a non-zero `selected_entries` count, and an empty `missing_branches` list. Inside `final_selection_report`, require `modes = ["logchi2_plus_flavor"]`, `flavor_weights = [0.3]`, and `max_abs_score_residual <= 1e-5`. Inside `fitted_neutrino_report`, require every selected entry to have a finite four-vector and positive energy, and require `max_abs_mass2_gev2 <= mass2_tolerance_gev2` (default `0.1 GeV^2`) as the numerical massless-closure check. Marlin exit 134/139 is acceptable only when this content validation passes; otherwise inspect the kinfit `.log` and, for Condor jobs, the corresponding `err/` file. A ROOT made before 2026-07-22 lacks these neutrino branches and must be rerun, not patched offline.

### Step 5 — run one complete CPV chunk and its SM denominator through HTCondor

Do not run a 12,500-event kinfit job on the login node. Submit chunk 0 as the first complete batch job:

```bash
cd condor/example
python3 make_arguments.py \
  --config ../../configs/analysis_ow_lr.yaml \
  --chunks 0
mkdir -p log out err
condor_submit submit_kinfit.sub
condor_q
condor_history -limit 5

# Only after the CPV job validates, submit the matching SM denominator job.
python3 make_arguments.py \
  --config ../../configs/analysis_ow_lr.yaml \
  --component sm \
  --chunks 0
condor_submit submit_kinfit.sub
cd ../..
```

After completion, inspect:

```text
outputs/ow_lr/kinfit/kinfit_tthcpv_reco_elpr_chunk0.root
outputs/ow_lr/kinfit/kinfit_tthcpv_reco_elpr_chunk0.validation.json
outputs/ow_lr/kinfit/kinfit_tthcpv_reco_elpr_chunk0.log
outputs/ow_lr/kinfit/kinfit_tthcpv_reco_elpr_chunk0.xml
outputs/ow_lr/kinfit/kinfit_tth_sm_reco_elpr_chunk0.root
outputs/ow_lr/kinfit/kinfit_tth_sm_reco_elpr_chunk0.validation.json
```

The same validation conditions as Step 4 must pass for both samples. Also
compare each ROOT's `entries`, `selected_entries`, and input event count so
reconstruction losses are explicit. `--component sm` changes only the input
sample; both jobs use the identical processor and selection.

Now replace the generator smoke table with the complete chunk-0 table, export the full reco baseline for that chunk, and build one $O_W$ example at each level:

```bash
python3 scripts/export_features.py \
  --config configs/analysis_ow_lr.yaml --level gen --chunk 0
python3 scripts/build_angular_observable.py \
  --config configs/analysis_ow_lr.yaml \
  --features outputs/ow_lr/features/features_gen_higgs_rest_chunk0.csv \
  --split all --output-tag gen

python3 scripts/export_features.py \
  --config configs/analysis_ow_lr.yaml --level gen --component sm --chunk 0
python3 scripts/build_angular_observable.py \
  --config configs/analysis_ow_lr.yaml \
  --features outputs/ow_lr/features/features_sm_gen_higgs_rest_chunk0.csv \
  --split all --weight-column weight_sm --output-tag sm_gen

python3 scripts/export_features.py \
  --config configs/analysis_ow_lr.yaml --level reco --chunk 0
python3 scripts/build_angular_observable.py \
  --config configs/analysis_ow_lr.yaml \
  --features outputs/ow_lr/features/features_reco_higgs_rest_chunk0.csv \
  --split all --output-tag reco

python3 scripts/export_features.py \
  --config configs/analysis_ow_lr.yaml --level reco --component sm --chunk 0
python3 scripts/build_angular_observable.py \
  --config configs/analysis_ow_lr.yaml \
  --features outputs/ow_lr/features/features_sm_reco_higgs_rest_chunk0.csv \
  --split all --weight-column weight_sm --output-tag sm_reco

python3 scripts/evaluate_fisher.py \
  --template outputs/ow_lr/angular/O_W/O_W_all_reco_bins.csv \
  --sm-template outputs/ow_lr/angular/O_W/O_W_all_sm_reco_bins.csv \
  --luminosity-scale 8000
```

The explicit output tags preserve all four templates without copying or
overwriting files. Check the associated metadata rather than identifying a
plot only by its appearance.

**Pass condition:** all four feature tables have `schema_report.ok=true`; the
SM metadata records finite LR physical normalization; reco metadata point to
the expected CPV/SM kinfit ROOT and SLCIO files; event-number mismatches are
zero; kinfit mode, score, and fitted-neutrino checks remain valid; all selected
reco rows have finite $O_W$ and $O_{\ell\nu}$; orientation counts/margins are
present; all four histograms have identical edges and `n_out_of_range=0`; and
the Fisher JSON names `O_W_all_sm_reco_bins.csv` as `nu0_source`. Do not force
identical gen/reco event populations: §2.8 defines inclusive gen and full reco
baseline populations.

### Step 6 — only after chunk 0 passes, submit the remaining kinfit chunks

For the standard 80-chunk LR production, chunk 0 is already complete, so submit 1–79:

```bash
cd condor/example
python3 make_arguments.py \
  --config ../../configs/analysis_ow_lr.yaml \
  --chunks 1-79
wc -l arguments.txt
condor_submit submit_kinfit.sub
condor_q

# After the CPV production validates, produce the matching SM denominator.
python3 make_arguments.py \
  --config ../../configs/analysis_ow_lr.yaml \
  --component sm \
  --chunks 1-79
condor_submit submit_kinfit.sub
cd ../..
```

Each argument file should contain 79 jobs. Monitor held/failed jobs and
validate every ROOT file; a collection of filenames is not evidence of a
successful production. Repeat the one-chunk gate and remaining-chunk
submission separately for `analysis_ow_rl.yaml`. The registered RL SM
cross section is physical, so the same absolute Fisher checks apply there.

## 3.5 Deliverable and Chapter 4 gate

Before starting Chapter 4, show the supervisor all of the following:

1. **One event-inspection note:** one generator event and one reco event, listing the input paths, run/event identifiers, main physics objects, relevant collection sizes, selected jet/PID information, and anything missing or surprising.
2. **One validation table:** environment/data status; CPV sidecar/alignment counts; SM normalization source; positive/negative interference counts; CPV/SM kinfit ROOT and selected entries; final-selection mode, flavour weight, score residual, and fitted-neutrino checks; all four gen/reco feature-row counts; W-orientation status counts and minimum/typical margin; invalid-object counts; $O_W$ and $O_{\ell\nu}$ filled/invalid/out-of-range counts; and the Fisher `nu0_source`. Every row must say pass/fail and point to its JSON, log, or metadata evidence.
3. **Four clearly labelled one-chunk validation plots:** CPV `O_W_all_gen.png` and `O_W_all_reco.png`, plus SM `O_W_all_sm_gen.png` and `O_W_all_sm_reco.png`, all using the same frame, `lab_axes` convention, binning, and chunk scope. These validate the observable and denominator implementation but are not yet the full-sample retention result.
4. **The underlying machine-readable products:** CPV and SM gen/reco feature CSVs with `.meta.json`, both canonical chunk-0 kinfit ROOT files with validation JSON/log/XML, and all four angular bin CSVs with metadata. Large ROOT/CSV outputs stay under `outputs/` and are not committed to GitHub.
5. **Batch evidence:** the first full HTCondor chunk passed end to end before the remaining chunks were submitted, and failed/held jobs have been accounted for rather than silently omitted.

Use this minimum validation-table structure; add rows when something unusual is found:

| Check | Observed value | Pass condition | Evidence |
|---|---|---|---|
| environment and registered data |  | no unexplained `FAIL/MISS/NOFI` | `check_environment.sh` output |
| sidecar/STDHEP alignment |  | validation `ok`, both weight signs present | generator inspection output / feature metadata |
| generator feature table |  | schema OK, unique IDs, expected frame/basis | gen `.meta.json` |
| SM generator denominator |  | schema OK, finite positive `weight_sm`, same binning | SM gen `.meta.json` |
| kinfit content |  | validator OK, selected entries $>0$ | `.validation.json` |
| final-selection score |  | mode correct, weight 0.3, residual $\leq10^{-5}$ | `.validation.json` |
| fitted neutrino |  | finite and positive energy for every selected event | `.validation.json` |
| reco W orientation |  | scores/status/margin present; counts explained | reco CSV and `.meta.json` |
| reco feature table |  | schema OK, event-number mismatches 0, finite $O_W$/$O_{\ell\nu}$ | reco `.meta.json` |
| SM reco denominator |  | separate validated SM kinfit ROOT, finite `weight_sm` | SM reco `.meta.json` |
| CPV and SM $O_W$ templates |  | identical edges, invalids recorded, out-of-range 0 | angular `.meta.json` files |
| Fisher denominator |  | `nu0_source` points to the SM bin CSV | Fisher JSON |
| HTCondor accounting |  | every requested chunk completed or has an explained failure | `condor_q`, `condor_history`, output inventory |

Chapter 4 starts only when another person can follow these records from the
configured CPV and SM inputs to all four $O_W$ templates and the LR Fisher JSON
and understand every event loss. Repeat the same closure for RL using its
polarization-matched SM denominator before combining running scenarios.

---

# Chapter 4 — Comparing two angular observables at generator and reconstruction level

**Current scope: pure LR only.**

In Chapter 3, we found that an angular observable with strong CPV-interference
sensitivity at generator level retains almost no information in the current
reconstruction baseline.

Two issues may contribute to this loss:

- **Reconstructing and ordering two light-quark jets is difficult.**
  The current diagnostics indicate approximately $75\%$ correct W-jet
  assignment, about $67\%$ performance in the relatively favourable
  $c/\bar c$ category, and substantially weaker signed-flavour identification
  for $u,d,s$ jets and their antiquarks.

  **Question:** can we construct an alternative observable using one
  well-reconstructed charged lepton and only one selected hadronic analyser
  jet?

- **The current quark-versus-antiquark ordering may not be the most suitable
  ordering for the physics information that we want to retain.**

  **Question:** can a down-type/up-type assignment, a W-decay pair constraint,
  or a better-identified subset preserve more information than the current
  inclusive quark-versus-antiquark decision?

This chapter therefore introduces a second angular observable,
$O_{\ell D}$, and compares it with the existing same-W observable $O_{jj}$.

The aim is not to assume that either observable must be better. The aim is to
measure:

1. how much CPV-interference information each observable contains at generator
   level;
2. how much of that information survives reconstruction;
3. which reconstruction decision causes the dominant loss;
4. whether using the charged lepton as a stable analyser makes
   $O_{\ell D}$ more robust than $O_{jj}$.

The quoted W-assignment and flavour-tagging numbers above are approximate
Chapter 3 diagnostics. Update them if the frozen Chapter 3 validation table
changes.

---

## 4.1 Observable definitions and common truth topology

### 4.1.1 Same-W jet-pair observable

The existing observable is

```math
O_{jj}
\equiv
O_W
=
\Delta\phi(j_{W,q},j_{W,\bar q})
=
\mathrm{wrap}
\left(
\phi_{j_{W,q}}-\phi_{j_{W,\bar q}}
\right).
```

Here:

* $j_{W,q}$ is the quark jet from the hadronic W decay;
* $j_{W,\bar q}$ is the antiquark jet from the same W decay;
* $\phi$ is the azimuthal angle in the selected reference frame;
* `wrap` maps the angular difference to $[-\pi,\pi)$.

The existing feature-table column remains

```text
O_W
```

because this name is already used throughout the repository. In this chapter,
the notation $O_{jj}$ is used when comparing it with the lepton–jet
observable.

### 4.1.2 Lepton–down-type-jet observable

Let

```math
U\in\{u,c\},
\qquad
D\in\{d,s\},
```

where $U$ denotes an up-type light quark and $D$ denotes a down-type light
quark.

The allowed hadronic W decays are

```math
W^+\to U\bar D,
\qquad
W^-\to D\bar U.
```

Let

```math
Q_\ell
```

denote the electric charge of the isolated charged lepton.

The charged-lepton sign determines which top decayed leptonically and which W
decayed hadronically.

For a positive charged lepton,

```math
Q_\ell>0:
\qquad
t\to bW^+\to b\ell^+\nu,
```

so the other side is

```math
\bar t\to\bar bW^-,
\qquad
W^-\to D\bar U.
```

The required hadronic spin analyser is therefore the down-type quark
$D=d,s$.

For a negative charged lepton,

```math
Q_\ell<0:
\qquad
\bar t\to\bar bW^-\to\bar b\ell^-\bar\nu,
```

so the other side is

```math
t\to bW^+,
\qquad
W^+\to U\bar D.
```

The required hadronic spin analyser is therefore the down-type antiquark
$\bar D=\bar d,\bar s$.

Define the top-side analyser $a_t$ and antitop-side analyser
$a_{\bar t}$ by

```math
(a_t,a_{\bar t})
=
\begin{cases}
(\ell^+,j_D),&Q_\ell>0,\\[1mm]
(j_{\bar D},\ell^-),&Q_\ell<0.
\end{cases}
```

The new observable is

```math
O_{\ell D}
=
\Delta\phi(a_t,a_{\bar t})
=
\mathrm{wrap}
\left(
\phi_{a_t}-\phi_{a_{\bar t}}
\right).
```

Explicitly,

```math
O_{\ell D}
=
\begin{cases}
\mathrm{wrap}
\left(
\phi_{\ell^+}-\phi_{j_D}
\right),&Q_\ell>0,\\[2mm]
\mathrm{wrap}
\left(
\phi_{j_{\bar D}}-\phi_{\ell^-}
\right),&Q_\ell<0.
\end{cases}
```

The ordering is always

```text
top-side analyser minus antitop-side analyser
```

and not “lepton minus jet” for both lepton charges.

The new feature-table column should be called

```text
O_lD
```

to avoid special characters in CSV column names and command-line arguments.

### 4.1.3 Common generator-level topology

The following scripts **has been updated!** from the last week.

```text
src/ilc_tth_cpv/objects.py
scripts/export_features.py
```

For implementing the generator-level topology selection. Now, it requires both

```math
H\to b\bar b
```

and a strict direct-electron or direct-muon semileptonic top-pair topology:

```math
N_{W,\mathrm{had}}=1,
\qquad
N_{W,e/\mu}=1.
```

Here:

* $N_{W,\mathrm{had}}$ is the number of W bosons with a direct light-quark
  decay;
* $N_{W,e/\mu}$ is the number of W bosons with a direct electron or muon
  decay.

However, last week, the generator level results was calculated by **the whole** 
population of the different tth decay channels. So, the total Fisher information
looks even larger. (We should always compare the same thing, so that was my mistake)

The truth selection now must exclude fully hadronic events, dilepton events, and
events in which the charged lepton is produced through a tau decay. The detail
explaination on the code is in the 4.2.1.

The baseline hadronic-W analyser is restricted to $u,d,s,c$ and their
antiquarks. A physical $W^+\to c\bar b$ or $W^-\to b\bar c$ decay is currently
classified as hadronic but then rejected by the required light-quark-pair
completeness check because the $b$ daughter is not a W-analyser candidate.
Preserve and report this policy for the baseline. Do not silently add $b$ to
the W-jet analyser set.

The generator feature table should record at least:

```text
truth_topology
hadronic_W_charge
lepton_charge
lepton_flavour
down_type_daughter_pdg
```

Both $O_{jj}$ and $O_{\ell D}$ must be calculated from the same strict
semileptonic $e/\mu$ truth population.

All generator-to-reconstruction comparisons later in this chapter must use
this same physics-channel definition.

But you can keep the old Chapter 3 products as historical validation records.

### 4.1.4 Chapter completion order

Specifically, the core task in this chapter is to modify the `/src/ilc-tth-cpv/
objects.py`, `flavor.py` to construct the observable `O_lD` and then write it
into a csv file by the `export_features.py`, then plot them by reading the csv 
file by `build_angular_observable.py` .

The commands below are what you need to execute for each step. But you should modify
the scripts mentioned above first. I also provided some hints to do this in the following
subchapters, but feel free to code by your own thoughts.

**Step 1 — create the complete Chapter 4 config.**

Copy the frozen LR config:

```bash
cp configs/analysis_ow_lr.yaml configs/analysis_angular_lr.yaml
```

Do not construct the new config from the short YAML fragment below; it would
omit the registered samples, weights, split, binning, and kinfit settings.
Keep all inherited settings and change only:

```yaml
analysis:
  name: angular_lr_comparison
  observable_family: O_W

outputs:
  base_dir: outputs/angular_lr
```

`observable_family: O_W` remains the default only. The template commands select
either feature-table column explicitly through `--observable`.

**Step 2 — implement the new observable.**

Modify `objects.py`, `flavor.py`, and `export_features.py` as specified in
§4.2. After this work, both the generator and reconstruction feature exporters
must write `O_W` and `O_lD`. Before this implementation is complete, a command
with `--observable O_lD` is expected to fail with no finite `O_lD` entries.

**Step 3 — export the CPV-interference generator features.**

```bash
python3 scripts/export_features.py \
  --config configs/analysis_angular_lr.yaml \
  --level gen \
  --chunk 0
```

This writes:

```text
outputs/angular_lr/features/features_gen_higgs_rest_chunk0.csv
outputs/angular_lr/features/features_gen_higgs_rest_chunk0.meta.json
```

**Step 4 — export the SM generator features.**

```bash
python3 scripts/export_features.py \
  --config configs/analysis_angular_lr.yaml \
  --level gen \
  --component sm \
  --chunk 0
```

This writes:

```text
outputs/angular_lr/features/features_sm_gen_higgs_rest_chunk0.csv
outputs/angular_lr/features/features_sm_gen_higgs_rest_chunk0.meta.json
```

Both feature CSVs must contain the `O_W` and `O_lD` columns before continuing.

**Step 5 — build the four generator-level templates.**

Build the two signed CPV-interference templates from the CPV feature table:

```bash
python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_gen_higgs_rest_chunk0.csv \
  --observable O_W \
  --split all \
  --output-tag gen

python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_gen_higgs_rest_chunk0.csv \
  --observable O_lD \
  --split all \
  --output-tag gen
```

Build the two SM templates from the SM feature table:

```bash
python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_sm_gen_higgs_rest_chunk0.csv \
  --observable O_W \
  --split all \
  --weight-column weight_sm \
  --output-tag sm_gen

python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_sm_gen_higgs_rest_chunk0.csv \
  --observable O_lD \
  --split all \
  --weight-column weight_sm \
  --output-tag sm_gen
```

The complete output prefix is:

```text
outputs/angular_lr/
```

The four template stems are:

| Input feature table | Observable | Output stem below `outputs/angular_lr/` |
| --- | --- | --- |
| CPV interference | `O_W` | `angular/O_W/O_W_all_gen` |
| CPV interference | `O_lD` | `angular/O_lD/O_lD_all_gen` |
| SM | `O_W` | `angular/O_W/O_W_all_sm_gen` |
| SM | `O_lD` | `angular/O_lD/O_lD_all_sm_gen` |

Each stem produces:

```text
<stem>.png
<stem>_bins.csv
<stem>_bins.meta.json
```

For the CPV templates, the default `weight_template` is
`weight_interference_signed`, so the histogram represents the signed
interference template $f_1$. For the SM templates, the `weight_sm` column is

```math
w_{\mathrm{SM}}
=
\frac{\sigma_{\mathrm{SM}}}{N_{\mathrm{written}}},
```

so the histogram provides the physical SM denominator $f_0$. These templates
are in cross-section units and have not yet been multiplied by the total
luminosity. The later Fisher command applies luminosity through
`--luminosity-scale`.

These four all-category templates provide the first generator-level closure.
The electron/muon-separated templates required for the headline Fisher result
are built later through the category interface in §4.5.

**Important truth-selection update.** The current generator exporter now
requires $H\to b\bar b$ and the strict direct-$e/\mu$ semileptonic topology.
Therefore, rerunning the generator export changes the selected event count,
template bin contents, template integrals, and Fisher information relative to
older Chapter 3 products made before this truth selection was added. Do not
mix old Chapter 3 templates with the new Chapter 4 templates.

For an event that remains selected, the truth selection alone should not
change its existing `O_W` value because the $O_W$ definition is unchanged. If
the same retained event receives a different `O_W`, investigate the object
selection or ordering rather than attributing the difference to the channel
filter.

Finally, check that $O_{jj}$ and $O_{\ell D}$ have the documented number of
finite generator entries. Any difference must be explained by an explicit
validity condition; do not silently filter different event populations.

---

## 4.2 Where to implement the new observable

Use the existing feature-export, histogram, and Fisher framework.

Do not create a second independent analysis chain.

### Start here: implementation map

Do not infer the repository status from a planned output filename. Use this
map before editing:

| Capability | Current status | Student action |
| --- | --- | --- |
| $H\to b\bar b$ plus direct $e/\mu$ semileptonic truth selection | implemented | preserve it in `objects.py` and `export_features.py` |
| `O_W` at gen and reco level | implemented | use it as the reference observable |
| `--observable <column-name>` | implemented | use the existing interface in `build_angular_observable.py` |
| truth down-type analyser metadata and `O_lD` | not implemented | extend `objects.py` and `export_features.py` |
| charge-dependent reco analyser ordering | not implemented | add one helper in `flavor.py`, then call it from `export_features.py` |
| reconstructed `lepton_flavour` | not implemented | return the source collection from `first_isolated_lepton()` |
| electron/muon template filtering | not implemented | add `--lepton-flavour` to `build_angular_observable.py` |
| Chapter 4 config | not present | copy the complete LR config as described in §4.1.4 |
| new schema entries and convention tests | not present | update `DATA_SCHEMA.md` and the tests named in §4.2.6 |

Recommended implementation order:

```text
1. truth metadata and gen O_lD
2. charge-ordering helper and its unit tests
3. reco lepton category and reco O_lD
4. electron/muon histogram filtering
5. schema documentation
6. one-chunk gen and reco validation
7. Fisher table and plots
```

### 4.2.1 Truth object identification

Relevant file:

```text
src/ilc_tth_cpv/objects.py
```

The existing function

```python
identify_semileptonic_truth(mc_list)
```

currently locates the Higgs, top, antitop, W bosons, W daughters, charged
lepton, and neutrino.

The file already defines the down-type analyser PDG sets:

```python
WPLUS_DOWNTYPE_ANALYZER = {-1, -3}  # dbar, sbar from W+
WMINUS_DOWNTYPE_ANALYZER = {1, 3}   # d, s from W-
```

Extend the existing returned truth structure rather than independently
re-reading the complete MCParticle tree inside `export_features.py`.

The truth object should provide enough information to determine:

```text
number of hadronic W decays
number of direct electron/muon W decays
hadronic W charge
lepton PDG and charge
lepton flavour
quark daughter
antiquark daughter
down-type analyser daughter
truth topology label
```

A possible function-level structure is:

```python
@dataclass
class SemileptonicTruth:
    # Existing objects
    higgs: object = None
    top: object = None
    antitop: object = None
    top_b: object = None
    antitop_bbar: object = None
    w_plus: object = None
    w_minus: object = None
    wjet_quark: object = None
    wjet_antiquark: object = None
    lepton: object = None
    neutrino: object = None

    # New topology and analyser information
    truth_topology: str = "invalid"
    hadronic_w_pdg: int | None = None
    lepton_pdg: int | None = None
    lepton_flavour: str | None = None
    down_type_daughter: object = None
```

The exact implementation may differ, but the topology and analyser information
must be returned from one common truth-navigation function.

### 4.2.2 Reconstructed W-pair orientation

Relevant file:

```text
src/ilc_tth_cpv/flavor.py
```

The existing functions are

```python
light_charge_scores(scores)
orient_w_pair(w1_scores, w2_scores)
```

`orient_w_pair()` returns:

```text
quark_slot
antiquark_slot
margin
status
```

for the two W jets selected by the kinematic fit.

The current reconstructed baseline first identifies

```text
wjet_quark
wjet_antiquark
```

and then uses the isolated-lepton charge to select the down-type candidate.

The mapping is:

```text
Q_l > 0:
    the leptonic side is t -> b l+ nu
    the hadronic side is anti-t -> anti-b W-
    W- -> D + anti-U
    wjet_quark is the down-type candidate j_D

Q_l < 0:
    the leptonic side is anti-t -> anti-b l- anti-nu
    the hadronic side is t -> b W+
    W+ -> U + anti-D
    wjet_antiquark is the down-type candidate j_anti-D
```

Add one reusable function for this charge-dependent analyser ordering.

For example:

```python
def semileptonic_down_type_order(
    lepton_charge: float,
) -> tuple[str, str] | None:
    """Return the top-side and antitop-side analyzer object names."""
    if lepton_charge > 0.0:
        return "lepton", "wjet_quark"

    if lepton_charge < 0.0:
        return "wjet_antiquark", "lepton"

    return None
```

This function does not decide which physical jets form the W pair. The
kinematic fit and `orient_w_pair()` have already done that.

It only converts

```text
lepton charge + q/qbar-oriented W pair
```

into

```text
top-side analyser + antitop-side analyser.
```

### 4.2.3 Feature export

Relevant file:

```text
scripts/export_features.py
```

At generator level, `export_gen()` already calls

```python
truth = identify_semileptonic_truth(mc_list)
```

and constructs existing observables through the local helper

```python
def dphi(a: str, b: str) -> float:
    ...
```

Add `O_lD` after the object angles have been filled.

At reconstruction level, `export_reco()` already reads:

```text
idx_W1
idx_W2
lepton_charge
OutputErrorFlowJets6 four-momenta
RefinedJets6 Weaver probabilities
```

and calls

```python
flavor.orient_w_pair(...)
```

to define

```text
wjet_quark
wjet_antiquark
```

After the object angles have been filled, construct the new observable through
the common ordering function:

```python
ordered_names = flavor.semileptonic_down_type_order(lepton_charge)

if ordered_names is None:
    record["O_lD"] = NAN
else:
    object_a, object_b = ordered_names
    record["O_lD"] = dphi(object_a, object_b)
```

Save enough information to diagnose the reconstructed choice:

```text
idx_W_down_candidate
down_candidate_source
hadronic_W_charge
lepton_charge
lepton_flavour
```

Freeze `hadronic_W_charge` as the electric charge $+1$ or $-1$, not the PDG
code $+24$ or $-24$. The reco mapping is:

```text
lepton_charge > 0:
    hadronic_W_charge = -1
    idx_W_down_candidate = idx_W_quark

lepton_charge < 0:
    hadronic_W_charge = +1
    idx_W_down_candidate = idx_W_antiquark
```

Use

```text
down_candidate_source = qqbar_orientation_plus_lepton_charge
```

for this initial baseline.

### 4.2.4 Reconstructed lepton flavour

The current helper

```python
first_isolated_lepton(evt)
```

returns the first object found in

```text
ISOElectrons
ISOMuons
```

but does not preserve the source collection.

Modify the interface so that it returns both the reconstructed object and its
category, for example:

```python
def first_isolated_lepton(evt):
    """Return the isolated lepton and its reconstruction category."""
    for collection_name, flavour in (
        ("ISOElectrons", "electron"),
        ("ISOMuons", "muon"),
    ):
        collection = get_collection(evt, collection_name)

        if collection is None:
            continue

        if collection.getNumberOfElements() > 0:
            return collection.getElementAt(0), flavour

    return None, None
```

The reconstructed `lepton_flavour` must come from the source collection.

Do not infer electron versus muon from the reconstructed four-momentum.

### 4.2.5 Data and sample locations

Do not hard-code data paths inside the feature exporter or plotting scripts.

The LR samples are registered in

```text
configs/samples.yaml
```

under the following keys:

```text
tthcpv_gen_elpr
tthcpv_reco_elpr
tth_sm_gen_elpr
tth_sm_reco_elpr
```

These entries provide the registered locations of:

```text
generator STDHEP files
signed-interference sidecars
reconstructed SLCIO files
SM cross-section normalisation
```

The analysis config selects the sample keys. `configs/samples.yaml` remains the
single source of truth for sample locations and normalisation.

### 4.2.6 Minimal convention tests

These tests protect the object mapping and angle convention. They are not
physics-performance tests.

Check that:

1. a positive-lepton event returns

   ```python
   delta_phi(lepton, wjet_quark)
   ```

2. a negative-lepton event returns

   ```python
   delta_phi(wjet_antiquark, lepton)
   ```

3. exchanging the input labels `W1` and `W2` does not change the final physical
   result after the W pair has been oriented;

4. missing, zero, or non-finite lepton charge produces an invalid `O_lD`
   rather than selecting a default ordering;

5. away from the $\pm\pi$ wrapping boundary, reversing the ordered analyser
   pair reverses the sign:

   ```math
   \Delta\phi(a,b)=-\Delta\phi(b,a).
   ```

For the W-slot exchange test, the important statement is not that the raw slot
indices remain unchanged. The important statement is that the same physical
quark, antiquark, and down-type candidate are recovered after the input slot
order is exchanged.

Put the charge-ordering and W-slot tests in

```text
tests/test_flavor.py
```

Keep the existing wrap and `delta_phi` checks in

```text
tests/test_angles.py
```

Add truth-topology and down-type-daughter tests in

```text
tests/test_objects.py
```

Add electron/muon table-filter tests in

```text
tests/test_angular_categories.py
```

These tests must show that the electron and muon rows are disjoint, their union
equals the `all` rows, and changing only `--output-tag` does not select a
category.

After implementation, run:

```bash
pytest -q \
  tests/test_flavor.py \
  tests/test_angles.py \
  tests/test_objects.py \
  tests/test_angular_categories.py
```

Then run one generator and one reco export and check that:

```text
O_W and O_lD have documented finite-event counts
electron count + muon count = all-category count
invalid lepton charge never receives a default O_lD ordering
the metadata records the H->bb, direct-e/mu and W->cb policies
```

---

## 4.3 Generator-to-reconstruction comparison

The primary comparison uses:

```text
gen:
    H->bb, strict direct-e/mu semileptonic events for which the observable is valid

reco:
    full accepted reconstruction baseline
```

Here, **full accepted reconstruction baseline** means every reconstructed event
that satisfies

```text
accepted == 1
fit_success == 1
```

in the canonical kinematic-fit ROOT file and has a finite value of the
observable being studied.

It does not mean a truth-matched subset.

For the headline generator-to-reconstruction comparison, do not intersect the
generator and reconstruction event IDs.

The following effects are intentionally included in the total information
loss:

```text
events lost before or during reconstruction
failed kinematic fits
wrong W-pair assignments
wrong W-jet orientations
invalid reconstructed objects
angular resolution and migration
```

A matched-event study may be made later as a diagnostic, but it must not
replace the total-retention result.

Use the same analysis conditions for $O_{jj}$ and $O_{\ell D}$:

```text
pure LR sample
strict direct-e/mu semileptonic channel
Higgs rest frame
boost-only lab-axes convention
36 angular bins
same luminosity scale
same generator and SM normalisation
same chunk scope
```

---

## 4.4 Fisher-information summary

Use the default absolute-yield Fisher information:

```math
I
=
\sum_i
\frac{\nu_{1,i}^2}{\nu_{0,i}}.
```

Here:

* $\nu_{0,i}$ is the SM yield in angular bin $i$;
* $\nu_{1,i}$ is the signed CPV-interference yield in angular bin $i$;
* $I$ is the Fisher information for the local CPV parameter.

The central generator-to-reconstruction retention is

```math
R_{\mathrm{reco}}
=
\frac{I_{\mathrm{reco}}}{I_{\mathrm{gen}}}.
```

It measures the total fraction of the observable information that survives the
current reconstruction chain.

### 4.4.1 Electron and muon categories

Electron and muon events are different reconstruction categories.

Keep them separate throughout the detector-level statistical calculation.

For lepton category

```math
c\in\{e,\mu\},
```

define

```math
\nu_{0,ci}
```

as the SM yield and

```math
\nu_{1,ci}
```

as the signed CPV-interference yield in category $c$ and angular bin $i$.

Calculate

```math
I_e
=
\sum_i
\frac{\nu_{1,ei}^2}{\nu_{0,ei}},
```

and

```math
I_\mu
=
\sum_i
\frac{\nu_{1,\mu i}^2}{\nu_{0,\mu i}}.
```

For statistically independent electron and muon categories, the combined
result is

```math
I_{e+\mu}
=
I_e+I_\mu.
```

This is equivalent to multiplying the two category likelihoods.

Do not merge electron and muon bin yields before evaluating the headline
Fisher information.

A yield-summed $e+\mu$ histogram may be shown as an optional visualisation,
but it must not replace the separate-category likelihood combination.

### 4.4.2 Required LR result table

Produce the following table:

| Observable            | Lepton category     | Gen population            | Reco population          | Frame        | $N_{\rm gen}$ | $N_{\rm reco}$ | $I_{\rm gen}$ | $I_{\rm reco}$ | $I_{\rm reco}/I_{\rm gen}$ |
| --------------------- | ------------------- | ------------------------- | ------------------------ | ------------ | ------------: | -------------: | ------------: | -------------: | -------------------------: |
| $O_{jj}$ (`O_W`)      | electron            | $H\to b\bar b$, strict semileptonic $e$   | full accepted reco $e$   | `higgs_rest` |               |                |               |                |                            |
| $O_{jj}$ (`O_W`)      | muon                | $H\to b\bar b$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` |               |                |               |                |                            |
| $O_{jj}$ (`O_W`)      | combined likelihood | $e+\mu$ categories        | $e+\mu$ categories       | `higgs_rest` |               |                |   $I_e+I_\mu$ |    $I_e+I_\mu$ |                            |
| $O_{\ell D}$ (`O_lD`) | electron            | $H\to b\bar b$, strict semileptonic $e$   | full accepted reco $e$   | `higgs_rest` |               |                |               |                |                            |
| $O_{\ell D}$ (`O_lD`) | muon                | $H\to b\bar b$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` |               |                |               |                |                            |
| $O_{\ell D}$ (`O_lD`) | combined likelihood | $e+\mu$ categories        | $e+\mu$ categories       | `higgs_rest` |               |                |   $I_e+I_\mu$ |    $I_e+I_\mu$ |                            |

For the combined rows:

```math
I_{\mathrm{gen}}^{e+\mu}
=
I_{\mathrm{gen}}^e
+
I_{\mathrm{gen}}^\mu,
```

```math
I_{\mathrm{reco}}^{e+\mu}
=
I_{\mathrm{reco}}^e
+
I_{\mathrm{reco}}^\mu,
```

and therefore

```math
R_{\mathrm{reco}}^{e+\mu}
=
\frac{
I_{\mathrm{reco}}^e+I_{\mathrm{reco}}^\mu
}{
I_{\mathrm{gen}}^e+I_{\mathrm{gen}}^\mu
}.
```

The event counts in the combined rows may be reported as

```math
N^{e+\mu}=N^e+N^\mu,
```

but the Fisher information must be combined from the independent category
results.

### 4.4.3 Optional frame study

The default frame in this chapter is

```text
higgs_rest
```

using the current boost-only `lab_axes` convention.

With additional time, repeat the comparison in

```text
lab
ttbar_rest
```

by copying the config, changing

```yaml
observable:
  default_frame: lab
```

or

```yaml
observable:
  default_frame: ttbar_rest
```

and using a separate output directory.

For example:

```text
outputs/angular_lr_lab/
outputs/angular_lr_ttbar_rest/
```

The current exporter measures angles against the fixed laboratory axes after
the Lorentz boost.

Changing the YAML text

```yaml
basis: production_plane
```

does not by itself change the calculation.

A production-plane coordinate system requires an explicit implementation using
the relevant functions in

```text
src/ilc_tth_cpv/frames.py
```

and should be treated as a separate optional study.

---

## 4.5 Plots and data interfaces

Use the same terminology throughout this chapter:

```text
SM template
signed CPV-interference template
```

Do not switch between several different names for the same template.

### 4.5.1 Minimum required plots

There are four required comparison types:

1. $O_{jj}$: signed CPV-interference template, generator versus
   reconstruction level;

2. $O_{\ell D}$: signed CPV-interference template, generator versus
   reconstruction level;

3. $O_{jj}$: SM template, generator versus reconstruction level;

4. $O_{\ell D}$: SM template, generator versus reconstruction level.

For the primary statistical result, electron and muon remain separate
categories.

Each of the four comparison types must therefore contain separate electron and
muon panels. This means either four two-panel figures or eight single-panel
figures. A single inclusive curve is not a substitute for these category
plots.

A combined $e+\mu$ curve may be shown for visual comparison, but the combined
Fisher result must still use

```math
I_{e+\mu}=I_e+I_\mu.
```

### 4.5.2 Event-level feature tables

The event-level inputs are under

```text
outputs/angular_lr/features/
```

Expected files include:

```text
features_gen_higgs_rest_chunk0.csv
features_sm_gen_higgs_rest_chunk0.csv
features_reco_higgs_rest_chunk0.csv
features_sm_reco_higgs_rest_chunk0.csv
```

Each table should contain both observable columns:

```text
O_W
O_lD
```

and the category and diagnostic columns:

```text
lepton_charge
lepton_flavour
hadronic_W_charge
w_orientation_status
w_orientation_margin
idx_W_down_candidate
down_candidate_source
```

The exact truth-only and reco-only diagnostic columns may differ, but all
columns must be documented in

```text
docs/DATA_SCHEMA.md
```

### 4.5.3 Angular-template interface

The histogram script is

```text
scripts/build_angular_observable.py
```

It reads one observable column from a feature CSV through

```bash
--observable <column-name>
```

The `--observable` interface already exists. At the start of Chapter 4, the
script does **not** yet filter electron and muon events. Add:

```text
--lepton-flavour all
--lepton-flavour electron
--lepton-flavour muon
```

with `all` as the default. Apply this filter to the `lepton_flavour` feature
column after the existing train/validation/test split. Record the selected
category and its event count in the output metadata.

The intended implementation is equivalent to:

```python
parser.add_argument(
    "--lepton-flavour",
    choices=("all", "electron", "muon"),
    default="all",
)

# Apply after the existing split filter.
if args.lepton_flavour != "all":
    if any("lepton_flavour" not in row for row in rows):
        raise SystemExit("Feature table has no lepton_flavour column")
    rows = [
        row for row in rows
        if row["lepton_flavour"] == args.lepton_flavour
    ]
```

`--output-tag` changes only the filename. It does not select events. Never
produce an `*_e_*` or `*_mu_*` file by changing only `--output-tag`.

The script writes the result under

```text
outputs/angular_lr/angular/<observable>/
```

For example:

```text
outputs/angular_lr/angular/O_W/
outputs/angular_lr/angular/O_lD/
```

Inclusive bin files may be kept as smoke-test products:

```text
O_W_all_gen_bins.csv
O_W_all_reco_bins.csv
O_W_all_sm_gen_bins.csv
O_W_all_sm_reco_bins.csv
```

and

```text
O_lD_all_gen_bins.csv
O_lD_all_reco_bins.csv
O_lD_all_sm_gen_bins.csv
O_lD_all_sm_reco_bins.csv
```

Write separate electron and muon templates with explicit output tags. Use the
following frozen convention:

```text
O_W_all_gen_e_bins.csv
O_W_all_gen_mu_bins.csv
O_W_all_reco_e_bins.csv
O_W_all_reco_mu_bins.csv
O_W_all_sm_gen_e_bins.csv
O_W_all_sm_gen_mu_bins.csv
O_W_all_sm_reco_e_bins.csv
O_W_all_sm_reco_mu_bins.csv
```

and the corresponding eight files for `O_lD`.

For example, the two `O_lD` generator interference templates are:

```bash
python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_gen_higgs_rest_chunk0.csv \
  --observable O_lD \
  --lepton-flavour electron \
  --split all \
  --output-tag gen_e

python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_gen_higgs_rest_chunk0.csv \
  --observable O_lD \
  --lepton-flavour muon \
  --split all \
  --output-tag gen_mu
```

Repeat this pair for `O_W`, for reco, and for SM. Use `weight_sm` for the SM
commands. The output metadata, not only the filename, must state
`lepton_flavour: electron` or `lepton_flavour: muon`.

### 4.5.4 Fisher interface

The Fisher driver is

```text
scripts/evaluate_fisher.py
```

It requires:

```text
--template
```

for the signed CPV-interference template and

```text
--sm-template
```

for the corresponding SM denominator.

For example:

```bash
python3 scripts/evaluate_fisher.py \
  --template outputs/angular_lr/angular/O_lD/O_lD_all_reco_e_bins.csv \
  --sm-template outputs/angular_lr/angular/O_lD/O_lD_all_sm_reco_e_bins.csv \
  --luminosity-scale 8000
```

For each observable, run the Fisher calculation separately for:

```text
electron gen
electron reco
muon gen
muon reco
```

Then calculate the combined-category Fisher by adding the electron and muon
results.

The minimum headline result therefore contains eight Fisher JSON files:

```text
2 observables x 2 levels x 2 lepton categories
```

The machine-readable Fisher result is stored in

```text
*.fisher.json
```

Use these JSON files when building the Chapter 4 summary table.

Do not copy Fisher values manually from terminal output when a JSON result is
available.

### 4.5.5 Additional plots

You are welcome to plot any further comparison that helps explain the
observation. The scripts should normally read the feature CSVs or binned angular
CSVs. They should not reopen the original STDHEP or SLCIO files unless the required
diagnostic quantity was not exported.

Necessary for us to deliver to others:

* reco/gen SM/CPV vs each other, muon/electron separately:
    * For the same observable, for curves on the same observable axis or comparing two by two(depends on how you feel about the layout);
    * $O_{jj}$ and $O_{\ell D}$ can also be compared on the same plot. 
* Supervisor: Compare the ratio of |w| and signed-weighted histogram between gen/reco, evaluate how many w-daughter is mis-ordered.

Some examples you might try for your own interest:

* per-bin Fisher contribution

  ```math
  I_i
  =
  \frac{\nu_{1,i}^2}{\nu_{0,i}};
  ```

* cumulative Fisher information as a function of the angular-bin ordering;

* electron and muon category comparison;

* W-orientation-status comparison;

* high- and low-orientation-margin categories;

* gen/reco angular migration for a matched diagnostic subset;

* correct and incorrect W-assignment categories on truth-labelled diagnostic
  events;

* correct and incorrect down-type-candidate categories on truth-labelled
  diagnostic events.



---

## 4.6 Think about the reconstructed down-type jet

No additional reconstruction optimisation is compulsory in the first Chapter
4 result. **Any further improvements of the angular observable beyond the student's 
limited time will be done by the supervisor.**

After producing the baseline comparison, explain which reconstruction stages
can affect the final down-type analyser:

* selection of the correct two W jets;

* jet four-momentum and angular resolution;

* quark-versus-antiquark orientation;

* up-type-versus-down-type identification;

* isolated-lepton charge and flavour reconstruction;

* low-confidence or internally inconsistent pair decisions.

The current baseline determines the down-type candidate through

```text
existing q/qbar orientation + isolated-lepton charge.
```

This provides a well-defined first result, but it is not guaranteed to be the
optimal estimator.

In particular, the signed flavour information is much weaker for several
$u,d,s$ and antiquark categories than for the relatively favourable charm
categories.

Several optional studies can be done from following ideas and further idea can be accessed from the /docs/W-DAUGHTER-ODERING.md

### Option A — Based on the HIGH CONFIDENCE SUBSET

**Better-identified flavour subset**

Test whether a restricted, better-identified event subset retains more
reconstruction-level Fisher information.

A possible example is a charm-enriched subset.

For a reconstructed $W^+$,

```text
a high-confidence c candidate identifies the other W jet as anti-D.
```

For a reconstructed $W^-$,

```text
a high-confidence anti-c candidate identifies the other W jet as D.
```

Compare at least:

```text
retained event fraction
down-type-candidate purity
I_reco
```

Do not judge the method from flavour accuracy alone.

A tighter category may have better purity but lower total Fisher information
because many events have been removed.

**Confidence Categories**

Do not immediately discard every ambiguous event.

Divide the events into a small number of non-overlapping orientation-confidence
categories, for example:

```text
high confidence
low confidence
```

Calculate the Fisher information in each category and combine the independent
category results.

Compare this with:

```text
one inclusive category
one hard confidence cut
```

A hard cut is justified only if it improves the final combined Fisher
information, not only the orientation accuracy.

### Option B — direct up-type/down-type pair assignment

It turns out the up/down-type quark identification accuracy of the ParT At ILC is higher than the quark/antiquark. (Check out the flavor_accuracy_confusion_matrix.png) So, instead of first reducing all light flavours to a single quark-versus-antiquark
score, define

```math
P_D(j)
=
P_d(j)+P_s(j),
```

```math
P_U(j)
=
P_u(j)+P_c(j),
```

```math
P_{\bar D}(j)
=
P_{\bar d}(j)+P_{\bar s}(j),
```

```math
P_{\bar U}(j)
=
P_{\bar u}(j)+P_{\bar c}(j).
```

For a reconstructed $W^-$, compare the two allowed assignments:

```math
L_1^{W^-}
=
P_D(j_1)P_{\bar U}(j_2),
```

```math
L_2^{W^-}
=
P_D(j_2)P_{\bar U}(j_1).
```

If

```math
L_1^{W^-}>L_2^{W^-},
```

select $j_1$ as the down-type candidate.

Otherwise select $j_2$.

For a reconstructed $W^+$, compare

```math
L_1^{W^+}
=
P_U(j_1)P_{\bar D}(j_2),
```

```math
L_2^{W^+}
=
P_U(j_2)P_{\bar D}(j_1).
```

This pair-level test uses the complete allowed W-decay structure:

```text
W- -> D + anti-U
W+ -> U + anti-D
```

rather than treating the two jets as independent charge classifications.


---

## 4.7 Deliverable

The Chapter 4 deliverable is:

1. a new `O_lD` observable column at generator and reconstruction level;

2. a strict common-topology comparison of `O_W` and `O_lD`;

3. separately validated electron and muon reconstruction categories;

4. the LR Fisher-information summary table;

5. the four required generator/reconstruction comparison types, each with
   separate electron and muon panels;

6. a short explanation of the main reconstruction processes that can affect
   the down-type analyser;

7. any optional plot or reconstruction test that helped explain the result.

The written conclusion should answer:

```text
Which observable is stronger at generator level?

Which observable retains more information at reconstruction level?

Where does the largest information loss occur?

Does using the charged lepton as a stable analyser make O_lD more robust
than O_jj?

Is the current q/qbar-based down-type assignment sufficient for the first
baseline?

Which optional improvement would be most motivated by the observed
diagnostics?
```

---
## 4.8 Other optional angular observable

Check out after we complete chapter 5, if there's time and any neccessity.

**Start only after the $O_W$ framework is stable and the above top-side
checkpoint has passed.** Reuse the frozen default frame and model
configuration — the point is a *quick, uniform* survey, not three new projects.

* $O_b=\Delta\phi(b_t,b_{\bar{t}})$

Ordering from signed ParT $b/\bar{b}$ scores + top-side assignment + lepton-charge consistency.

* $O_{\ell\nu}$

The generator definition is the charge-dependent CP ordering in §2.3. Reco
uses the selected fit's persisted `nu_fit_{E,px,py,pz}` and the isolated-lepton
charge. Do not silently substitute a different missing-momentum estimator.

* $O_{\mathrm{top}}$

The definition is $\Delta\phi(t,\bar t)$. At reco level, use the isolated
lepton charge to identify which reconstructed side is top and which is
antitop, and include the fitted neutrino in the leptonic-side composite.

**Interesting comparison (identical recipe for each) and Deliverable**

Gen/reco angle; one fixed BDT; Fisher at gen and reco; retention $R_{\mathrm{reco}}$; and the **correlation with $s_W$** — a strong branch that is highly correlated with $s_W$ adds little in fusion; a moderately strong but complementary one may add more.

A compact table identifying the strongest and the most *complementary* secondary observable → this selects $X$ for Chapter 7.


---


# Chapter 5 — ML-learned CP observable in the $O_{\ell D}$ branch

**Status: in development.**

After Chapter 4 establishing the better reconstructed angular observable $O_{\ell D}$ 
using the charged lepton and the selected down-type jet, the following parts have been 
frozen:

```text
strict semileptonic truth topology
O_jj and O_lD definitions
reconstructed analyser mapping
electron and muon category handling
SM and signed CPV-interference templates
generator-to-reconstruction Fisher comparison
```

Chapter 5 replaces this one-dimensional angular compression with a learned
observable constructed from reconstruction-level inputs **IN HIGGS REST FRAME**.

The supervised ML target is

$$
y=\mathrm{sign}(w_{\mathrm{int}})\in\{-1,+1\}.
$$

with $|w_{\mathrm{int}}|$ used as the non-negative training weight. The final
learned CP observable is

$$
O_{\mathrm{ML}}(x)=P(+\mid x)-P(-\mid x),
$$

which is evaluated on the CPV-interference and SM samples and compared through
Fisher information,

$$
I=\sum_i\frac{\nu_{1,i}^2}{\nu_{0,i}}.
$$

The purpose of this chapter is to determine how much CP information is retained by 
different reconstruction-level feature representations and hopefully to maximize it. 
Loss, AUC, and overtraining checks are model diagnostics, while Fisher information 
is the final physics metric.

We will start from a naive baseline with the least lepton, selected-down-type jets
kinematics by XGBoost(BDT) with further add-ons with auxiliary variables, permutation 
and likelihood-weighted, CatBoost, more jets and neutrino involvement...

Sections 5.1–5.4 form the two-week main study; the extensions in Section 5.5
are performed as time permits.

## 5.1 Data preparation

We will use one validated superset feature table for each physical sample and select
the inputs of each model through named YAML feature sets. Auxiliary inputs are
restricted to two groups: W-daughter assignment or ordering quantities,
including the kinematic-fit final-selection score, and reconstructed
invariant-mass combinations.

Prepare and validate the complete LR CPV-interference and SM all-chunk datasets
in the Higgs rest frame, correct the reconstructed top and antitop charge
ordering and down-type-object mapping, export the event weights, interference
sign, lepton, fitted neutrino, both W daughters, top-decay $b/\bar b$ objects,
assignment information, final-selection score, and invariant-mass variables,
and provide the HTCondor export and chunk-normalisation workflow.

**Update the export_features.py and test it with one chunk**

1. Check the reconstructed top/anti-top slot in export_features.py and fix it
2. Delete :
    * O_b, O_top, O_lnu (They just output from old template, but didn't be ordered carefully, and not in using)
    * y45,y56,y67(used in MVA for S/B)
    * Other information for kinfit, not useful,such as: top_n,n_constraint,n_unmeasured...But you can keep them if you don't want to work more.
3. Check what is already in the output "row" **at reconstruction level** in the export_feature, what haven't added
   based on the following list:
   * Event Infomration: event_id, chunk,split, weight(signed,abs,training),cp_sign(label)
   * Lepton information:lepton_px/py/pz/E/p_t/theta/phi/mass
   * W_daughter information:W1_E/theta/phi/mass,W2_E/theta/phi/mass(Existing name as wjet_quark/antiquark is fine),
     down_type_slot（1 means W1 is down-type, 2 means W2),
     down_assignment_likelihood(L12 and L21),margin
   * Neutrino information: nu_fit_px/py/pz/E/pt/theta/phi
   * b/bbar from top: b_had_E/theta/phi/mass, b_lep_E/theta/phi/mass
   * Auxiliary variables:
       * Invariant mass: m_W_had,m_top_had,m_top_lep,m_ttbar,m_H (some in the kinfit root（postfit）, m_ttbar need to calculate by the two tops)
         Hint: The invariant mass function is in frames.py, you can calculate it by
         ```
         ttbar_p4 = frames.add_p4(top_p4, antitop_p4)
          m_ttbar = frames.invariant_mass(ttbar_p4)
         ```
      * Flavor tagging/assginment/KinFit score:fitchi2,final_selection_score,final_fit_score, final flavor score
   * Hepful for debugging:idx_W1,idx_W2,idx_W_quark,idx_W_antiquark
  
    If haven't output, check what is included in the Kinfit Root first, then if it in the reco slcio collection, or calculate them by yourself.
   Note and record which one comes from the "post-fit" in KinFit, and which one comes from the "prefit" or Reconstruction slcio directly. Keep the current data source, prior to use post fit one, except strong conflict with previous convention. Make sure any edit will not affect your current angular pipeline.
   
4. Try with the current chunk 0 data, make sure in the output csv, all features above included. Look at the csv, confirm: all number finite, mass are positive... 
   

**Link all chunks root file with the corresponding  resolve_root_path()**

1. Run /scripts/link_kinfit_inputs.sh and check the eLpR of the tth-sm, tth-cpv in the /data/kinfit/physsim
2. Modify the kinfit_root_path() in export_feature.py by
   ```
   def kinfit_root_path(cfg: dict, sample_key: str, chunk_id: str) -> Path:
    """Resolve the canonical kinfit ROOT file.

    Prefer the repo-local shared-data link created by
    scripts/link_kinfit_inputs.sh. Fall back to the historical analysis-output
    directory so locally produced kinfit files remain usable.
    """
    filename = f"kinfit_{sample_key}_chunk{chunk_id}.root"

    family = cfg.get("kinfit", {}).get("input_family", "physsim")

    shared_path = (
        repo_root()
        / "data"
        / "kinfit"
        / family
        / filename
    )

    legacy_path = (
        repo_root()
        / cfg["outputs"]["base_dir"]
        / "kinfit"
        / filename
    )

    if shared_path.exists():
        return shared_path

    if legacy_path.exists():
        return legacy_path

    # Return the preferred path so the downstream error message tells the
    # student exactly where the missing link should have been created.
    return shared_path
   ```
   Check if the current root path match those under /data
   
**Create the Supersets with the training weight**

1. Copy and make a new config file called "analysis_ml_superdataset_lr.yaml", check the sample, frame, split, weights,outputs.base_dir:outputs/ml_superdataset.
2. cd to the condor/export_feature, read and understand what each file work for, and run a smoke test:
   ```
   cd condor/export_feature
   python3 make_arguments.py --config ../../configs/<new_ml_yaml>.yaml --chunks 0
   condor_submit submit_export_features.sub
   ```
3. Run the whole condorworkflow to get all ML dataset for the tth-cpv and tth-sm eLpR.
   Be aware of how many ill events(If any variables of some events get none output).
4. Write a new script /scripts/merge_feature_chunks.py : Merge the 80 chunk-level CSV files produced by `export_features.py` into a single superdataset, without recomputing selections, splits, weights, or features; check that all chunks are present, the schemas are identical, and there are no duplicated events; keep `lepton_flavor` so electron and muon channels can be selected later at training time; report the total event count and the electron/muon train/validation/test and ± label counts; and write the merged dataset plus simple metadata under `outputs/ml_superdataset/features/`..

## 5.2 BDT baseline comparison

**First Model "lD_minimal_xgb": lepton+Down-type jet kinematics with XGBoost**

Input the features only from the reconstructed lepton and selected down-type jet kinematics.
{E_l,pT_l,theta_l,phi_l, E_D,theta_D,phi_D,mass_D}

1. Modify the ml superset yaml, delete the angular observable information, holds the ml-related one:
   * Change the "analysis": name, family, such as ml_superdataset_lr, O_ML
   * Change the "observable": defination:"O_ML = P(+) - P(-)", n_bins:20, range:[-1.0,1.0]
   * Change the "features" as

      ```
      features:
        default_set: lD
      
        sets:
          lD:
            objects:
              lepton:
                - E
                - pt
                - theta
                - phi
      
              down_type_daughter:
                - E
                - theta
                - phi
                - mass
      
            auxiliary: []
      
          lD_auxiliary:
            objects:
              lepton:
                - E
                - pt
                - theta
                - phi
      
              down_type_daughter:
                - E
                - theta
                - phi
                - mass
      
            auxiliary:
              - w_assignment_likelihood_selected
              - final_selection_score
              - m_W_had
              - m_top_had
              - m_top_lep
              - m_H
              - m_ttbar
      ```

    * Add a training section
    
        ```
          training:
            lepton_flavors:
              - electron
              - muon
      
            label_column: label
            training_weight: weight_training
            balance_classes: true
        ```
  * Delete ` score: "P(+) - P(-)" ` in "model"
    
2. Modify the /scripts/train_cpv_model.py, hints are included as comments inside.
  * Resolve down-type jet by idx_W_down_candidate
  * Support the axiliary virtual feature "w_assignment_likelihood_selected"
  * Train electron and muon separately and output as two model : model/lD/electron, model/lD/muon

3. Look if the loss function converges, check the precision (hopefully higher than 0.5) Play around with the model parameters.
   * Output the model evaluation quantities.
   * Do the next step after get the reasonable precision.
   * Update 170826: The model need information to **learn the order of the two objects**. We have two solution:
     1. Add lepton charge to original(v1) dataset
     2. Change the lepton/quark to "top, anti-top fermions" as v2 dataset
4. Build the observable by the “scripts/build_ml_observable.py" (Same to the angular, first ,**split the lepton channel**).
   * Make sure the physics weight for the whole dataset is same logic to the one you write for the angular observable. **Note the training weight may
     not equal to the physics weight**.
   * Build the similiar pipeline as the angular observable from read models to the evaluate fisher
   * **Note** Only run the next pipeline when the test AUC is larger than the 0.5
5. Compare with the **CatBoost** (Check if the code in train_cpv_model.py for catboost works)
   * Raw v1 ( without lepton charge): It shouldn't work but for a complete comparison.
   * v1+lepton charge
   * v2


**Second Model: Adding  auxiliary variables**

See the lD_auxiliary above. Try only the first two first. Then all auxiliary variables.
If **The Taining Loss** is not converge, may need to wait me to make more data.

**Physics motivation: This section motivated by the fact that we have already known the angular O_lD works both gen and reco level , while O_jj works 
almost only gen. So the ML must can learn physics from the reco O_lD when we choose the down-type jet by ourself, but can it combine more information and 
exploit them for CPV, or just treat them as noise?**

## 5.3 W-daughter representation and assignment study
**Physics motivation: See whether the model can learn the order of the w-daughter rather than we choose one by ourself and can it save the O_jj from reco level?**

Compare the next two options on W
1. **Priority for 9.1** Add the kinematics of the second W daughter jet into features ( First with higher likelihood, second with lower, no other auxiliary )
   * Better using v1+lepton charge with Catboost, don't need to modify the export features.
2. Optional: Different jet as down-type input once （ One events, two rows)
   * With CatBoost v2, but each jet of the hadronic decay will be chosen as top/anti-side-top fermion filling the row once, weighted by the likelihood

## 5.4 Adding the fitted neutrino
**Physics motivation: See if the potential different sign of the delta_lnu, delta_jj, delta_lD will confuse the model?**
(I will provide some statistic comparison of the different angular observables)
**Priority for 9.1**
Add the fitted-neutrino kinematics to the selected $O_{\ell D}$-branch feature
set and test whether the learned observable retains more Fisher information
than the lepton-plus-down-type-jet baseline.

## 5.5 Optional studies

As time permits, repeat the selected setup with the following options

* **Priority for 9.1** Enlarge the input with the complete reconstructed W products and top-decay $b/\bar b$ objects to test whether additional physical information helps or confuses the model.
* Study an SM-inclusive three-class model
* A neural network and revisit the W-daughter permutation problem, train using the two W jets alone to test whether NN can avoid or resolve the jet-ordering problem

## Ideal Case for 9.1

**Project summary**: Study the sensitivity of the CPV observables induced by the t-tbar spin correlation on reconstruction level in e-e+>tth process at 550GeV linear collider. Compare the Fisher from cpv/sm without other background, assuming the new physics coefficient is 1.

**Plots**: 
  * Angular observable distribution: O_jj, O_lD, reco vs gen, sm vs cpv at Higgs rest frame with 10 chunks
  * Bar chart of the Fisher at different frame, showing the challenge of reconstruct the Higgs rest frame though it owns huge theoretical advantages.
  * ML observable training information: Compare the ROC,importance of the v1+lepton charge/v2 XGBoost,CatBoost in 5.2
  * Plain ML observable distribution(with only l,D feature input): sm vs cpv, ML vs angular O_lD
  * Best ML observable distribution after 5.5 marked by **priority for 9.1** 
  * Bar chart of the Fisher of all observables we studied.

**Background introduction and equations**: Don't assume our colleagues has enough QFT knowledge...but they also don't like too much equations and numbers, only necessary. The main line of the story maybe how to reconstruct the identity of the "down-type" quark and the order of the fermions. Be clear what we present come from and what the goal/physics question we are trying to explore for each plots. We may have more discussion on this part later.

**After 9.1** Hope the last week still working week, so we can do the next chapter 6 and 8. Hope they just need you to implement the current scripts. Then it will be enough for your poster. 

---

# Chapter 6 — Event-selection MVA and backgrounds

**Integrate as soon as the supervisor delivers a frozen MVA.** Chapters 3–5 must stay runnable without it.

## 6.1 Interface

Per event: `event_id`, `mva_score`, `pass_nominal_mva`, plus score convention, threshold, model version, provenance. Join on event ID ([../scripts/join_selection_mva.py](../scripts/join_selection_mva.py); spec: [MVA_INTERFACE.md](MVA_INTERFACE.md)).

## 6.2 Cost of selection (signal only)

```math
R_{\mathrm{selection}}
=
\frac{I_{\mathrm{selected}}^{\mathrm{signal}}}{I_{\mathrm{reco}}^{\mathrm{signal}}} .
```

## 6.3 Signal plus background

Rebuild templates with $\nu_{0,i}=s_{0,i}+b_i$, $\nu_{1,i}=s_{1,i}$ (§2.10); compare the angle and the ML observable after the nominal MVA cut. Background inputs: [BACKGROUND_INTERFACE.md](BACKGROUND_INTERFACE.md).

## 6.4 Two-dimensional diagnostic (where statistics permit)

Compare three strategies:

1. loose/common pool + 2D observable $(q_{SB}, O_{\mathrm{CP}})$;
2. nominal MVA cut + 1D $O_{\mathrm{CP}}$ (the baseline);
3. nominal MVA cut + 2D $(q_{SB}, O_{\mathrm{CP}})$.

The nominal cut remains the event-selection baseline; the loose-pool comparison *measures* how much CP information the hard cut throws away (§2.9).

## 6.5 Deliverable

First background-aware comparison + a quantitative measurement of selection-induced CP-information loss.

---

# Chapter 7 — Fusion of $O_W$ with one secondary observable

**Start after $O_W$ and at least one secondary branch are stable.** Pick one $X\in\{b,\ \ell\nu,\ \mathrm{top}\}$ from the Chapter 5 table.

Four strategies (concepts in §2.7):

1. **Early fusion:** one model on the union of features, $M_{\mathrm{early}}(F_W,F_X)$.
2. **Late fusion:** train per-branch models $s_W = M_W(F_W)$, $s_X=M_X(F_X)$, then a small combiner $s_{\mathrm{late}}=M_{\mathrm{fusion}}(s_W,s_X)$.
3. **Multidimensional likelihood:** use $(s_W,s_X)$ directly as a 2D binned observable — no extra training.

Metrics:

```math
I(s_W),\quad I(s_X),\quad I(M_{\mathrm{early}}),\quad I(s_{\mathrm{late}}),\quad I(s_W,s_X),
```
```math
\Delta I_{X|W}=I(W+X)-I(W)
```

This is the conditional information gain from adding branch $X$.

**Deliverable:** a justified answer to "one all-feature model, separated branches, or a multidimensional likelihood?" — including "they are equivalent", if that is what the numbers say.

---

# Chapter 8 — Physical LCF polarisation combination

**Do this only after observable definitions and models are frozen** — mixing polarisations with moving definitions makes results uninterpretable. All formulas: §2.13.

1. **Pure-helicity study first:** compare LR vs RL rates, shapes, interference, Fisher.
2. **Weighted physical training:** per run category $r$, combine LR/RL events with weights $a_r, b_r$. Do **not** use $a_r,b_r$ as features, do **not** multiply final scores by them, do **not** average independently trained scores without a calibrated common coordinate.
3. **Templates and likelihood:** use one template category per run configuration. Its luminosity and the combined likelihood are

```math
\mathcal{L}_r
=
f_r^{\mathrm{run}}\times 8~\mathrm{ab}^{-1},
\qquad
\mathcal{L}_{\mathrm{total}}(c)
=
\prod_r \mathcal{L}_r(c) .
```

Finally, run the polarisation **closure test** (Appendix B) before quoting anything.

**Deliverable:** pure LR/RL, four run-category, and combined LCF sensitivities, with a rate-vs-shape interpretation where possible.

---

# Chapter 9 — Minimal BSM interpretation

**Only after the final likelihood is stable.** Apply the supervisor-approved
$C^I_{t\varphi}/\Lambda^2$ conversion of §2.14, record conventions/sign/units
and the local nature of the conversion, and do not present it as a
multi-operator SMEFT fit.

---

# Chapter 10 — Optional extensions (at most one, only after required results are frozen)

## Option 1 — Hadronic tau category
Add semitau events as a separate statistical category, using a *frozen* tau tagger; keep the existing observables; **no tau polarimeter**. Prerequisites from the tagger team: frozen model/interface, efficiency and fake rates, constituent links, usable charge convention. Deliverable: sensitivity change from adding the category.

## Option 2 — W-pairing optimisation
The current baseline has two distinct steps: kinfit selects the W pair, then
the exporter orients only those two jets. Opposite q/qbar preferences are used
directly. For two q-like jets, larger $P(q)$ is q; for two qbar-like jets,
larger $P(\bar q)$ is qbar. It records opposite, both-q-like, both-qbar-like,
or exact-tie status plus the decision margin. b scores do not enter this
orientation.

First measure the ceiling with a truth-matched oracle assignment:
```math
\Delta I_{\mathrm{pairing}}=I_{\mathrm{oracle}}-I_{\mathrm{current}} .
```
Proceed only if the gap is relevant. Possible improvements include calibrating
the signed light-flavour probabilities; replacing the hard two-jet orientation
by an orientation likelihood; handling low-margin or same-sign pairs
explicitly; jointly optimising pair choice and orientation over top-K kinfit
candidates; and soft/posterior-weighted observables. Truth labels are a
diagnostic, never an analysis input. Deliverable: increased **CP information**,
not just higher pairing or orientation accuracy.

## Option 3 — Quadratic EFT term
$\nu_i(c)=\nu_{0,i}+c\,\nu_{1,i}+c^2\nu_{2,i}$. Justified if linear templates go negative, the interval is non-local, or a finite-coupling scan needs it. Deliverable: linear vs quadratic intervals, with EFT-truncation caveats.

## Option 4 — Wider fusion
Extend to e.g. $W+b+\mathrm{top}$ or $W+b+\ell\nu+\mathrm{top}$, only if the two-branch result is stable and additional branches show non-negligible conditional information $\Delta I$. Deliverable: an information-gain matrix per added branch.

## Option 5 — Neutrino correction

The baseline is now the kinematic fit's persisted massless `nuAfter`
four-vector; no new processor is needed to calculate reco $O_{\ell\nu}$.
Optionally compare it with raw missing momentum and a separately documented
neutrino-correction method. Keep this distinct from the existing SLD neutrino
handling inside heavy-flavour jets. Validate energy/momentum residuals, angular
bias and resolution, failure rate, $O_{\ell\nu}$ stability, and Fisher
information. Adopt a correction only if it improves the physics result without
introducing a charge- or sign-dependent bias.

---

# Chapter 11 — Deliverables and success criteria

## 11.1 Required scientific outputs

1. Validated $O_W$ angular baseline at gen/reco level.
2. Corresponding BDT/CatBoost and MLP baselines.
3. Controlled frame study for $O_W$.
4. Gen→reco information-retention result.
5. Fast $O_b, O_{\ell\nu}, O_{\mathrm{top}}$ baselines.
6. Event-selection MVA integration.
7. First signal-plus-background result (when inputs available).
8. Fusion of $O_W$ with one secondary observable.
9. Physical LCF polarisation combination.
10. Minimal generator→SMEFT conversion.

## 11.2 Required technical outputs

Documented schema; reproducible configs; deterministic splits; model metadata and seeds; validation plots; tested Fisher and likelihood code; polarisation closure test; runnable README; short report; internal presentation.

## 11.3 The one summary figure

Aim for a single figure/table comparing

```math
I_{\mathrm{gen}},\qquad
I_{\mathrm{reco}},\qquad
I_{\mathrm{selected}},\qquad
I_{\mathrm{sig+bg}}
```

for three observables: $O_W$ (angle), $M_W$ (ML), and one fused observable. This one plot answers questions 1, 2, and 4 of §1.3 at a glance.

## 11.4 Before you quote any number ("quote-readiness")

- [ ] no training/test overlap;
- [ ] stable event and weight bookkeeping;
- [ ] stable binning;
- [ ] no negative expected yields in the quoted scan range;
- [ ] adequate MC statistics in the high-information bins;
- [ ] documented gen/reco conventions;
- [ ] polarisation weights checked (Appendix B);
- [ ] background assumptions stated;
- [ ] result stable under model-seed variation.

## 11.5 Non-goals — you are explicitly NOT required to

- finish the complete $t\bar{t} H$ analysis independently;
- validate the generator;
- produce all missing MC samples;
- derive a full optimal observable;
- derive SMEFT matching from first principles;
- rewrite the ParT tagger;
- develop a full neutrino-correction Marlin processor unless Option 5 is
  explicitly chosen;
- complete any optional extension.

---

# Chapter 12 — Suggested reading

## Useful github repository related to the ILC software chain

1. ILCsoft, the integrated software system we used for data management and reconstruction https://github.com/ilcsoft
2. ILDAna, the repositories of the analysis work depends on the ILC software chian(maybe ours will be in it later) https://github.com/ILDAnaSoft
3. The ZHH repository under ILDAna, developing by Bryan and Julie, where I copy from, comprehensive introduction of the dependencies and workflow https://github.com/ILDAnaSoft/ZHH
4. The fancy introduction on the ilcsoft chain https://github.com/ILDAnaSoft/ILDDoc/blob/master/tutorial/gaede_ilcsoft_tutorial.md
5. Key4hep official site, you can find talk slides and tutorials: https://key4hep.github.io/key4hep-doc/main/talks-and-presentations/README.html

Our project starts from the stage where all these tools inside has been runned, so they are not necessary to view for you, but you can

```
cat /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh
```

and check where it actually source from.

## Highly-related papers

Most papers here are more like a theoretical ones. They study things from the Feynman diagram calculations, we check them on the dectector level. Don't need to read and understand all the details in them, just make sure the "observables" comes into the code match their ideas.

1. Where our angular observalbe inspired from? Ma et al. on frame-dependent $e^+e^-\to t\bar{t} H$ CP observables. arXiv:1809.07127
2. The previous studies on the ML observables: arXiv:2112.05052(LHC), arXiv:2511.08359(Future Collider)
3. tth signal/background measurement at ILC environment(old!): arXiv:1104.5132(500GeV), arXiv:1409.7157(1TeV)
4. Chapter 4.9 of this CLIC study, more modern experimental view https://inspirehep.net/files/99819d10bf92156c8ea84dd0c7527549

## Background enhanced papers

Something on the ILC/LCF, general future collider physics case, recent development of the algorithms and research motivation

1. A Linear Collider Vision for the Future of Particle Physics, arXiv:2503.19983.
2. ILC charge-aware ParticleTransformer https://arxiv.org/abs/2410.11322
3. ZHH studies by Bryan and Julie, showing their work on the reconstructions depending on the ILC softwares https://arxiv.org/pdf/2509.14148
4. Fancy theoretical story on why we need CPV in Higgs sector, for "Electroweak Baryongensis" , first chapter of arXiv:2508.09989

I also uploaded two of my talk slides here, which has enough graphic introduction to be understood.

---

# Appendix A — Recommended result table

Fill one row per (family, level, frame, representation, model, polarisation) combination:

| Family | Level | Frame | Representation | Model | Polarisation | $I$ | $R_{\mathrm{reco}}$ | $G_{\mathrm{ML/angle}}$ | Status |
|---|---|---|---|---|---|---:|---:|---:|---|
| $W$ | gen | Higgs rest | angle | — | LR |  | — | — |  |
| $W$ | reco | Higgs rest | angle | — | LR |  |  | — |  |
| $W$ | gen | Higgs rest | ML-min | BDT | LR |  | — |  |  |
| $W$ | reco | Higgs rest | ML-min | BDT | LR |  |  |  |  |
| $b$ | reco | default | angle | — | LR |  |  | — |  |
| $b$ | reco | default | ML | BDT | LR |  |  |  |  |
| fusion | reco | default | $(s_W,s_X)$ | 2D | LCF |  |  |  |  |

# Appendix B — Polarisation closure test

For each physical run configuration:

1. compute $a_r, b_r$ from §2.13;
2. build the weighted $LR+RL$ SM yields;
3. compare with a partially polarised sample if one exists;
4. compare total cross sections;
5. compare at least one angular distribution;
6. verify the pure limits $a(-1,+1)=1$, $b(-1,+1)=0$ and the reversed RL
   limits, and confirm that $a+b$ was not renormalised.

# Appendix C — Decision log template

Every frozen convention gets one entry (axis conventions, object ordering, feature sets, model output convention, binning, MVA threshold, background set, polarisation convention, SMEFT conversion):

```text
date:
decision:
alternatives considered:
physics reason:
technical reason:
validation performed:
person responsible:
```
