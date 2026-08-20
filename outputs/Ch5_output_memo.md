## 1. Data Preparation (Ch. 5.1)

### 1.1 Check/Edit `export_features.py`
In `export_features.py` fixed:
-  Reconstructed top/anti-top slot. Modified `export_reco()` function to correctly assign top/anti-top daughters based on the lepton charge.
-  Deleted `O_b`, `O_top`, `O_lnu`, `y45`, `y56`, `y67`, and other information for kinfit that are not useful, such as `top_n`, `n_constraint`, `n_unmeasured`. (Just commented them out.)

In `export_features.py` and its output (`.csv` file), checked that they exist:
- Event Infomration: `event_id`, `chunk_id` (named `chunk` in `.csv`), `split`, `weight` (`weight_interference_signed`, `weight_interference_abs`, `weight_training`), `label`
- Lepton information: `lepton_E/theta/phi/mass`
- W_daughter information: `wjet_quark_E/theta/phi/mass`, `wjet_antiquark_E/theta/phi/mass`, `w_orientation_margin`
- Neutrino information: `nu_fit_px//py/pz/E`
- bbar from top: `top_b_E/theta/phi/mass`, `antitop_bbar_E/theta/phi/mass`
- Invariant mass: `mW_had_prefit`, `mW_had_postfit`, `mt_had_prefit`, `mt_had_postfit`, `mt_lep_prefit`, `mt_lep_postfit`, `mH_prefit`, `mH_postfit`
- Flavor tagging/assginment/KinFit score: `fitchi2`, `final_selection_score`, `final_fit_score`, `final_flavor_score`
- Helpful for debugging: `idx_W1`, `idx_W2`, `idx_W_quark`, `idx_W_antiquark`

Added:
- Lepton information: `lepton_px/py/pz/pt`
- Neutrino information: `nu_fit_pt/theta/phi`
- Invariant mass: `m_ttbar`
- - W_daughter information: `L12`, `L21` (down_assignment_probablity)

Missing (still need to add):

### 1.2 Prepare ML Analysis Configs
Create `analysis_ml_superdataset_lr.yaml`:
- Sample is set to `manifest: configs/samples.yaml`, `gen_sample: tthcpv_gen_elpr`, `reco_sample: tthcpv_reco_elpr`, `sm_gen_sample: tth_sm_gen_elpr`, and `sm_reco_sample: tth_sm_reco_elpr`
- Frame is set to `default_frame: higgs_rest`
- Split is set to `train: 0.6`, `validation: 0.2`, `test: 0.2`, and `seed: 20260720`
- Weights is set to `training_weight: weight_training`, `template_weight: weight_interference_signed`, and `sm_template_weight: weight_sm`
- Outputs is set to `base_dir: outputs/ml_superdataset`

Test Run <br>
Input (Write arguments.txt for the feature-export HTCondor workflow and then submit condor):
```
python3 make_arguments.py \
  --config ../../configs/analysis_ml_superdataset_lr.yaml \
  --chunks 0

condor_submit submit_export_features.sub
```

Output: 
```
condor/export_feature/arguments.txt

outputs/ml_superdataset/features/features_reco_higgs_rest_chunk0.csv
outputs/ml_superdataset/features/features_reco_higgs_rest_chunk0.meta.json
```


### 1.3  Run the whole condor workflow to get all ML dataset for the tth-cpv and tth-sm eLpR
Input 1 (cpv, chunk1-79, gen-level, higgs_rest frame):
```
python3 make_arguments.py \
  --config ../../configs/analysis_ml_superdataset_lr.yaml \
  --chunks 1-79 \
  --component interference \
  --level gen
  
condor_submit submit_export_features.sub
```
**STATUS: Re-Run Complete (2026/08/19)**

Input 2 (sm, chunk1-79, gen-level, higgs_rest frame):
```
python3 make_arguments.py \
  --config ../../configs/analysis_ml_superdataset_lr.yaml \
  --chunks 1-79 \
  --component sm \
  --level gen
  
condor_submit submit_export_features.sub
```
**STATUS: Error**

