# ttH 半轻子信号—背景 MVA：完整实现、数据口径与结果审计档案

版本：2026-08-21

对象：`baseline-xgboost-v1`

分析能量与亮度方案：550 GeV，LC Vision 8 ab\(^{-1}\)

档案性质：根据 NAF 当前代码、冻结数据产物和模型输出逐项重建的技术记录

## 0. 这份档案回答什么

这份文档不是结果摘要，也不是组会宣传稿。它要回答以下问题：

1. 原始样本从哪里进入分析？
2. `nIso=1`、KinFit、HDF5 导出分别做了什么？
3. `tth-sm` 中的 \(H\to b\bar b\) 与非 \(b\bar b\) 如何定义成信号和背景？
4. 25 个输入特征究竟是什么，来自哪个 collection 或 ROOT branch？
5. `weight_phys` 和 `weight_train` 各自是什么，为什么不能混用？
6. train、validation、test 如何划分，为什么不存在 logical-shard 泄漏？
7. XGBoost 如何训练，早停、打分和阈值扫描如何实现？
8. AUC=0.95974、test \(Z=13.06\) 和 naive 8 ab\(^{-1}\) \(Z=25.42\) 分别表示什么？
9. SM 与 CPV 的效率如何公平比较？
10. 当前结果哪些可以认真使用，哪些仍然只能作为诊断？

结论先行：当前模型区分 \(t\bar tH(H\to b\bar b)\) 与所列背景的能力很强，AUC 和独立 test 效率是可信的模型性能结果。15 个 test 空层已经用不重训的 test-first/held-out-validation 方案完成统计覆盖诊断：工作点仍为 0.954，完整 8 ab\(^{-1}\) 得到 \(S=1277.21\)、\(B=1326.25\)、simple counting sensitivity \(Z=25.03\)。其中4个只有 train 的极小层合计 MVA 前物理产额 67.19；即使极端假设它们100%通过，\(Z\) 仍为24.72。这里的“闭合”只指当前样本清单、物理权重和简单 counting statistic；profile likelihood、系统学、有限 MC 尾部处理及可选 out-of-fold 复核仍未完成。

## 1. 整条数据流

当前实现不是一个脚本完成全部工作，而是由不可变产物连接起来的分阶段流水线：

```text
正式 KinFit job plan（1150 jobs）
        │
        ▼
build_mva_manifest.py
        │  固定 job_key / input SLCIO / KinFit ROOT / split_group
        ▼
mva_input_manifest.csv
        │
        ▼
export_mva_dataset.py × 1150
        │  ROOT accepted&&fit_success 事件按 event_index 回接原 SLCIO
        │  读取 jets、lepton、PID、truth，构造逐事件特征
        ▼
每 job 一个冻结 HDF5，共 5,256,280 events
        │
        ├──────────────► build_physical_normalization_inventory.py
        │                    │  generator N、截面、8 ab⁻¹ 极化亮度
        │                    ▼
        │              physical_normalization_inventory.json
        │
        ├──────────────► assign_mva_splits.py
        │                    │  logical shard 级 deterministic hash
        │                    ▼
        │              split_assignment.json
        │
        └──────────────► prepare_mva_weights.py
                             │  将 HDF5、split 和 normalization 精确关联
                             ▼
                       physical_weights catalog
                             │
                             ▼
train_selection_mva.py
        │  只读 train/validation，CPV 不进入拟合
        ▼
model.json + provenance.json + training_history.json
        │
        ▼
apply_selection.py
        │  每个 job 产生 event_index + score 的 score shard
        ▼
evaluate_selection.py
        │  validation 选阈值，test 只评估一次，CPV 单独做安全检查
        ▼
baseline-xgboost-v1.json
        │
        ▼
build_mva_group_materials.py
        │  只读审计、制表和画图，不训练、不改变物理结果
        ▼
组会材料与本档案
```

最重要的架构原则是：冻结 HDF5 中的 `split`、`weight_phys`、`weight_train` 仍保持 `unassigned/NaN`。split 和权重由外部 JSON catalog 管理。因此改变训练平衡策略或亮度方案时，不需要回写数百万事件的原始特征文件。

## 2. 代码与配置的职责

| 文件 | 关键入口 | 实际职责 |
|---|---|---|
| `configs/mva_samples.yaml` | sample/manifest contract | 六类样本、job 数、reco 分母、极化标签、是否参与训练 |
| `configs/mva_semilep.yaml` | collection/feature/split contract | ROOT tree、LCIO collections、事件门槛、特征 schema、70/15/15 split |
| `configs/mva_luminosity_scenarios.yaml` | luminosity contract | 550 GeV、8 ab\(^{-1}\)、四种运行极化占比及纯 helicity 有效亮度 |
| `configs/mva_normalization_sources.yaml` | normalization provenance | Physsim/Whizard 的 \(N_{\rm gen}\)、截面、源文件与哈希 |
| `configs/mva_training.yaml` | model contract | 25 特征、信号/背景定义、训练权重、XGBoost 参数、阈值规则 |
| `build_mva_manifest.py` | `build_manifest_row`, `validate_manifest` | 将正式 job plan 变成唯一 MVA manifest，检查路径和 job 身份 |
| `mva_common.py` | `read_selected_kinfit_rows`, `classify_event_target`, `build_export_event_row` | ROOT–SLCIO join、truth 分类、特征构造、HDF5 写入与验证 |
| `export_mva_dataset.py` | `main` | 导出一个 job |
| `export_all_mva_datasets.py` | `main` | 导出全部 job，形成 production summary |
| `build_physical_normalization_inventory.py` | `compute_effective_luminosities`, `scan_*` | 从生成器级来源建立物理归一化 inventory |
| `assign_mva_splits.py` | `deterministic_uniform`, `build_group_assignments` | 以 logical shard 为单位冻结 train/validation/test |
| `prepare_mva_weights.py` | `main` | 将每个 job 绑定到唯一 normalization key 和 `weight_phys` |
| `selection_mva_common.py` | `load_authority`, `load_matrix`, `training_weight_coefficients` | 训练/打分/评估共同的 fail-closed 数据入口 |
| `train_selection_mva.py` | `train_booster`, `main` | XGBoost 训练、早停、模型和 provenance 冻结 |
| `apply_selection.py` | `write_score_file`, `main` | 对 catalog 指定的每个 job 生成不可覆盖的 score shard |
| `evaluate_selection.py` | `choose_threshold`, `selected_yields`, `main` | validation 阈值扫描、test 指标与 CPV 安全检查 |
| `prepare_selection_mva_condor.py` | `main` | 生成 TRAIN→APPLY→EVALUATE DAG |
| `build_mva_group_materials.py` | `main` | 现有结果的只读审计和展示，不属于模型训练本身 |

### 2.1 JSON 和 HDF5 在这里各是什么

HDF5 不是神秘的模型文件。这里每个 `*.h5` 本质上是一张按列存储的事件表：`y45` 是一列，`btag_1` 是一列，`event_index` 又是一列；同一个 job 的各列行数完全相同。一个 row 对应一个 exported event。

JSON 主要保存 catalog 和 provenance：哪些 jobs 属于哪个 split、某个 job 对应哪个 HDF5、它用哪个 normalization key、模型和代码的 hash 是什么。真正的数百万事件特征不塞进 JSON。

