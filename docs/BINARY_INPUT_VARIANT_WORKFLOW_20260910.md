# CPV 二分类输入变量变体研究工作流（v0）

> 状态：实施前冻结方案。本文档本身不执行数据导出、训练或绘图。
>
> 用途：把本文档原样交给新的 Codex 对话，即可在不修改 Nana 原始脚本和结果的前提下开始实施。

## 1. 目标

沿用 Nana 已验证的 reco-level CPV 二分类工作流，在相同数据、事件选择、训练/验证/测试划分、权重、Higgs rest frame、电子/缪子通道和 Fisher 定义下，只改变输入特征，比较以下模型：

1. 六个 top 衰变产物的极简、无 top/anti-top 电荷排序输入；
2. 在 1 的基础上加入两个 Higgs-assigned b jets；
3. lepton/neutrino 按 fermion/anti-fermion 排序后替换裸输入；
4. 保留裸 lepton/neutrino，同时追加 fermion/anti-fermion 排序输入；
5. 仅输入 `O_lD、O_lnu、O_W、O_b` 和 selection/mass auxiliaries；
6. 保留当前 W-jet hard assignment，同时追加 d/s soft likelihood；
7. 用 `sin(phi)、cos(phi)、cos(theta)` 替换原始 `phi、theta`。

后续可单独研究 top-b、down-type W jet、lepton 的组合角变量，但不把尚未冻结的组合混入 v0 首批模型。

## 2. 不做的事

- 不修改、覆盖或删除 Nana 冻结副本中的任何文件。
- 不修改已有训练脚本、旧配置、旧模型或旧输出。
- 不触碰 `/data/dust/user/zhangyuy/tth-cpv-observable-ilc` 中现有的 MVA 工作。
- 不重跑 Marlin、kinfit 或大规模 LCIO production。
- 不在训练中加入 SM 或背景；本研究仍是 CPV `+/-` 二分类。SM 只用于形成匹配的 Fisher denominator。
- 不使用 test 集调参或决定 early stopping。
- 不把不同模型逐步累积成“大杂烩”；除明确标注的扩展模型外，每项都是相对固定基线的一因素对照。

## 3. 路径和只读边界

### 3.1 唯一允许写入的 NAF 工作副本

```text
/data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable/worktrees/
  tth-cpv-observable-ilc-ozakinan-repro-20260907
```

该副本应位于 `observable_workflow` 分支。新脚本、新配置和新输出全部位于这里。

### 3.2 永久只读的 Nana 冻结副本

```text
/data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable/archive/
  nana_naf_snapshot_20260907/dust/analysis/tth-cpv-observable-ilc
```

允许从这里读取旧脚本、配置、合并 CSV、模型 metadata 和原始结果；禁止写入。

### 3.3 禁止改动的独立 MVA 仓库

```text
/data/dust/user/zhangyuy/tth-cpv-observable-ilc
```

### 3.4 新输出根目录

```text
outputs/binary_input_variants_v0/
├── features/
├── models/
├── scores/
├── templates/
├── fisher/
├── plots/
├── manifests/
└── logs/
```

每个模型使用唯一 variant name，绝不复用旧输出路径。

## 4. 固定的物理、数据和训练合同

所有变体必须共享以下合同，任何偏离都要停止并报告：

- frame：reco Higgs rest frame；
- topology/selection：与 Nana `features_v2/reco_cpv` 和 `features_v2/reco_sm` 完全一致；
- Higgs decay：沿用原工作流的 H→bb truth filtering；
- channels：electron、muon 分开训练和评估，随后按原方法组合；
- CPV labels：`+1` 与 `-1`；
- SM：不参与训练，只通过同一模型得到 score/template；
- split：`train/validation/test = 0.6/0.2/0.2`，沿用既有 `split` 列，禁止重新抽样；
- data split seed provenance：`20260720`；
- model random seed：`42`；
- CatBoost：`depth=7`、`iterations=1000`、`learning_rate=0.05`；
- early stopping：`early_stopping_rounds=50`，1000 只是上限；
- class handling：沿用原 `train_cpv_model.py` 的 `weight_training` 和 class balancing；
- test 权重：严格沿用 `build_ml_observable.py` 的
  `sigma / (n_chunks * events_per_chunk * split_fraction)` 归一化；
