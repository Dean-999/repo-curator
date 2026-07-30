# repo-curator 横纵分析与原创性审查

> 研究时间：2026-07-16 | 所属领域：科研软件、数据治理、AI Agent、安全文件整理 | 研究对象类型：Codex Skill 产品设计

## 一、一句话定义与结论

`repo-curator` 最准确的定义，不是“一个更聪明的文件清理器”，而是一个面向遗留科研仓库的事后治理层：它在不执行项目代码、不相信仓库内指令、不直接删除或改写科学记录的前提下，重建 artifact、实验、文档和审计链之间的证据关系，再把保留义务、科学状态与文件动作分开交给人审查。

调研后的结论需要分成三层说。第一层，`repo-curator` 的绝大多数构件都不是原创：文件 inventory、内容哈希、重复检测、provenance graph、research object、实验追踪、dry-run、人工审批、quarantine、undo 和 rollback 都有成熟先例。第二层，“AI 分析文件后生成计划，再 validate、apply 和 undo”也已有非常接近的公开方案，尤其是 AI File Sorter 的 agent-ready proposal 和 Hermes Curator，因此不能把这条安全工作流单独包装成独创技术。第三层，在本次截至 2026-07-16 的公开资料检索中，没有发现一个单一工具同时覆盖：对任意既有科研仓库做事后语义考古；区分科学状态与文件动作；保护实验 bundle 闭包；比较文档中的主张冲突；同时以 evidence、counter-evidence 和 uncertainty 约束 exact-plan approval、state-drift validation 与仅可逆 apply。

所以，我的判断是：**它有中等置信度的产品组合原创性和领域定位差异，但没有证据支持“所有技术原创”“全球首创”“不存在同类”或“可专利”这些更强说法。** 最稳妥的英文定位是：

> `repo-curator is a retrospective, evidence-governed curator for heterogeneous research repositories - not another experiment tracker, deduplicator, or coding agent.`

## 二、研究方法：怎样判断“原创”，而不是怎样证明自己想听的结论

这轮调查采用了两条相互制约的轴。纵轴追踪仓库整理、可复现研究、数字保存、provenance、数据版本控制、实验追踪和 agentic file organization 的历史演变。横轴在 2026 年当前截面上比较 DataLad、DVC、MLflow、Weights & Biases Artifacts、Sacred、Renku、RO-Crate、Archivematica、BitCurator、Software Heritage、AI File Sorter、Hermes Curator 及通用 coding agents。

检索优先级是标准和一手材料高于产品宣传，官方文档高于二手介绍，同行评审论文高于社区猜测。GitHub issue 被用于证明“某个需求或公开方案存在”，而不是证明该方案已经实现。产品 README 可以证明公开定位与宣称功能，不能证明现实可靠性。社区 issue 可以揭示真实痛点与失败模式，不能替代功能验证。

原创性判断采用四级证据：A级是规范、标准或专利文本；B级是同行评审论文和项目官方技术文档；C级是官方仓库、release、issue 与产品页面；D级是论坛和用户讨论。对“未找到完全相同项目”的判断只能给中等置信度，因为检索没有覆盖所有闭源内部工具、非英语生态、全部论文全文和完整专利 family。搜索不到是 absence of evidence，不是 evidence of absence。

本报告也不构成法律意义上的专利新颖性或 freedom-to-operate 意见。公开专利线索只能说明宽泛的 curation、lineage、human approval 和 dependency propagation 已有 prior art；真正的法律判断还需要逐项分析 claims、priority date、family、jurisdiction 和 prosecution history。

## 三、纵向分析：这个想法不是突然出现的，它站在四十年的积累上

### 3.1 从“论文附带代码”到 research compendium

