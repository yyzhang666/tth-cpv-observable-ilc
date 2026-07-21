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
3. **Which branch is strongest?** How do the hadronic-$W$, top-decay $b/\bar{b}$, lepton–neutrino, and reconstructed-top observables compare with each other?
4. **How to combine?** Is it better to train one model on all features, keep separate physical branches, fuse branch outputs at the end, or use a multidimensional likelihood? (Definitions in §2.7 and Chapter 7.)
5. **Realistic beams.** How do you convert results from the idealised 100%-polarised LR/RL samples into the realistic LCF running scenario? (§2.13, Chapter 8.)

## 1.4 Required scope — the six deliverables

In order (this is also roughly the timeline):

1. A complete gen + reco **angular–ML baseline for $O_W$** (the hadronic-$W$ angle) — Chapters 3–4. This is the main milestone.
2. Integrate the supervisor's **event-selection MVA**; first selected-signal and signal-plus-background result — Chapter 6.
3. **Faster baselines** for the secondary observables $O_b$, $O_{\ell\nu}$, $O_{\mathrm{top}}$ — Chapter 5 (reuse the $O_W$ machinery; do not rebuild anything).
4. **Fusion** of $O_W$ with *one* chosen secondary observable — Chapter 7.
5. The **physical LCF polarisation combination** — Chapter 8.
6. A minimal, supervisor-approved **generator → SMEFT coupling conversion** — Chapter 9.

## 1.5 Optional extensions

Not required. Completing **none** of them is perfectly fine; normally at most **one** is opened, and only after the required results are frozen (Chapter 10):

1. add the hadronic-$\tau$ semileptonic channel as an extra category;
2. try to improve the ParT-assisted hadronic-$W$ jet pairing;
3. add the quadratic ($c^2$) EFT term;
4. extend fusion beyond "$O_W$ + one secondary observable".

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
\bar{t}\left(\cos\xi+i\sin\xi\,\gamma_5\right)t ,
\qquad\text{i.e.}\qquad
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

- $f_0 = d\sigma_{\mathrm{SM}}/dx$ — the SM prediction; **CP-even**: $f_0(\bar x)=f_0(x)$;
- $f_1 = d\sigma_{\mathrm{int}}/dx = 2\,\mathrm{Re}\!\left(\mathcal{M}_{\mathrm{SM}}^{\ast}\mathcal{M}_{\mathrm{CPV}}\right)d\Phi$ — the **interference** term, *linear* in $c$; **CP-odd**: $f_1(\bar x)=-f_1(x)$;
- $f_2 = d\sigma_{\mathrm{CPV}^2}/dx$ — the pure-CPV quadratic term; CP-even.

The same classification applies to observables: $O$ is **CP-even** if $O(\bar x)=O(x)$ and **CP-odd** if $O(\bar x)=-O(x)$. Two consequences drive the entire analysis strategy:

1. In a CP-symmetric sample (the SM part $f_0$ alone), any CP-odd observable has a distribution **symmetric around zero**, so $\langle O\rangle=0$. (This is also the "SM CP closure" validation check of §3.4.)
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

## 2.2 Signed interference weights — the most important bookkeeping rule

The generator provides, per event, an SM weight and a **signed interference weight** $w_{\mathrm{int}}$ that samples $f_1$. Because $f_1$ changes sign, $w_{\mathrm{int}}$ is negative for some events. This has two consequences:

**(a) You cannot treat $f_1$ as a probability density** — it is not one. You cannot "generate events distributed as $f_1$".

**(b) A classifier trick makes it usable for ML.** Define a label from the sign and a training weight from the magnitude:

```math
y=
\begin{cases}
+1,& f_1(x)>0,\\
-1,& f_1(x)<0,
\end{cases}
\qquad
w_{\mathrm{train}} \propto |f_1(x)| .
```

A classifier trained to separate $y=+1$ from $y=-1$ with weights $|f_1|$ learns exactly the regions where interference is positive vs. negative — which is the CP-sensitive direction in feature space.

**Connection to §2.1 — the two classes are CP mirror images.** Since $f_1(\bar x)=-f_1(x)$, applying a CP transformation to any $y=+1$ configuration produces a $y=-1$ configuration with the same $|f_1|$. The classifier is therefore literally being asked "does this event look more like itself or like its CP image?", and its ideal decision function is a **CP-odd function of the event**. In this sense the ML observable of §2.6 is the *learned* counterpart of the hand-built CP-odd angles of §2.3 — both are approximations to the same CP-odd score.

