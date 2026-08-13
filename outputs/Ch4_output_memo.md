## Confirmation of output files
### 0. NOTE
Added `scripts/run_pipeline.sh` to run the complete angular observable pipeline in one step.

Executing `./scripts/run_pipeline.sh` performs the following:
- Exports features using export_features.py for both CPV and SM (across gen and reco levels).
- Builds observables using `build_angular_observable.py` across all combinations of observables (O_W, O_lD), levels (gen, reco), and leptons (electron, muon, all).
- Calculates Fisher information using `evaluate_fisher.py` for all built histograms at $\mathcal{L} = 8000\text{ fb}^{-1}$.

Usage:
- Default frame (higgs_rest): `./scripts/run_angular_observable_pipeline.sh`.
- Specify frame: `./scripts/run_angular_observable_pipeline.sh lab` or `./scripts/run_angular_observable_pipeline.sh ttbar_rest`.

### 1. Export the CPV-interference features
**Running the code (from Ch 4.1.4):**
#### 1.1 Both electron and muon combined
##### 1.1.1 gen level
```
python3 scripts/export_features.py \
  --config configs/analysis_angular_lr.yaml \
  --level gen \
  --chunk 0
```

Produced:
```
outputs/angular_lr/features/features_gen_higgs_rest_chunk0.csv
outputs/angular_lr/features/features_gen_higgs_rest_chunk0.meta.json
```
default_frame: lab    
Output Message:
```
generator truth-channel selection:
  events_channel_selected: 2073
  events_hbb: 7204
  events_read: 12500
  events_truth_selected: 2072
  higgs_mode::H->WW: 2713
  higgs_mode::H->bb: 7204
  higgs_mode::H->gg: 1039
  higgs_mode::H->other: 716
  higgs_mode::H->tautau: 828
  missing_truth_object::wjet_antiquark: 1
  rejected_incomplete_truth_objects: 1
  rejected_non_hbb: 5296
  rejected_non_semileptonic_emu: 5131
  ttbar_mode::dileptonic: 1333
  ttbar_mode::hadronic: 5676
  ttbar_mode::semileptonic_emu: 3638
  ttbar_mode::semileptonic_tau: 1853
wrote 2072 rowsdefault_frame: lab    
```

Confirmed that `.csv` file contains (only first few rows are checked):
- `O_W` and `O_lD` columns with finite values (not all-NaN)
- `lepton_pdg` column with 11, -11, 13, or -13
- `lepton_flavor` column with `electron` or `muon`

Confirmed that `.json` file contains (reflects):
- truth_selection (`"higgs_decay": "H->bb"`, `"ttbar_decay": "semileptonic_emu"`)

##### 1.1.2 reco level

Produced:
```
outputs/angular_lr/features/features_reco_higgs_rest_chunk0.csv
outputs/angular_lr/features/features_reco_higgs_rest_chunk0.meta.json
```

Confirmed that `.csv` file contains (only first few rows are checked):
- `O_W` and `O_lD` columns with finidefault_frame: lab    te values (not all-NaN)
- `lepton_flavor` column with `sm_reco_electronelectron` or `muon`


#### 1.2 electron only (O_W, O_lD)
##### 1.2.1 gen level
Base Input:
```
python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_gen_higgs_rest_chunk0.csv \
  --observable O_lD \
  --split all \
  --lepton-flavor electron \
  --output-tag gen_electron
```

Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_gen_electron_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_gen_electron_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_gen_electron.png

outputs/angular_lr/angular/O_lD/O_lD_all_gen_electron_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_gen_electron_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lDdefault_frame: lab    _all_gen_electron.png
```

##### 1.2.2 reco level
Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_reco_electron_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_reco_electron_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_reco_electron.png

outputs/angular_lr/angular/O_lD/O_lD_all_reco_electron_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_reco_electron_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lD_all_reco_electron.png
```

#### 1.3 muon only (O_W, O_lD)
##### 1.3.1 gen level
Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_gen_muon_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_gen_muon_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_gen_muon.png

outputs/angular_lr/angular/O_lD/O_lD_all_gen_muon_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_gen_muon_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lD_all_gen_muon.png
```
##### 1.3.2 reco level
Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_reco_muon_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_reco_muon_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_reco_muon.png

outputs/angular_lr/angular/O_lD/O_lD_all_reco_muon_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_reco_muon_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lD_all_reco_muon.png
```

