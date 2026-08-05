## Confirmation of output files (.csv and .json file)

**Running the code (from Ch 4.1.4):**

### 1. Export the CPV-interference features
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
wrote 2072 rows
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
- `O_W` and `O_lD` columns with finite values (not all-NaN)
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
outputs/angular_lr/angular/O_lD/O_lD_all_gen_electron.png
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
  higgs_mode::H->tautau: 768
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

Produced :
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
| $O_{\ell D}\ (O_{\ell D})$ | electron | $H \to b\bar{b}$, strict semileptonic $e$ | full accepted reco $e$ | `higgs_rest` | 1064 | 2407 | 8.576818452904579 | 2.202669080356562 | 0.2568165681 |
| $O_{\ell D}\ (O_{\ell D})$ | muon | $H \to b\bar{b}$, strict semileptonic $\mu$ | full accepted reco $\mu$ | `higgs_rest` | 1008 | 2248 | 9.42454726292643 | 3.346593636322913 | 0.3550933051 |
| $O_{\ell D}\ (O_{\ell D})$ | combined likelihood | $e + \mu$ categories | $e + \mu$ categories | `higgs_rest` | 2072 | 2538 | $I_e + I_\mu =$ 18.00136572 | $I_e + I_\mu =$ 5.549262717 | 0.3082689838 |


## Additional Comparison Plots (Ch. 4.5.5)

## Frame Study (Ch. 4.4.3)
All output above used the default frame, `higgs_rest`.
### 1. `lab` frame


### 2. `ttbar_rest` frame