Input 3 (cpv, chunk1-79, reco-level, higgs_rest frame):
```
python3 make_arguments.py \
  --config ../../configs/analysis_ml_superdataset_lr.yaml \
  --chunks 1-79 \
  --component interference \
  --level reco
  
condor_submit submit_export_features.sub
```
**STATUS: Re-Run Complete (2026/08/19)**

Input 4 (sm, chunk1-79, reco-level, higgs_rest frame):
```
python3 make_arguments.py \
  --config ../../configs/analysis_ml_superdataset_lr.yaml \
  --chunks 1-79 \
  --component sm \
  --level reco
  
condor_submit submit_export_features.sub
```
**STATUS: Re-Run Complete(2026/08/20)**

### 1.4  Write a new script `/scripts/merge_feature_chunks.py`

Condition for the new code:
- [x] Merge the 80 chunk-level CSV files produced by `export_features.py` into a single superdataset, without recomputing selections, splits, weights, or features 
- [x] check that all chunks are present, the schemas are identical, and there are no duplicated events 
- [x] keep `lepton_flavor` so electron and muon channels can be selected later at training time 
- [x] report the total event count and the electron/muon train/validation/test and ± label counts 
- [x] write the merged dataset plus simple metadata under `outputs/ml_superdataset/features/` 

To Run (example: cpv, reco)
```
python3 scripts/merge_feature_chunks.py \
    --version v1 \
    --model cpv \
    --level reco \
    --chunks 1-79 
```

Output file example:
```
outputs/ml_superdataset/features/reco_cpv/features_reco_higgs_rest_chunk1_79.csv
outputs/ml_superdataset/features/reco_cpv/features_reco_higgs_rest_chunk1_79.meta.json
```

Status:
- gen, cpv **Run Complete (2026/08/19)**
- gen, sm **Features not produced**
- reco, cpv **Run Complete (2026/08/19)**
- reco, sm **Run Complete (2026/08/19)**

## 2. BDT Baseline Comparison (Ch. 5.2)
### 2.1 Modify Files Used for ML
Modify `analysis_ml_superdataset_lr.yaml` -> Complete

Modify the `/scripts/train_cpv_model.py` -> Complete
```
    # TODO: down_type_daughter is a virtual object.
    #
    # For features such as:
    #     down_type_daughter_E
    #     down_type_daughter_theta
    #     down_type_daughter_phi
    #     down_type_daughter_mass
    #
    # use:
    #     idx_W_down_candidate
    #     idx_W_quark
    #     idx_W_antiquark
    #
    # to decide whether the selected down-type jet corresponds to
    # wjet_quark or wjet_antiquark, then read the requested variable
    # from that object.
    #
    # Example logic:
    #
    # if feature_name.startswith("down_type_daughter_"):
    #     variable = feature_name.removeprefix("down_type_daughter_")
    #     ...
    #     return to_float(row[f"{selected_prefix}_{variable}"])


    # TODO: virtual auxiliary feature.
    #
    # w_assignment_likelihood_selected does not exist directly in the CSV.
    # Resolve it from L12 preference or L21 preference by the w_orientation_status
    # If it is L12 preference then return to L12
    # if feature_name == "w_assignment_likelihood_selected":
    #     ...
    #     return selected_L


    # TODO: electron / muon must be trained separately.
    # Do the next uncommented code under this for loop with two lepton flavors
    # for lepton_flavor in training_cfg["lepton_flavors"]:
    #     flavor_rows = [...] Judge if the lepton is muon or electron.
    #
    # Each category must produce an independent model and metadata file.


    # TODO: after electron/muon category splitting is implemented,
    # add the lepton flavor to the output path, for example:
    #
    #     model/lD/electron/
    #     model/lD/muon/
    # Also the meta data path also need to change later

```

### 2.2 Check the loss function and the precision 
Sample Input:
```
python3 scripts/train_cpv_model.py \
        --config configs/analysis_ml_superdataset_lr.yaml \
        --features outputs/ml_superdataset/features/reco_cpv/features_reco_higgs_rest_chunk1_79.csv \
        --feature-set lD
```