模型打分后的 `*.scores.h5` 更小，只保存 `event_index` 与 `score`。评估时再通过 `event_index` 与原 HDF5 一一对应，从而避免复制所有特征或改变冻结数据。

## 3. 输入样本与分母

### 3.1 六个样本组

| sample | 生成器/来源 | 在 baseline 中的作用 | KinFit 输入分母阶段 |
|---|---|---|---|
| `tth-sm` | Physsim | \(H\to bb\) 为信号，non-bb 为背景 | all-channel complete-reco |
| `tth-cpv` | Physsim signed-interference control | 不训练；检查选择对 CPV 是否产生明显偏好 | all-channel complete-reco |
| `ttz` | Physsim | 背景 | all-channel complete-reco |
| `ttbb` | Physsim | 背景 | all-channel complete-reco |
| `6q` | Whizard | 全强子六夸克背景 | 已经是 `nIso=1` reco skim |
| `4f2l` | Whizard；生产目录名曾写作 `4q2l` | 四费米子加两轻子/中微子背景 | 已经是 `nIso=1` reco skim |

Physsim 和 Whizard 的 `input` 不能直接解释为同一个物理效率分母。Physsim 四组从 all-channel complete-reco 开始；Whizard 两组在进入本 KinFit 生产前已经做过 `nIso=1`。因此下面的 production cutflow 只能逐组理解，不能把六组 `accepted/input` 横向当成同阶段的探测器效率。

### 3.2 KinFit 到 HDF5 的实际计数

| sample | KinFit input | accepted | fit_success | HDF5 exported |
|---|---:|---:|---:|---:|
| `tth-sm` | 1,974,649 | 734,477 | 734,443 | 734,443 |
| `tth-cpv` | 1,999,840 | 744,618 | 744,578 | 744,577 |
| `ttz` | 1,974,702 | 671,065 | 671,005 | 671,005 |
| `ttbb` | 1,812,137 | 661,289 | 661,139 | 661,139 |
| `6q` | 17,412 | 17,412 | 17,396 | 17,396 |
| `4f2l` | 2,429,494 | 2,429,490 | 2,427,720 | 2,427,720 |
| total | 10,208,234 | 5,258,351 | 5,256,281 | 5,256,280 |

唯一的 `fit_success` 与 exported 差异是一条 CPV 事件。它位于 `physsim__tth-cpv__eR.pL__I01234_0_19` 的 `event_index=285`；`cos_theta_bb_assigned_prefit` 的一个 four-momentum 含 NaN，因而触发 `non_finite_opening_angle`。exporter 通过显式 `SkipMVAEvent` 记录后跳过，而不是静默填零。普通 SM/背景 counting significance 不包含 CPV，因此这一个事件不改变 baseline 的 \(S\) 或 \(B\)，但它必须保留在 provenance 中。

### 3.3 三种不同分母

这套分析同时存在三种容易混淆的计数：

1. **KinFit/reco input**：上表的 `input`。它描述某个生产分支实际读到多少重建事件。
2. **HDF5 exported**：通过 `accepted && fit_success` 且特征可构造的事件数。
3. **generator denominator \(N_{\rm gen}\)**：计算物理权重时使用的生成器级事件数。

只有第 3 项能进入

\[
w_{\rm phys}=\frac{\sigma L}{N_{\rm gen}}.
\]

代码明确禁止用 `input_readable_events`、KinFit rows、exported HDF5 rows 或某个 truth category 的数量替代 \(N_{\rm gen}\)。

## 4. Manifest 如何固定事件身份

`build_mva_manifest.py` 从正式 `job_plan.jsonl` 读取 1,150 行。每行固定：

- `job_key`；
- 原始 SLCIO 路径；
- KinFit ROOT 路径；
- `sample_key`、polarization、generator；
- `logical_shard` 与 `physical_part`；
- production branch 与处理器库哈希；
- readable-event count。

逐事件全局身份定义为

```text
generator::sample_key::polarization::job_key::physical_part::event_index
```

训练 split 使用的组身份则是

```text
source::sample_key::polarization::logical_shard
```

前者避免事件 ID 碰撞；后者保证同一 logical shard 的 `_part1/_part2` 不会被拆到不同 split。实际有 1,150 jobs，但只有 1,149 个 split groups，正是因为 Whizard 的一个 logical shard 对应两个 physical parts。

### 4.1 当前确认的 manifest 重建风险

冻结 manifest 的 metadata 显示，它由 SHA-256 为

```text
15e1579d128458ed50da6d331f3fb9823e1b439f0a51cab8217044b8784f1325
```

的 `mva_samples.yaml` 生成。当前 NAF 上同名配置的哈希已经变成

```text
64bd38aafa7ff00a23f982e06ceb0d2e76323ed8517debe6a4304a8307ab89fc
```

而当前 `build_mva_manifest.py` 仍访问 `cfg["normalization"]["status"]`，当前 YAML 已没有这个字段。因此：

- **确认不受影响**：现有 baseline 的训练、打分和评估。它们绑定的是冻结 manifest、split、weights catalog、HDF5 和相应哈希。
- **当前不能声称可复现**：从原始 job plan 用现配置重新生成一模一样的 manifest。
- **需要后续修复**：恢复/版本化生成 manifest 时的旧配置，或更新 builder schema 并明确迁移，然后证明新 manifest 与冻结 manifest 的科学字段一致。

这是代码/配置漂移问题，不是当前模型数值造假；但它必须在完整实现档案中公开。

## 5. 从 KinFit ROOT 回接原始 SLCIO

### 5.1 事件门槛

`mva_semilep.yaml` 和 `mva_common.read_selected_kinfit_rows` 规定：

```text
accepted == 1 && fit_success == 1
```

其中：

- `accepted` 表示事件通过六 jet、单 isolated lepton 和组合选择门槛，并在 best tree 中有一条选中记录；
- `fit_success` 表示 fitter technical status 成功且 fit probability 有效；
- 它不是额外的 Higgs/top mass window，也不是人为设置的 `fitprob` 物理 cut。

进入 exporter 的事件必须同时满足：

- `TTHSemiLepKinFit` best tree 存在；
- ROOT 中所有必需 branch 存在且长度一致；
- `event_index` 非负、唯一、严格递增；
- 原始 SLCIO 中恰有一个 isolated electron 或 muon；
- `OutputErrorFlowJets6` 恰有 6 jets；
- `RefinedJets6` 恰有 6 jets。

在 MVA 之前，KinFit/组合阶段使用 `OutputErrorFlowJets6` 做拟合运动学、`RefinedJets6` 做 flavor ranking。每个通过六 jet 与单轻子门槛的事件保留 TopN=10 个 base assignments，再做 SLD enumeration；constraint mode 为 `fullMass4C`。正式 best row 的已有组合分数为

\[
\mathrm{final\ selection\ score}
=\log(1+\chi^2)+0.3\times\mathrm{signed\ flavor\ NLL}.
\]

XGBoost 不是取代这一步，而是在这一步选出的 best assignment 及其 postfit/score 信息上继续做事件级信号—背景分类。

### 5.2 为什么必须回接 SLCIO

KinFit ROOT 只保存拟合结果、组合索引和部分分数；Weaver tag、jet four-momentum、isolated lepton 和 Higgs truth 仍需从原始 SLCIO 读取。因此 exporter 以 ROOT 的 `event_index` 定位原始 SLCIO 的第几个顺序事件，并同时检查：