### 2. Export the SM features
#### 2.1 Both electron and muon combined
##### 2.1.1 gen level
```
python3 scripts/export_features.py \   
  --config configs/analysis_angular_lr.yaml \
  --level gen \
  --component sm \
  --chunk 0
```

Produced:
```
outputs/angular_lr/features/features_sm_gen_higgs_rest_chunk0.csv
outputs/angular_lr/features/features_sm_gen_higgs_rest_chunk0.meta.json
```

Output Message:
```
generator truth-channel selection:
  events_channel_selected: 1941
  events_hbb: 6653
  events_read: 11505
  events_truth_selected: 1938
  higgs_mode::H->WW: 2439
  higgs_mode::H->bb: 6653
  higgs_mode::H->gg: 992
  higgs_mode::H->other: 653
  higgs_mode::H->tautau: 768default_frame: lab    
  missing_truth_object::wjet_antiquark: 3
  rejected_incomplete_truth_objects: 3
  rejected_non_hbb: 4852
  rejected_non_semileptonic_emu: 4712
  ttbar_mode::dileptonic: 1254
  ttbar_mode::hadronic: 5207
  ttbar_mode::semileptonic_emu: 3375
  ttbar_mode::semileptonic_tau: 1669
wrote 1938 rows
```

Confirmed that `.csv` file contains (only first few rows are checked):
- `O_W` and `O_lD` columns with finite values (not all-NaN)
- `lepton_pdg` column with 11, -11, 13, or -13
- `lepton_flavor` column with `electron` or `muon`

Confirmed that `.json` file contains (reflects):
- truth_selection (`"higgs_decay": "H->bb"`, `"ttbar_decay": "semileptonic_emu"`)

##### 2.1.2 reco level

Produced:
```
outputs/angular_lr/features/features_sm_reco_higgs_rest_chunk0.csv
outputs/angular_lr/features/features_sm_reco_higgs_rest_chunk0.meta.json
```

Confirmed that `.csv` file contains (only first few rows are checked):
- `O_W` and `O_lD` columns with finite values (not all-NaN)
- `lepton_flavor` column with `electron` or `muon`

#### 2.2 electron only (O_W, O_lD)
##### 2.2.1 gen level
Base Input:
```
python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr.yaml \
  --features outputs/angular_lr/features/features_sm_gen_higgs_rest_chunk0.csv \
  --observable O_W \
  --split all \
  --weight-column weight_sm \
  --lepton-flavor electron \
  --output-tag sm_gen_electron
```

Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_sm_gen_electron_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_sm_gen_electron_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_sm_gen_electron.png

outputs/angular_lr/angular/O_lD/O_lD_all_sm_gen_electron_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_sm_gen_electron_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lD_all_sm_gen_electron.png
```

##### 2.2.2 reco level
Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_sm_reco_electron_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_sm_reco_electron_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_sm_reco_electron.png

outputs/angular_lr/angular/O_lD/O_lD_all_sm_reco_electron_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_sm_reco_electron_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lD_all_sm_reco_electron.png
```

#### 2.3 muon only (O_W, O_lD)
##### 2.3.1 gen level
Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_sm_gen_muon_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_sm_gen_muon_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_sm_gen_muon.png

outputs/angular_lr/angular/O_lD/O_lD_all_sm_gen_muon_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_sm_gen_muon_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lD_all_sm_gen_muon.png
```

##### 2.3.2 reco level
Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_sm_reco_muon_bins.csv
outputs/angular_lr/angular/O_W/O_W_all_sm_reco_muon_bins.meta.json
outputs/angular_lr/angular/O_W/O_W_all_sm_reco_muon.png

outputs/angular_lr/angular/O_lD/O_lD_all_sm_reco_muon_bins.csv
outputs/angular_lr/angular/O_lD/O_lD_all_sm_reco_muon_bins.meta.json
outputs/angular_lr/angular/O_lD/O_lD_all_sm_reco_muon.png
```

### 3. Build the four generator-level templates
Produced:
```
outputs/angular_lr/angular/O_lD/O_lD_all_gen.png
outputs/angular_lr/angular/O_lD/O_lD_all_sm_gen.png
outputs/angular_lr/angular/O_W/O_W_all_gen.png
outputs/angular_lr/angular/O_W/O_W_all_sm_gen.png
```