Output (electron):
```
outputs/ml_superdataset/model/lD/electron/cpv_xgboost.json
outputs/ml_superdataset/model/lD/electron/feature_importance.png
outputs/ml_superdataset/model/lD/electron/model_metadata.json
outputs/ml_superdataset/model/lD/electron/roc_curve.png
outputs/ml_superdataset/model/lD/electron/training_history.json
outputs/ml_superdataset/model/lD/electron/training_loss.png
```

Check logloss and precision:
- logloss (electron) => NOT CONVERGED!
  - Potential overfitting; train loss is decreasing over iterations, but validation loss increases
- precision (electron): 0.5177
- AUC Score
  - Validation: 0.5
  - Test: 0.521 

- logloss (muon) => NOT CONVERGED!
  - Potential overfitting; train loss is decreasing over iterations, but validation loss increases 
- precision (electron): 0.4658
- AUC Score
  - Validation: 0.578
  - Test: 0.426


### 2.3 Model Improvement
#### 2.3.1 Tuning Parameters
Modify `model:`, `params:` in `configs/analysis_ml_superdataset_lr.yaml` to tune the parameter.

Parameters and Scores:
| Scores | Parameters | Trial 1 | Trial 2 | Trial 3 | Trial 4 | Trial 5 | Trial 6 | Trial 7 | Trial 8 | Trial 9 |
|--------|------------|---------|---------|---------|---------|---------|---------|---------|---------|---------|
|  | n_estimators | 200 | 150 | 200 | 200 | 200 | 200 | 500 | 200 | 200 |
|  | max_depth | 6 | 6 | 3 | 4 | 4 | 4 | 4 | 6 | 6 |
|  | learning_rate| 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 0.05 | 0.05 | 0.05 | 0.05 |
|  | early_stopping_rounds| -- | -- | -- | -- | 20 | 20 | 20 | 20 | -- |
|  | random_seed | 20260720 | 20260720 | 20260720 | 20260720 | 20260720 | 20260720 | 20260720 | 42 | 42 |
|  |  |  |  |  |  |  |  |  |  |  |
| Precision | electron | 0.5032 | 0.5030 | 0.5027 | 0.5053 | 0.4952 | 0.4974 | 0.4974 | 0.5006 | 0.5026 |
| AUC: Train | electron | 0.814 | 0.785 | 0.604 | 0.664 | 0.535 | 0.520 | 0.520 | 0.535 | 0.750 |
| AUC: Validate | electron | 0.494 | 0.495 | 0.499 | 0.502 | 0.495 | 0.490 | 0.490 | 0.497 | 0.499 |
| AUC: Test | electron | 0.500 | 0.523 | 0.498 | 0.498 | 0.494 | 0.495 | 0.495 | 0.500 | 0.499 |
| Loss Curve: Validation | electron | overfit | overfit | overfit | overfit | overfit | overfit | overfit | overfit? | overfit? |
| Precision | muon | 0.5036 | 0.5050 | 0.5054 | 0.5067 | 0.4972 | 0.4996 | 0.4996 | 0.5066 | 0.5064 |
| AUC: Train | muon | 0.811 | 0.781 | 0.602 | 0.664 | 0.508 | 0.509 | 0.509 | 0.521 | 0.743 |
| AUC: Validate | muon | 0.495 | 0.493 | 0.497 | 0.491 | 0.499 | 0.499 | 0.499 | 0.495 | 0.490 |
| AUC: Test | muon | 0.506 | 0.443 | 0.503 | 0.505 | 0.499 | 0.500 | 0.500 | 0.502 | 0.506 |
| Loss Curve: Validation | muon | overfit | overfit | overfit | overfit | overfit | overfit | overfit | overfit? | overfit? |

#### 2.3.2 Let ML Learn `lepton_charge`
To let the ML learn the order of lepton or down-type-quark, add one another feature `lepton_charge` into the object `lepton` in the original config yaml to train. 