- luminosity：Fisher 使用 `8000 fb^-1`；
- primary binning：20 bins；可另做 64 bins 诊断，但不得替代 20-bin 主结果；
- comparison：同一 flavor、同一 test event IDs、同一权重和同一 binning 下比较。

现有最佳模型参考产物：

```text
outputs/ml_superdataset/model_v2/lD_auxiliary_wbjets_lepton/catboost/
  {electron,muon}/iter1000_d7_lr005_es50
```

其 39 个输入和 metadata 是 baseline 的唯一来源；不要凭记忆重写 baseline。

## 5. 原始工作流入口

应优先复用下列旧程序的行为，但不修改它们：

```text
scripts/export_features_v2.py
scripts/merge_feature_chunks.py
scripts/train_cpv_model.py
scripts/build_ml_observable.py
scripts/evaluate_fisher.py
src/ilc_tth_cpv/flavor.py
configs/analysis_ml_superdataset_lr_catboost_v2.yaml
```

不要直接复用旧的 `run_ml_observable_pipeline.sh` 跑新变体，因为它包含旧模型的硬编码路径。

## 6. 对象与变量定义

### 6.1 六个 top 衰变产物

“六个 top 衰变产物”在本文中固定定义为选中 kinfit candidate 中：

```text
w1, w2, b_had, b_lep, lepton, neutrino
```

每个对象输入：

```text
E, pT, theta, phi
```

因此运动学输入共 24 列。

- `w1/w2` 是 kinfit 的两个 W daughter slot，不按 quark/anti-quark 或 down/up type 重排。
- `b_had/b_lep` 是 kinfit 的 hadronic/leptonic decay-side slot，不按 top/anti-top 或 b/bbar 电荷重排。
- 不输入 `top_side_fermion`、`anti_top_side_fermion`、`wjet_quark`、`wjet_antiquark` 的重复块。
- lepton 和 neutrino 保持物理对象身份，不在这个“纯六产物”模型中做 fermion/anti-fermion 排序。

这满足“没有 top-side/anti-top-side 电荷排序和重复输入”，同时保留 kinfit 本来就给出的衰变侧/slot 身份。

### 6.2 固定 auxiliary 列

所有提到“selection/mass auxiliaries”的模型固定使用原最佳输入中的这五列：

```text
w_assignment_likelihood_selected
final_selection_score
m_H
m_ttbar
down_jet_mass
```

需要 lepton charge 的模型再加入：

```text
lepton_charge
```

不得未经批准追加 `m_W_had`、`m_top_had`、`m_top_lep` 或其他质量变量，以免失去一因素对照。

### 6.3 lepton/neutrino 的 fermion/anti-fermion 排序

对带电流 W→lν：

- `lepton_charge < 0`：`fermion = lepton`，`anti_fermion = neutrino`；
- `lepton_charge > 0`：`fermion = neutrino`，`anti_fermion = lepton`；
- charge 为 0、缺失或不合法：记录并拒绝该行，不允许猜测。

对两个排序对象分别构造 `E,pT,theta,phi`。

### 6.4 四个角观察量

所有 `delta_phi(a,b)` 使用统一定义：

```text
wrap(phi_a - phi_b) into [-pi, pi)
```

具体变量：

- `O_lD`：严格读取或复现现有 Nana 定义；
- `O_W`：严格读取或复现现有 Nana 定义；
- `O_lnu`：
  - l-：`delta_phi(lepton, neutrino)`；
  - l+：`delta_phi(neutrino, lepton)`；
- `O_b`：`delta_phi(top_b, antitop_bbar)`；其中 `top_b/antitop_bbar` 沿用现有 exporter 的 charge-oriented 定义。

若 CSV 已有同名列，首次构建时仍须从源 `phi` 列独立重算并做逐事件数值核对；定义不一致时停止，不可静默选一个。

### 6.5 Higgs-assigned b jets

扩展模型在六产物基础上加入选中 kinfit candidate 中的两个 Higgs-assigned jets：

```text
higgs_b, higgs_bbar
```

每个对象输入 `E,pT,theta,phi`。H1/H2 的 b/bbar 朝向由现有 Weaver `mc_b`、`mc_bbar` soft scores 决定：比较