**The golden rule — never mix these two kinds of weights:**

| Purpose | Weight | Class balancing allowed? |
|---|---|---|
| ML training | $\propto \lvert f_1 \rvert$ | yes (helps convergence) |
| Physics templates / yields / Fisher | signed $w_{\mathrm{int}} = \mathrm{sign}(f_1)\,\lvert w_{\mathrm{int}}\rvert$ | **never** |

If you balance classes or drop signs in a final yield template, your predicted physics is simply wrong. Keep the two weight columns separate in every table you write.

Code: [../src/ilc_tth_cpv/weights.py](../src/ilc_tth_cpv/weights.py).

## 2.3 Angular observables

**Why azimuthal angles? (following on from §2.1.)** The interference term $f_1$ is CP-odd, so to pick it up at first order we need observables that are themselves CP-odd (§2.1, consequence 2): quantities that flip sign when all momenta are reflected and particles are exchanged with antiparticles. Signed azimuthal differences are the classic construction. The sign of a signed $\Delta\phi(a,b)$ is the sign of the triple product

```math
\mathrm{sign}\bigl(\sin\Delta\phi(a,b)\bigr)
=
\mathrm{sign}\bigl(\hat z\cdot(\hat p_a\times\hat p_b)\bigr),
```

and a triple product of momenta flips sign under P (every vector in it is reversed). With a **charge-aware ordering** of $a$ and $b$ (so that C maps the ordered pair onto itself — e.g. "up-type before down-type", "$b_t$ before $b_{\bar{t}}$"), the full CP operation gives

```math
\Delta\phi \;\xrightarrow{\;CP\;}\; -\Delta\phi ,
```

i.e. $\Delta\phi$ is CP-odd. Consequently the SM part $f_0$ produces a $\Delta\phi$ distribution **symmetric** under $\Delta\phi\to-\Delta\phi$, while the interference $c\,f_1$ produces the **antisymmetric** component: the CP signal is the asymmetry between $\Delta\phi>0$ and $\Delta\phi<0$.

The basic building block is therefore a **signed azimuthal difference** between two objects $a$ and $b$:

```math
\Delta\phi(a,b)
=
\mathrm{wrap}(\phi_a-\phi_b)
\in(-\pi,\pi],
```

where "wrap" folds the raw difference back into $(-\pi,\pi]$ (e.g. $350°$ becomes $-10°$). Two things students often get wrong:

- **Order matters.** $\Delta\phi(a,b) = -\Delta\phi(b,a)$. Since the sign *is* the CP information, you must fix which object is "first" (e.g. up-type $W$ jet before down-type; $b_t$ before $b_{\bar{t}}$) and never deviate. Charge-aware ParT scores and the decay assignment define the ordering.
- **Wrapping matters.** Compute $\Delta\phi$ with a proper wrap function, never a naive subtraction.

The observable families studied in this project:

```math
O_W=\Delta\phi(j_{W,\mathrm{up}},\,j_{W,\mathrm{down}}) \quad\text{(hadronic-}W\text{ jets)},
```
```math
O_b=\Delta\phi(b_t,\,b_{\bar{t}}) \quad\text{(the two top-decay }b\text{ jets)},
```
```math
O_{\ell\nu}=\Delta\phi(\ell,\,\nu_W) \quad\text{(lepton and neutrino from the leptonic }W\text{)},
```

plus a supervisor-approved $O_{\mathrm{top}}$ built from the reconstructed $t$ and $\bar{t}$ systems.

> **Freeze conventions early.** Exact definitions, charge conventions, and axis conventions must be written down **once**, in a configuration file, and used everywhere (see the decision log, Appendix C). Silent convention changes are the classic way to waste two weeks.

Code: [../src/ilc_tth_cpv/angles.py](../src/ilc_tth_cpv/angles.py); conventions: [PHYSICS_CONVENTIONS.md](PHYSICS_CONVENTIONS.md).

## 2.4 Reference frames

An azimuthal angle is only defined *relative to a frame*, and CP-sensitive correlations can look sharper in one frame than another. The $O_W$ pilot study (Chapter 4) compares three frames:

