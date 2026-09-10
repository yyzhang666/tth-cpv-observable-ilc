# CP-aware three-class workflow validation — 2026-09-10

## Contract and scope

- Reco-level `eLpR`, selected kinfit candidate, strict per-event
  `q_sel > 0.954`.
- Targets are `-1=CPV-`, `0=neutral`, `+1=CPV+`.
- Scheme `sm`: neutral is SM; background is test-scored but never trained.
- Scheme `sm-plus-background`: SM and background share neutral target 0.
- Observable is `q_threeclass = P(+1) - P(-1)`; Fisher remains
  `sum S1**2/(S0+B)`, evaluated separately for electron and muon and then
  added.

## Data, weights, and split controls

- CPV target follows the sign of the interference template and is checked
  against any input label.  Its loss weight is nonnegative
  `abs(template_weight)` by default.
- SM/background template weights must be nonnegative.  Scheme 2 uses one
  neutral-class scale, so the physical SM:background ratio is unchanged.
- Authoritative row splits are preserved; otherwise the logical job/chunk
  group is hashed.  One group cannot cross splits.
- Formal readiness requires positive SM and all three target-class weights in
  every flavor/split.  Background must have positive test coverage for both
  flavors; scheme 2 additionally requires positive background train and
  validation coverage.
- Explicit input tables must either assert that every role/flavor test subset
  already represents 8 ab-1 or provide six projection factors.  Source
  weight, factor, and projected test template weight are all recorded and
  bound to the manifest SHA-256.

## Validation evidence

- Focused suite: `45 passed` for dataset construction, projection, negative
  guards, shared feature resolution, both tiny CatBoost schemes, plots, score
  CSVs, and downstream Fisher.
- Real v0 schema smoke after the strict cut: 55,860 retained rows = 7,222
  background + 24,434 SM + 24,204 CPV; CPV contains 12,071 negative and
  12,133 positive rows.  Every v0 row remains `split=test`.
- Both v0 schemes are correctly marked non-trainable because SM/CPV have no
  train or validation rows; scheme 2 also reports the missing background
  train/validation cells.
- Full repository suite retains only the pre-existing baseline failures:
  five `tests/test_flavor.py` expectations and two missing `mc_list` fixtures
  in `tests/test_objects.py`.
- SOL physics planning and independent SOL mistake review completed; the
  final review status is `PASS`.

NAF execution could not be repeated in this session because Nana's account
rejected the available SSH public key.  The focused end-to-end run used
CatBoost 1.2.10 locally.  No formal physics model or Fisher number is claimed
until full train/validation/test tables and their exposure projection factors
are supplied.