- ROOT 与 SLCIO 的 `(run_number,event_number)` 完全一致；
- lepton flavor 一致；
- lepton charge 在 \(10^{-5}\) 绝对误差内一致；
- jet assignment 是 0–5 的一个完整排列。

任一检查失败都会终止该 job，而不是根据文件名、entry ordinal 或近似事件号猜测配对关系。

## 6. 事件标签如何定义

### 6.1 普通样本

对 `ttz`、`ttbb`、`6q`、`4f2l`，所有事件的 binary label 都是 0，即背景。

### 6.2 inclusive `tth-sm`

`tth-sm` 是 inclusive production sample。exporter 从 `MCParticlesSkimmed` 识别 hard-process Higgs 的衰变：

- `H->bb`：`analysis_category=tth-hbb`，binary label=1；
- `H->nonbb`：`analysis_category=tth-nonbb`，binary label=0。

代码不会丢弃 non-bb 事件，也不会把无法识别 Higgs 的 `H->none` 默认为 non-bb；后一种情况会 fail closed。

最重要的归一化原则是：`tth-hbb` 和 `tth-nonbb` 共享同一个 inclusive `tth-sm × helicity` production weight。真值分类只决定标签，不改变 \(N_{\rm gen}\) 或截面。否则会把同一个 inclusive sample 按衰变类别重复归一化。

### 6.3 `tth-cpv`

`tth-cpv` 的 Hbb/non-bb truth 仍会写入 HDF5，便于做同定义效率比较；但它在训练时返回 label=-1，并被显式排除。它不是普通的正定信号产额样本。

## 7. 25 个 baseline 输入特征

### 7.1 事件形状/jet transition

| 特征 | 定义与来源 |
|---|---|
| `y45`, `y56`, `y67` | 从 `RefinedJets6` 的 `yth` ParticleID 参数读取；依次表示 4→5、5→6、6→7 jet transition 信息 |

`read_yth_values` 会在六个 flavor jets 中寻找第一个具有完整、有限 `yth` 参数的 jet，并要求 PID schema 在整个 job 内稳定。

### 7.2 flavor tagging

Weaver 提供带符号 flavor probabilities：

\[
b\text{-tag}=p_b+p_{\bar b},\qquad
c\text{-tag}=p_c+p_{\bar c}.
\]

对 6 个 `RefinedJets6` jets 分别计算后，降序排列：

| 特征 | 含义 |
|---|---|
| `btag_1`–`btag_4` | 六个 jet 中最高的四个 b-tag |
| `ctag_1`–`ctag_4` | 六个 jet 中最高的四个 c-tag |

模型没有输入 jet 的真值 flavor，只看到 tagger 概率。

### 7.3 KinFit/postfit masses

| 特征 | ROOT branch |
|---|---|
| `mH_postfit` | 被选为 Higgs 的两 jet 的 postfit 质量 |
| `mW_had_postfit` | hadronic W postfit 质量 |
| `mt_had_postfit` | hadronic top postfit 质量 |
| `mt_lep_postfit` | leptonic top postfit 质量 |

### 7.4 fit 和已有组合选择分数

| 特征 | 含义 |
|---|---|
| `fitchi2` | KinFit \(\chi^2\) |
| `chi2_over_ndof` | \(\chi^2/n_{\rm dof}\) |
| `fitprob` | fit probability |
| `final_selection_score` | KinFit/组合阶段的最终选择分数 |
| `final_fit_score` | 该阶段的 fit-score 分量 |
| `final_flavor_score` | 该阶段的 flavor-score 分量 |

这些量不是 MVA 输出，而是 MVA 的输入。XGBoost 在已有 KinFit/组合器之后再学习一次信号—背景分离。

### 7.5 isolated lepton

| 特征 | 含义 |
|---|---|
| `lepton_E` | isolated lepton 能量 |
| `lepton_theta` | polar angle |
| `lepton_pt` | transverse momentum |
| `lepton_charge` | 电荷 |

### 7.6 明确没有进入 baseline 的量

以下量虽可能保存在 HDF5 中，但不在当前 25 特征内：

- 三个 opening-angle features；
- truth decay、truth label；
- sample name、generator、process mask；
- polarization/helicity；
- `weight_phys`、`weight_train`；
- event/job/run ID；
- jet assignment `idx_*`；
- fitted neutrino `nu_fit_*`；
- CPV sign 或 signed interference weight。

`selection_mva_common.validate_feature_list` 要求特征顺序与冻结的 25 项完全一致，并通过 exact-name 与 prefix 黑名单阻止 truth、权重、ID、assignment 和 neutrino 信息泄漏。

### 7.7 特征的重建阶段不是全 postfit

这是一个 hybrid feature set：

- jet/lepton four-momentum 与 opening angles 来自重建 collections；
- flavor tag 来自 `RefinedJets6`；
- masses、fit scores 来自 KinFit ROOT 的 postfit/best-combination 输出。

因此不能把整套输入笼统称作“全 postfit observables”。

## 8. 物理归一化

### 8.1 从实际束流极化得到纯 helicity 有效亮度

LC Vision 的 550 GeV 运行方案为总亮度 8,000 fb\(^{-1}\)，四种运行状态占比 10:40:40:10，电子/正电子极化幅度分别为 80%/60%。

代码使用

\[
P=\frac{N_R-N_L}{N_R+N_L},\qquad
f_L(P)=\frac{1-P}{2},\qquad
f_R(P)=\frac{1+P}{2},
\]

把每个实际 partial-polarization run state 分解为纯 helicity luminosity。结果为：

| pure helicity | 有效亮度 [fb\(^{-1}\)] |
|---|---:|
| `eL.pL` | 1,424 |
| `eL.pR` | 2,576 |
| `eR.pL` | 2,576 |
| `eR.pR` | 1,424 |

四项之和严格闭合到 8,000 fb\(^{-1}\)。这就是为什么全极化生成样本可以代表实际 80%/60% 运行方案：不是把全极化截面当作实际束流截面，而是把实际束流分解为四个纯 helicity 组分后分别加权。

### 8.2 普通正定样本

对普通 MC：

\[
w^{\rm phys}_{p,h}=\frac{\sigma_{p,h}L_h^{\rm eff}}{N^{\rm gen}_{p,h}}.
\]

Physsim 的 \(N_{\rm gen}\) 来自唯一 run log 的最终 `Number of write events`；Whizard 的 \(N_{\rm gen}\) 来自权威 generator manifest 中去重后的 readable physical shards。截面在 Whizard manifest 中按 shard 重复记录，代码要求一致但绝不相加。

Physsim 的主要输入为：

| sample/helicity | \(\sigma\) [fb] | \(N_{\rm gen}\) | `weight_phys` |
|---|---:|---:|---:|
| `tth-sm eL.pR` | 2.96055 | 998,858 | 0.0076350961 |
| `tth-sm eR.pL` | 1.15889265 | 998,829 | 0.0029888074 |
| `ttz eL.pR` | 6.90699 | 999,862 | 0.0177948619 |
| `ttz eR.pL` | 1.93628 | 999,859 | 0.0049885607 |
| `ttbb eL.pR` | 2.03861 | 999,800 | 0.0052525099 |
| `ttbb eR.pL` | 0.858666 | 999,806 | 0.0022123528 |