## Fisher Information Calculation (Ch 4.4)
Base input code:
```
python3 scripts/evaluate_fisher.py \
  --template outputs/angular_lr/angular/O_W/O_W_all_gen_electron_bins.csv \
  --sm-template outputs/angular_lr/angular/O_W/O_W_all_sm_gen_electron_bins.csv \
  --luminosity-scale 8000
```

Produced:
```
outputs/angular_lr/angular/O_W/O_W_all_gen_electron_bins.fisher.json
outputs/angular_lr/angular/O_W/O_W_all_gen_muon_bins.fisher.json

outputs/angular_lr/angular/O_lD/O_lD_all_gen_electron_bins.fisher.json
outputs/angular_lr/angular/O_lD/O_lD_all_gen_muon_bins.fisher.json

outputs/angular_lr/angular/O_W/O_W_all_reco_electron_bins.fisher.json
outputs/angular_lr/angular/O_W/O_W_all_reco_muon_bins.fisher.json

outputs/angular_lr/angular/O_lD/O_lD_all_reco_electron_bins.fisher.json
outputs/angular_lr/angular/O_lD/O_lD_all_reco_muon_bins.fisher.json

```
### Fisher Information Summary Table
**Important Note**
- This table uses data from old `export_feature.py`, before updating the logic for select truth H->bb for reco level. So the fisher information of reco level might not be accurate.
- This also uses the signed score (old) method of ordering W daughters. The one with new method is in next section.

| Observable | Lepton category | Gen population | Reco population | Frame | $N_{\text{gen}}$ | $N_{\text{reco}}$ | $I_{\text{gen}}$ | $I_{\text{reco}}$ | $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` | 1064 | 2407 | 8.495167899547766 | 1.2397771189978357 | 0.1459390955 |
| $O_{jj}\ (O_W)$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` | 1008 | 2248 | 8.883643187780406 | 1.1993601792646105 | 0.1350076938 |
| $O_{jj}\ (O_W)$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` | 2072 | 4655 | $I_e + I_\mu =$ 17.37881109 | $I_e + I_\mu =$ 2.439137298 | 0.1403512177 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` | 1064 | 2407 | 8.576818452904579 | 1.444664681847666 | 0.1684382956 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` | 1008 | 2248 | 9.42454726292643 | 2.0646261290260095 | 0.2190689984 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` | 2072 | 4655 | $I_e + I_\mu =$ 18.00136572 | $I_e + I_\mu =$ 3.509290811 | 0.1949458094 |

## Updated W-daughter Orient Method Based on the Likelihood
### 1. Modification made
Modified the file `flavor.py` and changed the function `orient_w_pair()` according to `docs/W_DAUGHTER_ORDERING.md`.

### 2. Output file paths
Produced all files (`O_W` and `O_lD` for electron, muon, and electron+muon for both gen and reco level) under: <br>
`outputs/angular_lr/angular/O_W/joint_likelihood`, <br>
`outputs/angular_lr/angular/O_lD/joint_likelihood`, and <br>
`outputs/angular_lr/features/joint_likelihood`

The files with old method (naive q / q¯ orientation) is moved to: <br>
`outputs/angular_lr/angular/O_W/signed_score`, <br>
`outputs/angular_lr/angular/O_lD/signed_score`, and <br>
`outputs/angular_lr/features/signed_score`

### 3. Fisher Information Summary Table
**Important Note**
- For this table, the `export_feature.py` is updated for select truth H->bb for reco level.

| Observable | Lepton category | Gen population | Reco population | Frame | $N_{\text{gen}}$ | $N_{\text{reco}}$ | $I_{\text{gen}}$ | $I_{\text{reco}}$ | $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` | 1064 | 1323 | 8.495167899547766 | 1.1922170218389185 | 0.1403406073 |
| $O_{jj}\ (O_W)$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` | 1008 | 1215 | 8.883643187780406 | 1.3631981225429635 | 0.1534503462 |
| $O_{jj}\ (O_W)$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` | 2072 | 2538 | $I_e + I_\mu =$ 17.37881109 | $I_e + I_\mu =$ 2.555415144 | 0.1470420002 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` | 1064 | 1323 | 8.576818452904579 | 2.202669080356562 | 0.2568165681 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` | 1008 | 1215 | 9.42454726292643 | 3.346593636322913 | 0.3550933051 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` | 2072 | 2538 | $I_e + I_\mu =$ 18.00136572 | $I_e + I_\mu =$ 5.549262717 | 0.3082689838 |


