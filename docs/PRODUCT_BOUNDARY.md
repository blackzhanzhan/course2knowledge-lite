# Product Boundary

Course2Knowledge Lite 是一个“在线视频课程 -> 本地课程知识运行时”的公开子项目。它的目标不是复制一个完整学习教练系统，而是把课程导入、证据保留、知识编译、SQLite 持久化和前台交互这条公开链路跑通。

一句话边界：

```text
B 站课程证据
  -> 本地 SQLite 课程运行时
  -> Web Lite 课堂
  -> 可选 Hermes Lite 工具前台
```

## 1. 它是什么

Course2Knowledge Lite 是一个 local-first 课程知识产品。它把一门在线视频课程拆解和编译为一组本地对象：

- course：一门课程。
- lecture：课程中的一讲、一个视频或一个多 P 分片。
- transcript segment：带时间戳的字幕证据。
- lecture dossier：中文讲义、结构化摘要和课程上下文。
- knowledge atom：从课程证据派生出的知识节点。
- gate：学习关口或自检节点。
- visual evidence：绑定课程和讲次的视觉证据。
- note / bookmark / reading progress：学习者本地轻量记录。
- chat thread / message / event：前台聊天持久化。

这些对象统一落在本地 SQLite store 中。Web Lite 和 Hermes Lite 只是读取或调用同一份 store 的前台投影。

## 2. 它不是什么

Course2Knowledge Lite 明确不是以下几类产品：

| 不是 | 为什么 |
| --- | --- |
| LMS | 不管理班级、作业、成绩、教务、组织成员。 |
| 普通 RAG demo | 检索和问答存在，但核心产物是课程运行时，而不是一次性向量问答。 |
| 笔记软件 | 笔记是下游对象，系统重点是从课程证据编译出可检查学习对象。 |
| 视频下载器 | 不以保存视频为目标，重点是字幕、讲义、知识原子、关口和证据链。 |
| 通用 Agent 框架 | Hermes 是可选工具前台，不是业务内核。 |
| 闭环学习教练 | 公共版不写 mastery、diagnosis、review queue、exercise feedback。 |

这个边界很重要：项目的原创点在于“课程被编译成本地知识运行时”，不是“又做一个聊天入口”。

## 3. 公开能力

公共 Lite 版本应该包含并维护这些能力：

- B 站合集、系列课、普通视频、多 P 视频导入。
- 字幕探测和 transcript segment 归一化。
- 二维码登录、单次 cookie、remember-cookie 的本地登录态路径。
- 中文讲义、知识原子、学习关口和可选视觉证据生成。
- 临时 store + readiness + promotion gate，避免半成品覆盖正式课程。
- SQLite 本地课程 store。
- Web Lite 三模块前台：互动、课程管理、课程笔记。
- 课程搜索、证据引用问答、讲义阅读。
- 笔记、书签、阅读进度和聊天持久化。
- 可选 Hermes Lite 工具前台。
- 发布前测试、敏感信息扫描和部署说明。

## 4. 非目标能力

公共 Lite 版本不应该包含：

- 自动学习计划。
- 日历投射。
- mastery scoring。
- learner diagnosis。
- spaced-review queue。
- exercise-review workflow。
- 私有反馈闭环。
- 生产聊天导出。
- 母项目私有凭证、私有运行时状态或私有学习证据。
- 远程 SaaS 后端、多租户权限系统或机构教务系统。

如果未来要引入这些能力，应作为新合同单独设计，而不是混进当前公共 Lite 边界。

## 5. 前台边界

### Web Lite

Web Lite 是主要课堂前台，负责：

- 显示当前课程和课时。
- 让学习者直接聊天。
- 展示知识节点状态。
- 导入和删除课程。
- 查看 lecture 列表、readiness 和导入错误。
- 阅读中文讲义、笔记、书签和进度。

Web Lite 不应该变回控制台，也不应该堆出很多新栏目。当前公共交互应收敛为：

```text
互动
课程管理
课程笔记
```

### Hermes Lite

Hermes Lite 是可选工具前台，负责把课程 store 暴露给聊天工具调用。它不拥有业务状态，不维护第二套课程库，也不写入私有学习状态。

Hermes Lite 的正确位置是：

```text
Hermes tool call -> public package API -> local SQLite store
```

不是：

```text
Hermes profile -> 私有母项目状态 -> 子项目前台
```

## 6. 数据边界

公共仓库可以包含：

- 源码。
- Web 静态资源。
- Hermes Lite profile template 和 plugin。
- docs、截图和安全 demo fixture。
- 假 cookie 名、sentinel 测试值、公开视觉素材。

公共仓库不能包含：

- 真实 B 站 cookie。
- 二维码登录密钥。
- API key。
- 本地 SQLite 生产数据。
- `tmp/` 临时导入 store。
- `.codex/auth/`。
- 私有聊天记录或母项目私有状态。

## 7. 导入边界

B 站是当前公共版本唯一真实平台适配器。导入管线应做到：

- 支持公开 URL 类型。
- 能说明是否需要登录态字幕。
- 能把失败原因暴露给前台。
- 能在临时 store 中完成候选课程。
- 能通过 readiness 判断是否进入正式 store。
- 能阻止低质量重导入覆盖已有可用课程。

新增其他平台时，需要明确：

- source URL 如何识别。
- lecture 顺序如何确定。
- transcript evidence 如何取得。
- 登录态如何安全处理。
- 视觉证据如何绑定。
- promotion gate 的质量标准是否一致。

## 8. 为什么不迁移母项目私有能力

母项目中的学习教练闭环包含更复杂的状态：掌握度、诊断、复习队列、反馈、练习评估和长期计划。这些能力不是没有价值，而是不适合直接进入当前公共 Lite：

- 它们依赖更完整的个人学习历史。
- 它们可能包含私有运行时证据。
- 它们会把产品从“课程知识运行时”推向“个人学习教练”。
- 它们需要更严格的数据模型和迁移合同。

公共 Lite 的价值是把课程编译和本地运行时边界立住。只有这条主链稳定后，才适合讨论更重的学习闭环。

## 9. 发布边界检查

每次发布前至少确认：

- README 和 docs 能解释项目不是 LMS / RAG demo / Agent 框架。
- 本地 SQLite、`tmp/`、`.codex/auth/` 没有进入发布树。
- Web Lite 与 Hermes Lite 共享同一 store。
- 导入状态能区分失败、临时成功、promotion blocked、正式合并。
- 截图来自真实前台或明确标注为安全 demo，不伪装成生产数据。
- 文档没有真实 cookie、API key、本地用户路径或母项目私有状态。

## 10. 可接受的一句话介绍

推荐表述：

> Course2Knowledge Lite 把在线视频课程编译成本地 SQLite 课程知识运行时，并提供 Web Lite 课堂和可选 Hermes Lite 工具前台。

不推荐表述：

> 一个 RAG 学习助手。

因为后者会抹掉课程编译、SQLite 权威源、导入晋升和前台投影这些真正关键的架构边界。