- the **laboratory** (collider centre-of-mass) frame;
- the **Higgs rest frame** (boost everything by $-\vec p_H$);
- the **$t\bar{t}$ rest frame**.

Practical recipe: keep four-vectors as the internal representation, apply Lorentz boosts to the chosen frame, and *only then* evaluate angles.

To define axes in the boosted frame, use a **production-plane basis** for a system $X$:

```math
\hat z=\frac{\vec p_X^{\,\mathrm{lab}}}{|\vec p_X^{\,\mathrm{lab}}|}
\qquad\text{(the direction of }X\text{)},
```
```math
\hat x=
\frac{\hat p_{e^-}-(\hat p_{e^-}\cdot\hat z)\hat z}
{\left|\hat p_{e^-}-(\hat p_{e^-}\cdot\hat z)\hat z\right|}
\qquad\text{(beam direction, made perpendicular to }\hat z\text{)},
```
```math
\hat y=\hat z\times\hat x
\qquad\text{(completes the right-handed system)} .
```

Then the azimuth of any particle $i$ is

```math
\phi_i=\mathrm{atan2}(\vec p_i\cdot\hat y,\;\vec p_i\cdot\hat x).
```

> **One implementation, used by everyone.** The approved frame convention must live in exactly one shared library — [../src/ilc_tth_cpv/frames.py](../src/ilc_tth_cpv/frames.py) — so that a convention fix propagates everywhere at once.

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

The comparison in question 1 (§1.3) is only fair if the ML model uses **the same physical objects** as the angle. For the hadronic-$W$ branch, the model is a map

```math
M_W:\ F_W\ \rightarrow\ s_W
```

from a feature set $F_W$ to a score $s_W$. Two feature sets are defined:

- **minimal** — just the kinematics of the two $W$ jets (plus the information that defines the frame):
  ```math
  F_W^{\mathrm{min}} = \{E,\theta,\phi\}_{j_{W,\mathrm{up}}}\cup\{E,\theta,\phi\}_{j_{W,\mathrm{down}}} + \text{frame-defining info};
  ```