## Additional Comparison Plots (Ch. 4.5.5)
Created a new script `plot_four_hist.py` in `src/ilc_tth_cpv/` to plot four curves in a single figure:
- reco SM vs reco signed CPV-interference
- gen SM vs gen signed CPV-interference
SM bins are scaled by 0.1 (SM/10) for better visibility and make it easier to compare with CPV-interference.

Separate plots are generated for electron and muon categories in each execution. The observable (O_W or O_lD) can be specified via command-line arguments.

Frame (higgs_rest, lab, ttbar_rest) can also be specified via command-line arguments.

To run:
```
python3 src/ilc_tth_cpv/plot_four_hist.py \
  --observable O_W \
  --frame higgs_rest
```

Output:
```
outputs/angular_lr/angular/O_W/joint_likelihood/O_W_all_sm_vs_cpv_gen_vs_reco_electron_bins.png
outputs/angular_lr/angular/O_W/joint_likelihood/O_W_all_sm_vs_cpv_gen_vs_reco_muon_bins.png

outputs/angular_lr/angular/O_lD/joint_likelihood/O_lD_all_sm_vs_cpv_gen_vs_reco_electron_bins.png
outputs/angular_lr/angular/O_lD/joint_likelihood/O_lD_all_sm_vs_cpv_gen_vs_reco_muon_bins.png
```

## Frame Study (Ch. 4.4.3)
All output above used the default frame, `higgs_rest`.
### 1. `lab` frame
#### 1.1 Export Features
Created `configs/analysis_angular_lr_lab.yaml` and set `default_frame: lab`.

Base input:
```
python3 scripts/export_features.py \
  --config configs/analysis_angular_lr_lab.yaml \
  --level gen \
  --component sm \
  --chunk 0
```

Produced (CPV):
```
outputs/angular_lr_lab/features/features_gen_higgs_rest_chunk0.csv
outputs/angular_lr_lab/features/features_gen_higgs_rest_chunk0.meta.json

outputs/angular_lr_lab/features/features_reco_higgs_rest_chunk0.csv
outputs/angular_lr_lab/features/features_reco_higgs_rest_chunk0.meta.json
```

Produced (SM):
```
outputs/angular_lr_lab/features/features_sm_gen_lab_chunk0.csv
outputs/angular_lr_lab/features/features_sm_gen_lab_chunk0.meta.json

outputs/angular_lr_lab/features/features_sm_reco_lab_chunk0.csv
outputs/angular_lr_lab/features/features_sm_reco_lab_chunk0.meta.json
```

#### 1.2 Build angular observables
Base Input (CPV):
```
python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr_lab.yaml \
  --features outputs/angular_lr_lab/features/features_gen_lab_chunk0.csv \
  --observable O_W \
  --split all \
  --lepton-flavor electron \
  --output-tag gen_electron
```

Base Input (SM):
```
python3 scripts/build_angular_observable.py \
  --config configs/analysis_angular_lr_lab.yaml \
  --features outputs/angular_lr_lab/features/features_sm_gen_lab_chunk0.csv \
  --observable O_W \
  --split all \
  --weight-column weight_sm \
  --lepton-flavor electron \
  --output-tag sm_gen_electron
```

Produced: <br>
All files are on 
- O_W: `outputs/angular_lr_lab/angular/O_W`
- O_lD: `outputs/angular_lr_lab/angular/O_lD`

#### 1.3 Calculate Fisher Information

