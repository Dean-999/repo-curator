# 科研参照系、开源融合与独特性边界

> 研究日期：2026-07-18<br>
> 用途：为 repo-curator 的计算科研定位、PRD、第三方集成和评估语料提供依据<br>
> 证据边界：公开文档、论文、GitHub 仓库与许可证；未完成逐文件代码审计，也未验证研究者付费意愿

## 1. 结论

repo-curator 可以大量借鉴现有开源项目，但不应把它们拼成一个更大的扫描器。最佳融合方式是分层吸收：用研究标准定义交换语义，用科研工具的现有记录作为高价值 evidence，用代码理解工具补结构关系，用文件整理产品补 review 和可逆操作体验，最后由 repo-curator 自己负责事后证据重建、反证、保留判断、正式弃权和状态绑定执行。

最准确的产品类别不是“科研仓库清理器”，而是 **计算科研仓库的事后证据恢复与安全收敛工具**。它面向没有从第一天完整采用 provenance 工具、又被人和 AI 多轮修改的仓库，在投稿、复核、交接或归档前恢复论文主张、图表、结果、实验 attempt、配置、环境、代码和数据之间仍可支持的关系。

公开先例足以证明 provenance、experiment tracking、research object、reproducible paper、preview、undo 和 code graph 都不是新构件。当前差异性来自组合和时间方向：多数科研工具做 prospective capture，即从现在开始记录；repo-curator 做 retrospective reconstruction，即在记录残缺后恢复可支持的证据，并明确拒绝超出证据的结论。

## 2. 科学批判性判断

### 2.1 得到较强支持的主张