- **extended** — minimal plus quality/identity information:
  ```math
  F_W^{\mathrm{ext}} = F_W^{\mathrm{min}} + \{m_{jj},\ P_{\mathrm{pair}},\ P_{\mathrm{orientation}},\ \text{signed ParT probabilities}\}.
  ```

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
t_z(z)=\mathrm{E}\!\left[t(x)\mid z\right].
```

> **In plain words:** every feature group (W jets only, b jets only, everything, …) is a different *projection* of one and the same underlying CP-interference information. A "W-branch model" and a "b-branch model" are not measuring different physics parameters — they are partial views of the same $c$. (For a single coupling, they do **not** correspond to different CP phases.)

### What makes the projections physically different?

The CP structure of the $t\bar{t}H$ vertex is imprinted in the **production spin-density matrix** of the $t\bar{t}(H)$ system. Because the top decays before hadronising, its decay products act as **spin analysers**: each decay product reads out the parent top's spin through its own decay matrix, with its own analysing power, so the *same* spin-density matrix is projected into *different* angular distributions depending on which objects you use (see arXiv:1809.07127 for the formalism). Concretely:

- **Single-side objects** (decay products of only one top) mainly project out the **polarization of that single top**.
- **Objects from both sides** (one from $t$, one from $\bar{t}$ — as in $O_b$) directly access the **$t\bar{t}$ spin-correlation matrix**, where much of the CP-odd interference information sits.
- The **two hadronic-$W$ daughter jets** additionally encode the **$W$ helicity and decay-plane orientation** — an extra handle beyond the parent-top spin direction.
- The **reconstructed-top observable** $O_{\mathrm{top}}$ works at production level: it probes the kinematics of the $t$, $\bar{t}$, $H$ systems themselves, in particular the interference between Higgs emission off the top line (the $t\bar{t}H$ vertex being measured) and the Higgsstrahlung-like contribution where the Higgs is radiated off the intermediate $Z$ (the "ZH"-type diagram).

The projections also differ in **reconstruction quality**, not only in physics content: the isolated lepton is tagged with high efficiency, carries an unambiguous charge, and has no jet-assignment problem; a $b/\bar{b}$ ordering instead relies on flavour tagging (lower efficiency, mis-tag rates) *plus* jet assignment. A reco-level branch comparison therefore mixes analysing power with reconstruction quality — comparing gen level (physics only) against reco level (physics × detector) disentangles the two, which is exactly the $R_{\mathrm{reco}}$ logic of §2.12.

This is exactly why Chapter 7 compares:

- separate physical branches ($s_W$, $s_b$, …);
- **early fusion** — one model trained on all features at once;
- **late fusion** — a small model combining the branch scores $(s_W, s_X)$;
- a **multidimensional likelihood** — using $(s_W, s_X)$ directly as a 2D histogram.

If the branches are nearly independent projections, late fusion ≈ early fusion; if they are strongly overlapping, adding a branch gains little. Both outcomes are informative.

## 2.8 Comparing gen and reco correctly: same events only

The single most common way to get a *wrong* gen/reco retention number is to compare **different event populations**. The rule:

> Every gen-vs-reco comparison uses **identical event IDs** on both sides.

Define the common set

```math
S_{\mathrm{common}}
=
\{\text{events with the required reconstructed objects and a valid assignment}\},
```

and evaluate **both** $O_i^{\mathrm{gen}}$ and $O_i^{\mathrm{reco}}$ on exactly these events. Then any difference in information is genuinely due to resolution and mis-assignment — not to one side simply having more events.

You may additionally show an *inclusive* gen-level curve (all generated events) as an upper reference line on plots, but it must never enter a retention ratio.

Keep one global bookkeeping funnel, always up to date:

```math
N_{\mathrm{generated}}
\rightarrow
N_{\text{isolated lepton}}
\rightarrow
N_{\text{valid reconstruction}}
\rightarrow
N_{\text{MVA selected}} .
```

Schema and matching: [DATA_SCHEMA.md](DATA_SCHEMA.md), [../tests/test_event_matching.py](../tests/test_event_matching.py).

## 2.9 Event-selection MVA and backgrounds

The signal density is $f_{\mathrm{sig}}(x;c)=f_0(x)+c f_1(x)$. A fixed selection (a cut on the supervisor's MVA score) is an acceptance function $a(x)\in\{0,1\}$:

```math
f_{\mathrm{selected}}(x;c)=a(x)\left[f_0(x)+c f_1(x)\right].
```

Because $a(x)$ does not depend on $c$, the local score of **accepted** events is still $f_1/f_0$ — so selection *removes events* (and thus information) but does not bias the shape logic of the signal-only study. That is why Chapters 3–5 can proceed before the MVA arrives.

With a background $b(x)$ that does not depend on $c$, the ideal observable becomes

```math
t_{\text{sig+bg}}(x)
=
\frac{f_1(x)}{f_0(x)+b(x)}
=
\underbrace{\frac{f_0(x)}{f_0(x)+b(x)}}_{\text{signal purity}}
\;\cdot\;
\underbrace{\frac{f_1(x)}{f_0(x)}}_{\text{CP score}} .
```

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
\frac{\nu_{1,i}^2}{\nu_{0,i}} ,
\qquad\text{with per-bin contribution}\quad
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

Two variants to be aware of:

- **absolute-yield Fisher** (the formulas above) includes both *rate* and *shape* information;
- if the overall normalisation is removed or profiled away, use the **shape-only** Fisher:
  ```math
  I_{\mathrm{shape}}
  =
  \sum_i\frac{\nu_{1,i}^2}{\nu_{0,i}}
  -
  \frac{\left(\sum_i\nu_{1,i}\right)^2}{\sum_i\nu_{0,i}} .
  ```
  (For a purely CP-odd observable $\sum_i \nu_{1,i}\approx 0$ and the two coincide.)

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
I_{\text{sig+bg}}(z),
```

and form the ratios that answer the project questions directly:

```math
R_{\mathrm{reco}}=\frac{I_{\mathrm{reco}}}{I_{\mathrm{gen}}}
\quad\text{(what fraction survives reconstruction?)},
```
```math
R_{\mathrm{selection}}=\frac{I_{\mathrm{selected}}}{I_{\mathrm{reco}}}
\quad\text{(what does the MVA cut cost?)},
```
```math
R_{\mathrm{background}}=\frac{I_{\text{sig+bg}}}{I_{\mathrm{selected}}}
\quad\text{(what does background dilution cost?)},
```
```math
G_{\text{ML/angle}}=\frac{I_{\mathrm{ML}}}{I_{\mathrm{angle}}}
\quad\text{(what does ML gain over the plain angle?)}.
```