Parameters and Scores:
| Scores | Parameters | Trial 1 | Trial 2 | Trial 3 | Trial 4 | Trial 5 |
|--------|------------|---------|---------|---------|---------|---------|
|  | n_estimators | 200 |  |  |  |  |
|  | max_depth | 6 |  |  |  |  |
|  | learning_rate| 0.05 |  |  |  |  |
|  | early_stopping_rounds| -- |  |  |  |  |
|  | random_seed | 42 |  |  |  |  |
|  |  |  |  |  |  |  |
| Precision | electron | 0.5133 |  |  |  |  |
| AUC: Train | electron | 0.752 |  |  |  |  |
| AUC: Validate | electron | 0.515 |  |  |  |  |
| AUC: Test | electron | 0.514 |  |  |  |  | 
| Loss Curve: Validation | electron | overfit |  |  |  |  |
| Precision | muon | 0.5043 |  |  |  |  |
| AUC: Train | muon | 0.755 | 0. | 0. | 0. | 0. |
| AUC: Validate | muon | 0.507 | 0. | 0. | 0. | 0. |
| AUC: Test | muon | 0.507 | 0. | 0. | 0. | 0. |
| Loss Curve: Validation | muon | overfit |  |  |  |  |

#### 2.3.3 Version 2
Created `configs/analysis_ml_superdataset_lr_v2.yaml` and modified the features section to input with `top_side_fermion` and `anti_top_side_fermion` rather than `lepton` and `down_type_daughter`. For their kinematics, input `E`, `pt`, `theta`, `phi`, and `down_jet_mass` (to help identify the quark flavor). 

Create chunks 1-79:
```
python3 condor/export_feature/make_arguments_v2.py \
  --config configs/analysis_ml_superdataset_lr_v2.yaml \
  --chunks 1-79 \
  --component interference \
  --level reco
  
condor_submit condor/export_feature/submit_export_features_v2.sub
```
Outputs are in `outputs/ml_superdataset/features_v2`.

Combine chunks:
```
python3 scripts/merge_feature_chunks.py \
      --version v2 \
      --model cpv \
      --level reco \
      --chunks 1-79 
```
Outputs are in `outputs/ml_superdataset/features_v2`.

Train model:
```
python3 scripts/train_cpv_model_v2.py \
        --config configs/analysis_ml_superdataset_lr_v2.yaml \
        --features outputs/ml_superdataset/features_v2/reco_cpv/features_reco_higgs_rest_chunk1_79.csv \
        --feature-set lD
```

Outputs are in `outputs/ml_superdataset/model_v2/lD/xgboost`



#### 2.3.4 Version 0 (original version (v1) but without lepton_charge)
- Created `configs/analysis_ml_superdataset_lr_v0.yaml`
- Created `configs/analysis_ml_superdataset_lr_catboost_v0.yaml` for catboost
- Features are same as the v1, so they are used
- Created `script/train_cpv_model_v0.py` for training.

Input example (for catboost):
```
python3 scripts/train_cpv_model_v0.py \
  --config configs/analysis_ml_superdataset_lr_catboost_v0.yaml \
  --features outputs/ml_superdataset/features/reco_cpv/features_reco_higgs_rest_chunk1_79.csv \
  --feature-set lD
```

Outputs are in `outputs/ml_superdataset/model_v0/lD`

### 2.4 Build the ML Observable
#### 2.4.1 Build the ML Observable
Build the observable by the `scripts/build_ml_observable.py`.

- [x] Separate electron/muon 
- [x] Fix the weight

**NOTE (2026/08/20)**
I fixed the `scripts/build_ml_observable.py` so that it should work for both v1 and v2, regardless of their feature name, whether they contain `down_type_daughter_...` or not (which v2 should contain and v1 does not). Now, it should be ok to use `build_ml_observable.py` for both v1 and v2, by passing the `--version v2` argument. However, just in case, I copied the original code into `build_ml_observable_v2.py`, so for v2, `build_ml_observable_v2.py` can also be used fine.

