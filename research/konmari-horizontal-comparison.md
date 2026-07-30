# KonMari 与 repo-curator：相似的入口，不同的底座

> 横纵分析法深度研究报告<br>
> 研究日期：2026-07-16<br>
> 核验范围：公开仓库、提交历史、release、源码、CI、issue，以及本地对抗性复现实验<br>
> 结论强度：产品定位高置信度；市场采用度中等置信度；未做法律意义上的专利或商标意见

## 一、执行摘要

用户的直觉是对的：第一次使用时，KonMari 与 repo-curator 的表层流程确实很像。两者都从 AI 辅助开发造成的仓库混乱出发，都强调先理解什么应该保留，再扫描候选、生成提案、让用户确认，最后才进行整理。若 repo-curator 仍然以“扫描垃圾—询问愿景—展示高置信度 Quick Wins—用户说 Yes—开始清理”作为主要体验，它很容易被理解为 KonMari 的加强版。

但这种重合主要发生在交互外壳，不发生在核心数据模型和安全执行协议。KonMari 当前是一个带有鲜明整理仪式的 Agent Skill，加上一个由文件名、mtime、正则、简单 import 搜索和 Git 启发式组成的单文件 Python analyzer。repo-curator 已批准的方向则是先恢复项目意图、主线、竞争实现、过渡实现与历史证据，再把 evidence、counter-evidence、uncertainty、retention 和可逆动作分开记录。它还要求审批绑定计划的精确字节和仓库状态，并通过 mutation budget、journal、drift validation、recovery 与 rollback 控制执行。

因此，本报告给出四个分层判断：

- 用户旅程相似度：约 **75%—85%**；
- 核心数据模型相似度：约 **15%—25%**；
- 安全执行模型相似度：低于 **10%**；
- 用户感知的综合相似度：约 **60%—70%**，如果首屏仍以“清理文件”为中心，这个数字会更高。

真正需要警惕的技术竞品不是 KonMari，而是 RepoWise。RepoWise 已经公开覆盖多语言代码图、Git 行为、架构决策证据、dead-code 分级和 refactoring blast radius。repo-curator 不能再把“结合代码图和 Git”当成独有卖点。更可靠的差异化必须落在以下六点：从多轮 AI 修改中重建 `change_episode`；把相同责任的竞争实现归入 `capability_family`；将 preservation 与 deadness 分开；同时保存证据与反证；无法判断时正式输出 `UNRESOLVED`；审批与执行必须状态绑定、可恢复、可撤回。

最终建议不是停止 Issue #1，而是继续做安全 inventory 与 fixture。它们恰好是 repo-curator 与 KonMari 从第一步就不同的地方。不过应在 Issue #1 开始前补一个 project-bundle protection fixture，覆盖 workspace、submodule、不可拆的 Unity/Blender/CAD 类项目目录和 symlink boundary。产品文案和首次结果也必须从“清理器”改成“项目意图与主线恢复器”。

一句话定位建议是：

> **KonMari 帮你清掉看起来过时的东西；repo-curator 先重建项目为什么会变成现在这样，再给出可以审计、可以撤回的收敛方案。**

## 二、为什么用户会觉得它们很像

### 2.1 两者占据了同一个叙事入口

