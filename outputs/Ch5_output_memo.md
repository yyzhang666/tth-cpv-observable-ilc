## 1. Data Preparation (Ch. 5.1)

In `export_features.py` fixed:
-  Reconstructed top/anti-top slot. Modified `export_reco()` function to correctly assign top/anti-top daughters based on the lepton charge.
-  Deleted `O_b`, `O_top`, `O_lnu`, `y45`, `y56`, `y67`, and other information for kinfit that are not useful, such as `top_n`, `n_constraint`, `n_unmeasured`. (Just commented them out.)

In `export_features.py` and its output (`.csv` file), checked that they exist:
- Event Infomration: `event_id`, `chunk_id` (named `chunk` in `.csv`), `split`, `weight` (`weight_interference_signed`, `weight_interference_abs`, `weight_training`), `label`
- Lepton information: `lepton_E/theta/phi/mass`
- W_daughter information: `wjet_quark_E/theta/phi/mass`, `wjet_antiquark_E/theta/phi/mass`
- Neutrino information: `nu_fit_px//py/pz/E`
- bbar from top: `top_b_E/theta/phi/mass`, `antitop_bbar_E/theta/phi/mass`
- Invariant mass: 
- Flavor tagging/assginment/KinFit score: `fitchi2`, `final_selection_score`, `final_fit_score`, `final_flavor_score`
- Hepful for debugging: `idx_W1`, `idx_W2`, `idx_W_quark`, `idx_W_antiquark`

Added:
- f

Missing (still need to add):
- Lepton information: `lepton_px/py/pz/p_t/eta`
- W_daughter information: down_type_index, down_assignment_probablity(L12 or L21), margin
- Neutrino information: `nu_fit_pt/eta/phi`
- Invariant mass: `m_W_had`, `m_top_had`, `m_top_lep`, `m_ttbar`, `m_H` (some in the kinfit root, m_ttbar need to calculate by the two tops)