Whizard 有 58 个 process-mask × helicity normalization entries，必须逐项查询，不能给整个 `4f2l` 或 `6q` 强行指定一个共同常量。

### 8.3 CPV signed interference

CPV sample 使用另一套定义：

\[
w_{\rm int,event}=s_{\rm event}\,
\frac{\sigma_{\rm absint,h}L_h^{\rm eff}}{N^{\rm gen}_h},
\qquad s_{\rm event}=\pm1.
\]

inventory 已冻结 \(\sigma_{\rm absint}\)、\(N_{\rm gen}\) 和 weight magnitude，但 reconstructed HDF5/score 与原始 sidecar 的逐事件 sign 尚未完成可靠 join。因此：

- CPV `weight_phys=None`；
- 不能把 CPV 当普通正产额加入 \(S\)；
- 当前只能做未加权选择效率和 score-shape safety check；
- `evaluate_selection.py --cpv-signed` 会明确报错 `CPV_EVENT_SIGN_JOIN_UNAVAILABLE`。

## 9. split 如何生成

split 不是逐事件随机切分，而是以 `split_group` 为最小单位。对每个 group 计算

```text
SHA256(seed + "\0" + split_group)
```

取前 64 bit 映射到 \([0,1)\)：

- <0.70：train；
- 0.70–0.85：validation；
- ≥0.85：test。

seed 为 `mva-semilep-split-v1`。这种方法可复现，并保证同一 generator logical shard 的 physical parts 不跨 split。

### 9.1 实际 split 计数

| split | jobs | groups | 含 CPV events | 普通训练/评估 events | CPV events |
|---|---:|---:|---:|---:|---:|
| train | 785 | 784 | 3,623,401 | 3,121,211 | 502,190 |
| validation | 171 | 171 | 780,162 | 668,328 | 111,834 |
| test | 194 | 194 | 852,717 | 722,164 | 130,553 |

逐 sample 的 HDF5 events 为：

| sample | train | validation | test | total |
|---|---:|---:|---:|---:|
| `tth-sm` | 469,917 | 111,580 | 152,946 | 734,443 |
| `tth-cpv` | 502,190 | 111,834 | 130,553 | 744,577 |
| `ttz` | 501,290 | 93,120 | 76,595 | 671,005 |
| `ttbb` | 446,594 | 73,215 | 141,330 | 661,139 |
| `6q` | 11,779 | 3,024 | 2,593 | 17,396 |
| `4f2l` | 1,691,631 | 387,389 | 348,700 | 2,427,720 |

split 脚本会重新打开每个 HDF5，检查 `split` dataset 仍为 `unassigned`，并核对 HDF5 内的 `split_group`、event count 和 analysis-category count。它只输出外部 assignment JSON，不修改 HDF5。

## 10. `weight_train` 为什么存在

原始训练样本数量严重不平衡：背景远多于信号，LL/RR 背景又远少于 LR/RL。直接按 raw event count 训练，loss 会主要被大样本或大 helicity cell 支配。

训练权重只由 train split 计算：

\[
w_{\rm train}(y,h)
=\frac{N_{\rm train}}
{2\,n_h(y)\,N_{\rm train}(y,h)},
\]

其中 \(y\in\{0,1\}\)，signal 有两个 helicities，background 有四个。这样：

- signal 与 background 各占总训练权重的一半；
- 同一 binary class 内，各 helicity 获得相同总权重；
- validation 使用 train split 冻结出的同一系数，不根据 validation 自己重新平衡。

当前系数为：

| label/helicity | coefficient |
|---|---:|
| background `eL.pL` | 13.2493 |
| background `eL.pR` | 0.232371 |
| background `eR.pL` | 0.347815 |
| background `eR.pR` | 13.0774 |
| signal `eL.pR` | 5.67757 |
| signal `eR.pL` | 6.30456 |

这些数只进入 XGBoost loss。它们不代表截面、亮度或 expected yield，绝不能用于最终 \(S\)、\(B\) 或 significance。

## 11. XGBoost 训练

### 11.1 训练集合

训练 label 定义：

```text
signal = tth-sm AND analysis_category == tth-hbb
background = tth-sm/tth-nonbb + ttz + ttbb + 6q + 4f2l
tth-cpv = excluded
```

实际使用：

- train：3,121,211 ordinary events，677 jobs；
- validation：668,328 ordinary events，147 jobs；
- CPV used for training：false。

### 11.2 模型参数

| 参数 | 数值 |
|---|---:|
| library | XGBoost 2.1.1 |
| objective | `binary:logistic` |
| tree method | `hist` |
| max depth | 6 |
| learning rate | 0.05 |
| maximum rounds | 1,000 |
| early stopping | 50 rounds |
| min child weight | 1 |
| L2 regularization | 1 |
| subsample | 1.0 |
| column sample | 1.0 |
| max bins | 256 |
| metric | weighted logloss |
| seed | 20260820 |
| threads | 8 |

最优迭代为 871，validation weighted logloss 最优值约 0.150593。模型预测时只使用第 0 到 871 轮，共 872 轮，不使用后续早停等待轮。

### 11.3 防止旧模型与新代码混用

模型目录不允许覆盖。`provenance.json` 保存：

- training config、split、weights catalog 和 inventory hash；
- 五个 MVA implementation files 的 SHA-256；
- git commit 与 tracked-dirty 状态；
- 25 特征及顺序；
- model SHA-256；
- best iteration、seed、软件版本、train/validation job 数。

打分和评估时会重新计算这些身份；代码、catalog 或模型不匹配就终止。

### 11.4 模型主要利用了什么

现有模型的 XGBoost mean-gain importance 只统计实际预测使用的第0–871轮、共872轮树；保存模型中用于 early-stopping patience 的后50轮没有计入。前几项为：

1. `btag_3`；
2. `final_selection_score`；
3. `mH_postfit`；
4. `lepton_E`；
5. `y45`；
6. `y67`。

对应 mean gain 分别约为 7686.99、2019.47、277.18、229.13、194.84 和149.19。`btag_3` 明显支配模型，它非常直接地反映 \(H\to bb\) 所需的多 b-jet 拓扑；其次是已有组合选择分数、Higgs postfit mass、lepton kinematics 和 jet-transition 信息。

![XGBoost gain importance](../outputs/mva/group_materials/baseline-xgboost-v1_20260821_exact_audit_v7/feature_importance_gain.png)

逐特征数值见 `feature_importance_gain.csv`。Gain 不是因果解释，也不等于删除某特征后的性能损失；严肃结论仍需要 ablation 或 permutation/SHAP 检查。

## 12. 打分阶段

`apply_selection.py` 对每个 catalog job：

1. 验证 HDF5 hash、job identity、event count 和 feature order；
2. 按冻结的 25 特征构造矩阵；
3. 用最佳迭代范围预测 \([0,1]\) score；
4. 检查 score 有限、位于 \([0,1]\) 且不是常数；
5. 输出一个只含 `event_index` 和 `score` 的 `.scores.h5`。

score shard 同时保存 source HDF5、model、catalog、provenance、implementation 和 apply script 的哈希。若文件已经存在，程序不是无条件跳过，而是先逐项验证后才允许 reuse；不一致则报错，不覆盖。

