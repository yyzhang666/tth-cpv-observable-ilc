# Yuyang observable-result catalog (2026-09-07)

This catalog freezes the interpretation of the research tree at
`/data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable`.  Its byte-level
snapshot and manifests live under `archive/yuyang_research_snapshot_20260907`.
The snapshot is evidence, not a second maintained codebase.

| Output directory | Producing investigation | Status / reproduction note |
|---|---|---|
| `angular_lr` | `run_secondary_chunk.py`, `derive_secondary_observables.py`, template combine and Fisher scripts | Signal-only Higgs-rest `O_lnu`, `O_b`, `O_top`, 10 chunks. See `docs/SECONDARY_OBSERVABLE_FULL_RUN_20260825.md` in the snapshot. |
| `angular_lr_lab` | `run_o_top_lab.py`, `summarize_o_top_lab.py`, `validate_o_top_lab.py` | Signal-only lab-frame `O_top`, 10 chunks. See `docs/O_TOP_LAB_FULL_RUN_20260825.md`. |
| `angular_2d_fisher` | `calculate_2d_angle_fisher.py`, `calculate_2d_angle_truth_fisher.py` | 2D angular Fisher and truth-category diagnostics; the `O_lD`/`O_lnu` 10x10 control record reports the exact configuration. |
| `angular_lr_ml_test` | `plot_o_lnu_ml_test_20bins.py`, `export_strongest_ml_observable_64bins.py` | Angle/ML test-split comparisons and the separate 64-bin ML observable export. |
| `event_csv_fisher_v0_validation` | former `evaluate_event_csv_fisher.py` | Superseded operationally by `scripts/workflows/run_event_fisher.py`; golden regression source. |
| `feature_distributions` | `plot_mttbar_feature_distributions.py` | Feature-shape diagnostic. |
| `ml_test_angle_agreement` | `analyze_ml_test_angle_agreement.py` | Pairwise angle/sign/correlation audit. See the 2026-08-31 control record. |
| `ml_truth_matching` | `analyze_ultimate_model_bjet_truth.py`, `run_sm_truth_checkpoints.py`, `calculate_bjet_truth_fisher.py`, plotting helpers | CPV/SM b-jet truth-matching diagnostic and checkpointed SM processing. |
| `mva_background_fisher_minimal2` | `run_mva_background_fisher.py` | Earlier minimal-2 event-selection/background diagnostic. |
| `mva_background_fisher_exact_signal_qsel` | `run_mva_background_fisher_exact_signal.py` | Exact signal-side `q_sel` rerun; superseded by the versioned event CSV workflow for supported observables. |
| `mva_background_fisher_exact_signal_qsel_rerun_validation` | same exact-signal command | Independent rerun-validation product. |
| `mva_background_fisher_lnu_wbjets_lepton_exact_qsel` | `run_mva_background_fisher_lnu_wbjets_lepton.py` | Final source of the v0 per-event background/SM/CPV tables; see `docs/MVA_BACKGROUND_FISHER_LNU_WBJETS_LEPTON_20260826.md`. |
| `neutrino_phi_olnu64_20260828` | `diagnose_neutrino_phi_and_olnu64.py` | Neutrino-phi and 64-bin `O_lnu` frame/binning diagnostic. |
| `O_lnu_ttbar_rest_fisher100_20260828` | `diagnose_neutrino_phi_and_olnu64.py` follow-up configuration | 100-bin ttbar-rest `O_lnu` diagnostic; not a maintained baseline. |
| `observable_comparison_64bins` | `plot_rescaled_observable_comparison_64bins.py` and flavor variant | Display-only rescaled comparison; use underlying Fisher JSON/CSV for numbers. |
| `optimal_observable_hbb_semilep_10chunks_64bins` | `build_optimal_observable_fisher_hbb_semilep.py` | Signal-only optimal-observable comparison over the same ten chunks. |
| `workflow_repro_validation_20260907` | maintained event workflow and multiclass schema smoke | Golden checks for ML-20, `O_lnu`-36, and future three-class table schema. |
| `superseded_chunk1_smoke_wrong_naming_20260825` | early smoke commands | Intentionally superseded; retain only to document the rejected naming/semantics. |

The frozen snapshot also contains every original investigation command,
run note, validation JSON, plot, and intermediate CSV.  For new results, use
`docs/OBSERVABLE_RESEARCH_WORKFLOW.md`; consult snapshot scripts only to
reproduce or audit a historical figure.