| Observable | Lepton category | Gen population | Reco population | Frame | $N_{\text{gen}}$ | $N_{\text{reco}}$ | $I_{\text{gen}}$ | $I_{\text{reco}}$ | $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `lab` | 1064 | 1323 | 3.4739567161702447 | 1.3866406525629114 | 0.3991531173 |
| $O_{jj}\ (O_W)$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `lab` | 1008 | 1215 | 4.2117530909483065 | 1.2584917076540516 | 0.2988047211 |
| $O_{jj}\ (O_W)$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `lab` | 2072 | 2538 | $I_e + I_\mu =$ 7.685709807 | $I_e + I_\mu =$ 2.64513236 | 0.3441624035 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `lab` | 1064 | 1323 |  1.886180439729501 | 0.9299193474038754 | 0.4930171726 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `lab` | 1008 | 1215 |  1.8638692419128255 | 1.4025894528999923  | 0.7525149412 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `lab` | 2072 | 2538 | $I_e + I_\mu =$ 3.750049682 | $I_e + I_\mu =$ 2.3325088 | 0.6219941062 |

### 2. `ttbar_rest` frame
Produced: <br>
All files are on 
- O_W: `outputs/angular_lr_ttbar_rest/angular/O_W`
- O_lD: `outputs/angular_lr_ttbar_rest/angular/O_lD`

| Observable | Lepton category | Gen population | Reco population | Frame | $N_{\text{gen}}$ | $N_{\text{reco}}$ | $I_{\text{gen}}$ | $I_{\text{reco}}$ | $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `ttbar_rest` | 1064 | 1323 | 1.8096434531980166 | 0.8180989115551697 | 0.4520774024 |
| $O_{jj}\ (O_W)$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `ttbar_rest` | 1008 | 1215 | 2.1305163901406736 | 1.37752157362855 | 0.6465669919 |
| $O_{jj}\ (O_W)$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `ttbar_rest` | 2072 | 2538 | $I_e + I_\mu =$ 3.940159843 | $I_e + I_\mu =$ 2.195620485 | 0.5572414756 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `ttbar_rest` | 1064 | 1323 | 1.4632860464897457 | 0.9007705483003049 | 0.6155806313 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `ttbar_rest` | 1008 | 1215 | 1.8800197000334817 | 1.1422979981077648 | 0.6075989513 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `ttbar_rest` | 2072 | 2538 | $I_e + I_\mu =$ 3.343305747 | $I_e + I_\mu =$ 2.043068546 | 0.6110923441 |


### 3. Comparison of All Frames (Fisher Information)

| Observable | Lepton category | `higgs_rest`: $I_{\text{reco}} / I_{\text{gen}}$ | `lab`: $I_{\text{reco}} / I_{\text{gen}}$ | `ttbar_rest`: $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | 0.1403406073 | 0.3991531173 | 0.4520774024 |
| $O_{jj}\ (O_W)$ | muon | 0.1534503462 | 0.2988047211 | 0.6465669919 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | 0.2568165681 | 0.4930171726 | 0.6155806313 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | 0.3550933051 | 0.7525149412 | 0.6075989513 |


## More Chunks (1-10) Combined 
### 1. Export files for combined chunk
- Use `scripts/combine_angular_templates.py` to compute the O_W/O_lD plot, .csv, and .json files for combined chunks (1-10).

Input (O_W, electron):
```
python3 scripts/combine_angular_templates.py \
        --chunks 1-10 \
        --compare-plot \
        --reco-cpv-csv "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_reco_electron_chunk{chunk}_bins.csv" \
        --reco-cpv-meta "outputs/angular_lr/features/chunk1-10/features_reco_higgs_rest_chunk{chunk}.meta.json" \
        --reco-sm-csv  "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_reco_electron_chunk{chunk}_bins.csv" \
        --reco-sm-meta  "outputs/angular_lr/features/chunk1-10/features_sm_reco_higgs_rest_chunk{chunk}.meta.json" \
        --gen-cpv-csv  "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_gen_electron_chunk{chunk}_bins.csv" \
        --gen-cpv-meta  "outputs/angular_lr/features/chunk1-10/features_gen_higgs_rest_chunk{chunk}.meta.json" \
        --gen-sm-csv   "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_gen_electron_chunk{chunk}_bins.csv" \
        --gen-sm-meta   "outputs/angular_lr/features/chunk1-10/features_sm_gen_higgs_rest_chunk{chunk}.meta.json" \
        --out-dir outputs/angular_lr/angular/O_W \
        --tag O_W_electron
```