```text
L12 = P_b(H1) * P_bbar(H2)
L21 = P_b(H2) * P_bbar(H1)
```

选择较大的联合似然作为 `higgs_b/higgs_bbar` 顺序；同时保存选择 likelihood 和 margin 作为审计列，但 v0 模型不把这些审计列作为输入。

这里仍保留 kinfit 的“top-assigned/Higgs-assigned”角色，因为研究问题正是让模型判断该 assignment 的可靠性；不得把真值 origin 输入模型。

### 6.6 d/s soft likelihood

当前 hard W assignment 完全保留，不重新选择 down-type jet。只追加连续信息。

对与 lepton charge 相容的 down-type 概率，构造：

```text
selected_down_p_ds
alternate_down_p_ds
ds_assignment_log_ratio
```

其中：

- 对需要 down quark 的候选，`p_ds = mc_d + mc_s`；
- 对需要 anti-down quark 的候选，`p_ds = mc_dbar + mc_sbar`；
- `selected` 是当前 hard assignment 已选中的 jet；
- `alternate` 是另一个 W daughter；
- `log_ratio = log((selected + eps)/(alternate + eps))`，`eps` 在配置中固定并写入 manifest；
- 不用这些概率翻转、替代或重新训练现有 assignment。

### 6.7 三角函数角表示

对原最佳 39-feature baseline 中每个对象：

- 删除原始 `phi`，加入 `sin(phi)`、`cos(phi)`；
- 删除原始 `theta`，加入 `cos(theta)`；
- 保留 `E`、`pT` 和全部原 auxiliary；
- 不同时保留原始 `phi/theta`。

这样处理角周期边界，同时保持 theta 只用一个无冗余坐标。

## 7. 模型矩阵

每个 variant 对 electron 和 muon 各训练一个模型。

| 顺序 | variant name | 输入定义 | 数据阶段 |
|---:|---|---|---|
| 0 | `control_lD_aux_wbjets_lepton` | 精确复现原最佳 39-feature 输入 | A |
| 1 | `six_top_products_raw` | 六产物 24 列 + charge + 5 auxiliaries | A/B schema check |
| 2 | `six_top_products_plus_higgs` | variant 1 + `higgs_b/higgs_bbar` 的 8 列 | B |
| 3 | `lnu_ordered_replace` | 原 baseline 中删除裸 l/ν 8 列，加入 ordered fermion/anti-fermion 8 列 | A |
| 4 | `lnu_ordered_append` | 原 baseline 完整保留，再追加 ordered fermion/anti-fermion 8 列 | A |
| 5 | `four_delta_phi_aux` | `O_lD,O_lnu,O_W,O_b` + charge + 5 auxiliaries | A |
| 6 | `baseline_plus_ds_soft` | 原 baseline + 三个 d/s soft likelihood | B |
| 7 | `baseline_trig_angles` | 原 baseline 的 phi/theta 按 6.7 替换 | A |

说明：

- variant 0 是新路径中的 control，不覆盖旧模型；它用于验证新 wrapper 没有改变旧语义。
- variant 1 的 `w1/w2/b_had/b_lep` 若不在合并 CSV 中，则只补导出这些 slot；不得用 charge-oriented 列冒充。
- variant 2 是 variant 1 的明确扩展，除此之外其余模型均是相对 control 的独立变体。
- 首批执行优先级严格为：0 → 1 → 2；通过后再执行 3–7。

## 8. 两阶段数据准备

### Phase A：从现成合并 CSV 派生

只读输入优先使用 Nana 冻结副本中的：

```text
outputs/ml_superdataset/features_v2/reco_cpv/
  features_reco_higgs_rest_chunk1_79.csv
outputs/ml_superdataset/features_v2/reco_sm/
  features_sm_reco_higgs_rest_chunk1_79.csv
```

Phase A 可直接完成 control、l/ν 两种排序、四角变量包、trig 变换。若六产物所需的 raw slots 已存在，也可直接完成 variant 1；否则转 Phase B。

派生程序只读取源 CSV，向新 `outputs/binary_input_variants_v0/features/` 写 variant CSV，不原地改列。