> **Fair-comparison rule:** every ratio requires the *same* luminosity, the *same* coupling convention, the *same* event pool (§2.8), and the *same* binning strategy on both sides. If any of these differ, the ratio is meaningless.

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

> **Check before use:** the generator's cross-section normalisation convention (spin averaging, factors of 4) must be verified before applying these mixture factors — that is the closure test of Appendix B.

**Polarisation in ML training — three rules:**

1. $a_r,b_r$ are **event weights**, never input features, and must never multiply the final classifier score.
2. To train for physical run configuration $r$: pool the LR and RL events, weight them as
   ```math
   w_{e,r}^{\mathrm{phys}}
   =
   \begin{cases}
   a_r\, w_e^{LR}, & e\in LR,\\
   b_r\, w_e^{RL}, & e\in RL,
   \end{cases}
   ```
   preserving the physical LR/RL mixture *inside* each class. Equalising total (+) vs (−) class weight for training stability is allowed.
3. Final templates use unbalanced physical yield weights including luminosity:
   ```math
   w_{e,r}^{\mathrm{template}}
   =
   \mathcal{L}_r\, a_r\, w_e^{LR}
   \quad\text{or}\quad
   \mathcal{L}_r\, b_r\, w_e^{RL}.
   ```

Per-run likelihoods are combined by multiplication: $\mathcal{L}_{\mathrm{LCF}}(c)=\prod_r\mathcal{L}_r(c)$.

The initial physics study nevertheless keeps pure $LR$ and $RL$ separate — mix only in Chapter 8.

Code: [../src/ilc_tth_cpv/polarization.py](../src/ilc_tth_cpv/polarization.py), config [../configs/lcf_polarization.yaml](../configs/lcf_polarization.yaml).

## 2.14 Generator convention → SMEFT convention