**计算科研仓库存在持续的可复现性和材料完整性问题。** 2025 年对 296 个 OSF R 项目的研究报告，98.8% 缺少正式依赖描述；重建环境后只有 25.87% 的脚本无错误完成。该研究直接支持“公开代码不等于可执行研究材料”，但它只覆盖 R/OSF 样本，不能外推为所有计算科研仓库的失败率。[Computational Reproducibility of R Code Supplements on OSF](https://arxiv.org/abs/2505.21590)

**现有工具广泛采用主动记录或规范化打包。** DataLad 通过 `datalad run` 捕获命令、输入和输出；Renku 通过 `renku run` 记录执行关系；ReproZip 通过系统调用跟踪一次执行并打包；Whole Tale 创建带代码、数据、环境和叙事的 executable research object；showyourwork 用 Snakemake 将论文和图表生成链组织成可构建项目。这些工具证明领域需求与数据模型合理，也共同暴露一个前提：研究者需要在执行时或项目整理时采用它们。[DataLad provenance](https://docs.datalad.org/en/latest/design/provenance_capture.html) [Renku provenance](https://renku.readthedocs.io/en/0.12.14/topic-guides/provenance.html) [ReproZip](https://docs.reprozip.org/en/latest/) [Whole Tale](https://wholetale.readthedocs.io/en/stable/README.html) [showyourwork](https://show-your.work/en/latest/)

**研究对象必须同时包含多类材料。** Workflow Run RO-Crate 明确将 workflow execution 的 inputs、outputs、code 等产品放入同一个 provenance 表达；Whole Tale 将 data、code、environment 和 narrative 视为一个 Tale。这支持 repo-curator 的 experiment bundle closure，而不是单文件清理模型。[Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) [Whole Tale](https://wholetale.readthedocs.io/en/stable/README.html)

### 2.2 只有中等支持的主张

**市场存在一个独立的“事后科研仓库治理”品类。** 本轮 GitHub 精确检索没有找到以 scientific repository curator、research code reproducibility curator 或 experiment provenance repository cleanup 为定位的直接项目；但是搜索不到不能证明市场空白。闭源工具、实验室内部脚本、数据仓库 curation 服务和非英语项目均可能遗漏。因此只能说“未发现单一公开工具覆盖完整组合”，不能说“全球首创”。

**研究者会采用 repo-curator。** 可复现性困难和 curation 工作量有直接证据，但采用意愿还受安装成本、隐私、学科差异、算力、截止日期和缺乏奖励影响。产品需要真实研究者与 Research Software Engineer 试用，不能从论文中的痛点直接推导付费意愿。

### 2.3 不应提出的主张

repo-curator 不运行目标代码，因此不能声称验证了实验可复现、科学结论正确或结果能够重建。它只能审计 **reproducibility evidence completeness**：已发现哪些必要材料、哪些关系有直接证据、哪些只是推断、哪些缺失或冲突。任何“验证复现”必须由外部受控执行系统完成并把结果作为新 evidence 返回。

它也不能从时间顺序推断因果，从相似代码推断相同科学目的，从显著结果推断 canonical result，或从失败状态推断可删除。确认偏差、HARKing、publication bias 和 survivorship bias 要成为保留策略的一部分：负结果、未发表 attempt 和不支持最终主张的材料可能恰恰是最重要的反证。

## 3. 分层参照与融合矩阵

| 来源 | 已解决的问题 | 借鉴方式 | 不接管的权力 | 许可证/状态 |
|---|---|---|---|---|
| RO-Crate 1.3 | 研究对象、人员、软件、数据、provenance 的可交换表达 | 采用术语、ID 映射和只读 import/export profile | 不把有效 RO-Crate 等同于可复现或保留正确 | Apache-2.0 |
| Workflow Run RO-Crate | workflow run 的 inputs、outputs、code、environment 关系 | 映射 experiment attempt 与 bundle closure | 不凭声明自动确认实际执行 | Apache-2.0 |
| FAIR4RS | research software 的 findable、accessible、interoperable、reusable 原则 | 输出 evidence gap，不自动补写事实 | 不把 FAIR score 当科学正确性 | 社区规范 |
| DataLad | Git/git-annex 数据集、subdataset、`run` provenance、安全 drop 思想 | 解析声明和 run records；借 availability-before-drop 原则 | 不调用仓库命令或下载数据 | 需逐文件确认；仓库活跃 |
| Renku | input/output/code execution lineage 与知识图 | 导入已声明 lineage；借 lineage view 语言 | 不运行 `renku run`，不托管 KG | Apache-2.0 |
| noWorkflow | 无 workflow 系统时捕获 trial、文件、函数与环境 provenance；比较 trials | 借 trial comparison 和 prospective/retrospective vocabulary；可选导入已有数据库 | 核心不通过执行脚本采集 provenance | MIT |
| ReproZip | 通过系统调用确定一次运行的文件与依赖闭包 | 借 bundle closure、trace/pack 分离和 fixture；读取已有 `.rpz` 仅在有界 adapter 中 | repo-curator 不 ptrace、不执行实验、不自动打包 | BSD-3-Clause |
| Whole Tale | 数据、代码、环境、叙事和发表对象的统一封装 | 借 publication-centered research object 和 reviewer/curator persona | 不构建云执行平台 | BSD-3-Clause；主仓库更新较少 |
| showyourwork | 论文、图表、脚本、数据与环境的可构建关系 | 识别其声明；借 figure-to-script-to-article fixture | 不执行 Snakemake/LaTeX，不强制项目采用其布局 | MIT |
| Snakemake/Nextflow | 科研 workflow DAG、输入输出、参数和执行环境 | 只读解析受支持声明或导入安全 dry metadata | 不执行 workflow，不以 DAG 覆盖人工证据 | MIT / Apache-2.0 |
| DVC | 数据版本、pipeline、experiment 与 GC scope | 导入 `.dvc`/`dvc.yaml`/params/metrics 声明；借 scoped GC 和 orphan 问题 | 不调用 DVC、不下载 cache、不把未跟踪等同于垃圾 | Apache-2.0 |
| MLflow/Sacred | experiment、run、parameter、metric、artifact、status | 导入本地声明和导出；借 experiment/attempt 分离 | 不启动 server、不上传、不把最佳 metric 自动设为 canonical | Apache-2.0 / MIT |
| RepoWise/CodeGraph | 代码图、Git co-change、decision evidence、dead code、blast radius | 优先稳定 CLI/JSON adapter；借 coverage 与 risk 表达 | 不让图结论决定 retention 或 mutation | RepoWise AGPL-3.0；CodeGraph 按实际来源审查 |
| Knip 等生态 detector | 精确的 unused file/dependency/export finding | 作为 typed observation 导入，保留工具版本和覆盖范围 | finding 不能直接创建动作 | 按 detector 许可证审查 |
| AI File Sorter | review table、preview、path safety、collision、continue later、undo | port 独立、可测试的文件操作与 review pattern | taxonomy/learned preference 不成为科研保留模型 | AGPL-3.0 |
| KonMari | 温和的清理语言、保留项、分批呈现、positive completion | 借交互心理学和低权重 candidate nomination | 不采用百分比分数、mtime、自然语言 Yes 后直接删除 | MIT |

## 4. 大量借鉴的工程方式

### 4.1 借标准，而不是重造本体

repo-curator 内部记录可以保持紧凑、确定和安全，但输出应映射到 RO-Crate、Workflow Run RO-Crate 和适用的 PROV 关系。标准负责 interoperability，repo-curator 负责从混乱现场生成带 provenance 和 uncertainty 的候选。标准中没有确定性来源的字段不得由模型补写成事实。

### 4.2 借已有声明，而不是重新猜

如果仓库已有 DVC、DataLad、MLflow、Sacred、Renku、Snakemake、Nextflow、showyourwork 或 RO-Crate 记录，优先读取声明。声明仍需验证内部一致性和适用 snapshot，但其权重通常高于文件名、mtime 或语义相似度。adapter 输出统一为 observation、origin、scope、version、limitations 和 source location。

### 4.3 借算法时优先 adapter，其次 attributed port，最后 vendor

优先级是：

1. 固定版本 CLI/JSON adapter；
2. 对小型、无副作用算法做 attributed port；
3. 只有无法隔离且收益明确时才 vendor；
4. 不把完整平台、数据库、dashboard、server 或 hooks 并入安全核心。

adapter 失败只能减少 coverage，不能使核心 audit 失败，也不能提升其他弱证据的权重。所有外部输出按不可信输入解析，实施 byte、record、time、depth 和 process budget。

### 4.4 借 fixture 和失败案例

开源项目最有价值的资产不一定是代码。公开 issue、known limitations、示例仓库和失败模式可转为 repo-curator 的对抗性 fixture：

- KonMari：旧但必要的计划/测试、同名不同内容、script-only dependency、外部 symlink；
- AI File Sorter：不可拆的 Unity/Blender/CAD 项目目录和大批量错误分类；
- showyourwork：论文图表可生成但输出被 ignore、不可生成的 static figure；
- DVC/DataLad：内容在 remote、只有 pointer、共享 cache、subdataset 不完整；
- MLflow/Sacred：run 记录存在但 artifact 缺失、status 与文件状态矛盾；
- ReproZip：trace 与 pack 之间文件发生变化；
- RO-Crate：metadata 合法但引用对象缺失、profile 不完整；
- noWorkflow：多个 trial 相似但参数和环境不同；
- scientific literature：依赖缺失、绝对路径、环境漂移、只保留成功结果。

fixture 可以在不引入运行时依赖的情况下大量吸收项目经验，并直接提高产品可靠性。

### 4.5 许可证和来源锁

每个 adapter、port 或 vendor 条目必须记录 repository URL、固定 commit、原路径、许可证、集成方式、修改说明、SPDX、测试 fixture 和 upstream monitoring policy。AGPL 来源在计划采用 AGPL 的产品中通常方向兼容，但仍需履行来源、notice 和修改标识义务；许可证兼容不能代替逐文件审查。

只有思想、术语或失败案例被借鉴时，也应在设计或研究文档中说明来源，但不把概念归属伪装成代码归属。第三方来源不能获得产品决策权：更新 upstream 不会自动改变分类或安全策略。

## 5. repo-curator 必须自研并保持独特的核心

### 5.1 Retrospective Evidence Reconstruction

从残缺、矛盾和跨工具材料中重建仍可支持的关系。每个关系必须区分 declared、observed、inferred 和 user-asserted，并携带 counter-evidence、coverage 和 limitation。没有证据时正式弃权。

### 5.2 Research Evidence Chain

以 `research_claim → figure/table → canonical_result → experiment_attempt → configuration/environment → code_revision → dataset_snapshot` 为审查视图。它不是强制每个项目都存在完整链；缺口本身就是输出。

### 5.3 Canonical Result 与 Scientific Mainline

“最佳 metric”“最新文件”“论文里出现过”都不能单独决定 canonical。canonical result 是项目当前认可的结果假设，可能有发表、review、freeze、release、用户决定和活动 workflow 等证据，也可能保持 unresolved。scientific mainline 同时包含生成结果所需的代码、数据、配置、环境和解释材料，不只是默认分支。

### 5.4 Preservation 与 Deadness 分离

静态不可达、失败、过时或未发表不等于可清理。负结果、失败 attempt、审计记录、模型选择反证、合规材料和不可重建输入可能具有高保留价值。相反，一个当前被引用的中间产物也可能可再生成，但只有闭包与 policy 完整时才产生非执行候选。

### 5.5 Scientific Claim Restraint

repo-curator 评估证据完整性，不验证科学真理。它不运行目标代码，不重新计算统计结果，不判定因果，不根据显著性决定价值，不自动补写缺失 provenance。产品报告必须将事实、推断、用户决定和未知分开。

### 5.6 State-bound Reversible Curation

语义判断不产生执行权。只有 exact plan bytes、repository snapshot、policy、decision set、bundle closure、mutation budget 和 journal readiness 全部匹配，才允许可逆 movement。任何漂移使批准失效；永久删除和自动合并不可执行。

## 6. 建议的首个支持边界

首个受支持人群应是准备投稿、复核、交接或归档的计算科研项目，而不是所有实验室活动。优先材料是 Python、R、Jupyter、Markdown、LaTeX、CSV/JSON、manifest、Git history 和常见实验追踪声明。大型原始数据、二进制模型、Pickle/checkpoint 和其他不安全序列化对象只做身份与 metadata inventory，不反序列化。

首个报告只承诺：

1. inventory 与 protected research bundle；
2. project intent 与 scientific mainline hypotheses；
3. research evidence chain 与缺口；
4. canonical result/experiment attempt 候选；
5. evidence、counter-evidence、coverage、UNRESOLVED；
6. 非执行建议和明确的最小用户问题。

任何实际复现、workflow 执行、统计复核、论文结论验证、云归档和永久删除都在当前范围外。

## 7. 验证计划

桌面调研只能支持产品假设，不能验证使用价值。下一步需要预先定义的实仓研究：

- 样本：至少覆盖机器学习、生物信息、计算社会科学和数值/HPC 四类公开仓库，同时保留项目规模与成熟度分层；
- 基线：KonMari 式启发式清理、RepoWise/CodeGraph 结构分析、原生 DVC/DataLad/RO-Crate 声明读取；
- 任务：识别 scientific mainline、canonical result、figure/result lineage、bundle 缺口、保护项和可逆候选；
- ground truth：仓库作者或两名独立 RSE/curator 标注，保留 reviewer disagreement；
- 指标：claim-specific precision、recall、coverage、abstention、unresolved、review time、unsafe false positive；
- 偏差控制：预先登记入选标准与指标，不只选择组织良好的成功案例，不把工具无法读取的仓库从分母中删除；
- 准入：没有直接 ground truth 的语义关系不得进入高置信标签，任何保护对象的 unsafe action candidate 都进入永久 regression corpus。

## 8. 当前置信度

| 判断 | 置信度 | 主要限制 |
|---|---:|---|
| 科研定位显著提高与 KonMari 的差异 | 高 | 用户是否感知仍需原型试用 |
| 计算科研存在材料与可复现性债务 | 高 | 不同学科严重程度不同 |
| 公开工具主要偏 prospective capture/packaging | 中高 | 部分工具可能支持有限导入或恢复 |
| 完整产品组合在公开市场中相对少见 | 中 | 搜索覆盖不可能完备 |
| 大量 adapter/fixture 复用能减少实现工作 | 中高 | 每个来源仍需代码与许可证审查 |
| 研究者会持续使用或付费 | 低至中 | 尚无访谈、试用或购买证据 |

产品文案必须与这一证据强度相称：可以说“面向未被完整记录的计算科研仓库做事后证据恢复”，不能说“全球首创”或“保证复现”。
