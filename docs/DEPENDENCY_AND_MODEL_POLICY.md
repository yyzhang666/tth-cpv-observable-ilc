# Dependency And Model Policy

The baseline separates always-needed analysis code from optional model studies.
A fresh NAF account should not need private Python installs for inspection,
generator feature export, or the standard Marlin/kinfit smoke tests once the
ZHH stack is sourced.

## Dependency Tiers

| Tier | Purpose | Expected source |
|---|---|---|
| core | configs, CSV/metadata IO, frames, angles, sidecar weights | standard Python + this repo |
| lcio-marlin | STDHEP/SLCIO inspection, ROOT validation, TTHSemiLepKinFit | `env/setup.sh` / ZHH stack |
| baseline-ml | default CP classifier (`xgboost`) | key4hep/ZHH stack on NAF |
| classical-ml | CatBoost/sklearn/LightGBM comparisons | optional managed environment |
| plotting | PNG diagnostics and notebook figures | optional local/shared env |

The default model is `xgboost`, because it is expected in the NAF software
stack. CatBoost is optional, not a reason to block the baseline.

## Model Profiles

Profiles live in `configs/model_profiles.yaml`.

```bash
python3 scripts/check_model_profile.py
python3 scripts/check_model_profile.py --profile xgboost_baseline
python3 scripts/check_model_profile.py --profile catboost_optional
python3 scripts/check_model_profile.py --profile marlin_kinfit --strict
```

The checker is informational unless `--strict` is set.

## Extension Rules

- Every new model gets a profile entry before a new training script relies on
  it.
- Optional imports stay inside the profile-specific code path.
- Saved model metadata records model type, feature list, class order, score
  definition, training weight policy, and input table.
- Classifier scores must map back to the frozen convention:

```text
O_ML = P(+) - P(-)
class_order = [-1, +1]
```

Physics templates always use signed, class-unbalanced weights. Training may use
`|w_int|` and class balancing, but that stays in `weight_training` and model
metadata.
