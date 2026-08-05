## Ch.3 Step 1 - Generator and Reconstructed Events Output

### Generator Output
sample     : tthcpv_gen_elpr (chunk 0) <br>

#### STDHEP and sidecar paths
stdhep     : `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/cpv_tth/eL.pR/I01234_0/generator/stdhep/E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.0.stdhep` <br>
sidecar    : `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/cpv_tth/eL.pR/I01234_0/generator/sidecars/E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.0.tthcpv_me.csv` <br>

#### sidecar/alignment counts
sidecar rows=12500 skipped=0 aligned=12500 <br>

#### positive and negative weight counts
weight check: ok=True n_pos=6298 n_neg=6202 signed_sum=0.00303872 fb <br>

#### one event's t , t¯ , Higgs, b / b¯, and hadronic W daughter identities
=== event 1 (stdhep #0) w_signed=+3.16534e-05 fb

  higgs         : pdg= +25 E=  162.66 GeV <br>
  top           : pdg=  +6 E=  176.37 GeV <br>
  antitop       : pdg=  -6 E=  183.44 GeV <br>
  top_b         : pdg=  +5 E=   53.06 GeV <br>
  antitop_bbar  : pdg=  -5 E=   66.61 GeV <br>
  wjet_quark    : pdg=  +1 E=   52.82 GeV <br>
  wjet_antiquark: pdg=  -2 E=   64.01 GeV <br>
  lepton        : MISSING <br>
  neutrino      : MISSING <br>
  frame lab        : O_W = -0.9702 rad <br>
  frame higgs_rest : O_W = -0.0235 rad <br>
  frame ttbar_rest : O_W = -1.3729 rad <br>


### Reco Output

#### Input SLICO File Path
`/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/cpv_tth/eL.pR/I01234_0/complete_reco/complete_reco_kinfit_ready_E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.0_sgv.slcio` <br>


#### Inspect in particular OutputErrorFlowJets6, RefinedJets6, ISOElectrons, and ISOMuons
=== event #0 run=1 event=0 <br>

OutputErrorFlowJets6 n=6: <br>
  jet 0: E= 114.54 GeV  weaver[] <br>
  jet 1: E=  87.19 GeV  weaver[] <br>
  jet 2: E=  69.66 GeV  weaver[] <br>
  jet 3: E=  56.75 GeV  weaver[] <br>
  jet 4: E=  51.40 GeV  weaver[] <br>
  jet 5: E=  47.07 GeV  weaver[] <br>

RefinedJets6 n=6 <br>
  jet 0: E= 114.54 GeV  weaver[mc_d=0.210, mc_g=0.177, mc_ubar=0.175, mc_sbar=0.136] <br>
  jet 1: E=  87.19 GeV  weaver[mc_dbar=0.180, mc_u=0.180, mc_sbar=0.169, mc_d=0.133] <br>
  jet 2: E=  69.66 GeV  weaver[mc_b=0.734, mc_bbar=0.252, mc_cbar=0.006, mc_g=0.005] <br>
  jet 3: E=  56.75 GeV  weaver[mc_cbar=0.733, mc_g=0.097, mc_b=0.060, mc_bbar=0.029] <br>
  jet 4: E=  51.40 GeV  weaver[mc_bbar=0.499, mc_b=0.381, mc_c=0.094, mc_g=0.018] <br>
  jet 5: E=  47.07 GeV  weaver[mc_g=0.197, mc_s=0.160, mc_sbar=0.155, mc_u=0.145] <br>

ISOMuons: n=0

ISOElectrons: n=0


## Ch.3 Step 2 - Inspect the Underlying LCIO Records Directly

### Generator Event
1. run/event number
   - Event: 0, run: 0
2. incoming electron direction (PDG: 11) 
   - momentum (px, py, pz) = (0.00e+00, 0.00e+00, 2.48e+02) <br>
   => Direction: +z direction 
3. the parent/daughter chain for t , t¯ , H , and the two hadronic W daughters
   - t (PDG: 6)
     - parent: e-, daughter: b, W+
   - t¯ (PDG: -6)
     - paremt: e-, daughter: b¯, W-
   - H (PDG: 25) and the two hadronic W daughters (PDG: 24, -24)
     - parent: e-, daughter: W+, W-
       - parent: W+, daughter: d¯, u
       - parent: W-, daughter: s, c¯

### Reco Event
1. run/event number
   - Event: 0, run: 1
2. collection names and sizes:
   - ISOElectrons, Size 0
   - ISOMuons, Size 0
   - OutputErrorFlowJets6, Size 6
     - momentum (px,py,pz) = (-5.44e+01, -9.37e+01, +1.09e+01)
     - Energy = 1.15e+02
     - mass = 3.54e+01
     - charge = 1.00e+00
     - position (x,y,z) = (+0.00e+00, +0.00e+00, +0.00e+00)
   - RefinedJets6, Size 6
     - Unprinted due to segmentation fault (core dumped)
3. the six-jet collections
  - Both OutputErrorFlowJets6 and RefinedJets6 exist and contain 6 reconstructed jets each.
4. isolated-lepton collection
  - Both ISOElectrons and ISOMuons have a size of 0 (no isolated leptons identified for this event).
5. any PID parameters visible for the jets
  - OutputErrorFlowJets6: No PID parameters.
  - RefinedJets6: Unprinted in this specific dumpevent execution due to a Segmentation fault.


## Ch.3 Step 3 - Run the local generator example and inspect its table
> Memo: <br> When you run `run_baseline.sh` it executes these 6 steps in order: <br> 1. Inspect Generator Data <br> 2. Export CSV Features (CPV & SM) <br> 3. Create Angular Histograms <br> 4. Train XGBoost ML Model <br> 5. Evaluate ML Scores <br> 6. Calculate Fisher Information / Sensitivity


## Ch.3 Step 4 - Run a 50-event kinfit smoke in a separate directory
### Inspecting
> Memo: <br> Since running <br>`bash scripts/run_kinfit_assignment.sh \` <br> `--config configs/analysis_ow_lr.yaml \` <br> `--chunk 0 \ <br> --max-events 50 \` <br>  `--out-dir outputs/ow_lr/kinfit_smoke` <br> gave me an error: `Refusing to overwrite /data/dust/user/ozakinan/analysis/tth-cpv-observable-ilc/outputs/ow_lr/kinfit_smoke/kinfit_tthcpv_reco_elpr_chunk0.root`, <br> so I run `--out-dir outputs/ow_lr/kinfit_smoke_2` instead.


### Replace the generator smoke table with the complete chunk-0 table, export the full reco baseline, and build one `O_W` example at each level
```
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

## Ch.3 Step 5 - Run one complete CPV chunk and its SM denominator through HTCondor
Things to check about Pass condition:
- schema_report
- the SM metadata records finite LR physical normalization
- reco metadata point to the expected CPV/SM kinfit ROOT and SLCIO files
- event-number mismatches are zero; kinfit mode, score, and fitted-neutrino checks remain valid
- all selected reco rows have finite O_W and O_ℓν
- orientation counts/margins are present; all four histograms have identical edges and n_out_of_range=0
- the Fisher JSON names O_W_all_sm_reco_bins.csv as nu0_source.


## Ch.3 Step 6 - Run one complete CPV chunk and its SM denominator through HTCondor

## Ch.3 Summary
1. Which generator STDHEP, sidecar, reco SLCIO, and kinfit ROOT file entered the run?
   - stdhep : `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/cpv_tth/eL.pR/I01234_0/generator/stdhep/E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.0.stdhep`
   - sidecar : `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/cpv_tth/eL.pR/I01234_0/generator/sidecars/E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.0.tthcpv_me.csv`
   - reco SLICO: `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/cpv_tth/eL.pR/I01234_0/complete_reco/complete_reco_kinfit_ready_E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.0_sgv.slcio`
   - kinfit ROOT file: NEED TO CHECK

2. Which objects and collections were read from one event?
   - ISOElectrons (size 0 in test event)
   - ISOMuons (size 0 in test event)
   - OutputErrorFlowJets6 (6 reconstructed jets with momentum)
   - RefinedJets6 (6 reconstructed jets with Weaver/PID probabilities)
     
3. Which frame, axis convention, object ordering, and weight column were used?
   - a
4. How many events entered, failed reconstruction, passed kinfit, and filled OW ?
   - a
5. Where are the event table, metadata, validation JSON, histogram CSV, and plot?
   - a