`binary:logistic` 保证 score 位于 0–1，但当前没有做 probability calibration。因此它应被称为分类分数或 signal-like score，不能默认解释成“该事件有 97% 概率是真信号”。

CPV 只有在 `--include-cpv` 时参与打分。Condor 的正式 job list 显式包含 CPV，这是为了生成 safety-control scores，不表示它进入模型拟合。

## 13. validation 阈值如何选择

`evaluate_selection.choose_threshold` 在 validation 上扫描 1,001 个阈值：

\[
t=0,0.001,0.002,\ldots,1.
\]

每个阈值使用普通正定样本的 `weight_phys` 计算

\[
S(t)=\sum_{i:y_i=1,\,s_i\ge t}w_i^{\rm phys},
\qquad
B(t)=\sum_{i:y_i=0,\,s_i\ge t}w_i^{\rm phys},
\]

再最大化

\[
Z_{\rm count}(t)=\frac{S(t)}{\sqrt{S(t)+B(t)}}.
\]

得到工作点

\[
t_{\rm MVA}=0.954.
\]

该点在 validation 子集上：

\[
S_{\rm val}=164.016,\quad
B_{\rm val}=195.358,\quad
Z_{\rm val}=8.652,\quad
S/B=0.840.
\]

test 没有参与阈值选择。代码和 evaluation JSON 都明确写有 `test_used_for_threshold_selection=false`。

原始 evaluation JSON 的阈值状态是

```text
provisional_incomplete_validation_normalization_coverage
```

因为当时尚未完成细分 normalization strata 的覆盖审计。

为了让11个 test 空、但有 validation 的层能够作为独立效率估计样本，覆盖修补时先把全部15个 test 空层对应的 normalization keys 从 validation 阈值优化中排除，再按完全相同的1,001点网格重算。结果仍然是

\[
t_{\rm MVA}=0.954,
\]

而排除后的 validation 子集在该点为

\[
S_{\rm val}=164.016,\qquad
B_{\rm val}=176.879,\qquad
Z_{\rm val}=8.883.
\]

因此工作点没有因为覆盖修补而改变；11个 fallback validation 层既未参加模型训练，也未参加这次阈值选择。原始 `threshold_scan.png` 不需要重画；新增的双纵轴图展示信号效率与阈值统计量的权衡：

![validation efficiency and significance](../outputs/mva/group_materials/baseline-xgboost-v1_20260821_exact_audit_v7/validation_efficiency_significance.png)

## 14. AUC=0.95974 究竟是什么

test AUC 为

\[
\mathrm{AUC}_{\rm test}=0.9597399.
\]

它不是“95.97% 的 ttH 被识别成功”，也不是选择效率。AUC 的直观含义是：从当前 test 中随机抽一个 `tth-sm/Hbb` 信号事件和一个背景事件，模型把信号排在背景前面的概率约为 95.97%（标准 AUC 对相同分数作半权处理）。

AUC 综合所有可能阈值；真正的信号保留率必须指定一个阈值。当前阈值 0.954 下，SM Hbb 的 raw test efficiency 是 58.68%，而不是 95.97%。

模型还报告了 `auc_weight_train=0.98383`。这个数使用训练平衡权，回答的是“各 binary class/helicity 被人为等权后排序有多好”；它不能代替未加权 AUC，更不能当物理效率。

当前 headline AUC 是未加权 raw-event AUC，不是 `weight_phys` 加权 AUC。物理产额的判断由阈值后的 `weight_phys` 求和完成。

完整的 split-level 指标为：

| split | events | raw AUC | `weight_train` AUC | raw logloss | `weight_train` logloss |
|---|---:|---:|---:|---:|---:|
| train | 3,121,211 | 0.968513 | 0.983211 | 0.313493 | 0.151925 |
| validation | 668,328 | 0.968521 | 0.984562 | 0.277850 | 0.150593 |
| test | 722,164 | 0.959740 | 0.983834 | 0.354835 | 0.152921 |

三份 `weight_train` 指标很接近，没有表现出典型的训练集极好、validation/test 明显崩塌。raw 指标的差异还包含各 split 样本与 helicity composition 不同的影响，不能只凭 raw logloss 的大小判断过拟合。

## 15. 独立 test 结果

### 15.1 普通样本 cutflow

| analysis category | test events before cut | pass score≥0.954 | raw efficiency | test weighted yield |
|---|---:|---:|---:|---:|
| `tth-hbb` | 84,672 | 49,688 | 58.6829% | 275.528 |
| `tth-nonbb` | 68,274 | 1,141 | 1.6712% | 6.393 |
| `ttz` | 76,595 | 4,166 | 5.4390% | 36.726 |
| `ttbb` | 141,330 | 8,896 | 6.2945% | 35.630 |
| `6q` | 2,593 | 2 | 0.0771% | 1.035 |
| `4f2l` | 348,700 | 147 | 0.0422% | 89.770 |

因此 held-out test 子集直接得到

\[
S_{\rm test}=275.528,
\qquad
B_{\rm test}=169.555,
\]

\[
S/B=1.625,
\qquad
Z_{\rm test}=13.060.
\]

这证明在未参与训练、也未用于选阈值的 jobs 上，工作点保持了较强的信号—背景分离。

### 15.2 为什么 test \(Z=13.06\) 不是完整 8 ab\(^{-1}\)

每个 test MC event 的确已经带有按 8 ab\(^{-1}\) 定义的

\[
w_{\rm phys}=\sigma L/N_{\rm gen}.
\]

但 test 只包含约 15% logical shards。将这些 event 的权重相加，只得到“落入 test MC 子集的那部分 expected yield”，不会自动把未进入 test 的 train/validation events 补回来。换言之，亮度在每个 event weight 中是 8 ab\(^{-1}\)，但 MC acceptance/efficiency 的估计只使用了 test 子样本，yield 仍按 test 所占 generator/reco 份额缩小。

这就是 test \(Z\) 与完整曝光 projection 不同的原因，不是重复乘亮度，也不是物理矛盾。

## 16. SM 与 CPV 是否被公平筛选

为了避免把 CPV non-bb truth composition 混入比较，公平检查只在 `analysis_category=tth-hbb` 内进行，并按 polarization 分开：

| sample | polarization | Hbb before | Hbb pass | efficiency |
|---|---|---:|---:|---:|
| SM | `eL.pR` | 46,016 | 27,338 | 59.4098% |
| SM | `eR.pL` | 38,656 | 22,350 | 57.8177% |
| CPV | `eL.pR` | 49,219 | 29,096 | 59.1154% |
| CPV | `eR.pL` | 23,326 | 13,626 | 58.4155% |

合并两种 helicity 后：

- SM Hbb：58.6829%；
- CPV Hbb：58.8903%。

在当前 test MC 统计下，两者非常接近，没有看到 baseline 对 CPV Hbb 的明显效率压制。这与模型未输入显式 CP-odd observable 的设计预期一致。

但这不是“严格证明模型完全 CP-neutral”。还需检查：

- CPV 与 SM 的 score shape，而不仅是单一阈值；
- efficiency 随 helicity、lepton flavor 和 phase-space 的变化；
- 被丢事件携带的 signed interference/Fisher information 是否与保留事件相同；
- CPV event sign 正式 join 后的 signed efficiency。

evaluation JSON 里 CPV 全样本效率约 33%，是因为它同时包含 Hbb 和 non-bb；不能拿该数与 Hbb-only 的 59% 直接比较。

