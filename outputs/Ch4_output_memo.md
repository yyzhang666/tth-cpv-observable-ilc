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
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` | 1064 | 1064 | 8.576818452904579 | 2.202669080356562 | 0.2568165681 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` | 1008 | 2248 | 9.42454726292643 | 3.346593636322913 | 0.3550933051 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` | 2072 | 1215 | $I_e + I_\mu =$ 18.00136572 | $I_e + I_\mu =$ 5.549262717 | 0.3082689838 |


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


## More Chunks (1~10)
**IMPORTANT NOTE**
I used AI to create a script (`scripts/summarize_fisher_info_per_chunk.py`) to extract the Fisher information and n_events_filled  from each chunk's JSON files, compiling them into a single summary CSV table. The table below displays this output; however, the script still requires code review, so these values are pending final verification.

| Chunk | Observable | Lepton Category | Frame | N_gen | N_reco | I_gen | I_reco | I_reco / I_gen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | O_lD | electron | higgs_rest | 1049 | 1311 | 8.0853 | 2.0869 | 0.2581 |
| **1** | O_lD | muon | higgs_rest | 1058 | 1249 | 10.1370 | 2.8403 | 0.2802 |
| **1** | O_lD | combined likelihood (e+mu) | higgs_rest | 2107 | 2560 | 18.2224 | 4.9272 | 0.2704 |
| **2** | O_lD | electron | higgs_rest | 1106 | 1385 | 9.9692 | 1.8295 | 0.1835 |
| **2** | O_lD | muon | higgs_rest | 1092 | 1294 | 11.1204 | 2.4675 | 0.2219 |
| **2** | O_lD | combined likelihood (e+mu) | higgs_rest | 2198 | 2679 | 21.0896 | 4.2970 | 0.2037 |
| **3** | O_lD | electron | higgs_rest | 1123 | 1389 | 10.9075 | 2.6797 | 0.2457 |
| **3** | O_lD | muon | higgs_rest | 1115 | 1340 | 8.5179 | 2.9515 | 0.3465 |
| **3** | O_lD | combined likelihood (e+mu) | higgs_rest | 2238 | 2729 | 19.4254 | 5.6312 | 0.2899 |
| **4** | O_lD | electron | higgs_rest | 1026 | 1266 | 8.4859 | 1.6161 | 0.1904 |
| **4** | O_lD | muon | higgs_rest | 1093 | 1319 | 10.0533 | 2.7349 | 0.2720 |
| **4** | O_lD | combined likelihood (e+mu) | higgs_rest | 2119 | 2585 | 18.5392 | 4.3511 | 0.2347 |
| **5** | O_lD | electron | higgs_rest | 1092 | 1335 | 8.5421 | 2.4869 | 0.2911 |
| **5** | O_lD | muon | higgs_rest | 1008 | 1266 | 9.5455 | 2.3777 | 0.2491 |
| **5** | O_lD | combined likelihood (e+mu) | higgs_rest | 2100 | 2601 | 18.0876 | 4.8646 | 0.2689 |
| **6** | O_lD | electron | higgs_rest | 1104 | 1382 | 9.5162 | 2.1367 | 0.2245 |
| **6** | O_lD | muon | higgs_rest | 1025 | 1245 | 8.1213 | 1.8252 | 0.2247 |
| **6** | O_lD | combined likelihood (e+mu) | higgs_rest | 2129 | 2627 | 17.6376 | 3.9619 | 0.2246 |
| **7** | O_lD | electron | higgs_rest | 1074 | 1343 | 10.3945 | 2.9801 | 0.2867 |
| **7** | O_lD | muon | higgs_rest | 1024 | 1247 | 8.4316 | 2.0436 | 0.2424 |
| **7** | O_lD | combined likelihood (e+mu) | higgs_rest | 2098 | 2590 | 18.8261 | 5.0237 | 0.2668 |
| **8** | O_lD | electron | higgs_rest | 1049 | 1323 | 8.6405 | 2.3642 | 0.2736 |
| **8** | O_lD | muon | higgs_rest | 1051 | 1267 | 10.0276 | 2.7159 | 0.2708 |
| **8** | O_lD | combined likelihood (e+mu) | higgs_rest | 2100 | 2590 | 18.6682 | 5.0801 | 0.2721 |
| **9** | O_lD | electron | higgs_rest | 1067 | 1297 | 9.6624 | 2.6085 | 0.2700 |
| **9** | O_lD | muon | higgs_rest | 1040 | 1237 | 9.0090 | 2.0004 | 0.2220 |
| **9** | O_lD | combined likelihood (e+mu) | higgs_rest | 2107 | 2534 | 18.6714 | 4.6089 | 0.2468 |
| **10** | O_lD | electron | higgs_rest | 1102 | 1312 | 10.6737 | 2.8081 | 0.2631 |
| **10** | O_lD | muon | higgs_rest | 1052 | 1311 | 11.1689 | 2.0441 | 0.1830 |
| **10** | O_lD | combined likelihood (e+mu) | higgs_rest | 2154 | 2623 | 21.8426 | 4.8522 | 0.2221 |

Still need to check other frames (chunk 1-10)...ongoing