KonMari 将自己描述为面向 AI-assisted development 的 repository cleanup ceremony，触发词包括 `clean up this repo`、`what files can I delete`、`reduce context bloat`、`wrap up` 和 `/konmari`。它承诺先询问理想代码库和必须保留的文件，再按五类分析，生成 `CLEANUP_PROPOSAL.md`，逐项询问用户是否删除。[KonMari README](https://github.com/Hmbown/KonMari)

repo-curator 的起因同样是 AI 反复写代码后出现多套实现、遗留脚本、矛盾文档和用途不明的文件。如果只压缩成一句“帮助用户安全清理 AI 弄乱的仓库”，两者几乎处在同一句产品文案里。用户并不会在第一次体验中自动看到 artifact/location/content/lineage 或 exact-byte approval；他最先看到的是工具问什么、展示什么、什么时候要求确认。

这说明产品相似度不能只通过内部架构来判断。一个技术上完全不同的系统，仍可能因为同样的 onboarding、分类词汇和审批仪式，被用户认成同一产品。相反，只要第一屏先展示主线恢复、保护边界和证据冲突，repo-curator 的技术差异就能转化为用户可感知的差异。

### 2.2 KonMari 的真实用户旅程

KonMari 的 Skill 指令要求宿主 AI 先问三个开放问题：理想代码库是什么样、哪些文件必须保留、当前工作重点是什么。随后运行 analyzer，按 Dead Files、Dependencies、Documentation、Configuration、Legacy Code 的固定顺序处理候选。这五类被赋予 “sacred order”，不鼓励跳过或重排。[KonMari SKILL 用户问题](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/SKILL.md#L45-L60) [固定分类](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/SKILL.md#L35-L43)

扫描后，宿主 AI 被要求自行生成 Markdown 提案，把分数不低于 80 的项目放进 `Quick Wins`，50—79 放进 `Decisions Needed`，并展示 `Already Sparking Joy`。Python 脚本本身只把 JSON 打到 stdout，并不生成或校验提案文件，因此最终建议、语言和动作映射仍由宿主模型自由完成。[提案模板](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/SKILL.md#L82-L161)

用户说 Yes 后，示例要求宿主 AI 直接删除文件、修改依赖清单和修订 README。执行后再把 Deleted 或 Kept 追加到原 Markdown 中。这里没有结构化 action ID、plan hash、批准范围、状态快照或恢复状态机。[对话执行示例](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/examples/conversation_example.md#L101-L180) [日志模板](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/SKILL.md#L191-L210)

将上述流程抽象后，它与早期 repo-curator 设想的表层流程高度相似：

1. 用户提出仓库混乱；
2. 工具询问什么应保留；
3. 工具扫描和分类；
4. 工具生成提案；
5. 用户确认；
6. 工具整理并记录。

所以问题不是“我们有没有比它更深的内部设计”，而是“用户是否能在第一分钟感知到更深的设计”。若不能，产品仍然显得像。

## 三、纵向分析：KonMari 是怎样形成的

### 3.1 一次性完整发布

KonMari 的首次公开提交是 2026-01-06 的 [`f1868ee`](https://github.com/Hmbown/KonMari/commit/f1868ee68406086bff534a64b78a5ac58f37c906)，同一个提交也承载唯一 release `v1.0.0`。初始版本一次加入 33 个文件和约 8,444 行内容，同时包含根目录实现与 `skill_package/` 副本、`pyproject.toml`、requirements、CLI、Skill bundle、CI、示例、安全政策和发布包装。[v1.0.0 release](https://github.com/Hmbown/KonMari/releases/tag/v1.0.0)

第二天的提交快速完成跨助手兼容、CI、打包、安装和目录重命名。随后 [`238d93b`](https://github.com/Hmbown/KonMari/commit/238d93ba01417c2fd04503d386ebbaaa37c7a856) 一次删除约 3,618 行，提交信息明确写着 remove PyPI cruft、keep skill-only files。也就是说，项目在两天内从“Python 包 + CLI + Skill”收缩为“Skill 为主、脚本为辅”。截至 2026-07-16，GitHub 仍显示 14 个提交、一个 release，主线最后 push 停留在 2026-01-07。[KonMari 提交历史](https://github.com/Hmbown/KonMari/commits/main/)

这段时间线很关键。它说明 KonMari 已经抢先定义了“仓库整理仪式”的用户语言，但没有公开证据表明它经历了长期真实仓库验证、社区问题反馈和多轮误判修正。仓库仍公开不等于持续维护；同样，低 star 和缺少 issue 也不能证明它无用，只能说明市场验证证据有限。

### 3.2 项目自身出现了文档与主线漂移

唯一 release 仍称其为 PyPI-ready，并给出 `pip install konmari-skill` 路径；第二天的 main 却已经删除 `pyproject.toml` 和 requirements，并明确收缩为 skill-only。一些嵌套文档还残留旧的 `skill_package/` 名称。这正是 repo-curator 想解决的典型问题：发布承诺、目录结构和当前主线之间发生漂移。

这不是用来嘲讽 KonMari，而是一个非常有价值的真实案例。简单的“过时文档检测”只能说某个字符串不匹配；主线重建则要说明哪个承诺曾经有效、何时被替代、release 为什么仍指向旧形态、用户现在应该相信什么。后者才是 repo-curator 应该拥有的解释深度。

### 3.3 架构没有形成可独立校验的判断层与执行层

当前主要实现是一个约 1,497 行、53 KB 的单体 `analyze_repo.py`，外加约 314 行 Skill 指令。CI 只做 Python 语法编译、自扫描 smoke test 和 Skill bundle diff，没有单元测试、gold corpus、误判基准、敌意路径 fixture 或恢复测试。[当前 analyzer](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/scripts/analyze_repo.py) [当前 CI](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/.github/workflows/ci.yml#L8-L27)

这使得 KonMari 的两层责任无法独立校验：analyzer 只负责提名候选，宿主 LLM 负责解释、写提案、理解用户保护项、决定动作并执行。用户的“必须保留”不会作为结构化保护范围传入 analyzer。相同扫描结果可以被不同宿主模型改写成不同提案，也没有工具可以证明执行动作与用户看到的文字完全一致。

## 四、源码核验：KonMari 实际如何判断

### 4.1 分数是启发式积分，不是正确率

KonMari 的 confidence 从固定分数开始，根据名称模式、文件年龄、AI artifact 等条件加减。它没有基于 gold corpus 做校准，也没有公开 precision、recall 或 false-positive rate。[评分实现](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/scripts/analyze_repo.py#L192-L232)

因此 `80% confidence` 不能解释为“有 80% 概率可以安全删除”。它只表示满足了若干手写规则。文档示例与代码计算也并不一致：示例中的 143 天 backup 为 95，实际函数得到 80；289 天 temp 示例为 88，实际得到 85；17 天 `CLAUDE-CONTEXT.md` 示例为 92，实际得到 65；82 天 verify 文件示例为 85，实际得到 75。这里的风险不是差十几分本身，而是 UI 使用百分号制造了统计置信度的错觉。

repo-curator 应避免复制这种表达。更合适的是分别展示证据强度、反证、覆盖范围和风险；当必要条件没有建立时直接输出 `UNRESOLVED`，而不是用一个总分把不确定性压平。

### 4.2 “重复”只是文件名归一化

KonMari 将 `_old`、`_backup`、`_v1`、`copy` 等片段从文件名中移除后分组，并没有比较 exact-byte hash。[duplicate 实现](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/scripts/analyze_repo.py#L310-L372) 这会把名称相近但内容与职责不同的文件当成可能重复，也会把为了发行而有意复制的 README 或 LICENSE 分到一起。

repo-curator 的四身份模型恰好可以解决这个问题：location 相近不等于 content 相同；content 相同不等于 lineage 相同；同一 lineage 也不代表可以删除其中一个 location。判断必须明确自己在比较哪一种身份。

### 4.3 mtime、AI 文风和 import 搜索都是弱证据

文件年龄使用本地 filesystem mtime，而不是 Git 最后变更时间。新 clone 会让旧文件看起来很新，复制目录则可能让活跃文件显得很旧。AI commit 检测除了显式 trailer，还使用 conventional commit 和 `implement`、`refactor`、`fix bug` 等普通措辞。这些信号可以提名候选，但不能可靠证明文件过时或提交由 AI 生成。

依赖分析也容易把只在 npm scripts、配置、插件注册、动态加载或构建系统中使用的包当成 orphan。静态 import 缺失最多只能表达“在已分析的直接 import 范围内没有发现引用”，不能升级为“未使用”。repo-curator 已经采用的 “no known reference in analyzed scopes” 是更合适的上限表述。

### 4.4 大仓库和 monorepo 宣称高于实现深度

当文件数超过 10,000 时，代码会设置 `sample_mode=true`，但后续扫描仍然多次遍历全仓；该标志没有真正改变扫描函数的预算。monorepo 检测能识别若干 marker，但 JavaScript 和 Python 依赖分析仍主要读取根 manifest，无法兑现完整的 per-package 聚合分析。[主流程 sampling flag](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/scripts/analyze_repo.py#L1344-L1363)

这提示 repo-curator：安全预算不能只是输出里的布尔状态，必须进入每个 walker、parser 和 analyzer 的实际控制流；超过预算的对象也不能消失，而应保留 inventory record 并写出 limitation。

## 五、本地对抗性复现实验

### 5.1 方法

为了避免只比较文案，本研究在临时目录构造了一个最小敌意 fixture，并用 KonMari 当前 commit `d77dbe5` 的 analyzer 扫描。fixture 包含：

- `src/auth/PLAN.md`：mtime 很旧，但内容声明它是当前认证迁移的约束文档，用户也明确要求保护；
- `src/auth/test_auth.py`：mtime 很旧，但仍是有效测试；
- `config.json` 与 `config_copy.json`：名称相似但内容不同；
- `eslint`：只在 npm script 中使用，没有源码 import；
- 一个仓库内 symlink，目标指向仓库外的 `old_backup.py`；
- 普通主线代码与 manifest。

这不是完整 benchmark，不能据此估计总体误判率。它的用途是检验几个可证伪的安全主张：用户保护项是否进入 analyzer、duplicate 是否比较内容、依赖检测是否理解 script usage、symlink 是否被当作边界，以及旧文件是否会因名称与时间直接成为 Quick Win。

### 5.2 结果

KonMari 将受保护的 `src/auth/PLAN.md` 标为 100 分 Quick Win，将仍有效的 `src/auth/test_auth.py` 标为 85 分 Quick Win。`config.json` 和内容不同的 `config_copy.json` 被作为 70 分重复候选。仅在 npm script 中使用的 eslint 被作为 60 分 orphaned dependency。指向仓库外的 symlink 被跟随到目标 metadata，并被作为 dead-file 候选记录。

另一次在同一个 repo-curator checkout 上连续运行两遍，两个 JSON 输出的 SHA-256 不同。原因包括当前时间戳和随机 gratitude message。也就是说，即使仓库没有变化，输出字节也不稳定，无法直接作为 exact approval 的输入。

这些结果不能证明 KonMari 会自动删错，因为 Python analyzer 本身不执行删除，Skill 也要求用户确认。它们证明的是另一件事：用户看到的“高分 Quick Win”可能由弱证据组成，而自然语言确认没有机器可验证的保护边界。如果宿主 AI 忘记对话中的保留要求、误读提案或在确认后仓库发生变化，现有协议没有第二道硬门。

### 5.3 对 repo-curator fixture 的直接影响

Issue #1 的 safety fixture 应把这组案例转成长期回归测试：

- 旧的 `PLAN.md` 和测试文件不得仅因名称或 mtime 获得 movement qualification；
- 名称相似、内容不同的文件必须保持不同 `contentId`；
- npm script、manifest、CI、entry point 和动态加载都应成为独立 evidence，未覆盖时写 limitation；
- symlink 只分类，不跟随遍历；外部目标不得进入仓库 artifact inventory；
- protected bundle 和 workspace 边界先于单文件候选；
- 相同输入、run ID 和 createdAt 必须生成逐字节相同的 inventory；
- 扫描失败、权限错误和预算耗尽必须保留记录并失败关闭。

## 六、2026 年横向竞争格局

### 6.1 对比矩阵

| 维度 | KonMari | AI File Sorter | RepoWise | neat-freak | repo-curator 已批准方向 |
|---|---|---|---|---|---|
| 核心对象 | 文件、依赖、文档、配置 | 普通文件、类别、名称、位置 | 文件/符号图、Git、决策、风险 | 规则、docs、agent memory | artifact、location、content、lineage、evidence |
| 首要问题 | 什么不再 spark clarity | 文件应放哪里、叫什么 | 代码如何连接、哪里危险、为何如此 | 知识应放在哪个权威入口 | 当前主线是什么，多套实现为何共存 |
| 意图发现 | 先问三个开放问题 | taxonomy、whitelist、用户修订 | docs/ADR/commit/代码决策提取 | 先读规则、README、docs | 先读规则、入口、CI、release、ownership，再最小提问 |
| 不确定性 | 单一启发式分数 | 模型建议与 review | verified/fuzzy/unverified 等状态 | 人工核验冲突 | evidence、counter-evidence、coverage、UNRESOLVED |
| 关系模型 | 名称、mtime、简单引用 | 文件到类别 | dependency/call/co-change/decision graph | 文档职责与受众 | capability_family、change_episode、bundle、implementation role |
| 执行批准 | Markdown + 自然语言 Yes | preview/edit/confirm | 计划交给人或 agent | 破坏性动作询问 | exact plan bytes + snapshot + policy + decisions + budget |
| 恢复 | 依赖 Git 历史 | persistent undo，best effort | 主要产出 finding/plan | 依赖 Git/人工复核 | journal、drift、recovery、重新批准 rollback |
| 主要优势 | 交互清晰、有温度、安装轻 | 产品成熟、review/undo 完整 | 技术图谱和解释能力强 | 文档与规则收敛 | 保守主线恢复与可审计执行 |
| 主要风险 | 分数未校准、保护与执行不结构化 | 批量分类的 blast radius | 安装面和产品范围很大 | 不做仓库语义考古 | 范围过大、早期实现难度高 |

### 6.2 AI File Sorter：可借鉴的文件操作基础设施

[AI File Sorter](https://github.com/hyperfield/ai-file-sorter) 面向 Downloads、NAS、图片和文档等普通文件整理，已有 review table、preview、dry run、continue later 和 persistent undo。它的产品成熟度明显高于 KonMari。其 agent-ready [Issue #104](https://github.com/hyperfield/ai-file-sorter/issues/104) 进一步提出 inspect→analyze→plan→validate→apply→undo，并把 filename 和文档文本视为 untrusted input。

它证明了 reviewable plan、preview、undo 和不信任文件文本都不是 repo-curator 的独有创新。更值得注意的是 [Issue #73](https://github.com/hyperfield/ai-file-sorter/issues/73)：用户要求自动识别并保护 Unity、Blender、InDesign、CAD 等不可拆项目目录。维护者当时主要建议手工 exclusions。这验证了 project-boundary guardian 的真实需求：用户往往不知道一个目录为何不可拆，工具必须在用户意识到风险之前，从 manifest、workspace、build marker 和内部依赖建立保护边界。

AI File Sorter 适合借鉴 review table、路径校验、destination collision、provider abstraction、format extraction 和 undo 数据结构。但一次用户判断不能悄悄泛化为全局偏好；每个 learned decision 应绑定项目、范围、证据、时间和 decision-set hash。

### 6.3 RepoWise：更接近的技术竞品

[RepoWise](https://github.com/repowise-dev/repowise) 于 2026-03 创建，截至 2026-07-16 约 3,654 stars、438 forks，最新 release `0.31.0` 发布于 2026-07-12，7 月 15 日仍有 push。它用 tree-sitter 为多语言仓库建立文件与符号两层图，并结合 Git、documentation、decision 和 code-health 五个 intelligence layers。[RepoWise Intelligence Layers](https://github.com/repowise-dev/repowise/blob/main/docs/INTELLIGENCE_LAYERS.md)

这意味着“代码图 + Git + 文档/ADR”已经不是空白。RepoWise 还提供 dead-code-cleanup Skill，把静态 finding、风险和 blast radius 交给 agent 使用。[RepoWise dead-code-cleanup Skill](https://github.com/repowise-dev/repowise/blob/main/plugins/codex/skills/dead-code-cleanup/SKILL.md)

repo-curator 与它的技术竞争关系是中高，不应回避。但两者仍有清晰边界。RepoWise 的主问题是让人和 agent 理解、衡量和重构代码库；repo-curator 的主问题是面对多轮 AI 造成的竞争实现和意图漂移，恢复“哪一条是当前交付主线、哪些是兼容层、哪些是历史证据、哪些仍无法判断”，并把任何移动资格绑定到 retention 与 transaction protocol。

可借鉴内容包括 graph adapter、Git co-change、decision 原文 span 校验、verified/fuzzy/unverified 状态、dead-code 风险因素、blast-radius 表达和 benchmark 方法。暂时不应吞入它的数据库、MCP、dashboard、hooks 和完整安装面；这会破坏 repo-curator 当前的最小攻击面与可验证范围。优先选择固定版本的只读 adapter，或只 port 有明确测试的独立算法。

### 6.4 dead-code cleanup protocols：更窄但更激进

2026 年又出现了 [dead-code-cleanup](https://github.com/nanzhi84/dead-code-cleanup) 和 [agentic-dead-code-cleanup-protocol](https://github.com/nardobeast/agentic-dead-code-cleanup-protocol) 等项目。它们强调 worktree、baseline green、静态工具、false-positive checklist、分批删除、adversarial review 和 CI 验证。这类方案与 repo-curator 的工程纪律接近，但目标更窄：尽可能删除不影响行为的 dead code。

repo-curator 不应与它们争夺“更会删 dead code”。它要把 deadness 与 preservation 分开：一个实现没有当前调用者，仍可能是回滚路径、迁移证据、兼容约束或尚未接线的当前工作；反过来，一个被引用的兼容层也可能是应当逐步退出的过渡实现。是否被调用不是最终角色。

### 6.5 Knip 与 neat-freak：专业工具与意图工具

[Knip](https://github.com/webpro-nl/knip) 是 JS/TS 生态中成熟的 unused files、dependencies 和 exports 检测器。它在受支持生态内的精度和插件覆盖远高于通用 LLM 猜测。repo-curator 应把这类工具的声明性结果当作 adapter evidence，而不是重新实现一个较差版本；同时不能把 unused finding 自动升级为 movement action。

[neat-freak](https://github.com/KKKKhazix/khazix-skills/blob/main/neat-freak/SKILL.md) 更关注 README、项目规则、文档与 agent memory 的持续收敛。它不是直接清理竞品，却提供了重要设计来源：规则要与实际代码互相校验；不同文档服务不同受众；稳定知识应回到权威入口；先读材料，再问用户。这与 repo-curator 的 intent-first onboarding 高度一致。

## 七、什么可以融合，什么不能照搬

### 7.1 可以借鉴的 KonMari 部分

KonMari 最值得借鉴的是降低决策心理负担，而不是判断算法：

- 每次只呈现一个认知范围，避免一次给用户几百个候选；
- 同时展示“应保留的清晰部分”和“需要决定的部分”；
- 询问当前工作焦点，防止把活跃实验误当残骸；
- 报告可以保存，用户能在之后继续；
- 没发现问题时给出明确、正向的完成状态；
- 使用温和语言承认旧实现曾经有价值。

MIT 许可允许复用代码和文字逻辑，但需要保留许可 notice。值得 port 的实现仅包括低权重 cruft filename patterns、显式 AI trailer 作为 declared evidence、生态 marker、context-heavy warning 和渐进呈现结构。每次复用应固定源 commit、原路径、许可证、修改说明和测试 fixture，写入 `third_party/sources.lock.yaml` 与 `THIRD_PARTY_NOTICES.md`。

### 7.2 不应照搬的 KonMari 部分

- 不把 `confidence >= 80` 表述为 safe to remove；
- 不以 mtime 作为主要陈旧依据；
- 不把文件名归一化等同于内容重复；
- 不从普通 commit 文风推断 AI 作者；
- 不采用固定的 sacred order；
- 不把 Git 历史当成删除安全兜底；
- 不让宿主 LLM 根据一句自然语言 Yes 直接删除；
- 不默认把 `PLAN.md`、`CLAUDE-CONTEXT.md` 或测试脚本当临时垃圾；
- 不允许随机语言或当前时间破坏计划的字节确定性；
- 不把“扫描器本身不删除”误写成端到端流程安全。

### 7.3 融合开源项目的边界

用户明确鼓励吸收开源项目，这是合理的工程策略，但“开源”不等于可以无条件拼接。KonMari 和 neat-freak 使用 MIT；AI File Sorter 与 RepoWise 使用 AGPL-3.0。repo-curator 若采用 AGPL-3.0，总体许可证方向可以兼容，但仍需履行对应源代码、版权 notice、修改标识和网络交互场景下的义务。

技术上也应优先 adapter over vendor：能读取 Knip JSON、RepoWise export、DVC metadata 或 RO-Crate，就不要把整个系统嵌入核心。adapter 必须是可选、只读、固定输入输出契约；目标仓库没有安装依赖时，核心 inventory 仍能工作。只有被清楚隔离、测试价值高、许可证归属明确的算法，才适合 port。

## 八、repo-curator 应立即调整的产品体验

### 8.1 首屏不再问泛化愿景

启动后先做只读 preflight 和 intent discovery。读取项目规则、README、ADR、manifest、entry point、CI/CD、release、ownership 和工作区结构，然后把推断展示给用户。只有证据发生关键冲突时，才问一个最小问题。

例如：

> README 声明 `src/api` 是主入口，但 CI 实际部署 `packages/api-next`；两个目录近期都在更新。当前建议同时保护。哪个是当前交付主线？

这与“你的理想代码库是什么样”有本质差异。问题带有证据、反证、保守默认值和决策范围，用户不需要从零描述整个项目。

### 8.2 第一份结果先展示保护和主线

顺序建议改为：

1. 我理解的项目主线；
2. 自动保护的交付路径和不可拆 bundle；
3. competing、transition、historical implementations；
4. 证据冲突、覆盖限制和 `UNRESOLVED`；
5. 只需用户回答的一件事；
6. 可逆收敛候选；
7. 尚未获得执行资格的候选。

状态词建议使用 `PROTECTED`、`ACTIVE_MAINLINE`、`REQUIRED_COMPATIBILITY`、`HISTORICAL_EVIDENCE`、`CLEANUP_CANDIDATE` 和 `UNRESOLVED`。不要使用 `Quick Wins = safe to remove`。

### 8.3 把 capability 作为界面中心

用户面对 AI 写乱的仓库，最困惑的通常不是“哪些文件属于 Documentation”，而是“为什么有三套登录实现、哪套在生产、另外两套能不能动”。因此报告应以 `capability_family` 为中心，将实现、消费者、时间顺序、配置、测试、CI 和兼容关系放在一张视图中。

这会形成与 KonMari 最直观的差异：KonMari 按文件类别整理；repo-curator 按项目能力恢复主线。

### 8.4 决策与动作分开批准

用户可以先接受语义判断，例如“`auth-v2` 是当前主线、`auth-old` 是历史证据”，但这不等于批准移动任何文件。动作批准必须绑定 exact plan bytes、HEAD/worktree snapshot、retention policy、user-decision set、destination 和 mutation budget。任何文件、规则、主线或计划字节变化都使批准过期。

永久删除在当前支持范围内不可执行。只允许 allowlisted archive/quarantine 等可逆动作，并在 apply 前验证 journal、destination、collision 和 recovery 条件。rollback 也不是隐式按钮，而是在状态变化后重新计算、重新展示并重新批准的计划。

## 九、对现有实施计划的影响

### 9.1 Issue #1 应继续

Issue #1 的 forensic inventory 是最正确的第一步。它不应该因为 KonMari 而取消，也不需要改成先做 LLM 分类。相反，确定性 inventory、no-follow walker、artifact/location/content/lineage 分离、研究 metadata 声明检测和 hostile fixture，正是 repo-curator 能够证明自己不是启发式清理 prompt 的基础。

建议只增加一个验收维度：project-bundle protection fixture。至少覆盖：

- workspace 根与成员；
- submodule 与 linked worktree；
- Unity、Blender、CAD 或类似项目 marker；
- manifest/entry point/build graph 形成的不可拆目录；
- 文件 symlink、目录 symlink、broken link 和外部目标；
- 同名不同内容、同内容不同 location；
- 旧但受保护的计划、测试和迁移材料；
- 扫描中仓库状态变化与输出 no-overwrite。

### 9.2 后续 issue 需要显式强化

后续 project-intent、classification、planning 和 scenario corpus 的 issues 应加入以下验收标准：

- 先读项目材料，再提出证据特定的问题；
- `capability_family` 和 `change_episode` 成为面向用户的主要视图；
- evidence 与 counter-evidence 同时输出；
- `UNRESOLVED` 是正常且被测试的结果；
- semantic decision 与 mutation approval 分离；
- 引入本报告的 KonMari 对抗性 fixture；
- 引入 AI File Sorter #73 的不可拆项目目录案例；
- 引入 RepoWise 作为 graph/decision benchmark，而不是假定市场空白；
- 第三方 adapter 失败时不降低核心 audit 的安全性。

### 9.3 不需要推翻整体路线

KonMari 暴露的是定位风险，不是核心路线失效。若现在因为表层相似就把 repo-curator 改成更激进的自动清理器，反而会丢掉真正的优势。合理策略是让底层差异更早出现在体验里，并用 fixture 和可复现实验证明它，而不是只在 PRD 里声明。

## 十、三种未来情景

### 情景 A：KonMari 保持轻量仪式型 Skill

若 KonMari 继续维持当前形态，它会作为易安装、低门槛的清理仪式存在。repo-curator 应避免与它竞争温暖文案和五类清单，而应专注复杂仓库、主线冲突、高风险保留和可审计执行。两者甚至可以互补：KonMari 的低权重候选可成为一个输入 adapter，但不能给出动作资格。

### 情景 B：KonMari 增加 tests、结构化 approval 与 rollback

若 KonMari 后续补齐保护契约、确定性 plan、drift、journal 和恢复，它会侵入 repo-curator 的安全执行空间。此时 repo-curator 的防线必须是 capability/mainline/change_episode 与反证模型，而不是单纯 workflow。也就是说，现在就应把差异建在领域模型上。

### 情景 C：RepoWise 扩展到完整仓库收敛

这是更值得警惕的情景。RepoWise 已有图、Git、决策、dead-code 与 agent-facing plan；若它增加 retention contract、竞争实现归组和 transaction engine，会成为直接竞品。repo-curator 的应对不是复制整个 RepoWise，而是保持小而可信：敌意仓库安全、明确弃权、来源可追溯、精确批准、可恢复动作，并通过 adapter 使用外部图谱。

## 十一、最终结论与置信度

本报告对“用户端逻辑很像”的判断置信度为高。KonMari 的公开 Skill、README 和示例明确展示了与 repo-curator 早期表层流程相近的 onboarding、proposal 和 approval。否认这一点会导致错误定位。

对“核心技术路线仍显著不同”的判断置信度也为高。KonMari 没有公开实现 repo-curator 已批准的四身份、主线重建、capability family、change episode、反证、正式弃权、retention contract、exact approval、drift、mutation budget 和 recovery journal。

对“市场上没有更接近方案”的判断则不成立。RepoWise 已经成为中高重合的技术竞品；AI File Sorter 已经占据 review/preview/undo 与 agent-ready file operations；dead-code protocols 已经展示 adversarial/TDD 清理流程。repo-curator 必须把它们视为基线与可借鉴来源。

本次对抗实验只覆盖一个小型人工 fixture，不能估计现实仓库的总体正确率。后续正确率不应由单一 confidence score 保证，而应由分层机制共同约束：强弱证据分开、反证必存、覆盖范围明确、低证据正式弃权、动作只允许可逆、审批绑定状态、测试语料持续增长、每次误判转成 regression fixture。

最终决策是：**继续 Issue #1，但先补 project-bundle protection fixture；同时修改产品首屏与后续 issue 的验收语言，使 repo-curator 从第一次运行起就表现为“意图恢复与安全收敛系统”，而不是“更聪明的 KonMari”。**

## 十二、主要来源

- [Hmbown/KonMari 仓库](https://github.com/Hmbown/KonMari)
- [KonMari 当前 analyzer](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/scripts/analyze_repo.py)
- [KonMari 当前 Skill](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/konmari/SKILL.md)
- [KonMari CI](https://github.com/Hmbown/KonMari/blob/d77dbe5ebf3460dd4cdf3bd9a73dd5feeba93255/.github/workflows/ci.yml)
- [KonMari v1.0.0 release](https://github.com/Hmbown/KonMari/releases/tag/v1.0.0)
- [KonMari 主线提交历史](https://github.com/Hmbown/KonMari/commits/main/)
- [AI File Sorter](https://github.com/hyperfield/ai-file-sorter)
- [AI File Sorter agent-ready proposal #104](https://github.com/hyperfield/ai-file-sorter/issues/104)
- [AI File Sorter project-boundary request #73](https://github.com/hyperfield/ai-file-sorter/issues/73)
- [AI File Sorter large wrong structure report #47](https://github.com/hyperfield/ai-file-sorter/issues/47)
- [RepoWise](https://github.com/repowise-dev/repowise)
- [RepoWise Intelligence Layers](https://github.com/repowise-dev/repowise/blob/main/docs/INTELLIGENCE_LAYERS.md)
- [RepoWise dead-code-cleanup Skill](https://github.com/repowise-dev/repowise/blob/main/plugins/codex/skills/dead-code-cleanup/SKILL.md)
- [Knip](https://github.com/webpro-nl/knip)
- [neat-freak Skill](https://github.com/KKKKhazix/khazix-skills/blob/main/neat-freak/SKILL.md)
- [dead-code-cleanup](https://github.com/nanzhi84/dead-code-cleanup)
- [agentic-dead-code-cleanup-protocol](https://github.com/nardobeast/agentic-dead-code-cleanup-protocol)

## 十三、研究限制

公开 GitHub 状态会继续变化，stars、forks、release 和 issue 数只代表 2026-07-16 的截面。没有独立用户研究可以证明 KonMari 的真实采用量或满意度；缺少 issue 既可能表示使用少，也可能表示用户在其他渠道反馈。本报告没有执行 KonMari 的删除阶段，只复核 analyzer 和 Skill 指令，因此不会将候选误判等同于实际数据丢失。

横向检索不能覆盖所有闭源产品、内部工具、非英语项目和未来提交。对“未发现单一工具覆盖全部 repo-curator 设计”的陈述只能给中等置信度，不能写成“全球首创”。许可证部分是工程风险提示，不构成法律意见。任何实际代码复用仍需基于固定 commit 做逐文件 license review。