## 17. naive 8 ab\(^{-1}\) 外推是怎样得到的

当前材料中的 naive projection 对每个大 category 使用

\[
N^{\rm proj}_c
=N^{\rm full,preMVA}_c
\times
\epsilon^{\rm test}_c.
\]

由完整 weights catalog 得到的 pre-MVA 产额为：

| category | full pre-MVA yield at 8 ab\(^{-1}\) |
|---|---:|
| `tth-hbb` | 2,166.129 |
| `tth-nonbb` | 1,736.184 |
| `ttz` | 7,629.200 |
| `ttbb` | 2,480.764 |
| `6q` | 8,983.713 |
| `4f2l` | 1,475,308.069 |

这张表也说明 MVA 的主要任务：pre-MVA 的 `4f2l` 物理产额比 Hbb 信号大约三个数量级，必须依靠非常强的尾部抑制。

例如 Hbb：

\[
2166.129\times0.586829=1271.148.
\]

六类相加后：

\[
S^{\rm naive}_{8\,ab^{-1}}=1271.148,
\qquad
B^{\rm naive}_{8\,ab^{-1}}=1228.987,
\]

\[
Z^{\rm naive}=25.422.
\]

材料生成器用简单二项近似估计该 projection 的有限 test-MC 误差约为 \(\sigma_S=3.67\)、\(\sigma_B=51.93\)。这尚未包含截面、luminosity、detector 或 modeling systematics，也不能修复缺失 strata。

这个 25.42 不是凭空产生，也不是把 test yield 再乘一个统一常数。它是“完整 pre-MVA 物理产额 × test category-global efficiency”的结果。

### 17.1 15个 test 空层究竟是什么

Whizard 背景由许多 process mask 和 helicity 组成，不同层的权重差异巨大，选择效率也可能不同。严格外推应使用

\[
N^{\rm proj}
=\sum_{k,c}
N^{\rm full,preMVA}_{k,c}
\epsilon^{\rm test}_{k,c},
\]

其中 \(k\) 是 normalization key。当前 66 个 `normalization_key × category` 层中，test 只覆盖 51 个；15 个没有任何 test HDF5/score event，对应完整 pre-MVA yield 278,287.956，主要来自高截面的 `4f2l` masks。

这里的根因不是“先把所有6q或4f2l事件合成一类，再按事件数70/15/15切分”，也不是“KinFit后事件太少所以进不了test”。`assign_mva_splits.py` 明确只把

```text
seed + "\0" + split_group
```

做 SHA-256，并按哈希值落入70% train、15% validation、15% test。它完全不看 sample label、process mask、事件数、feature或物理权重。`split_group` 是 logical production shard；同一shard的physical parts不会泄漏到不同split，但脚本没有在每个 `process mask × helicity` normalization层内强制至少安排一个test shard。

因此，若某层只有8个shard，test抽到0个的概率仍为 \(0.85^8=27.25\%\)；若只有2个shard，概率为 \(0.85^2=72.25\%\)。最大的空层 `P6f_yyveyx/eL.pR` 实际有399,392条MVA输入MC事件，只是它的8个shard恰好7个进train、1个进validation、0个进test。这直接证明“事件太少”不是必要原因。

下表中的“MVA输入MC事件”是冻结HDF5中的事件数。对Whizard而言，它们已经经过上游 `nIso=1` skim、KinFit处理以及exporter可用性条件；不是generator \(N_{\rm gen}\)，也不是MVA阈值后的数量。“MVA前物理产额”是这些冻结事件按 \(w_{\rm phys}=\sigma L/N_{\rm gen}\) 换算到550 GeV、8 ab\(^{-1}\)的expected events。

| process mask | helicity | 可用独立层 | train jobs/events | validation jobs/events | test jobs/events | MVA输入MC | MVA前物理产额 | fallback pass/total | efficiency | MVA后投影 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4f2l `eexxxx` | eL.pR | train-only | 8 / 3,992 | 0 / 0 | 0 / 0 | 3,992 | 29.0188 | 0 / 3,992 | 0 | 0 |
| 4f2l `eexyyx` | eR.pL | validation | 6 / 6,634 | 2 / 2,174 | 0 / 0 | 8,808 | 2,072.5492 | 0 / 2,174 | 0 | 0 |
| 4f2l `eeyyyy` | eL.pR | validation | 6 / 2,443 | 2 / 766 | 0 / 0 | 3,209 | 45.4122 | 4 / 766 | 0.5222% | 0.2371 |
| 4f2l `llxyyx` | eL.pR | validation | 7 / 6,000 | 1 / 887 | 0 / 0 | 6,887 | 3,548.2278 | 0 / 887 | 0 | 0 |
| 4f2l `llyyyy` | eR.pL | train-only | 8 / 4,192 | 0 / 0 | 0 / 0 | 4,192 | 35.8938 | 24 / 4,192 | 0.5725% | 0.2055 |
| 4f2l `vvxxxx` | eR.pL | validation | 7 / 14 | 1 / 3 | 0 / 0 | 17 | 0.0995 | 0 / 3 | 0 | 0 |
| 4f2l `vvxyyx` | eR.pL | train-only | 7 / 27 | 0 / 0 | 0 / 0 | 27 | 0.9103 | 0 / 27 | 0 | 0 |
| 4f2l `xxveyx` | eL.pR | validation | 6 / 14,273 | 2 / 4,772 | 0 / 0 | 19,045 | 9,419.1576 | 0 / 4,772 | 0 | 0 |
| 4f2l `xxxyev` | eL.pR | validation | 6 / 14,290 | 1 / 2,376 | 0 / 0 | 16,666 | 9,441.8144 | 0 / 2,376 | 0 | 0 |
| 4f2l `xxxyev` | eR.pL | validation | 7 / 17,043 | 1 / 2,443 | 0 / 0 | 19,486 | 75.4486 | 0 / 2,443 | 0 | 0 |
| 4f2l `xxxylv` | eL.pR | validation | 6 / 12,943 | 2 / 4,354 | 0 / 0 | 17,297 | 8,911.3269 | 0 / 4,354 | 0 | 0 |
| 4f2l `yyveyx` | eL.pR | validation | 7 / 348,716 | 1 / 50,676 | 0 / 0 | 399,392 | 244,192.6668 | 30 / 50,676 | 0.05920% | 144.5611 |
| 4f2l `yyxyev` | eR.pR | validation | 4 / 7,065 | 4 / 7,167 | 0 / 0 | 14,232 | 509.3762 | 0 / 7,167 | 0 | 0 |
| 6q `xxxyyx` | eR.pL | train-only | 2 / 41 | 0 / 0 | 0 / 0 | 41 | 1.3708 | 1 / 41 | 2.4390% | 0.0334 |
| 6q `yyyyyy` | eL.pR | validation | 5 / 85 | 2 / 33 | 0 / 0 | 118 | 4.6828 | 2 / 33 | 6.0606% | 0.2838 |

其中11个validation层合计 MVA 前物理产额278,220.7621，4个train-only层合计67.1937；此前口头所说“约66”应以这里的精确值67.19为准。逐层机器可读版本是 `missing_strata_detailed.csv`。

### 17.2 不重训的覆盖修补结果

最小修补遵守三条规则：