Input (O_W, muon):
```
python3 scripts/combine_angular_templates.py \
        --chunks 1-10 \
        --compare-plot \
        --reco-cpv-csv "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_reco_muon_chunk{chunk}_bins.csv" \
        --reco-cpv-meta "outputs/angular_lr/features/chunk1-10/features_reco_higgs_rest_chunk{chunk}.meta.json" \
        --reco-sm-csv  "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_reco_muon_chunk{chunk}_bins.csv" \
        --reco-sm-meta  "outputs/angular_lr/features/chunk1-10/features_sm_reco_higgs_rest_chunk{chunk}.meta.json" \
        --gen-cpv-csv  "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_gen_muon_chunk{chunk}_bins.csv" \
        --gen-cpv-meta  "outputs/angular_lr/features/chunk1-10/features_gen_higgs_rest_chunk{chunk}.meta.json" \
        --gen-sm-csv   "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_gen_muon_chunk{chunk}_bins.csv" \
        --gen-sm-meta   "outputs/angular_lr/features/chunk1-10/features_sm_gen_higgs_rest_chunk{chunk}.meta.json" \
        --out-dir outputs/angular_lr/angular/O_W \
        --tag O_W_muon
```

Input (O_lD, electron):
```
python3 scripts/combine_angular_templates.py \
        --chunks 1-10 \
        --compare-plot \
        --reco-cpv-csv "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_reco_electron_chunk{chunk}_bins.csv" \
        --reco-cpv-meta "outputs/angular_lr/features/chunk1-10/features_reco_higgs_rest_chunk{chunk}.meta.json" \
        --reco-sm-csv  "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_sm_reco_electron_chunk{chunk}_bins.csv" \
        --reco-sm-meta  "outputs/angular_lr/features/chunk1-10/features_sm_reco_higgs_rest_chunk{chunk}.meta.json" \
        --gen-cpv-csv  "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_gen_electron_chunk{chunk}_bins.csv" \
        --gen-cpv-meta  "outputs/angular_lr/features/chunk1-10/features_gen_higgs_rest_chunk{chunk}.meta.json" \
        --gen-sm-csv   "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_sm_gen_electron_chunk{chunk}_bins.csv" \
        --gen-sm-meta   "outputs/angular_lr/features/chunk1-10/features_sm_gen_higgs_rest_chunk{chunk}.meta.json" \
        --out-dir outputs/angular_lr/angular/O_lD \
        --tag O_lD_electron
```

Input (O_lD, muon):
```
python3 scripts/combine_angular_templates.py \
        --chunks 1-10 \
        --compare-plot \
        --reco-cpv-csv "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_reco_muon_chunk{chunk}_bins.csv" \
        --reco-cpv-meta "outputs/angular_lr/features/chunk1-10/features_reco_higgs_rest_chunk{chunk}.meta.json" \
        --reco-sm-csv  "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_sm_reco_muon_chunk{chunk}_bins.csv" \
        --reco-sm-meta  "outputs/angular_lr/features/chunk1-10/features_sm_reco_higgs_rest_chunk{chunk}.meta.json" \
        --gen-cpv-csv  "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_gen_muon_chunk{chunk}_bins.csv" \
        --gen-cpv-meta  "outputs/angular_lr/features/chunk1-10/features_gen_higgs_rest_chunk{chunk}.meta.json" \
        --gen-sm-csv   "outputs/angular_lr/angular/O_lD/chunk1-10/chunk{chunk}/O_lD_all_sm_gen_muon_chunk{chunk}_bins.csv" \
        --gen-sm-meta   "outputs/angular_lr/features/chunk1-10/features_sm_gen_higgs_rest_chunk{chunk}.meta.json" \
        --out-dir outputs/angular_lr/angular/O_lD \
        --tag O_lD_muon
```

Output (for electron only): 

**Output files are under `chunk1-10` folder in each angular observable folder.**

```
outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_gen_combined_bins.csv
outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_gen_combined_bins.meta.json

outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_sm_gen_combined_bins.csv
outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_sm_gen_combined_bins.meta.json

outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_reco_combined_bins.csv
outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_reco_combined_bins.meta.json

outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_sm_reco_combined_bins.csv
outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_sm_reco_combined_bins.meta.json

outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_gen_vs_reco_cpv_vs_sm_combined.png
```

