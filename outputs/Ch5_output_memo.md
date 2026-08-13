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
Input 1 (Write arguments.txt for the feature-export HTCondor workflow):
```
python3 make_arguments.py \
  --config ../../configs/analysis_ml_superdataset_lr.yaml \
  --chunks 0
```

Output 1: `condor/export_feature/arguments.txt`

Input 2 (Submit condor):
```
condor_submit submit_export_features.sub
```

Output 2: 
```
outputs/ml_superdataset/features/features_reco_higgs_rest_chunk0.csv
outputs/ml_superdataset/features/features_reco_higgs_rest_chunk0.meta.json
```

### 1.3  Run the whole condor workflow to get all ML dataset for the tth-cpv and tth-sm eLpR

Example Input (sm, chunk0, gen-level, higgs_rest frame):
```
python3 make_arguments.py \
  --config ../../configs/analysis_ml_superdataset_lr.yaml \
  --chunks 0 \
  --component sm \
  --level gen
  
condor_submit submit_export_features.sub
```