### Phase B：补充旧 CSV 不含的列

已知合并表中可能缺少：

- `w1/w2/b_had/b_lep` 的全部 raw slot 四矢量；
- individual `H1/H2` 四矢量；
- individual `mc_d/mc_s/mc_dbar/mc_sbar` scores。

因此新增一个 exporter，复制并最小化复用 `export_features_v2.py` 的读取/boost/selection 逻辑，从相同既有 LCIO/kinfit/weaver 输入补导这些列。禁止修改原 exporter，也禁止重跑上游 reconstruction。

Phase B 输出必须携带与旧 CSV 相同的事件键。与 Phase A 基表做 one-to-one join；出现 duplicate key、missing key 或多对多 join 立即失败。

## 9. 需要新增的文件

只新增以下文件；名字可细调，但职责不得混淆：

```text
scripts/workflows/prepare_binary_feature_variants.py
scripts/workflows/export_binary_extended_inputs.py
scripts/workflows/run_binary_input_variant.py
scripts/diagnostics/compare_binary_variant_control.py
configs/binary_input_variants/control_lD_aux_wbjets_lepton.yaml
configs/binary_input_variants/six_top_products_raw.yaml
configs/binary_input_variants/six_top_products_plus_higgs.yaml
configs/binary_input_variants/lnu_ordered_replace.yaml
configs/binary_input_variants/lnu_ordered_append.yaml
configs/binary_input_variants/four_delta_phi_aux.yaml
configs/binary_input_variants/baseline_plus_ds_soft.yaml
configs/binary_input_variants/baseline_trig_angles.yaml
docs/BINARY_INPUT_VARIANT_RESULTS.md
```

职责：

- `prepare_binary_feature_variants.py`：纯 CSV 派生、schema 校验、event-key 保持和 manifest；
- `export_binary_extended_inputs.py`：只补 raw kinfit slots、Higgs jet 和 d/s scores；
- `run_binary_input_variant.py`：调用既有训练、score/template、Fisher 步骤，并强制唯一输出目录；
- `compare_binary_variant_control.py`：检查 event IDs、权重、事件保留率和 control 数值一致性；
- 每个 YAML：显式列出 feature list、数据路径、固定超参数和输出 variant name；
- results 文档：记录最终表格、命令、commit、输入 checksum 和残余风险。

不要为了方便重构旧文件。本轮只加最小 plumbing。

## 10. 实施顺序

### Step 0：环境和工作树确认

```bash
ssh naf
source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh
cd /data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable/worktrees/tth-cpv-observable-ilc-ozakinan-repro-20260907
git status --short --branch
git branch --show-current
```

要求：位于 `observable_workflow`，并确认没有会被覆盖的用户改动。

### Step 1：冻结 baseline schema

从原最佳 electron/muon model metadata 自动读取 feature list、超参数和输入表路径，生成只读审计报告。禁止手工录入 39 列作为唯一依据。

### Step 2：实现并 smoke-test Phase A

先只读 1000 行 CPV 和 1000 行 SM：

- 校验必需列；
- 校验 charge 只有 ±1；
- 校验所有角变量范围；
- 校验 feature 值有限；
- 校验 event keys 不变；
- 输出 feature manifest，不训练。

### Step 3：control 小样本闭环

在新输出路径跑 control 的小样本训练、CPV/SM scoring 和 Fisher，确认 wrapper 和旧逻辑一致后再全量。control 的 feature list 必须与原 metadata byte-for-byte 同序。

### Step 4：全量 variant 1

运行 `six_top_products_raw`。若 raw slots 缺列，先执行 Phase B 的 slot-only export，再 join；不要用 charge-ordered proxy。

### Step 5：全量 variant 2

补导 H1/H2 和 b/bbar scores，构造 `higgs_b/higgs_bbar`，运行 `six_top_products_plus_higgs`。

### Step 6：其余独立变体

依次运行 `lnu_ordered_replace`、`lnu_ordered_append`、`four_delta_phi_aux`、`baseline_plus_ds_soft`、`baseline_trig_angles`。

### Step 7：固定比较

对所有模型输出 electron、muon、combined：