Input (reco, cpv, electron, v2):
```
python3 scripts/build_ml_observable.py \
    --config configs/analysis_ml_superdataset_lr_v2.yaml \
    --features outputs/ml_superdataset/features_v2/reco_cpv/features_reco_higgs_rest_chunk1_79.csv \
    --model outputs/ml_superdataset/model_v2/lD/xgboost/electron/cpv_xgboost.json \
    --lepton-flavor electron \
    --version v2
```

Outputs are in `outputs/ml_superdataset/ml_observable_v2/xgboost`.

#### 2.4.3 Run All XGBoost
ML Observables:
- [x] reco, cpv, electron (v0: x, v1: x, v2: x)
- [x] reco, cpv, muon (v0: x, v1: x, v2: x)
- [x] reco, sm, electron
- [x] reco, sm, muon
- [ ] gen, cpv, electron
- [ ] gen, cpv, muon
- [ ] gen, sm, electron
- [ ] gen, sm, muon

### 2.5 CatBoost
#### 2.5.1 Prepare and Run for CatBoost
- Created `configs/analysis_ml_superdataset_lr_catboost.yaml`
- Created `configs/analysis_ml_superdataset_lr_catboost_v2.yaml`

Train model input example (v1):
```
python3 scripts/train_cpv_model.py \
        --config configs/analysis_ml_superdataset_lr_catboost.yaml \
        --features outputs/ml_superdataset/features/reco_cpv/features_reco_higgs_rest_chunk1_79.csv \
        --feature-set lD
```

Outputs (for v1) are in `outputs/ml_superdataset/model/lD/catboost`

Building ML observable input example (v2, electron, reco):
```
python3 scripts/build_ml_observable.py \
    --config configs/analysis_ml_superdataset_lr_catboost_v2.yaml \
    --features outputs/ml_superdataset/features_v2/reco_cpv/features_reco_higgs_rest_chunk1_79.csv \
    --model outputs/ml_superdataset/model_v2/lD/catboost/electron/cpv_catboost.cbm \
    --lepton-flavor electron \
    --version v2
```
#### 2.5.2 Run All CatBoost 
Run CatBoost model (Train Model):
- [x] Raw v1 (without lepton charge) = named as v0
- [x] v1+lepton charge
- [x] v2

Build ML Observables:
- [x] reco, cpv, electron (v0: x, v1: x, v2: x)
- [x] reco, cpv, muon (v0: x, v1: x, v2: x)
- [x] reco, sm, electron
- [x] reco, sm, muon
- [ ] gen, cpv, electron ... error when building v1, need to check
- [ ] gen, cpv, muon ... error when building v1, need to check
- [ ] gen, sm, electron
- [ ] gen, sm, muon


### 2.6 the Build Pipeline for ML Analysis
Build the similar pipeline as the angular observable from read models to the evaluate fisher.

File: `scripts/run_ml_observable_pipeline.sh`

How to run:
- `./scripts/run_ml_observable_pipeline.sh reco` or `./scripts/run_ml_observable_pipeline.sh gen`
- You need to specify if you want to run for reco/gen.