The CPV generator sample should not be read as a physical finite-$\alpha$
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
\Delta\!\left(\frac{C^I_{t\varphi}}{\Lambda^2}\right)
=
\frac{\Delta c_{\mathrm{gen}}}{|K|}\ \mathrm{TeV}^{-2}.
```

The numerical factor and the sign convention must still be supervisor-approved
before quoting a result. This is a one-parameter reinterpretation, not a
multi-operator SMEFT fit.

---

# Chapter 3 — Common analysis baseline (build this first)

**Goal:** one shared data + code layer that *every* angle and *every* ML model uses. **Finish the data contract, weight checks, event matching, and a first angular distribution before doing any model scans.**

## 3.1 Why this comes first

Every result in Chapters 4–9 is a ratio between two runs of the same machinery. If the machinery (weights, matching, frames, splits) is not trustworthy, every later number is silently wrong. One week here saves several weeks later.

## 3.2 The standard event table

One table (see [DATA_SCHEMA.md](DATA_SCHEMA.md)), one row per event, containing:

- unique **event ID** (the backbone of all gen/reco matching);
- **LR/RL** sample label;
- gen and reco **validity flags**;
- isolated-lepton flavour and charge;
- **SM event weight** and **signed interference weight** (separate columns, §2.2), optional quadratic weight;
- event-selection **MVA score** (filled when it arrives, Chapter 6);
- gen and reco **four-vectors** of all analysis objects;
- the current ParT-assisted **assignments** and **signed ParT probabilities**;
- reconstruction-quality variables;
- a **deterministic train/validation/test split** label (same event always in the same split, for every model).

Reconstruction-level objects come from the kinfit + jet-assignment stage — students use its selected candidate (slots `W1, W2, b_had, b_lep, H_b1, H_b2` + fitted lepton/neutrino), *not* raw jets: [KINFIT_JET_ASSIGNMENT.md](KINFIT_JET_ASSIGNMENT.md).

## 3.3 Shared software

Reusable, tested functions for: table reading/validation; event-ID matching; Lorentz boosts; frame axes; $\theta,\phi,\Delta\phi$; feature construction; deterministic splitting; angular and ML templates; Fisher; likelihood scans; polarisation weights; metadata and plotting. These live in [../src/ilc_tth_cpv/](../src/ilc_tth_cpv/) — extend them, do not fork private copies into notebooks.

## 3.4 Validation checklist (all must pass before Chapter 4)

- [ ] no train/validation/test overlap;
- [ ] exact event-ID closure between gen and reco tables;
- [ ] SM and interference weight sums match expected normalisations;
- [ ] signed-weight sums stable across reruns;
- [ ] $\phi$ wrapping correct (test values around $\pm\pi$);
- [ ] exactly one frame implementation in use;
- [ ] **SM CP closure**: on the SM sample alone, every CP-odd observable is symmetric within statistics (if not, a convention bug exists);
- [ ] every output file carries complete metadata (config, code version, seed).

## 3.5 Deliverable

A frozen baseline configuration, documented schema, validated common event table, and a first gen + reco $O_W$ distribution plot.

---

# Chapter 4 — The full $O_W$ angular–ML baseline (main milestone)

**This is the core of the project** — expect roughly two to three effective weeks including debugging. Everything later reuses this machinery.

## 4.1 Observable

```math
O_W=\Delta\phi(j_{W,\mathrm{up}},\,j_{W,\mathrm{down}})
```

at gen and reco level, using the current ParT-assisted assignment, on the common event set (§2.8).

## 4.2 Frame study

Evaluate $O_W$ in the laboratory frame, the Higgs rest frame, and the $t\bar{t}$ rest frame (§2.4). Pick a default frame based on the results and freeze it (Appendix C).

## 4.3 Feature schemes

Train with the minimal set $F_W^{\mathrm{min}}$ and the extended set $F_W^{\mathrm{ext}}$ of §2.6 (respecting the current raw-variables decision of §2.5).

## 4.4 Models — deliberately simple

1. a BDT (e.g. CatBoost) as the baseline;
2. a small MLP as a cross-check.

> This is a *stability* study, not an architecture search. If the BDT and the MLP disagree strongly, the interesting question is *why* — not which is bigger.

## 4.5 Required comparisons

Compute (per §2.10, with the rules of §2.12):

```math
I_{\mathrm{angle}}^{\mathrm{gen}},\quad
I_{\mathrm{angle}}^{\mathrm{reco}},\quad
I_{\mathrm{ML}}^{\mathrm{gen}},\quad
I_{\mathrm{ML}}^{\mathrm{reco}},
```

plus $R_{\mathrm{reco}}$ and $G_{\text{ML/angle}}$ — **separately for pure LR and pure RL**.

## 4.6 Deliverable

One result matrix (template: Appendix A) covering: frame dependence; angle vs ML; BDT vs MLP; minimal vs extended features; gen→reco retention; LR vs RL.

Configs and driver: [../configs/analysis_ow_lr.yaml](../configs/analysis_ow_lr.yaml), [../configs/analysis_ow_rl.yaml](../configs/analysis_ow_rl.yaml), [../scripts/run_baseline.sh](../scripts/run_baseline.sh).

---

# Chapter 5 — Secondary-observable baselines (fast, by reuse)

**Start only after the $O_W$ framework is stable.** Reuse the frozen default frame and model configuration — the point is a *quick, uniform* survey, not three new projects.

## 5.1 $O_b=\Delta\phi(b_t,b_{\bar{t}})$

Ordering from signed ParT $b/\bar{b}$ scores + top-side assignment + lepton-charge consistency.

## 5.2 $O_{\ell\nu}=\Delta\phi(\ell,\nu_W)$ (or approved equivalent)

The reco-level neutrino is an *estimate* (from missing momentum / kinematic fit) — document which estimator is used and its validity flag.

## 5.3 $O_{\mathrm{top}}$

A top-level angle from the reconstructed $t,\bar{t}$ systems. **Freeze the exact definition with the supervisor before writing code.**

## 5.4 Required comparison (identical recipe for each)

Gen/reco angle; one fixed BDT; Fisher at gen and reco; retention $R_{\mathrm{reco}}$; and the **correlation with $s_W$** — a strong branch that is highly correlated with $s_W$ adds little in fusion; a moderately strong but complementary one may add more.

## 5.5 Deliverable

A compact table identifying the strongest and the most *complementary* secondary observable → this selects $X$ for Chapter 7.

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
\quad\text{(the conditional gain from adding }X\text{)}.
```