- validation best iteration；
- test AUC/accuracy（仅诊断）；
- 20-bin CPV/SM template；
- Fisher information 和相对 control 比值；
- feature count；
- train/validation/test event count；
- feature-invalid rejection count；
- test weighted yield；
- common-event-subset Fisher（若任何模型出现额外丢失）。

### Step 8：后续组合角变量的入口

首批结果冻结后，再另开 v1 config family。候选 top-b/down-jet/lepton 组合角必须先在文档中逐一定义方向、charge convention 和 wrap，不得自动枚举全部 pair，也不得混入 v0 结果。

## 11. 命令行接口合同

下一位实现者应使以下接口可用；这是接口目标，不是要求此刻执行：

```bash
python3 scripts/workflows/prepare_binary_feature_variants.py \
  --config configs/binary_input_variants/six_top_products_raw.yaml \
  --sample cpv \
  --input /ABS/PATH/features_reco_higgs_rest_chunk1_79.csv \
  --output-root outputs/binary_input_variants_v0/features \
  --write-manifest
```

```bash
python3 scripts/workflows/export_binary_extended_inputs.py \
  --config configs/binary_input_variants/six_top_products_plus_higgs.yaml \
  --sample cpv \
  --output-root outputs/binary_input_variants_v0/features \
  --chunks 1-79 \
  --jobs 1
```

```bash
python3 scripts/workflows/run_binary_input_variant.py \
  --config configs/binary_input_variants/six_top_products_raw.yaml \
  --output-root outputs/binary_input_variants_v0 \
  --stages train,score-sm,score-cpv,fisher,plot \
  --luminosity-fb 8000 \
  --bins 20
```

必要参数：

- `--dry-run`：只显示将读取/写入的绝对路径和命令；
- `--stages`：允许失败后从独立阶段恢复；
- `--force` 默认关闭；目标存在时失败，不静默覆盖；
- `--flavor electron|muon|all`；
- `--jobs` 默认 1，首版不引入并行随机性；
- `--bins` 默认 20；
- 所有运行把解析后的完整 config、git commit、环境、输入 checksum 写入 manifest。

## 12. 训练和 Fisher 的数据流

```text
frozen CPV merged CSV ─┐
                      ├─ feature variant builder ─ CPV variant table
extended raw columns ─┘                              │
                                                    ├─ CPV +/- train
                                                    └─ CPV test score/template

frozen SM merged CSV ─┐
                      ├─ same feature transform ─ SM variant table
extended raw columns ─┘                              │
                                                    └─ frozen model score/template

CPV template + SM template + original test weights + 8000 fb^-1
    └─ Fisher (electron, muon, combined)
```

SM 和 CPV 必须使用同一个 variant transformer 和同一 model metadata feature order。

## 13. 必须保留的输出

每个 variant/flavor 至少包含：

```text
model.cbm
model_metadata.json
resolved_config.yaml
feature_manifest.json
input_checksums.json
event_counts.json
feature_importance.csv
training_history.csv
loss_curve.png
roc_curve.png
test_scores_cpv.csv
test_scores_sm.csv
templates_20bins.csv
templates_20bins.png
fisher_20bins.json
fisher_bin_contributions.csv
fisher_bin_contributions.png
run.log
```

根目录再生成：

```text
variant_comparison.csv
variant_comparison.png
common_event_comparison.csv
```

## 14. 校验门和失败信号

### 数据一致性

- CPV/SM 每个 flavor 的 event-key 集合与源表一致；
- 变体不应因派生数学操作丢事件；
- Phase B join 必须 one-to-one；
- split、label、flavor、权重列不得改变；
- 同一事件在不同变体中的 `weight_training` 和 evaluation weight 必须相同。

### 物理语义

- `O_lnu` 按 charge 翻转顺序的单元测试覆盖 l+ 和 l-；
- `delta_phi` 在 ±π 边界的单元测试；
- 六产物模型不存在 `top_side_*`、`anti_top_side_*`、`wjet_quark*`、`wjet_antiquark*` 输入；
- replace 变体不存在裸 `lepton_*`、`neutrino_*`；
- append 变体同时存在裸块和 ordered 块；
- d/s 变体的 hard assignment/event selection 与 control 完全一致；
- Higgs b/bbar 排序只用 reco soft score，不用真值 origin/charge。

