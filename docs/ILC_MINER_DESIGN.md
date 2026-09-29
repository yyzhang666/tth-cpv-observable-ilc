# ilc-miner：设计契约与分阶段实施计划

状态：开发骨架与设计提案，尚未实现下述分析 API / CLI。2026-09-29。

分支起点：`observable_workflow@c116c86895d96f309c97196593f30514d6668a6e`。
所有新工作仅在 `ilc-miner` 分支进行。历史教学材料、分析脚本、专用配置、已跟踪数据 / 产物及旧包结构已从本分支移除；不保留 legacy 目录。
当前只保留本设计、项目说明、原许可声明、可安装的 `ilc_miner` 包骨架及通用 provenance 工具和测试。下述目标模块布局是后续实施计划，不代表已经存在。
其他分支、外部原始数据、训练结果与同步项目文件不修改。删除前的完整树可从 [`476383ddf2f4179150c681eed4eec00797c10a48`](https://github.com/yyzhang666/tth-cpv-observable-ilc/tree/476383ddf2f4179150c681eed4eec00797c10a48) 恢复；未重写 Git 历史。

## 1. 范围与取舍

目标是一个用户选择 feature、训练目标、模型参数与实验条件之后，就能完成训练、观察量、模板和 Fisher 评估的 ILC 机器学习观察量包。

借鉴 [MadMiner](https://arxiv.org/abs/1907.10621) 的函数组织、模块边界和调用体验，不重建它的通用模拟 / morphing / 推断平台。第一版针对当前 CPV 干涉正负分类；保留将来其他过程和局域 score 回归的扩展点。

用户已授权：新分支不必兼容旧目录、旧脚本、旧 CLI、旧数据文档。不能适应新工作流的结构可删除或重写，不要求保留一个永久 legacy 子系统。保留的是经过检查的物理算法、可用的 ILC 输入适配器及有意义的测试，而不是历史脚本入口。原分支和 Git 历史承担历史复现用途。

旧 DATA_SCHEMA 或 weight 列不是物理定义的权威。当前脚本中重新计算权重的做法不能仅因不符合旧文档就被判错。物理契约、生成方式、实际来源元信息和采样统计共同决定归一化。

非目标：第一版不运行事件生成 / 探测器模拟，不自动发生产任务，不实现全局参数扫描、通用 morphing 或任意 nuisance profiling。不把“给 feature”误解成无需训练样本、目标定义、归一化信息就能生成物理结论；这些由一次配置提供。

## 2. 对现有代码的定向检查

以下为清理前固定提交的历史源码检查；表中的路径属于历史版本，不是当前包的可用入口。只检查 feature → training → observable → templates/Fisher 边界，不作全仓库质量结论。

| 候选逻辑 | 源码证据与已确认行为 | 新包决策 |
| --- | --- | --- |
| Feature 解析 | `src/ilc_tth_cpv/ml_features.py` 已集中部分派生 feature；`scripts/build_ml_observable.py` 仍有重复解析；两个 exporter 含重叠的对象构造 / IO | 提取并逐项验证算法，所有消费者只使用新 resolver；不保留重复解析 |
| 归一化与模板 | `scripts/build_ml_observable.py` 由截面、生成统计及 split fraction 重建权重；`src/ilc_tth_cpv/event_workflow.py` 则消费 `weight_8ab` | 不把两种输入契约混用；用统一、显式的 normalization 模块替代隐含约定 |
| 三分类 | `scripts/workflows/prepare_multiclass_dataset.py` 和 `train_threeclass_model.py` 已有 SM / SM+background 中性类、class balancing 和 split 管理；旧类别集合为 (-1,0,1) | 复用经测试的算法思想，不沿用旧标签、固定亮度列或手工 test scale 契约 |

以上是源码行为确认，不等于已经验证真实样本的生成器归一化。实际样本的 cross section 定义、signed sample 采样方式、生成层 split 统计、过滤效率与参数 convention 仍需在首个 sample manifest 中逐项核对。未运行旧训练或生产任务。

源码基准均为 [上述固定提交](https://github.com/yyzhang666/tth-cpv-observable-ilc/tree/c116c86895d96f309c97196593f30514d6668a6e)。

## 3. 模块边界

包名暂定 `ilc-miner`，Python import 为 `ilc_miner`。先保持薄模块，不先开发插件框架。

```text
src/ilc_miner/
    feature.py           # feature 函数、注册、依赖解析、元信息
    dataset.py           # 事件身份、sample manifest、split、feature materialization
    io/                  # CSV/Parquet 与 ILC ROOT/LCIO/sidecar 源适配
    normalization.py     # 来源归一化、极化、train/physical weight 的计算
    targets.py           # binary / threeclass 标签与 reference-class 构成
    models.py            # 训练 / 预测统一接口、后端适配、训练产物
    ml_observable.py     # 概率到观察量的命名函数和能力要求
    templates.py         # SM、背景、参数导数模板及 sumw2
    fisher.py            # 局域 Fisher；明确 rate+shape / shape-only
    pipeline.py          # 顺序调度、检查、缓存复用与失败恢复
    provenance.py        # 内容指纹、版本、resolved config、产物清单
    cli.py               # 参数解析后调用上述函数，不含物理计算
    processes/
        tth_cpv.py       # ttH 对象语义、selection、基准 feature 集与样本角色

configs/                 # 最小可运行分析配置 / 样本配置示例
examples/                # 小型 CPV 二 / 三分类示例
tests/                   # 单元、toy closure、端到端测试
```

初期 feature 函数可以集中在 `feature.py`；变大后可拆文件并自动导入注册，但用户只需增加一处定义，无需编辑 exporter、trainer 和 evaluator。

IO 只负责原始字段读取和事件关联，feature 库负责物理语义及计算。对象处于 lab / boosted frame、gen / reco / fit 阶段、对象排序与单位都属于定义。不能把数值列同名当作物理等价。

核心模块不得硬编码 ttH、H→bb、电子 / μ 子道、某个极化、8 ab⁻¹、固定 chunk 数、固定选择阈值或分析机器路径。上述配置在 process adapter / run config 中提供。ROOT / LCIO 依赖为可选输入组件，CSV toy 流程不依赖完整 ILC 环境。

## 4. 数据身份与归一化元信息

事件表与样本元信息分开，但通过来源 ID 强关联。

- `event_uid` 至少区分 dataset/process、生成来源文件或 chunk 和原始事件号。CSV 行号不能作 join key。
- `source_group_id` 标明共享一个归一化积分的生成样本；不同 chunk 是同一 sample 的分片，不是各自独立的完整截面。
- `split_group_id` 把同一物理事件的多种表示、相关变体等绑定在同一个 split。标签名和 process 名不能代替对相关样本的识别。
- manifest 记录 source 列表、完整内容校验或可信不可变 ID、生成统计、截面及其单位、beam energy、helicity / generation polarization、生成阶段过滤与衰变约定、权重 convention、参数定义和 reference point。
- split 记录分配规则、seed、所属来源、生成层总数（若可得）或已知抽样概率。选择失败或没有事件通过选择的来源仍可能属于生成归一化覆盖范围。
- dataset selection 与 feature validity mask 独立记录，不通过减小生成器分母来“补偿”选择损失。

缺失必要元信息时，preflight 报具体 sample 和字段，允许用户手动补齐；不从旧 weight 列反推未知物理参数。

## 5. 物理权重：运行时从实际 test 来源计算

### 5.1 正权、无权事件的基本情形

对运行时期 r、过程 p、纯 helicity h 和归一化组 g：

```text
w_phys(i,r) = L_r × f_h(P_e-,r, P_e+,r) × sigma_norm(p,h,g) / N_gen,test(p,h,g) × u_i
```

在普通无权正样本中 `u_i = 1`。其中：

- `L_r` 为目标实验积分亮度，不是 MC 文件的亮度。
- `L_r × f_h` 为该目标运行时期的 helicity exposure。
- `N_gen,test` 是 test 所代表的生成统计，定义在分析选择之前；不是 test CSV 的行数。
- `sigma_norm` 的生成相空间、衰变分支比、生成器过滤阶段与分母必须匹配。
- 同一分布的多个独立 chunk 使用合并后的生成统计；不能让每个 chunk 都代表完整截面后再相加。互不相交相空间子样本需各自明确的积分和合并规则。

若只知道 parent 生成总数以及独立于物理变量的 test 抽样概率 q，可使用 inverse-inclusion-probability 估计：母样本权重乘 1/q，等价于无权情形分母 q×N_gen,parent。必须记录这是抽样估计，不冒充已知的精确生成层 test 数。非均匀抽样要有逐事件 inclusion probability；不知道就不能自动恢复无偏归一化。不得隐式假定 test 永远占 20%。

两个“有效亮度”不能共用一个含糊字段：

- MC effective luminosity：正无权样本的 `N_gen / sigma_norm`；
- 目标 helicity exposure：`L_target × f_h`。

允许用户输入其中足以确定归一化的一组量；冗余输入 N、sigma、L_MC 必须一致，单位显式转换。signed 样本中的 N/sigma_abs 只能叫绝对采样归一化 exposure，不能冒充有符号物理截面的普通 MC 亮度。

### 5.2 干涉和一般加权事件

若生成样本按绝对干涉密度采样：

```text
sigma_abs = integral |d sigma_1|
u_i       = sign(d sigma_1 at generated event)
```

则上述公式的 sigma_norm 为 sigma_abs。正负事件共享同一个绝对密度采样的生成分母；不能把可能接近零的有符号积分当成该采样的 sigma_abs。只有确实分别生成并具有各自积分的正 / 负来源，才能按它们各自的生成契约归一化。

若事件具有非恒定 generator / importance weights，N、sigma、L 三个总量不足以恢复事件间的相对权重。适配器必须同时提供可信的原始相对权重以及 sumw / proposal normalization convention。首版支持哪些 convention 要列白名单，不认识就拒绝，不套用常数权重。

旧 CSV weight 不作为默认真值；但这不意味着可以抹去真实的非平凡 generator 权重。

`sigma_1` 和 S1 必须表示指定参数 c 在 c0 处的导数。矩阵元干涉项的因子 2、角度或耦合参数变换的 Jacobian 都要显式处理，不能仅根据“CPV sample”名字决定。

### 5.3 极化

采用 P=(N_R−N_L)/(N_R+N_L)，纯 helicity cross sections 的混合系数为：

```text
f_LR = (1-P_e-) (1+P_e+) / 4
f_RL = (1+P_e-) (1-P_e+) / 4
f_LL = (1-P_e-) (1-P_e+) / 4
f_RR = (1+P_e-) (1+P_e+) / 4
```

符号约定和公式可核对 [Quach et al., PTEP 2022, Sec. 3](https://academic.oup.com/ptep/article/2022/7/073C01/6617888)。

保留四种 helicity 接口，不默认 LL/RR 永远为零。缺少有非零贡献的来源时 preflight 失败，除非过程配置提供有物理依据的零贡献声明或有效重加权方案。

已经按部分极化生成、且截面已经包含该混合的样本，不能再无条件乘一次纯 helicity fraction。改变它的目标极化需要足够的 helicity / matrix-element 信息；只有一个混合截面时一般不能恢复新的分布。

不同运行时期可有不同 luminosity / polarization。一个时期内 helicity 分量通常是不可观测的混合，应先合并模板再计算 Fisher；统计独立且运行条件可区分的时期 / 子道分别计算后相加。不能把潜在 helicity 分量当作已标记实验子道，从而虚增信息量。共享 nuisance 将来要在联合模型中处理。

### 5.4 手工覆盖与输出

优先级：显式 CLI override > 用户配置 > 来源 metadata。按 sample / normalization group / helicity / split 定位，不允许一个模糊全局参数悄悄覆盖所有背景。

每次输出 `normalization_report.json`：原值、覆盖值、单位、来源、分母依据、split 抽样概率、极化分数、目标 exposure、选择前后计数及各角色 sumw / sumw2。

权重按当前 resolved config 生成。可缓存一个配置指纹匹配的计算结果，但不能把某次实验条件下的权重列永久当作 dataset 的物理属性。

## 6. 训练权重和二 / 三分类

训练权重与模板物理权重共享来源归一化引擎，但不是同一份数组：

- template 权重使用 test 来源统计、评估时期与物理符号；
- training 权重使用 train 来源统计、训练混合条件及合法的非负损失权重；
- 干涉正 / 负事件的分类训练使用绝对导数贡献，正负号进入 target，不能把负权直接传入普通分类损失；
- SM 与背景使用相应正参考贡献；一般 signed-NLO 名义样本不能靠无提示取绝对值解决，首版要明确支持范围。

训练混合支持指定一个极化或多个运行时期的 exposure。按来源生成量、截面及极化分数共同决定混合，不能只乘极化分数却忽略不同 sample 的 MC 统计。训练与评估运行方案可以不同，但必须显式记录；分类概率的解释针对训练方案，不能声称自动变成另一个方案的最优 score。

建议对外使用语义标签 `minus`、`plus`、`reference`，默认整数映射为：

| 类别 | 对外默认 ID | 内容 |
| --- | --- | --- |
| minus | 0 | 负的参数导数贡献 |
| plus | 1 | 正的参数导数贡献 |
| reference | 2 | SM，或 SM+background |

旧的 ±1 标签只在一次输入适配时转换。模型后端的内部类别顺序必须保存，观察量通过语义索引读概率，不能依赖数组第几列恰好是什么。

三分类选项：

- `reference_class: sm`：类别 2 只训练 SM，背景仍可在最终 Fisher 中出现；
- `reference_class: sm_plus_background`：类别 2 包含 SM 和背景，内部比例由物理混合权重决定；
- classifier label 不覆盖 sample 的物理 role。即便 SM / background 都标成 2，模板仍分别保留 S0 和 B。

允许 `class_balance: none | equal_total`。推荐先提供不平衡的物理混合基线；兼容已有分析结论时也记录其平衡方案。平衡只能在构成物理类别混合之后做，并记录全局类别乘子 a_k，不能先把每个 helicity 或背景过程等权而破坏物理混合。

若训练权重额外乘了 a_k，模型 raw probability 近似比例于 a_k×真实类别密度。仅在这种全局类别重缩放的条件下，可恢复：

```text
q_k = (P_k / a_k) / sum_j(P_j / a_j)
```

重采样也要计入有效类别倍率。不能在已经物理加权后再不加判断地除一次经验类别先验。概率校准、训练效果以及是否实际学到目标密度仍需验证；倍率修正不是校准的替代。

## 7. Feature：定义一次，所有阶段共用

概念接口（尚未实现）：

```python
# src/ilc_miner/feature.py
@feature(deps=("top_pt", "higgs_pt"), version="1", unit="GeV", stage="reco")
def v(top_pt, higgs_pt):
    return top_pt - higgs_pt
```

用户只加这个命名函数和同处的声明即可，不另改三套解析或手动维护一个外部 feature 列表。读取现有列的 feature 也注册为明确定义；原始字段的读取通过统一 dataset/source 接口完成。

`ensure_features(dataset, names)` 的行为：

1. 检查名称和允许的输入角色，拒绝 target、weight、truth label 等隐性泄漏字段作为普通 reco feature。
2. 已有列只有在定义 / 来源 / stage / frame 指纹兼容时直接复用；同名不等于同定义。
3. 缺列时递归解析依赖，拓扑排序，检测循环；共享依赖每批只算一次。
4. 先利用已有 primitive columns；必要时按 event_uid 批量读取关联源文件的所需 collection / branch。
5. 若依赖不可得，报告 feature → dependency → missing source；不猜值、不静默换 feature。
6. 保存结果和 provenance。训练和 test 调用相同函数，feature 顺序从模型 artifact 固定读取。

旧 CSV 可通过显式 `import-existing` 步骤绑定列语义与来源；未确认的旧列不能自动宣称通过版本校验。已有可确认的列无需重新导出全部原始事件。

定义元信息至少包含：名称、定义版本、依赖、dtype、单位、gen/reco/fit stage、参考系、对象排序、有效域 / missing policy。角度区间、缺失对象如何处理、输入 sentinel 如何转为 missing 均为物理定义的一部分。

有效性默认“保留行并报告 invalid”，不是自动 drop。若分析选择要求丢弃无效行，应显式形成 selection mask、报告各 sample 接受率，保持原来的生成分母。比较 feature set 时要报告共同事件集合与各自接受率，避免把接受率变化混同于模型改善。

插补器、scaler、校准器只能在训练 / 指定校准集合拟合，然后冻结给 test；这种有状态变换属于模型产物，不是全数据通用 feature 缓存。

## 8. 增量导出与缓存

概念 CLI（尚未实现；无需兼容旧脚本内部结构）：

```bash
ilc-miner features export --samples samples.yaml --features baseline --output ml_superdataset.csv
ilc-miner features add --input ml_superdataset.csv --add v,another_feature

# 可提供同一库函数的薄便利入口：
python scripts/export_features.py --input ml_superdataset.csv --add v
```

`add` 只新增选定列及必要的依赖缓存，默认不覆盖已有定义不同的列、不改变事件数、身份、split 和已有值。发现同名不同版本时要求显式 `--recompute v`。运行中断不留下一个看似成功的半表。

CSV 不能高效原地追加“列”：实现时需要流式读旧表、join 新列、写临时文件，然后原子替换（可保留备份）。这避免重新解析和计算完整原始数据，但仍有一次表 IO。大数据默认内部列缓存可用 Parquet sidecar；CSV 保留用户交换入口。CLI 和 pipeline 共享同一个 materialization 函数。

保证 event_uid 一对一，不用行顺序强行拼接。若新列计算时 source/filter/order 不匹配立即失败。table 和 metadata 的提交采用单写锁、事务清单和校验值，避免一份已更新 CSV 搭配旧 metadata。

Feature cache key 至少包含：来源内容 / source ID、事件身份集合、定义版本 / 代码指纹、依赖指纹、物理配置（stage/frame/对象排序）。共同 helper 改变也必须失效。包 / Git 版本用于总 provenance，不以“任意代码改动让所有 feature 缓存全部失效”作为常态。

缓存依赖方向：

```text
sources + feature definitions → feature columns
samples + normalization config + split → weights
features + target + training weights + model config → model
model + feature matrix → probabilities
probabilities + observable definition → observable
observable + physical weights + selection + bins → templates
templates + inference settings → Fisher
```

只改变 observable 时复用概率；只改变评估亮度通常可复用固定模型 / 固定 binning 下的概率与基础模板，但必须重算预期计数和 Fisher。训练极化、类别混合或相应训练权重改变，模型缓存失效。相同模型下改变评估极化可重组合 helicity 模板，但不能宣称模型已对新极化重新优化。

缓存 key 包含 seed、后端版本、模型参数、feature 顺序、target 与 reference 定义。损坏 / 不完整 artifact 不参与复用。首版只需简单确定性的阶段调度和 manifest，无需通用任务图服务。

## 9. 可扩展 ML 观察量

所有定义在 `src/ilc_miner/ml_observable.py`，命名注册。函数接收带语义类名的概率对象及显式参数，不自己读取 CSV、不重算 feature、不重建权重。

初始定义：

- `prob_diff`：P(plus) − P(minus)，默认，支持二 / 三分类，范围 [-1,1]。
- `prob_diff_over_reference`：[P(plus) − P(minus)] / P(reference)，仅三分类。
- `corrected_diff_over_reference`：使用上节修正后的 q；单独命名，不能悄悄改变 raw observable 的定义。

这里将用户的比值表达式理解为整个差值除以第三类概率。第三类为 SM+background 时称 P(reference) 或 P(2)，不能标成纯 P(SM)。

关键区别：raw probability 比值受训练的类别倍率影响。若分类器准确学习了以物理强度构造的类别、基准和导数 normalization 匹配，且正确消除了额外类别倍率，则：

```text
(q_plus - q_minus) / q_reference
≈ local derivative intensity / reference intensity
```

当 reference=SM+background 且背景不随参数变化，分母才对应总参考强度。若 reference=SM 而最终存在背景，或 train/evaluation 极化不同，不能直接宣称同一比值就是最终实验的最优 score。

比值无 [-1,1] 有界性。P(reference)≈0 的处理必须显式配置：denominator floor / bounded transform / error，记录参数和触发数，不静默丢事件。floor 是对 observable 的改变，需做敏感性检查。binning 在训练 / validation 上固定，包含明确 underflow / overflow 策略，不在最终 test 上选择最优 binning。

增加其他构造时，只在该文件增加函数及其 required classes、参数与有效域声明。preflight 发现二分类模型配三分类 ratio 时在训练前报错。

## 10. 模板和 Fisher 契约

首版采用一个参数 c，在 reference point c0：

```text
mu_b(c) = S0_b + B_b + (c-c0) S1_b + O((c-c0)^2)
mu0_b   = S0_b + B_b
mu1_b   = d mu_b / d c at c0
I       = sum_b (mu1_b)^2 / mu0_b
```

背景在首版假定参数无关；若不是，必须把其导数加入 mu1。S1 为有符号模板，不能对它取绝对值，也不是把模型输出直接求和。每个模板由对应 sample 的物理 event weights 填充，同时保存 sumw2 及必要的相关性描述。

默认报告固定背景、无 nuisance 的 rate+shape Poisson Fisher，并另名提供 shape-only：
`I_shape = I - (sum_b mu1_b)^2 / sum_b mu0_b`。
多通道 shape-only 必须注明是条件于每通道总数还是只条件于总和，两者不同。

对 mu0≤0 或低统计不稳定 bin，采用明确的报错 / validation 阶段预定合并策略，不静默跳过。局域 Fisher 不应因任意有限 c（例如 c=1）处线性截断负值就自动删除 bin；局域可导性、参数有效域和有限参数模板验证是不同问题。有限参数测试需要相应完整预测或受控小步长。

高方差 signed S1 的平方会造成有限 MC 的乐观偏差；保留 sumw2，提供独立 sample / bootstrap 稳定性检查，不把一次高 Fisher 当作证明。

独立运行时期与不重叠实验子道的 Fisher 可以相加。复用同一 MC 构造多时期预期不影响实验独立性，但 MC 不确定度可能相关，不能当成独立 MC 重复估计误差。

## 11. 一次配置与一个入口

以下是接口草案，示例字段不是旧 data schema 的延续：

```yaml
process: tth_cpv
data:
  manifest: samples.yaml
  table: ml_superdataset.csv
  missing_features: compute_and_cache

features: [top_pt, higgs_pt, v]

target:
  kind: cpv_threeclass
  reference_class: sm_plus_background

experiment:
  run_plan: run_plan.yaml      # 各时期 luminosity、P_e-、P_e+
normalization:
  overrides: normalization_overrides.yaml  # 可省略；按 sample 定位

training:
  run_plan: same_as_experiment
  class_balance: none
  seed: 42
  model:
    backend: catboost
    params:
      iterations: 500
      depth: 6

observable:
  name: prob_diff             # 默认；也可选择 ratio
templates:
  binning: fixed_from_validation
fisher:
  mode: rate_and_shape
output: runs/example
```

数据配置还需绑定已定义的 selection 和 split；模型超参数仅为语法示例，不是本分析推荐最优值。

```bash
ilc-miner run --config configs/cpv.yaml --features top_pt,higgs_pt,v
ilc-miner run --config configs/cpv.yaml --features top_pt,higgs_pt,v --dry-run

# 覆盖物理输入的示例语法，ID 必须确实存在于 manifest / run plan：
ilc-miner run --config configs/cpv.yaml \
  --set samples.signal_lr.cross_section_fb=VALUE \
  --set samples.signal_lr.generated_test_count=VALUE \
  --set experiment.periods.run1.luminosity_fb_inv=VALUE
```

VALUE 为用户提供的真实数值，不使用示例猜测。若只有 parent 统计而不是精确 generated_test_count，应设置相应分母策略和 sampling probability，不混用字段。

```python
from ilc_miner import run

result = run(
    config="configs/cpv.yaml",
    features=["top_pt", "higgs_pt", "v"],
)
print(result.fisher)
```

执行顺序：preflight → ensure_features → resolve weights/targets/splits → train → predict → observable → templates → Fisher → report。
dry-run 展示哪些 feature 会复用 / 计算、哪些来源会被读取、resolved 归一化和待执行阶段，不启动训练。

结果目录包含 resolved config、input manifest、normalization report、feature manifest、模型与预处理、class mapping / 倍率、预测缓存、observable 定义与版本、模板与 sumw2、Fisher 和闭合检查报告。最终输出必须区分“计算成功”和“验证通过”。

## 12. 验证与闭合标准

物理正确性优先于复现旧文件中的错误。

1. **Feature 一致性**：完整导出、增量追加、训练按需计算、test 按需计算在同一事件上数值一致；单位、参考系、W daughter ordering 等使用手工 / toy 例核对。
2. **数据完整性**：加列前后 event_uid、行数、split、已有列不变；检测 duplicate key、错误 source、依赖环与缺字段。
3. **归一化闭合**：无选择 toy 的总 yield=L×sigma；有选择 toy 为 L×sigma×efficiency；覆盖多 chunk、零通过 chunk、test 抽样、手工 override 和单位转换。
4. **Signed 闭合**：正负抵消、绝对采样 normalization、S1 符号和参数因子正确；对可用基准做小步长有限差分核对导数。
5. **极化闭合**：纯 LR / RL 极限、无极化四份 1/4、fraction 总和为 1；train 与 test 各用自身来源统计；输入已混合时无重复 fraction。
6. **分类闭合**：类别 2 的两种组成、后端概率顺序、标签转换均显式测试；背景 role 不因 target=2 而丢失。
7. **权重隔离**：改变 class balancing 不改变同一实验配置的模板物理权重；toy 后验验证类别倍率修正；记录训练和评估极化差异。
8. **观察量闭合**：默认差值与既有正确实现一致；ratio 的有限性、floor 触发、无界范围和 overflow 处理；禁止不满足 required classes 的调用。
9. **Fisher 闭合**：单 bin 手算、背景稀释、S1 全局变号下 I 不变、纯 Poisson 设定下 I∝L、独立时期相加；不可观测 helicity 先混合。
10. **防泄漏与稳定性**：相关事件不跨 split；test 不参与 scaler/校准/调参/binning 拟合；feature 扫描在 validation 比较，最终锁定 test，必要时独立 holdout 或 nested validation。
11. **缓存与恢复**：修改依赖后只失效相关产物；中断 / 并发写入不产生可复用的半成品；同配置 resume 结果一致。
12. **真实小样本端到端**：先固定可人工核对的样本，比较旧流程中已验证正确的部分；预期差异逐项解释，不为了数值一致重新引入旧错误。

## 13. 分阶段落地与删除策略

### 阶段 0：本设计与物理样本契约

建立独立分支、保存设计。下一步核对首批真实数据的 metadata：生成器总数、sigma 的含义、干涉采样、split 以及参数 convention。缺少的量由用户补齐或源适配器读取，不能发明。

完成标准：明确哪些量可自动读取、哪些必须手动输入，并有一个可核对的 sample / run plan。

### 阶段 1：干净包骨架与归一化基础

进度：旧文件清理、包重命名和通用 provenance 迁移已完成；身份 / manifest、极化与归一化模块尚未实现。

建立 ilc_miner 核心、身份 / manifest、极化和权重模块，先用合成数据闭合。仅迁入经过检查的基础算法和输入适配逻辑。

已按明确的 tracked-file 清单清理本分支的历史 workflow 脚本、固定路径配置、重复 exporter、旧数据文档和 tracked 产物；不兼容旧命令。清理没有涉及外部原始数据、未跟踪用户文件或其他分支。原许可声明保持不变，保留新设计和通用 provenance 测试。需要复用的物理算法以后从上述固定历史提交逐项验证后迁入，不把整个旧包作为新 API 暴露。

完成标准：无依赖旧工作目录的 import / toy tests；归一化与极化闭合全部通过。

### 阶段 2：feature 库与增量 materialization

集中现有 baseline 定义和一个新增 feature 示例；实现 export/add、递归依赖、源文件回读、sidecar 缓存和共同矩阵构建。

完成标准：只增加一处 feature 函数即可触发自动补列；export、train 和 test 的数值一致；增加一列不重新计算无关 feature、不改变样本统计。

### 阶段 3：一个命令贯通 CPV 二 / 三分类

接入最小模型后端、targets、训练极化权重、概率 artifact、两种 reference 类、观察量注册、模板和 Fisher。提供可以直接运行的小样本配置；需要第二个模型后端时复用同一接口。

完成标准：用户只改 features / model / target / observable 配置就能完整训练评估；真实小样本和 toy closure 通过；所有物理归一化可追溯。

### 阶段 4：可分发和跨过程扩展

整理安装 extras、ILC 环境说明、API 文档、示例和 CI。用第二个过程的最小输入适配验证核心不存在 ttH 假设，而非只改类名宣称通用。

未来新增 `local_score_regression` target 时，需要逐事件导数、joint score 或可验证的 benchmark / reweight 信息；只有 feature 不足以构造监督目标。所谓“局域线性”指参数响应在 reference point 附近展开，不要求回归模型对输入 feature 线性。

区分 normalized-density score 与 intensity derivative ratio：
`d log p(x|c)/dc = lambda1(x)/lambda0(x) - mu1/mu0`。
扩展 Poisson 实验还包含 rate 信息。届时新增 target / estimator 能力，不改 feature、数据身份、normalization 和 provenance 的基本边界。