### 2. Calculate Fisher Information
#### 2.1 `higgs_rest` frame
Input (O_W, electron, gen):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_gen_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_sm_gen_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_gen.fisher.json
```

Input (O_W, muon, gen):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_W/chunk1-10/O_W_muon_chunk1-10_gen_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_W/chunk1-10/O_W_muon_chunk1-10_sm_gen_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_W/chunk1-10/O_W_muon_chunk1-10_gen.fisher.json
```

Input (O_lD, electron, gen):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_electron_chunk1-10_gen_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_electron_chunk1-10_sm_gen_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_electron_chunk1-10_gen.fisher.json
```

Input (O_lD, muon, gen):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_muon_chunk1-10_gen_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_muon_chunk1-10_sm_gen_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_muon_chunk1-10_gen.fisher.json
```

Input (O_W, electron, reco):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_reco_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_sm_reco_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_W/chunk1-10/O_W_electron_chunk1-10_reco.fisher.json
```

Input (O_W, muon, reco):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_W/chunk1-10/O_W_muon_chunk1-10_reco_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_W/chunk1-10/O_W_muon_chunk1-10_sm_reco_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_W/chunk1-10/O_W_muon_chunk1-10_reco.fisher.json
```

Input (O_lD, electron, reco):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_electron_chunk1-10_reco_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_electron_chunk1-10_sm_reco_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_electron_chunk1-10_reco.fisher.json
```

Input (O_lD, muon, reco):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_muon_chunk1-10_reco_combined_bins.csv \
        --sm-template outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_muon_chunk1-10_sm_reco_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr/angular/O_lD/chunk1-10/O_lD_muon_chunk1-10_reco.fisher.json
```

Output:
```
outputs/angular_lr/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_gen.fisher.json
outputs/angular_lr/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_reco.fisher.json

outputs/angular_lr/angular/O_W/chunk_1-10/O_W_muon_chunk1-10_gen.fisher.json
outputs/angular_lr/angular/O_W/chunk_1-10/O_W_muon_chunk1-10_reco.fisher.json

outputs/angular_lr/angular/O_lD/chunk_1-10/O_lD_electron_chunk1-10_gen.fisher.json
outputs/angular_lr/angular/O_lD/chunk_1-10/O_lD_electron_chunk1-10_reco.fisher.json

outputs/angular_lr/angular/O_lD/chunk_1-10/O_lD_muon_chunk1-10_gen.fisher.json
outputs/angular_lr/angular/O_lD/chunk_1-10/O_lD_muon_chunk1-10_reco.fisher.jso4+n
```

| Observable | Lepton category | Gen population | Reco population | Frame | $N_{\text{gen}}$ | $N_{\text{reco}}$ | $I_{\text{gen}}$ | $I_{\text{reco}}$ | $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` |  |  | 7.9338364292670125 | 0.3752751568988437 | 0.04730059162 |
| $O_{jj}\ (O_W)$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` |  |  | 7.74643456580977 | 0.2635881333035203 | 0.03402702638 |
| $O_{jj}\ (O_W)$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` |  |  | $I_e + I_\mu =$ 15.680271 | $I_e + I_\mu =$ 0.6388632902 | 0.04074312811 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` |  |  | 8.040236627440306 | 1.3281079392986155 | 0.1651826931 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` |  |  | 8.135175165809148 | 1.3947006277514555 | 0.1714407618 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` |  |  | $I_e + I_\mu =$ 16.17541179 | $I_e + I_\mu =$ 2.722808567 | 0.1683300928 |

#### 2.2 Other frames
`lab` frame

Base Input:
```
python3 scripts/combine_angular_templates.py \
        --chunks 1-10 \
        --compare-plot \
        --feature-meta-pattern "outputs/angular_lr_lab/features/chunk1-10/features_gen_lab_chunk{chunk}.meta.json" \
        --reco-cpv-pattern "outputs/angular_lr_lab/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_reco_electron_chunk{chunk}_bins.csv" \
        --reco-sm-pattern  "outputs/angular_lr_lab/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_reco_electron_chunk{chunk}_bins.csv" \
        --gen-cpv-pattern  "outputs/angular_lr_lab/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_gen_electron_chunk{chunk}_bins.csv" \
        --gen-sm-pattern   "outputs/angular_lr_lab/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_gen_electron_chunk{chunk}_bins.csv" \
        --out-dir outputs/angular_lr_lab/angular/O_W \
        --tag O_W_electron
```