Running this file ...:
- creates ML observables for all:
  - different versions (v0, v1, and v2). They are contained in different folders (`outputs/ml_superdataset/ml_observable`, `outputs/ml_superdataset/ml_observable_v0`, and `outputs/ml_superdataset/ml_observable_v2`).
  - xgboost and catboost (in separate folders)
  - electron and muon (they have different file names, either `electron` or `muon`
  - cpv and sm
- evaluates fisher information for all:
  - different versions
  - electron and muon
  - cpv and sm


### 2.7 Fisher Information Comparison
#### 2.7.1 Current Status of ML Analysis Data Prep for Fisher Info Comparison

Create Features (both XGBoost and catboost):
- Raw v1 (without lepton_charge):
  - I think we can use the same feature file as v1
- v1 + lepton_charge:
  - [x] reco, cpv
  - [x] reco, sm
  - [x] gen, cpv
  - [ ] gen, sm ... Error, NEED CHECK
- v2: 
  - [x] reco, cpv
  - [x] reco, sm 
  - [x] gen, cpv 
  - [ ] gen, sm ... Error (below)

 
Error in v2, gen, sm:
```
Traceback (most recent call last):
File "/data/dust/user/ozakinan/analysis/tth-cpv-observable-ilc/scripts/export_features_v2.py", line 1227, in <module>
  raise SystemExit(main())
                   ^^^^^^
File "/data/dust/user/ozakinan/analysis/tth-cpv-observable-ilc/scripts/export_features_v2.py", line 1220, in main
  export_gen(cfg, args.chunk, args.max_events, args.component)
File "/data/dust/user/ozakinan/analysis/tth-cpv-observable-ilc/scripts/export_features_v2.py", line 575, in export_gen
  mc_list = [col.getElementAt(k) for k in range(col.getNumberOfElements())]
                                                ^^^^^^^^^^^^^^^^^^^^^^^^^
ReferenceError: attempt to access a null-pointer
```

ML Observable Production: <br>
- v0 (= Raw v1, without lepton_charge):
  - [ ] XGBoost
  - [ ] catboost
- v1 (+ lepton_charge):
  - [ ] XGBoost
  - [ ] catboost
- v2: 
  - [ ] XGBoost
  - [ ] catboost
 
#### 2.7.2 Fisher Information Calculation
Input example:
```
python3 scripts/evaluate_fisher.py \
  --template outputs/ml_superdataset/ml_observable_v2/xgboost/template_test_electron_reco_cpv_bins.csv \
  --sm-template outputs/ml_superdataset/ml_observable_v2/xgboost/template_test_electron_reco_sm_bins.csv \
  --luminosity-scale 8000
```

Output example:
```
outputs/ml_superdataset/ml_observable_v2/xgboost/template_test_electron_reco_cpv_bins.fisher.json
```

OR you can also use `script/run_ml_observable_pipeline.sh` mentioned above, which will creates ML observables and evaluate fisher for all!

| Observable | Lepton category | Frame | ML model | version | N gen | N reco | I gen | I reco | I reco / I gen |
|------------|-----------------|-------|----------|---------|-------|--------|-------|--------|----------------|
| O_ML | electron | higgs_rest | xgboost | v0 |  |  |  | 0.030311 |  |
| O_ML | muon | higgs_rest | xgboost | v0 |  |  |  | 0.0175953 |  |
| O_ML | electron + muon | higgs_rest | xgboost | v0 |  |  |  |  |  |
| O_ML | electron | higgs_rest | xgboost | v1 |  |  |  | 0.0391572 |  |
| O_ML | muon | higgs_rest | xgboost | v1 |  |  |  | 0.0270757 |  |
| O_ML | electron + muon | higgs_rest | xgboost | v1 |  |  |  |  |  |
| O_ML | electron | higgs_rest | xgboost | v2 |  |  |  | 0.8781519013438279 |  |
| O_ML | muon | higgs_rest | xgboost | v2 |  |  |  |  | 0.883595206181391 |
| O_ML | electron + muon | higgs_rest | xgboost | v2 |  |  |  |  |  |
| O_ML | electron | higgs_rest | catboost | v0 |  |  |  | 0.00316548 |  |
| O_ML | muon | higgs_rest | catboost | v0 |  |  |  | 0.00219951 |  |
| O_ML | electron + muon | higgs_rest | catboost | v0 |  |  |  |  |  |
| O_ML | electron | higgs_rest | catboost | v1 |  |  |  | 0.826041 |  |
| O_ML | muon | higgs_rest | catboost | v1 |  |  |  | 0.88406 |  |
| O_ML | electron + muon | higgs_rest | catboost | v1 |  |  |  |  |  |
| O_ML | electron | higgs_rest | catboost | v2 |  |  |  | 1.156579449909343 |  |
| O_ML | muon | higgs_rest | catboost | v2 |  |  |  | 1.1259856676365156 |  |
| O_ML | electron + muon | higgs_rest | catboost | v2 |  |  |  |  |  |