### 训练可比性

- 每个 config 明确显示 `depth=7, iterations=1000, learning_rate=0.05, early_stopping_rounds=50, seed=42`；
- early stopping 只看 validation；
- test 集只在模型冻结后评估一次；
- control 新跑结果若与旧模型显著不一致，停止其他全量训练并定位差异。

### 输出安全

- 所有写入路径必须位于 `outputs/binary_input_variants_v0`；
- 目标已存在且没有显式 `--force` 时必须失败；
- frozen Nana archive 和 MVA repo 的 `git status`/mtime 不得因本流程改变。

## 15. 结果判读

主要指标是 20-bin Fisher，不以 feature importance、AUC 或 score 集中程度代替 Fisher。

比较表至少包含：

| variant | flavor | n_features | best_iter | test_events | weighted_yield | Fisher | Fisher/control | common-set Fisher |
|---|---|---:|---:|---:|---:|---:|---:|---:|

判读原则：

- `six_top_products_plus_higgs` 对比 `six_top_products_raw`，回答加入 Higgs-assigned jets 是否帮助模型处理 top/Higgs b-jet assignment 不可靠性；
- `lnu_ordered_replace` 对比 control，检验显式 fermion ordering 能否替代裸身份；
- `lnu_ordered_append` 对比 replace/control，检验保留两种表示的冗余是否有益；
- `four_delta_phi_aux` 检验高度压缩的理论角变量能保留多少信息；
- `baseline_plus_ds_soft` 只回答 soft d/s 信息是否补充当前 hard assignment；
- `baseline_trig_angles` 检验周期友好表示是否优于裸角度。

不因单个 test 结果选择新超参数。若需要迭代，应另建 v1 预注册比较。

## 16. 每个新增功能的必要性

- raw-slot exporter：源合并 CSV 缺失六产物无 charge-order 表示和 individual Higgs jets，无法从现有有序列无损反推。
- d/s extended columns：当前 CSV 只保留聚合 q/qbar 与部分 flavor score，无法构造指定 soft likelihood。
- variant manifest：防止不同模型无意间使用不同事件、权重、feature order 或超参数。
- no-overwrite gate：防止新研究覆盖 Nana 的旧模型和可复现基线。
- common-event comparison：防止额外 missing-feature rejection 被误解为模型输入本身的收益或损失。

除此之外不添加新抽象、依赖、安全层或训练技巧。

## 17. 五分钟人工检查

在全量训练前，人类只需检查：

1. `git diff --stat` 只含新文件；
2. dry-run 的所有输入指向 frozen Nana archive，所有输出指向 `binary_input_variants_v0`；
3. variant 1 的 feature list 恰为 24 个六产物运动学 + charge + 5 auxiliaries；
4. variant 2 只比 variant 1 多 8 个 Higgs-jet 运动学；
5. replace/append 的 feature list 与名称符合第 6.3 节；
6. 两个 flavor 的 config 都显示固定 CatBoost 参数和 ES50；
7. control 的 event counts、weighted yields 和 Fisher 与旧结果在数值容差内一致。

## 18. 可直接粘贴给下一位 Codex 的执行指令

```text
请严格按照 docs/BINARY_INPUT_VARIANT_WORKFLOW_20260910.md 实施。

先阅读 NAF_WORKING_RULES.md、ILC_NAF_MARLIN_ANALYSIS_GUARDRAILS_COMPACT.md、相关 handoff 和 targeted mistake-log；这是会改变物理输入定义和正式 Fisher 比较的 STRICT 工作。用户禁止 Luna，规划、实现和复核全部使用 SOL/主代理完成。

只在 /data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable/worktrees/tth-cpv-observable-ilc-ozakinan-repro-20260907 的 observable_workflow 分支新增文件和输出。Nana frozen archive 以及 /data/dust/user/zhangyuy/tth-cpv-observable-ilc 永久只读。source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh。

不要一开始跑全量。先完成 Step 0–2，并向我展示：源字段审计、精确 feature schemas、dry-run 路径、1000 行 smoke-test、事件键/权重不变性结果。得到确认后再跑 control 闭环，然后按 0→1→2→3…7 的顺序继续。不要修改旧脚本或覆盖旧结果。
```