**followings are not updated yet**

Base Input (Fisher):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr_lab/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_reco_combined_bins.csv \
        --sm-template outputs/angular_lr_lab/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_sm_reco_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr_lab/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_reco.fisher.json
```


| Observable | Lepton category | Gen population | Reco population | Frame | $N_{\text{gen}}$ | $N_{\text{reco}}$ | $I_{\text{gen}}$ | $I_{\text{reco}}$ | $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `lab` | 10792 | 13343 | 3.130581638208485 | 0.3482550399514282 | 0.1112429191 |
| $O_{jj}\ (O_W)$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `lab` | 10558 | 12775 | 2.9898720814711726 | 0.1832275545347169 | 0.06128274038 |
| $O_{jj}\ (O_W)$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `lab` |  |  | $I_e + I_\mu =$ 6.12045372 | $I_e + I_\mu =$ 0.6368255587 | 0.10404875 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `lab` | 10792 | 13343 | 0.6082786705337033 | 0.1425834647429117 | 0.2344048405 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `lab` |  10558 | 12775 | 0.6905160758656582 | 0.14412731089810796 | 0.2087240485 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `lab` |  |  | $I_e + I_\mu =$ 1.298794746 | $I_e + I_\mu =$ 0.2867107756 | 0.2207514132 |

`ttbar_rest` frame
Base Input:
```
python3 scripts/combine_angular_templates.py \
    --chunks 1-10 \
    --compare-plot \
    --reco-cpv-pattern "outputs/angular_lr_ttbar_rest/angular/O_lD/chunk_1-10/chunk{chunk}/O_lD_all_reco_electron_chunk{chunk}_bins.csv" \
    --reco-sm-pattern  "outputs/angular_lr_ttbar_rest/angular/O_lD/chunk_1-10/chunk{chunk}/O_lD_all_sm_reco_electron_chunk{chunk}_bins.csv" \
    --gen-cpv-pattern  "outputs/angular_lr_ttbar_rest/angular/O_lD/chunk_1-10/chunk{chunk}/O_lD_all_gen_electron_chunk{chunk}_bins.csv" \
    --gen-sm-pattern   "outputs/angular_lr_ttbar_rest/angular/O_lD/chunk_1-10/chunk{chunk}/O_lD_all_sm_gen_electron_chunk{chunk}_bins.csv" \
    --out-dir outputs/angular_lr_ttbar_rest/angular/O_lD \
    --tag O_lD_electron
```

Base Input (Fisher):
```
python3 scripts/evaluate_fisher.py \
        --template outputs/angular_lr_ttbar_rest/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_reco_combined_bins.csv \
        --sm-template outputs/angular_lr_ttbar_rest/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_sm_reco_combined_bins.csv \
        --luminosity-scale 8000 \
        --out outputs/angular_lr_ttbar_rest/angular/O_W/chunk_1-10/O_W_electron_chunk1-10_reco.fisher.json
```

| Observable | Lepton category | Gen population | Reco population | Frame | $N_{\text{gen}}$ | $N_{\text{reco}}$ | $I_{\text{gen}}$ | $I_{\text{reco}}$ | $I_{\text{reco}} / I_{\text{gen}}$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $O_{jj}\ (O_W)$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `ttbar_rest` | 10792 | 13343 | 0.9008688807685551 | 0.22532621140069078 | 0.2501209845 |
| $O_{jj}\ (O_W)$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `ttbar_rest` | 10558 | 12775 | 0.9322779095649241 | 0.1844631953187181 | 0.1978628834 |
| $O_{jj}\ (O_W)$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `ttbar_rest` |  |  | $I_e + I_\mu =$ 1.83314679 | $I_e + I_\mu =$ 0.4097894067 | 0.2235442404 |
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `ttbar_rest` | 10792 | 13343 | 0.4070811955363107 | 0.2002197603343643 | 0.4918423217 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `ttbar_rest` | 10558 | 12775 | 0.30379145640583227 | 0.1940640253045214 | 0.6388067249 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `ttbar_rest` |  |  | $I_e + I_\mu =$ 0.7108726519 | $I_e + I_\mu =$ 0.3942837856 | 0.5546475653 |