1. 51个已有test层仍只用test效率；
2. 11个test空层使用未参与训练的validation效率，并从重算阈值的validation集合中排除；
3. 4个只有train的层不假装独立，中央值列出模型表观效率，同时用“全部不通过”和“100%全部通过”给极端界限。

重算阈值仍为0.954。逐层汇总得到

\[
S_{8\,ab^{-1}}=1277.210,\qquad
B_{8\,ab^{-1}}=1326.255,
\]

\[
Z_{\rm count}=\frac{S}{\sqrt{S+B}}=25.031.
\]

4个train-only层中央投影只贡献0.239个背景expected events。若把它们设为零通过，\(Z=25.033\)；若极端设为全部通过，\(Z=24.716\)。所以这15层会把旧naive值25.42修正到约25.03，但不会把结果推翻。

这套方法仍不能称为“所有层都有独立test”的最终 cross-validation；更准确的名称是 `coverage-closed statistical diagnostic with bounded train-only remainder`。若要完全消除最后4层的训练内评估，只需以后做分层新split或K-fold out-of-fold复核，不需要重做HDF5、KinFit或物理归一化。

绝对不能把当前单模型在全部train+validation+test上的score直接混起来选阈值或报AUC/显著性，因为物理权重不能消除模型已经见过train事件造成的乐观偏差。全MC score只能作为明确标注的响应示意图。

## 18. significance 与 \(y_t\) 精度

当前使用的

\[
Z=\frac{S}{\sqrt{S+B}}
\]

专业上可称作 simple counting significance，或更谨慎地称 `S/sqrt(S+B) sensitivity metric`。它不是含 nuisance parameters 的 profile-likelihood significance。

在背景完全已知、仅统计误差、信号强度只改变 \(S\) 的理想近似下：

\[
\frac{\Delta\sigma}{\sigma}\approx\frac{1}{Z}.
\]

若进一步近似 \(\sigma_{t\bar tH}\propto y_t^2\)，则

\[
\frac{\Delta y_t}{y_t}
\approx\frac{1}{2}
\frac{\Delta\sigma}{\sigma}
\approx\frac{1}{2Z}.
\]

但 e\(^+\)e\(^-\)→ttH 并非严格只有一个与 \(y_t^2\) 成正比的图；严肃精度应使用实际 \(d\ln\sigma/d\ln y_t\) 或模板/likelihood。当前也没有背景系统学、截面不确定度、探测器系统学和 nuisance profiling。

因此：

- 对 test \(Z=13.06\) 计算出的 3.83% 只属于 test 子集的形式换算，没有完整曝光物理意义；
- coverage-closed \(Z=25.03\) 可以作为当前样本清单下的8 ab\(^{-1}\)、统计-only simple-counting sensitivity认真报告；
- 代入 \(1/(2Z)\) 得到约2.00%只能称作“\(\sigma\propto y_t^2\)、背景完全已知”下的直观换算，不能冒充正式 \(y_t\) 精度；
- AUC、独立 test efficiency、test category rejection 和 SM/CPV Hbb efficiency compatibility仍是最直接的模型性能证据。

## 19. 与旧文献怎样公平比较