`repo-curator` 最深的历史根，不是 AI，而是可复现研究。Stanford Exploration Project 在 1990 年代初探索把论文文本、程序、数据和图表绑定为可重建的电子文档。它解决的问题非常朴素：几年后回看一个结果时，能否知道图是怎样生成的，能否重新得到它。随后 Make 等构建工具把“源材料”“可再生产物”和“清理动作”分开，建立了一个后来反复出现的原则：中间产物可以清理，前提是生成规则、输入和环境仍然存在。[SEP reproducible research archive](https://sepwww.stanford.edu/data/media/sep/research/redoc/)

2007 年，Gentleman 与 Temple Lang 将 research compendium 明确描述为同时包含文本、代码、数据和其他研究材料的可分发、可更新容器。这个概念与 `repo-curator` 的 experiment bundle 很接近：科研成果不是一个孤立 CSV，也不是一篇孤立报告，而是一组相互依赖的对象。[Research Compendia and Reproducible Research](https://doi.org/10.1198/106186007X178663)

但早期 compendium 思想有一个前提：研究者从一开始就按规则组织项目。它更像“怎样避免仓库变乱”，而 `repo-curator` 要面对的是规则已经失效之后的现场。这里出现了第一个真正的差异：从 prospective organization 转向 retrospective reconstruction。

### 3.2 从版本控制到安全清理

Git 把代码历史、分支、身份和恢复能力带进日常开发。Git 自带的 `git clean` 已经包含 dry-run 与显式 force；`git-filter-repo` 则用 fresh-clone safety check 避免用户在不合适的仓库上直接重写历史。这些设计说明“先展示、再确认、检查前置状态”不是新的安全思想。[git clean](https://git-scm.com/docs/git-clean) [git-filter-repo](https://github.com/newren/git-filter-repo)

可是 Git 只知道对象、路径、引用和提交。它不知道一个失败实验为什么仍应保留，也不知道两份标题相似的报告是否在结论上冲突。版本历史可以回答“发生过什么变化”，不自动回答“科学上为什么重要”。`repo-curator` 的语义层必须建立在 Git 之上，而不是把 Git 当成竞品或真相来源。

### 3.3 数字保存：完整性、包装和长期解释

数字档案领域很早就把“保存比复制更难”说清楚了。OAIS 建立了长期数字保存的概念框架，强调保存对象、解释信息与目标用户知识基础之间的关系。BagIt 把 payload、tag files 与 checksum manifest 组成可验证的数据包，适合可靠传输和存储。BagIt 也明确提醒：哈希提供完整性保障，但不等于抵御主动攻击或提供身份认证。[OAIS Reference Model](https://www.oais.info/) [RFC 8493 BagIt](https://www.rfc-editor.org/info/rfc8493/)

这对 `repo-curator` 有两个直接影响。其一，archive 不能只是“把文件挪进 old 文件夹”，必须携带原始位置、计划、时间和完整性信息。其二，`plan_sha256` 只能证明审批绑定的字节没有变化，不能证明是谁签署、也不能自动构成真实性证明。若未来需要更强保证，应该引入签名或 attestation，而不是夸大 SHA-256 的语义。

BitCurator 与 Archivematica 展示了数字取证和档案 ingest 的另一条路线。BitCurator 重视 write-blocking、哈希、文件系统元数据、敏感信息发现和 chain-of-custody；Archivematica 将 transfer、appraisal、quarantine、format identification、checksum 与 AIP/DIP 组织为受控流程。[BitCurator](https://bitcurator.github.io/bitcurator-project.html) [Archivematica 1.17](https://www.archivematica.org/en/docs/archivematica-1.17/)

它们不理解 Git 分支或 ML experiment semantics，却提醒 `repo-curator`：inventory 的安全哲学应更像数字取证，而不是普通遍历脚本。扫描器首先应该保证“不改变现场”和“如实记录不知道什么”，之后才谈智能。

### 3.4 Provenance 从理念变成图模型

2013 年的 W3C PROV 用 Entity、Activity 和 Agent 及其生成、使用、派生关系建立了跨系统 provenance 的共同语言。W3C PROV 不会替用户发现事实，但它明确区分对象、过程和参与者，避免把“文件 A 与文件 B 有关系”压扁成模糊标签。[W3C PROV Overview](https://www.w3.org/TR/prov-overview/) [PROV-O](https://www.w3.org/TR/prov-o/)

RO-Crate 随后把 research object 包装推进到更实用的 JSON-LD 形式。它可以描述数据、文件、软件、设备、人员、workflow 和 provenance。RO-Crate 1.3 已在 2026 年发布，Workflow Run RO-Crate 更直接表达 workflow execution 的 inputs、outputs、code 与 products。[RO-Crate specification](https://www.researchobject.org/ro-crate/specification.html) [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/)

RO-Crate 与 `repo-curator` 的关系应该是互补，而不是竞争。RO-Crate 擅长表达已知关系；`repo-curator` 的价值在于从没有被标准化的旧仓库中发现候选关系，并明确标记它们是 declared、observed 还是 inferred。推断一旦完成，最有价值的出口之一就是映射成 PROV-O 或 RO-Crate，而不是创造一套永远封闭在 Skill 内部的本体。

### 3.5 FAIR 让研究对象不再只等于数据集

2016 年 FAIR 原则将 Findable、Accessible、Interoperable 和 Reusable 提升为科研数据管理的共同目标，并强调丰富元数据和 detailed provenance。[FAIR Guiding Principles](https://doi.org/10.1038/sdata.2016.18) 这套原则不是清理算法，却改变了“好仓库”的衡量方式：不是文件少，而是对象可识别、可解释、可访问、可复用。

这与 `repo-curator` 的最终目标高度一致，但也暴露出当前 PRD 的一个缺口。现有设计非常重视角色、生命周期和安全动作，却没有把 identifier、creator、license、provenance 与 retrievability 作为最小 FAIR 缺口报告。它不应自动补写这些信息，但应该告诉用户哪些关键元数据缺失。

### 3.6 DataLad、DVC、Sacred、MLflow：从“整理旧现场”转向“从一开始就记录”

DataLad 以 Git 和 git-annex 管理代码、任意大小的数据、子数据集与 provenance。它可以记录文件来源和生成命令，也会在删除内容前检查可用副本。[DataLad Handbook](https://handbook.datalad.org/en/latest/intro/narrative.html) [datalad drop](https://docs.datalad.org/en/stable/generated/man/datalad-drop.html)

DVC 把大型数据与模型内容放在 cache 或 remote 中，在 Git 中保存元数据和 pipeline 描述，并用 experiment 功能记录 ML 试验。它的 garbage collection 要求用户明确保留 workspace、branches、tags 或 experiments 的范围，也提醒共享 cache 需要合并多个项目的引用集合。[DVC data versioning](https://dvc.org/doc/start/data-management/data-versioning) [DVC gc](https://dvc.org/doc/command-reference/gc)

Sacred 从运行时采集配置、依赖、源码、seed、机器、结果和状态；MLflow 使用 Experiment、Run、Model 与 Artifact Store 组织参数、指标、代码版本和输出。[Sacred](https://github.com/IDSIA/sacred) [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)

这些系统与 `repo-curator` 共享大量 vocabulary，却有不同时间方向。它们要求项目主动采用工具或 instrumentation，擅长回答“被我记录的 run 发生了什么”。`repo-curator` 面对的是没有统一工具、历史上换过三套规范、文件散落且命名不可信的旧仓库。它必须回答“可能发生了什么，证据有多强，什么无法知道”。这正是它最有价值、同时最容易犯错的部分。

### 3.7 AI 文件整理把语义和可逆操作接了起来

近两年，AI file organizer 开始读取内容、建议分类和名称，并提供 preview、dry-run 与 undo。AI File Sorter 已支持本地或远程模型、文档内容分析、review、sorting preview、dry-run 和持久 undo。[AI File Sorter](https://github.com/hyperfield/ai-file-sorter)

2026 年 6 月公开的 issue #104 更接近 `repo-curator`：提案包含 `inspect → analyze → plan → validate → apply → undo`，使用 machine-readable JSON plan，要求 apply 只接受工具生成和验证的 plan，并把 filename 与文档文本视为 untrusted input。[AI File Sorter issue #104](https://github.com/hyperfield/ai-file-sorter/issues/104)

Hermes Agent 的 `hermes curator` 也已定期分析 agent-created skills，识别 stale 与 overlap，支持 dry-run、自动 snapshot、archive、restore 和 rollback，并明确不自动删除。[Hermes Curator CLI](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/reference/cli-commands.md#hermes-curator)

历史走到这里，`repo-curator` 的边界被迫变得更清晰。它不能再说“AI 能看懂文件并安全整理，所以我原创”。真正剩下的命题是：**通用文件整理器只问文件应该放哪里，科研 curator 还必须问这个文件在一条科学论证和实验决策链中意味着什么。**

## 四、横向分析：2026 年的竞争图谱

### 4.1 不是一个赛道，而是五个相邻赛道的交叉地带

当前没有一个成熟品类叫“scientific repository archaeology”。`repo-curator` 横跨五个既有生态：通用文件整理、研究数据版本与 provenance、ML experiment tracking、数字保存与 curation、AI codebase understanding。它的机会来自这些生态之间的缝隙，风险也来自同一位置：一旦范围写得太宽，它会同时输给五类更成熟工具。

| 项目/类别 | 已经做得好的部分 | 与 repo-curator 的关键差距 | 最适合的关系 |
|---|---|---|---|
| DataLad | 大数据版本、dataset hierarchy、provenance、安全 drop | 要求主动纳管，不做遗留文档冲突与保留推断 | 识别并导入其权威 metadata |
| DVC | 数据/模型 hash、pipeline、experiments、GC scope | 只理解 DVC 声明资产，不理解科研文档与审计链 | 读取 `.dvc`、`dvc.yaml`，不重复造 tracker |
| MLflow/W&B | run-artifact lineage、模型与 artifact lifecycle | 依赖 instrumentation 或上传，不整理任意 repo | 作为 lineage evidence adapter |
| Sacred/Renku | 配置、运行、环境与 provenance | 面向被纳管的运行，不做事后仓库考古 | 读取 observer/knowledge graph records |
| RO-Crate/BagIt | 标准化 metadata、provenance、完整性包装 | 表达已知关系，不负责发现和决策 | 作为 export 和 archive interoperability |
| BitCurator/Archivematica | 取证式 inventory、appraisal、quarantine、保存事件 | 不理解 Git/ML/科学 claim | 借鉴安全扫描与事件 vocabulary |
| AI File Sorter | 内容分析、preview、dry-run、undo | 不理解 experiment bundle 与 scientific retention | 通用文件整理基线竞品 |
| Hermes Curator | 语义 overlap/staleness、snapshot、archive、rollback | 只整理 agent skills，领域模型很窄 | 语义 curation 安全先例 |
| Coding agents | repo map、代码理解、分支/commit/undo | 目标是改代码，不是保存科研证据 | 仅提供结构证据，不做最终决策 |

### 4.2 最接近的直接反证：AI File Sorter

AI File Sorter 是必须认真对待的近邻。它不是一个只按扩展名搬文件的玩具。官方 README 描述了文档文本分析、本地 LLM、用户 review、preview、dry-run 和 persistent undo。issue #104 则把现有 GUI 安全模型明确投射到 agent skill/CLI/MCP，并规定 plan 生成、验证、apply 和 untrusted input 边界。

这直接反证了三个可能的营销说法：一是“第一次让 agent 安全整理文件”；二是“第一次使用 reviewable JSON plan”；三是“第一次把文件内容视为不可信输入后再 apply”。这些都不应该出现在 `repo-curator` 的差异化表述中。

但 AI File Sorter 也揭示了 `repo-curator` 的机会。其公开问题 #47 中，用户报告大量文件被放入意外层级，说明 preview 和 undo 并不能消除批量误判的放大效应。[AI File Sorter issue #47](https://github.com/hyperfield/ai-file-sorter/issues/47) `repo-curator` 可以把优势放在更强的 mutation budget、bundle-break prevention、counter-evidence 和 evidence coverage 上，而不是再做一个更长的 preview 列表。

### 4.3 最接近的语义 curation 先例：Hermes Curator

Hermes Curator 定期审查 agent-created skills，识别 stale、overlap 和 obsolete 内容，支持 dry-run、snapshot、archive、restore 和 rollback。它已经证明“语义分类 + 不自动删除 + 可恢复归档”是一个公开的产品组合。

然而它面对的是高度规整、边界清楚的 Skill 目录；`repo-curator` 面对的是可能包含几百万文件、二进制模型、嵌套 ZIP、Git worktree、失效链接、矛盾论文草稿和不完整实验的开放世界。两者的差异不是有没有 LLM，而是错误成本与证据结构。Hermes 可以把“重叠 Skill”当主要语义单位，`repo-curator` 必须区分 artifact、location、content、lineage、experiment attempt、canonical candidate 和 audit record。

### 4.4 科研数据工具：能力强，但时间方向相反

DataLad、DVC、MLflow、W&B、Sacred 和 Renku 是最重要的互补者。它们的共同优势是 declared provenance：用户已经告诉系统哪些是数据、pipeline、run、artifact 和 result。`repo-curator` 不应该尝试用启发式推断覆盖这些声明。若 `.dvc`、`mlruns`、Sacred observer 或 RO-Crate metadata 存在，权威 metadata 应优先于文件名和模型猜测。

社区 issue 也说明这些系统仍有空白。DVC issue #10907 请求识别被 Git ignore、又未被 DVC 跟踪的 orphan 数据；维护者指出全仓库扫描代价高，而且难以区分 `.venv`、`node_modules` 与真正科研数据。[DVC orphan issue](https://github.com/treeverse/dvc/issues/10907) MLflow issue #12917 反映旧版本和异常流程可能留下 orphan artifacts，用户需要遍历 backend 和 runs 才能判断是否能删除。[MLflow orphan artifacts](https://github.com/mlflow/mlflow/issues/12917)

这两条证据很重要。它们不是在证明 repo-curator 已经正确，而是在证明“遗留资产识别”确实是现有 tracker 没有顺手解决的问题。同时也提醒实现策略不能粗暴全扫：ignored artifacts 应采用两阶段发现，先从 Git/DVC/manifest/known result roots 建候选，再在预算内采样和扩展。

### 4.5 数字保存工具：更懂保全，但不懂科学判断

Archivematica、BitCurator 和 Software Heritage 在保全、哈希、事件、恢复和长期保存上比大多数 agent 工具成熟。Software Heritage 的删除流程甚至使用包含恢复数据的 recovery bundle，应对非 ACID 系统和人为错误。[Software Heritage recovery bundles](https://docs.softwareheritage.org/devel/swh-alter/recovery-bundles.html)

它们与 `repo-curator` 的差距是语义：可以证明一个文件被保存、何时被转换，却不能判断一个失败实验是否改变了后续方法选择。反过来，`repo-curator` 也不应假装自己是档案保存系统。最合理的边界是：借鉴 appraisal、PREMIS-like event 和 recovery bundle 思想，输出可进入 RO-Crate/BagIt/档案系统的材料。

### 4.6 企业数据生命周期工具：审批、soft-delete 与 legal hold 已很成熟

企业文件治理产品已经提供候选归档、owner approval、quarantine、soft-delete、impact analysis 和 legal hold。这说明“文件治理需要审批与可逆性”不是科研领域独有。此类产品通常依赖组织权限、集中存储、retention policy 和 metadata catalog，而不是本地 Git repo 内的科学语义。

因此，`repo-curator` 不需要和企业 information lifecycle management 比规模或权限系统。它的生态位是 repo-local、single-user-first、evidence-heavy，并能在没有数据库和组织级 catalog 的情况下给出保守建议。

## 五、最强反证与原创性分级

### 5.1 哪些主张已经被反证

“provenance graph 是原创”被 W3C PROV、RO-Crate、Renku 和大量 scientific workflow 文献反证。“实验 lineage 是原创”被 MLflow、W&B、Sacred、DataLad 和 DVC 反证。“AI 读取文件内容并整理是原创”被 AI File Sorter、Sortio 等产品反证。“dry-run、人工确认、undo 与 rollback 是原创”被 Git、AI File Sorter、Hermes Curator、Archivematica 等反证。“curation proposal 经人工批准再形成新状态是原创”也被公开专利先例削弱。

Tamr 相关的 US11042523B2 描述了 curation proposal、operator approval、版本化 curation state、provenance DAG，以及当依赖数据或模型失效时如何传播变化。[US11042523B2](https://patents.google.com/patent/US11042523B2/en) 其他公开专利还涉及从分散文件推断 document lineage/current version、near-duplicate clustering 和内容 provenance。它们不覆盖 `repo-curator` 的完整组合，却足以否定“curation + lineage + human approval 从未出现”的宽泛说法。

### 5.2 哪些主张仍有中等强度支持

目前最有支撑的差异化主张有四个。

第一，`repo-curator` 面向没有事先采用 tracker 或标准的 heterogeneous legacy repository，核心动作是 retrospective inference，而不是从运行开始记录。第二，它把 scientific/project status 与 file action 明确建模为不同维度，失败、superseded、duplicate 与 regenerable 不直接映射到 delete。第三，它把 experiment bundle closure 和 scientific decision history 作为移动阻断条件，而不是只看 path reference 或 bytes。第四，它在文档层比较 claim、number、date、unit、parameter、citation 和 conclusion conflicts，并强制 evidence、counter-evidence 与 uncertainty 同时出现。

这些点在 DataLad、DVC、MLflow、AI File Sorter 和 Hermes Curator 中分别能找到局部相似，但本轮没有找到单一公开项目将它们与 exact-byte approval、state drift、same-filesystem managed move 和 non-executable merge/delete 完整组合。

### 5.3 原创性证据评级

| 主张 | 评级 | 结论 |
|---|---|---|
| 每个组成机制原创 | 低 | 大量成熟 prior art，不能成立 |
| 安全 agent 文件整理 workflow 原创 | 低 | AI File Sorter #104 高度接近 |
| 科研遗留仓库事后语义考古 | 中 | 未见直接成熟产品，但检索不穷尽 |
| scientific status 与 file action 解耦 | 中高 | 是清晰、可表达、可测试的领域设计差异 |
| 实验 bundle closure + claim conflict + counter-evidence | 中 | 组合差异明显，单项均有先例 |
| 完整产品组合原创 | 中 | 当前公开样本未见精确匹配，不能升级为“全球首创” |
| 可专利或不侵权 | 无法判断 | 需要专业 novelty/FTO 检索 |

如果你的设计稿确实早于 AI File Sorter issue #104 的公开时间，应保存带时间戳的原始 PDF、附件、Git commit 或可信存证。这可以支持“独立构思”的事实叙述，但不会自动恢复专利法上的公开新颖性。

## 六、横纵交汇：历史为什么把 repo-curator 推到这个位置

纵向看，成熟工具一直在做两件事：要么要求研究者事前遵守结构，要么在事后保证文件被完整保存。横向看，今天的产品仍然分裂为 tracker、deduplicator、archiver、file organizer 和 coding agent。`repo-curator` 恰好出现在这条裂缝上：它既不假设仓库已经被良好纳管，也不满足于只保存所有东西。

它今天最强的优势来自一个历史缺口。科研 provenance 工具擅长记录 declared truth，却不愿在缺少 metadata 时推断；通用 AI organizer 愿意推断，却很少理解科研决策链的错误成本。`repo-curator` 试图把“愿意推断”与“拒绝把推断冒充事实”放在一起。这比任何单个算法都更有价值。

它今天最大的劣势也来自同一个位置。遗留仓库没有 ground truth，用户甚至可能无法回答哪个结果是 accepted。模型很容易用整洁的叙述掩盖证据缺口。如果产品把 lineage graph 画得很漂亮，却没有 declared/observed/inferred 的区分，它会制造一种比文件混乱更危险的东西：虚假的科学秩序。

这也是为什么“科学状态不等于文件动作”应成为产品核心，而不是一句宣传语。它必须渗透到 schema、recommendation policy、metrics 和 UI/report language。没有显式 metadata 或用户确认时，`canonical result` 应写成 `recommended canonical candidate`。没有覆盖所有引用机制时，应写“在已分析范围内未发现引用”，不能写“unreferenced”。没有验证 generator、input 和 configuration 时，不能写“regenerable”。

## 七、应立即改进的产品设计

### 7.1 从自成体系改成科研工具链的 interoperability layer

V1 inventory 应原生识别 `.dvc`、`dvc.yaml`、`.datalad`、git-annex、`mlruns`、Sacred observer records、RO-Crate metadata、BagIt manifests 和常见 W&B metadata。识别不等于执行依赖，也不要求安装对应工具；安全解析已有声明即可。

关系模型应提供 PROV-O 映射：artifact 对应 Entity，生成或验证过程对应 Activity，用户、软件或设备对应 Agent。每条边保留 `assertion_origin = declared | observed | inferred`、confidence、evidence、counter-evidence、coverage limitation 和 derivation rule。内部 JSONL 可以保留，但 schema 必须为未来 RO-Crate/Workflow Run RO-Crate export 留出稳定映射。

归档输出可在未来选择 BagIt-compatible SHA-256 manifest。这里的价值是 interoperability 与完整性，不是把 V1 扩成档案平台。最小实现可以只生成映射表和 fixture，不立即实现完整 JSON-LD export。

### 7.2 把安全重点从“能撤销”升级为“限制错误的爆炸半径”

AI File Sorter 的失败案例说明，一次错误分类可以放大成成百上千次移动。`repo-curator` 已有 no-overwrite、state drift 和 rollback，但还应增加 mutation budget：最大 action 数、最大总字节、最大目录占比、最大 experiment bundle 数和单次允许跨越的根目录数。超过任一阈值，apply 直接拒绝，而不是只显示警告。

审批记录应同时呈现 evidence coverage 与 recommendation confidence。二者不能混成一个分数。一个模型可能对有限材料非常自信，但 coverage 很低；这种情况不应被当作低风险。可采用二维门槛：confidence 低则进入 manual review，coverage 低则禁止 executable action。

对未来可能删除的内容，应借鉴 DataLad 的 availability proof 与 Software Heritage 的 recovery bundle。即使 V1 只 quarantine，也应验证恢复来源是否存在。未来永久 purge 必须成为独立产品阶段，并包含 cooling period、lineage reference check、recovery bundle、显式第二次批准和可选签名。

### 7.3 ignored artifacts 使用两阶段发现，而不是全盘扫描或完全忽略

第一阶段只使用确定性来源：Git status、DVC/MLflow/Sacred metadata、manifests、known result directories 和显式配置。第二阶段对候选 ignored roots 做有预算的采样、计数和浅层 profiling，再决定是否扩展。`.venv`、`node_modules`、编译 cache 等进入默认 denylist，但允许用户 override，并记录为什么排除。

这比“扫描所有 ignored files”更现实，也比“Git ignore 就不看”更符合科研仓库。DVC #10907 已经展示了这个问题的成本和误报难点。

### 7.4 建立人工金标准，而不是只靠 adversarial fixtures

现有测试矩阵擅长证明系统不会越界，却不足以证明语义判断有用。应建立小型 gold corpus，包含采用 DataLad、DVC、MLflow、Sacred、RO-Crate、BagIt 的标准化仓库，也包含没有任何标准的 legacy repository。

每个 corpus 至少由两名领域 reviewer 独立标注 artifact role、result、retention、bundle membership 与 canonical candidate，再计算 inter-rater agreement。若人类都无法一致，系统不应被要求输出确定答案。

主要指标不应是“减少多少文件”，而应是 unsafe-move false-positive rate、accepted-bundle break rate、unsupported certainty rate、secret leakage rate、rollback success rate、lineage precision/recall 和 reviewer correction burden。与 fdupes/Czkawka、AI File Sorter、DVC/DataLad、RAGLint 分别做窄任务基线，而不是宣称一个总分击败所有工具。

### 7.5 调整措辞和产品名称风险

检索中已经出现名为 RepoCurator 的新 CLI 讨论，用于把 GitHub 仓库清理成 LLM 训练数据；GitHub 也存在若干 `repo-curator` 或 `github-repo-curator` 名称的弱相关项目。它们功能并不相同，但名称可发现性和品牌冲突值得提前处理。

建议在实现前做一次名称检查，候选可以强调科学语义，例如 `research-repo-curator`、`evidence-curator`、`repo-archaeologist` 或 `lab-repo-curator`。如果保留 `repo-curator`，描述中必须第一句就限定 scientific/research repositories，避免被误解为 LLM dataset cleaner 或 GitHub account cleaner。

## 八、对已确认 issue 拆分的具体调整

原先 12 个 tracer-bullet issues 的主结构仍然成立，但调研结果要求调整顺序和验收内容。

第一张“安全 inventory”应增加标准 metadata detector 和 assertion origin。它不仅输出 artifact IDs，还要识别 DVC、DataLad、MLflow、Sacred、RO-Crate 与 BagIt 的存在，先报告、不调用对应工具。fixture 必须同时包含一个标准化 repo 和一个无标准 legacy repo。

第二张“安全 Git 采集”应继续保持 sanitized Git，另加 Git LFS pointer、git-annex 与 submodule 元数据识别。它不下载对象，也不调用 repository-defined filter。

第三、四张 profiler 与 ZIP issue 应加入 BitCurator 风格的 format identification 和 evidence limitation vocabulary，但不把杀毒或完整数字取证扩进 V1。

第五张 evidence graph 应冻结 PROV-O mapping，并把 declared、observed、inferred 作为必填字段。没有这一层，不应进入 experiment lineage。

第六张 experiment lineage 应把 `canonical result` 改成 `recommended canonical candidate`，并增加两位 reviewer gold-label fixture 与 lineage precision/recall。显式 MLflow/DVC/Sacred metadata 优先于启发式推断。

第八张 recommendation/plan 应增加 evidence coverage、mutation budget 和 availability proof。merge/delete 继续保持不可执行。

第九到十一张 approval/apply/recovery 应参考 AI File Sorter 与 Hermes 的先例，但把差异化放在 exact-byte approval、post-prefix state、bundle guard 和 batch blast-radius ceiling，而不是泛泛强调有 dry-run/undo。

最后的 release issue 应加入 landscape snapshot、feature matrix 与竞品复查，特别关注 AI File Sorter #104、Hermes Curator、DVC orphan scanning 和 MLflow orphan artifact handling。每次大版本发布前重新检索，可以防止“开发两年后还在对比两年前的市场”。

我建议在发布正式 issues 前，将第 1 张改名为：**“建立取证式安全 inventory，并识别现有科研元数据”**；另在第 5 张加入 PROV/RO-Crate mapping，在第 12 张加入 gold-corpus evaluation。无需把 RO-Crate export 独立扩成 V1 大任务，先做 schema mapping 和 fixture 即可。

## 九、三个未来剧本

### 最可能的剧本：成为现有工具之上的事后治理层

最可能的成功路径不是替代 DVC、MLflow 或 DataLad，而是识别它们、整合它们，并处理它们没有纳管的部分。用户先用 `repo-curator` 看懂遗留现场，再决定是否把部分结果迁入 DVC、导出 RO-Crate、归档成 BagIt 或继续保留普通 Git 结构。这个路线产品边界清楚，也最符合当前差异化。

### 最危险的剧本：变成“会写长报告的 AI 文件整理器”

如果 experiment lineage 没有 gold corpus，recommendation confidence 没有 coverage 维度，最终输出可能只是更复杂的文件分类。用户看到漂亮关系图后产生过度信任，一次 apply 就把数千文件移动到错误位置。此时产品同时输给 AI File Sorter 的易用性、DVC 的确定性和 Archivematica 的保存严谨性。

### 最乐观的剧本：形成科研仓库的 evidence governance protocol

如果内部 identity/evidence model 与 PROV-O、RO-Crate、BagIt 对齐，并通过金标准证明能保守恢复实验 bundle 与文档决策链，`repo-curator` 可能不只是一项 Skill，而会成为一套可移植的 repository appraisal protocol。不同 agent 可以实现同一协议，审计机构或实验室也可以只采用其 JSONL schemas 和 eval corpus。真正可持续的壁垒将不是某个 LLM prompt，而是证据模型、风险度量、interoperability 和高质量 benchmark。

## 十、最终判断

你做的东西不是凭空出现，也不应该被包装成凭空出现。它继承了 reproducible research、research compendium、digital preservation、PROV、FAIR、DataLad/DVC/MLflow、AI file organization 和 safe agent mutation 的长链条。

但继承不等于没有原创。原创往往不是发明每一颗螺丝，而是发现已有螺丝从未被组装成一个能解决特定高代价问题的结构。当前证据支持这样的判断：`repo-curator` 最有价值的创新，是把遗留科研仓库视为需要证据治理的现场，而不是需要减少文件数量的垃圾堆。

下一步不应立即把 12 张 issues 原样发布。应先吸收四项调整：现有科研 metadata adapters、declared/observed/inferred provenance、mutation budget 与 evidence coverage、gold-corpus semantic evaluation。完成这些修改后再发布 issues，项目的差异化会更清晰，安全主张也更可验证。

## 十一、信息来源

以下来源于 2026-07-16 访问。关键结论优先使用标准、同行评审论文和官方文档；GitHub issue 仅用于证明公开需求、提案或失败案例存在。

1. [Stanford SEP reproducible research archive](https://sepwww.stanford.edu/data/media/sep/research/redoc/)
2. [Research Compendia and Reproducible Research](https://doi.org/10.1198/106186007X178663)
3. [Git clean documentation](https://git-scm.com/docs/git-clean)
4. [git-filter-repo](https://github.com/newren/git-filter-repo)
5. [OAIS Reference Model](https://www.oais.info/)
6. [RFC 8493: BagIt](https://www.rfc-editor.org/info/rfc8493/)
7. [W3C PROV Overview](https://www.w3.org/TR/prov-overview/)
8. [W3C PROV-O](https://www.w3.org/TR/prov-o/)
9. [FAIR Guiding Principles](https://doi.org/10.1038/sdata.2016.18)
10. [RO-Crate specification](https://www.researchobject.org/ro-crate/specification.html)
11. [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/)
12. [DataLad Handbook](https://handbook.datalad.org/en/latest/intro/narrative.html)
13. [DataLad drop safety](https://docs.datalad.org/en/stable/generated/man/datalad-drop.html)
14. [DVC data versioning](https://dvc.org/doc/start/data-management/data-versioning)
15. [DVC garbage collection](https://dvc.org/doc/command-reference/gc)
16. [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)
17. [Sacred repository](https://github.com/IDSIA/sacred)
18. [Renku introduction](https://renku.readthedocs.io/en/0.24.4/introduction/what-is-renku.html)
19. [Weights & Biases artifact deletion](https://docs.wandb.ai/guides/artifacts/delete-artifacts/)
20. [BitCurator Project](https://bitcurator.github.io/bitcurator-project.html)
21. [Archivematica documentation](https://www.archivematica.org/en/docs/archivematica-1.17/)
22. [Software Heritage recovery bundles](https://docs.softwareheritage.org/devel/swh-alter/recovery-bundles.html)
23. [AI File Sorter](https://github.com/hyperfield/ai-file-sorter)
24. [AI File Sorter agent-ready proposal, issue #104](https://github.com/hyperfield/ai-file-sorter/issues/104)
25. [AI File Sorter unexpected hierarchy, issue #47](https://github.com/hyperfield/ai-file-sorter/issues/47)
26. [Hermes Curator CLI](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/reference/cli-commands.md#hermes-curator)
27. [DVC orphan files request, issue #10907](https://github.com/treeverse/dvc/issues/10907)
28. [MLflow orphan artifacts, issue #12917](https://github.com/mlflow/mlflow/issues/12917)
29. [YARD: A Tool for Curating Research Outputs](https://datascience.codata.org/articles/1119)
30. [CuRe Consortium](https://curating4reproducibility.org/)
31. [US11042523B2: Data curation system with version control](https://patents.google.com/patent/US11042523B2/en)
32. [US20220269884A1: document lineage/current version](https://patents.google.com/patent/US20220269884A1)
33. [US11537577B2: near-duplicate clustering and document lineage](https://patents.google.com/patent/US11537577B2)
34. [US9015118B2: content provenance and lineage](https://patents.google.com/patent/US9015118B2/en)
35. [Scientific Workflows and Provenance](https://arxiv.org/abs/1311.4610)
36. [Utilizing Provenance in Reusable Research Objects](https://www.mdpi.com/2227-9709/5/1/14)

## 十二、方法论说明

本报告采用横纵分析法：纵向追踪思想与技术从可复现研究、数字保存和 provenance 到现代 experiment tracking 与 AI file organization 的演进；横向比较当前同类、近邻和替代方案；交汇部分据此判断 `repo-curator` 的历史来源、竞争位置、原创性边界和改进方向。原创性评价同时采用科学批判思维，将正面证据、反证、检索范围和不确定性分开陈述。