**Deliverable:** a justified answer to "one all-feature model, separated branches, or a multidimensional likelihood?" — including "they are equivalent", if that is what the numbers say.

---

# Chapter 8 — Physical LCF polarisation combination

**Do this only after observable definitions and models are frozen** — mixing polarisations with moving definitions makes results uninterpretable. All formulas: §2.13.

1. **Pure-helicity study first:** compare LR vs RL rates, shapes, interference, Fisher.
2. **Weighted physical training:** per run category $r$, combine LR/RL events with weights $a_r, b_r$. Do **not** use $a_r,b_r$ as features, do **not** multiply final scores by them, do **not** average independently trained scores without a calibrated common coordinate.
3. **Templates and likelihood:** $\mathcal{L}_r = f_r^{\mathrm{run}}\times 8~\mathrm{ab}^{-1}$; one template category per run configuration; combine as $\mathcal{L}_{\mathrm{total}}(c)=\prod_r \mathcal{L}_r(c)$.
4. Run the polarisation **closure test** (Appendix B) before quoting anything.

**Deliverable:** pure LR/RL, four run-category, and combined LCF sensitivities, with a rate-vs-shape interpretation where possible.

---

# Chapter 9 — Minimal BSM interpretation

**Only after the final likelihood is stable.** Apply the supervisor-approved
$C^I_{t\varphi}/\Lambda^2$ conversion of §2.14, record conventions/sign/units
and the local nature of the conversion, and do not present it as a
multi-operator SMEFT fit.

---

# Chapter 10 — Optional extensions (at most one, only after required results are frozen)

## Option 1 — Hadronic-$\tau$ category
Add semitau events as a separate statistical category, using a *frozen* tau tagger; keep the existing observables; **no tau polarimeter**. Prerequisites from the tagger team: frozen model/interface, efficiency and fake rates, constituent links, usable charge convention. Deliverable: sensitivity change from adding the category.

## Option 2 — W-pairing optimisation
First measure the ceiling with a truth-matched oracle assignment:
```math
\Delta I_{\mathrm{pairing}}=I_{\mathrm{oracle}}-I_{\mathrm{current}} .
```
Proceed only if the gap is relevant. Possible methods: probability calibration, global assignment, top-$K$ candidates, soft assignment, posterior-weighted observables. Deliverable: increased **CP information**, not just higher pairing accuracy.

## Option 3 — Quadratic EFT term
$\nu_i(c)=\nu_{0,i}+c\,\nu_{1,i}+c^2\nu_{2,i}$. Justified if linear templates go negative, the interval is non-local, or a finite-coupling scan needs it. Deliverable: linear vs quadratic intervals, with EFT-truncation caveats.

## Option 4 — Wider fusion
Extend to e.g. $W+b+\mathrm{top}$ or $W+b+\ell\nu+\mathrm{top}$, only if the two-branch result is stable and additional branches show non-negligible conditional information $\Delta I$. Deliverable: an information-gain matrix per added branch.

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
I_{\text{sig+bg}}
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
- develop a full neutrino-correction Marlin processor;
- complete any optional extension.

---

# Chapter 12 — Suggested reading

1. Project $t\bar{t} H$ generator-level CP-observable theory report.
2. Ma et al. on frame-dependent $e^+e^-\to t\bar{t} H$ CP observables.
3. CLIC $t\bar{t} H$ CP reconstruction study.
4. Qu et al., Particle Transformer.
5. ILC charge-aware ParticleTransformer material.
6. arXiv:2401.02474 — optimal-observable ideas and detector-level ML.
7. A Linear Collider Vision for the Future of Particle Physics, arXiv:2503.19983.
8. Project ZH CPV WORKLOG.
9. Current hadronic-$\tau$ ParticleTransformer report.
10. DESY Summer Student 2026 supervisor guidelines.

---

# Appendix A — Recommended result table

Fill one row per (family, level, frame, representation, model, polarisation) combination:

| Family | Level | Frame | Representation | Model | Polarisation | $I$ | $R_{\mathrm{reco}}$ | $G_{\text{ML/angle}}$ | Status |
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
6. document any generator factor-of-four or spin-average convention found.

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