[arXiv:1104.5132](https://arxiv.org/abs/1104.5132) 的设置约为 500 GeV、1 ab\(^{-1}\)、\((P_{e^-},P_{e^+})=(-0.8,+0.3)\)、\(m_H=120\) GeV、fast simulation。其报告：

| 通道 | 文献 \(Z\) | 文献 \(\Delta y_t/y_t\) |
|---|---:|---:|
| semileptonic | 3.7 | 14% |
| semileptonic + 8-jet combined | 5.2 | 10% |

如果只做统计亮度缩放到 8 ab\(^{-1}\)：

\[
Z(8)=Z(1)\sqrt8,
\qquad
\delta(8)=\delta(1)/\sqrt8.
\]

得到：

| 通道 | 纯亮度外推 \(Z\) | 纯亮度外推 \(\Delta y_t/y_t\) |
|---|---:|---:|
| semileptonic | 10.47 | 4.95% |
| combined | 14.71 | 3.54% |

这只能作为量级比较，因为当前分析使用 550 GeV、125 GeV Higgs、新 reconstruction/flavor tagging、不同极化方案、不同背景组成和 MVA。

[arXiv:2503.19983](https://arxiv.org/abs/2503.19983) 所引用的 550 GeV、8 ab\(^{-1}\) 约 1.9% 预期，不是把 500 GeV/1 ab\(^{-1}\) 的 10% 单纯除以 \(\sqrt8\)。550 GeV 相对 500 GeV 的 ttH 截面增益和整体分析假设也进入了该估计。

公平比较应至少列出：能量、亮度、beam polarization、Higgs mass、通道、生成器、探测器模拟、preselection、背景清单、系统学、统计方法，以及比较的是一个通道还是 combined。

## 20. Condor DAG 到底做什么

`prepare_selection_mva_condor.py` 生成的依赖图是：

```text
TRAIN
  └── APPLY0000, APPLY0001, ...（每个进程最多 20 jobs）
          └── EVALUATE
```

`condor_submit_dag workflow.dag` 的含义是把这张依赖图交给 Condor。命令本身很快返回，不代表训练和评估瞬间完成；真正状态要看 DAG nodes、Condor logs 和最终输出。

仓库还有 `run_selection_mva_staged_condor.sh`：

- 检查 Kerberos ticket；
- 依次提交 TRAIN、APPLY、EVALUATE；
- 每阶段用 `condor_wait` 等完成；
- 核对 score shard 和 completion JSON 数目；
- 可安全复用已存在且 provenance 完全匹配的模型/score。

本档案重建过程中没有提交 Condor，也没有重新训练。所有数字来自既有 `baseline-xgboost-v1`。

## 21. 现有图应如何阅读

### 21.1 validation 阈值扫描

![validation threshold scan](../outputs/mva/group_materials/baseline-xgboost-v1_20260821_exact_audit_v7/threshold_scan.png)

虚线是 0.954。左上只表示 validation 子集上 `S/sqrt(S+B)` 的最大点，不是完整 8 ab\(^{-1}\) significance。

### 21.2 test score 分布

![test score distributions](../outputs/mva/group_materials/baseline-xgboost-v1_20260821_exact_audit_v7/score_distributions_exact.png)

左图按 category 各自单位面积归一，回答 shape separation；右图使用 test `weight_phys`，回答 test 子集的加权 yield。右图纵轴为 log scale。两图不能混读。

### 21.3 SM/CPV Hbb efficiency

![SM CPV Hbb efficiency](../outputs/mva/group_materials/baseline-xgboost-v1_20260821_exact_audit_v7/sm_cpv_hbb_efficiency.png)

四条曲线在大部分阈值范围内接近。它支持“当前 baseline 没有明显 CPV Hbb 效率偏置”，但不替代 signed-information 检查。

### 21.4 训练曲线

![training logloss](../outputs/mva/group_materials/baseline-xgboost-v1_20260821_exact_audit_v7/training_logloss.png)

曲线到约 871 轮仍缓慢改善，随后早停。validation weighted logloss 略低于 train 并不自动意味着错误，因为训练/validation 的样本 composition 不同，且二者使用同一 train-derived balancing coefficients；是否存在 domain composition 效应可通过逐 sample/helicity loss 进一步检查。

v7中的上述四张旧图与v6逐文件SHA-256完全相同；代码没有改变它们的数据口径。v7只新增覆盖修补表、效率—显著性双轴图和feature importance图。

## 22. 当前最值得组会检查的错误线索

1. **manifest 配置漂移**：冻结 manifest 的生成配置与当前 `mva_samples.yaml` 不同，当前 builder 对 `normalization.status` 仍有旧 schema 依赖。
2. **4个train-only小层尚无独立效率**：15个test空层中11个已由held-out validation补齐；剩余4层合计MVA前产额67.19，已用零通过/全通过极端范围约束到 \(24.72\le Z\le25.03\)。
3. **背景高分尾部 MC 很稀疏**：test 中 `6q` 只有 2 个、`4f2l` 只有 147 个通过；完整 projection 的 background MC uncertainty 不能忽略。
4. **单一 train/validation/test split**：当前没有 K-fold/out-of-fold closure，split fluctuation 尤其会影响高权重 Whizard masks。
5. **统计量过于简化**：没有 profile likelihood、背景系统学、normalization uncertainties 或 shape fit。
6. **CPV sign 尚未回接**：目前只能比较 raw Hbb efficiency，不能计算选择后的 signed interference 或 CP Fisher information。
7. **feature importance 可能暴露依赖**：`btag_3` 的 gain 极高。应做去除 `btag_3`、去除已有 `final_selection_score`、去除 fit-score group 的 ablation，确认结果不是某一输入或已有 selection score 的单点支配。
8. **physics-background completeness**：当前背景清单是 `tth-nonbb, ttz, ttbb, 6q, 4f2l`。正式会议结果必须说明是否还有未纳入但在 selection 后相关的过程。

## 23. 当前可以与不可以说的话

### 可以说

- 已在 5,256,280 个冻结 HDF5 events 上建立 catalog-driven MVA pipeline。
- baseline 使用 25 个明确冻结、无 truth/ID/weight 泄漏的特征。
- XGBoost 未使用 CPV 训练；阈值只在 validation 上选择。
- independent ordinary test AUC 为 0.95974。
- 阈值 0.954 时，SM Hbb test efficiency 为 58.68%，主要背景效率被压到 0.04%–6.29%。
- SM 与 CPV 在 Hbb、同 polarization 条件下效率非常接近。
- test-first/held-out-validation覆盖修补给出完整8 ab\(^{-1}\)统计-only \(S=1277.21\)、\(B=1326.25\)、\(Z=25.03\)；4个train-only层取全通过的极端保守值为24.72。

### 暂时不能说

- “半轻子完整 8 ab\(^{-1}\) profile-likelihood significance 已正式达到25。”当前只有simple counting、无系统学的sensitivity metric。
- “\(\Delta y_t/y_t\) 已正式达到2.0%。”这仍缺正确的 \(\sigma(y_t)\) dependence和nuisance profiling。
- “当前一个通道已经严格超过旧文献两个通道 combined。”
- “选择对 CP 信息完全无损。”
- “AUC 0.95974 等于 95.974% 信号识别成功率。”

## 24. 形成正式会议结果的最短闭环

1. 保留本次66层 `projection_coverage_closed.csv` 作为当前统计结果，并由第二种独立实现复算 \(S\)、\(B\) 和 \(Z\)。
2. 对高分尾部给出有限 MC 统计不确定度；必要时合并有物理依据的 masks，但不得静默合并。
3. 加入背景/normalization systematics，至少给 counting likelihood；随后再考虑 score-shape likelihood。
4. 用正确的 \(\sigma(y_t)\) dependence 把信号强度精度映射为 \(y_t\) 精度。
5. 完成 CPV event-sign join，比较 selection 前后 signed interference/Fisher information。
6. 分层新split或K-fold out-of-fold是消除最后4个train-only层并检验split波动的增强项，不再是获得当前约25统计量的前置条件。
7. manifest builder/config drift仍应单独修复，以恢复从job plan重建冻结manifest的端到端可复现性。

## 25. 权威文件位置

NAF 仓库：

```text
/data/dust/user/zhangyuy/tth-cpv-observable-ilc
```

冻结数据与模型：

```text
outputs/mva/datasets/export_test/
outputs/mva/manifests/mva_input_manifest.csv
outputs/mva/normalization/physical_normalization_inventory.json
outputs/mva/splits/mva_semilep_split_assignment.json
outputs/mva/weights/mva_semilep_physical_weights.json
outputs/mva/training/baseline-xgboost-v1/
outputs/mva/scores/baseline-xgboost-v1/
outputs/mva/evaluation/baseline-xgboost-v1.json
```

审计材料：

```text
outputs/mva/group_materials/baseline-xgboost-v1_20260821_exact_audit_v7/
```

其中 `manifest.json` 将 exact test 的 194 jobs、852,717 events 与 `(job_key,event_index,score)` 绑定，并记录 builder、production summary、cutflow source 和所有材料文件的 SHA-256。

### 25.1 各阶段命令关系

在环境已经配置且输入产物存在时，核心命令关系是：

```bash
source env/setup.sh

# 生成器级归一化 inventory
python3 scripts/mva/build_physical_normalization_inventory.py

# 对冻结 HDF5 建立 logical-shard split
python3 scripts/mva/assign_mva_splits.py

# 将 split/HDF5 与物理 normalization 关联
python3 scripts/mva/prepare_mva_weights.py

# 使用新 run ID 训练；已存在的 baseline 目录不会被覆盖
python3 scripts/mva/train_selection_mva.py \
  --config configs/mva_training.yaml \
  --run-id <new-run-id>

# 对 catalog jobs 打分；CPV 只在显式开关下打分
python3 scripts/mva/apply_selection.py \
  --config configs/mva_training.yaml \
  --model outputs/mva/training/<new-run-id>/model.json \
  --output-dir outputs/mva/scores/<new-run-id> \
  --include-cpv

# validation 选阈值，test 独立评估
python3 scripts/mva/evaluate_selection.py \
  --config configs/mva_training.yaml \
  --model outputs/mva/training/<new-run-id>/model.json \
  --scores-dir outputs/mva/scores/<new-run-id> \
  --output outputs/mva/evaluation/<new-run-id>.json
```

这不是让人现在重跑 baseline 的指令。现有 baseline 已冻结；任何新训练必须使用新 run ID。更上游的 `build_mva_manifest.py` 当前还存在第 4.1 节记录的配置漂移，修复和版本化之前不应声称可从 job plan 原样重建。

## 26. 最终判断

这项工作绝不是“简单 cut 两下后和十年前差不多”。现有结果已经明确证明，新 reconstruction、flavor tagging、KinFit 和 MVA 在独立 test MC 上提供了很强的 signal ranking 与 background rejection；这部分应当认真对待。

现在已经把强模型性能转换成当前样本清单下、口径明确的8 ab\(^{-1}\) simple-counting统计诊断 \(Z=25.03\)，并证明15个test空层不会推翻该量级。真正尚未完成的是有限MC尾部不确定度、系统学、likelihood统计以及严格的 \(y_t\) 映射。

因此最准确的研究状态是：**模型性能结果已经成立；完整8 ab\(^{-1}\)统计-only counting sensitivity约为25并已做归一化覆盖诊断；正式 \(y_t\) 精度仍待系统学、likelihood和耦合依赖闭环。**
