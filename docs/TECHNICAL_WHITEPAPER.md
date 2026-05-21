---
layout: technical
title: 技术白皮书
permalink: /technical-whitepaper/
---
# Course2Knowledge Lite 技术白皮书

## 摘要

Course2Knowledge Lite 是一个面向在线视频课程的本地优先知识运行时。它不把视频课程仅仅视为下载对象、转写文本、笔记材料或一次性问答语料，而是把课程当作带来源证据的可编译对象：系统从 B 站课程 URL 出发，展开课程结构，获取字幕与可选视觉证据，生成中文讲义、知识原子和关口，再通过 readiness 与 promotion gate 写入本地 SQLite 课程运行时。Web Lite 课堂和可选 Hermes Lite 工具前台都读取同一份本地运行时。

这个架构的核心命题是：视频课程学习的瓶颈不是“缺少聊天框”，也不是“缺少向量检索”，而是线性课程材料没有被转化为可复用、可引用、可检查、可交互的课程知识状态。Course2Knowledge Lite 因此选择把课程编译和本地状态作为内核，把聊天、网页、Hermes 工具调用视为同一运行时上的前台投影。

## 1. 问题定义

在线视频课程天然是线性媒体。学习者在观看视频时，知识常常被绑定在时间轴、字幕片段、讲者语境和画面证据中。常见工具可以解决局部问题，但很少把课程转化为稳定的学习运行时：

- 视频下载器解决获取问题，但不解决知识结构问题。
- 转写工具得到文本，但通常丢失课程层级、视觉证据和学习状态。
- 笔记软件能承载人的整理结果，但不负责把课程证据编译成可复用对象。
- 普通 RAG demo 能检索片段并回答问题，但往往没有课程级导入保护、讲义、知识原子、关口、前台共享状态和可检查的本地数据模型。
- LMS 关注班级、作业、成绩、机构教务，不关注把一门视频课变成可交互知识运行时。
- 通用 Agent 框架关注工具调用与任务编排，但并不自动给出课程证据、知识节点、导入质量和学习界面的领域模型。

Course2Knowledge Lite 要解决的问题可以表述为：

> 如何把一门在线视频课程编译为一个本地优先、证据保留、可查询、可交互、可被多个前台共享使用的课程知识运行时？

这个问题的成功标准不是“模型能聊几句课的内容”，而是系统能稳定地回答以下问题：

- 课程包含哪些讲，顺序是什么？
- 每讲是否有可用字幕、讲义、知识原子、关口和可选视觉证据？
- 每个生成对象来自哪些字幕片段、视频时间点或课程来源？
- 导入失败或质量不足时，系统是否能阻止坏数据污染正式 store？
- Web 前台和 Hermes 前台是否读取同一份课程状态？
- 发布包是否不包含本地 cookie、私有 SQLite、临时 store、API key 和母项目私有状态？

## 2. 设计主张

Course2Knowledge Lite 的设计主张可以概括为五条。

### 2.1 课程是可编译对象

系统不把课程看成一串互不相关的视频，也不把字幕文本直接交给聊天模型即兴总结。课程首先被展开为有序 lecture，然后每讲被编译为字幕证据、讲义、知识原子、关口和可选视觉证据。编译结果进入本地课程运行时，成为后续阅读、检索、问答、聊天和状态展示的共同基础。

### 2.2 证据链优先于回答文本

问答本身不是系统的唯一目标。更重要的是保留回答可以依赖的证据结构，包括 transcript segment、lecture dossier、knowledge atom、gate、visual evidence 和 source URL。没有证据时，系统应明确说明证据不足，而不是用通用模型知识补齐课程内容。

### 2.3 SQLite 是本地写入权威

公共版本采用 local-first 架构，默认写入权威是本地 SQLite。JSON 可以作为 seed、fixture、迁移输入或调试导出存在，但不再是正式写入权威。这样可以避免“网页一份状态、聊天一份状态、导入脚本一份状态”的数据孤岛。

### 2.4 前台是投影，不是内核

Web Lite 是可视化课堂，Hermes Lite 是可选聊天工具前台。两者都不是业务内核。它们通过相同 package API 和同一 SQLite store 读取课程运行时。这个边界让系统可以同时支持网页交互和工具调用，而不把产品核心锁死在某个聊天框、Lark/Feishu 通道或 Agent 框架中。

### 2.5 导入必须有晋升保护

课程导入先写临时 SQLite store，再通过 readiness 与 promotion gate 决定是否合并到生产 store。字幕、讲义、知识原子、关口缺失时，系统应该诚实阻断 promotion。探测性导入和半成品导入不能静默覆盖正式课程。

## 3. 系统架构

整体流程如下：

```text
Bilibili Course URL
  -> Bilibili Import Adapter
  -> Temporary SQLite Import Store
  -> Transcript Segments
  -> Lecture Dossier
  -> Knowledge Atoms / Gates
  -> Optional Visual Evidence
  -> Readiness Check
  -> Promotion Gate
  -> Production SQLite Course Runtime
  -> Web Lite Classroom
  -> Optional Hermes Lite Tool Frontdesk
```

主要容器包括：

- `packages/bilibili-import`：真实 B 站平台适配器，负责 URL 校验、合集/系列课/普通视频/多 P 展开、字幕获取、cookie 登录态接入和导入状态。
- `packages/course-store`：本地 SQLite 课程运行时，负责 course、lecture、transcript segment、dossier、knowledge atom、gate、visual evidence、note、bookmark、reading progress、chat thread 等数据。
- `packages/qa`：基于课程证据的引用式问答。
- `packages/guidance`：从公共课程证据派生只读带学 payload，不写 mastery、diagnosis、review queue 或学习计划。
- `apps/web`：Web Lite 课堂，承担课程导入、互动学习、知识节点状态、课程管理和课程笔记。
- `hermes/profile-template` 与 `hermes/plugins/course2knowledge-lite`：可选 Hermes 原生工具层，提供导入、状态、阅读、问答、视觉证据、笔记和进度工具。

这套架构刻意避免把系统做成远程后端依赖。默认形态是单机本地运行：用户安装包、启动 Web Lite、导入课程，本地 SQLite 负责持久化。

## 4. 数据模型

Course2Knowledge Lite 的数据模型围绕“课程证据到学习对象”的编译链路组织。

| 实体 | 作用 | 来源或状态 |
| --- | --- | --- |
| Course | 一门导入课程 | B 站 URL 与导入元数据 |
| Lecture | 课程中的一讲或一个视频 | 合集、系列课、普通视频或多 P 展开结果 |
| Transcript Segment | 带时间戳的字幕片段 | 课程证据源 |
| Lecture Dossier | 一讲的中文讲义与结构化摘要 | 从字幕证据编译 |
| Knowledge Atom | 概念、定义、要点或解释单元 | 从讲义和字幕证据派生 |
| Gate | 学习关口或自检节点 | 从课程知识结构派生 |
| Visual Evidence | 绑定课程和 lecture 的视觉证据 | 公开 demo 图或真实关键帧 |
| Note | 学习者本地笔记 | 用户写入 |
| Bookmark | 书签 | 用户写入 |
| Reading Progress | 轻量阅读状态 | 用户写入 |
| Import Status | 导入进度和错误解释 | 导入管线写入 |
| Chat Thread / Message / Event | 前台聊天持久化 | Web/Hermes 前台写入 |

这个模型不包含母项目私有学习教练状态，例如 mastery scoring、diagnosis、spaced-review queue、exercise-review workflow、feedback state 或私有生产聊天导出。公共 Lite 的边界是课程知识运行时，不是闭环学习教练。

## 5. 导入与晋升管线

B 站导入是公共版本保留的真实平台适配器。系统支持合集/列表 URL、系列课 URL、普通视频 URL 和多 P 视频。导入管线的关键不是“能抓到视频列表”，而是确保每讲都能进入相同的课程编译路径。

导入分为六个阶段：

1. **课程展开**：把 B 站 URL 展开成有序 lecture，保留 `sequence`、`bvid`、标题和来源 URL。
2. **字幕获取**：优先获取可用 B 站字幕。需要登录态时，可通过二维码登录、单次 cookie 粘贴、remember-cookie 或本地环境变量提供。
3. **证据归一化**：把字幕转为 timestamped transcript segments。
4. **课程编译**：生成中文讲义、知识原子、关口和可选视觉关键帧。
5. **readiness 检查**：检查课程是否具备可用 transcript、notes、atoms、gates 和必要元数据。
6. **promotion gate**：仅在候选课程质量可接受时合并或替换生产 SQLite store。

这一管线的一个重要设计点是“先临时 store，后晋升”。同课程重导入只有在候选不比现有课程差时才替换。`max_lectures` 一类探测导入不会自动覆盖正式课程。失败、缺字幕、缺原子、缺关口和半成品状态都应该在前台可见。

## 6. Hermes 的架构位置

Hermes 在 Course2Knowledge Lite 中是可选工具前台，不是项目内核，也不是远程后端。它的价值在于让聊天前台能调用课程原生工具，而不是猜测文件、运行临时脚本或直接把所有上下文塞给模型。

Hermes Lite 工具层注册的能力包括：

- `collection_import_start`
- `import_status_get`
- `course_transcript_coverage_get`
- `knowledge_cards_generate`
- `knowledge_card_list`
- `lecture_reader_get`
- `learning_guide_get`
- `course_search`
- `course_question_answer`
- `course_visual_evidence_send`
- notes、bookmarks、reading progress 相关工具

这些工具调用同一套 package API 和同一个 child-local SQLite store。它们不读取母项目私有 profile，不写入母项目私有学习状态，也不依赖外部 Agent 框架。Course2Knowledge Lite 的核心创新在课程到知识运行时的编译和本地状态边界，而不是某个特定 Agent 框架。

## 7. 与常见范式的区别

| 范式 | 典型关注点 | Course2Knowledge Lite 的差异 |
| --- | --- | --- |
| LMS | 班级、作业、成绩、教务 | 不处理教务，处理课程证据编译和本地知识运行时 |
| RAG Demo | 分块、检索、回答 | 检索只是下游能力，核心产物是可复用课程运行时 |
| 笔记软件 | 人写笔记和链接 | 笔记是课程编译后的下游表达，不是唯一状态 |
| 视频下载器 | 获取视频或字幕 | 重点是生成讲义、知识原子、关口和证据链 |
| Agent 框架 | 工具调用和任务编排 | Hermes 是可选前台，SQLite 课程运行时才是业务权威 |
| 远程 SaaS 后端 | 多租户服务与云端状态 | 默认 local-first，用户本机 SQLite 持久化 |

这种差异使项目更接近“课程运行时”而不是“学习聊天机器人”。聊天可以是重要入口，但聊天不是全部。

## 8. 评估方式

当前公共版本更适合用工程可验证指标评估，而不是用泛泛的“学习效果更好”来表述。建议采用以下评估维度：

### 8.1 导入完整性

- 能否展开目标 B 站课程为正确 lecture 序列。
- 每讲是否具有 transcript coverage。
- 是否生成中文讲义、知识原子和关口。
- 需要登录态时，cookie 是否只在本地保存，API 是否只暴露脱敏信号。

### 8.2 晋升安全

- 临时导入 store 是否和生产 store 隔离。
- 缺字幕、缺讲义、缺原子、缺关口时是否阻断 promotion。
- 探测性导入是否不会覆盖正式课程。
- 同课程重导入是否遵守“不倒退替换”原则。

### 8.3 前台一致性

- Web Lite 是否读取同一 SQLite store。
- Hermes Lite 工具是否读取同一 SQLite store。
- 聊天记录、笔记、书签和阅读进度是否持久化。
- 视觉证据是否绑定 course 与 lecture，而不是裸本地路径。

### 8.4 发布安全

- wheel 能否构建。
- 单元测试和部署 smoke 是否通过。
- 前端 JavaScript 是否通过语法检查。
- 发布树是否排除本地 SQLite、`tmp/`、`.codex/auth/`、真实 cookie、API key 和母项目私有运行时证据。

项目 `v0.1.0` 发布前在干净发布目录中验证过：`python -m unittest discover -s tests` 通过 118 个测试，`python -m unittest tests.test_deployment` 通过 3 个测试，wheel 构建成功，`node --check apps/web/static/app.js` 通过，敏感路径扫描确认发布树不包含本地 SQLite、`tmp/`、`.codex/auth/` 和运行时生成关键帧。

## 9. 限制

Course2Knowledge Lite 当前有明确边界：

- 不提供 LMS 教务能力。
- 不提供自动学习计划。
- 不提供 mastery scoring、diagnosis、spaced-review queue 或 exercise-review workflow。
- 不复制母项目私有学习教练认知、生产聊天导出或私有运行时证据。
- 不依赖外部 Agent 框架。
- B 站是当前公共版本唯一真实平台适配器，其他平台需要未来公共合同。
- 模型生成能力取决于本地配置的 provider；没有模型凭证时，确定性 fallback 不应被描述为模型质量等价。
- 视觉关键帧依赖可用媒体源；不可用时应记录明确原因，而不是生成占位证据冒充真实截图。

这些限制并不是缺陷掩饰，而是公共 Lite 版本的产品边界。它要证明的是课程知识运行时架构，而不是一次性复制母项目所有私有学习闭环。

## 10. 结论

Course2Knowledge Lite 提出了一种面向视频课程的本地优先知识运行时架构。它把视频课程从线性媒体转换为可检查的课程状态：有序 lecture、字幕证据、中文讲义、知识原子、关口、视觉证据、笔记、书签、阅读进度和聊天记录共同落到本地 SQLite 中。Web Lite 与 Hermes Lite 只是这个运行时的两个前台投影。

这个项目的关键创新不在“又做了一个 RAG 问答”，也不在“又接了一个聊天 Agent”，而在把课程导入、证据保留、知识编译、晋升保护和前台投影组织成一个可发布、可测试、可本地运行的系统。对学习软件来说，这意味着课程材料不再只是被观看、总结或检索，而是可以被编译为一个稳定的知识空间。

## 附录 A：可复现入口

本地开发安装：

```bash
pip install -e .
course2knowledge-lite --help
```

启动 Web Lite：

```bash
course2knowledge-lite web
```

默认地址：

```text
http://127.0.0.1:3014/
```

发布前检查：

```bash
python -m unittest tests.test_deployment
python -m unittest discover -s tests
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps --no-cache-dir
node --check apps/web/static/app.js
git diff --check
```

## 附录 B：后续论文版工作

如果将本文扩展为 arXiv 风格 LaTeX 论文，建议补充：

- 相关工作：LMS、RAG 系统、个人知识管理、local-first 软件、Agent tool use。
- 形式化定义：课程编译对象、证据单元、promotion gate、前台投影。
- 实验表格：不同课程 URL 的展开数量、字幕覆盖率、编译耗时、promotion 结果。
- 失败案例：无字幕、登录态缺失、媒体不可用、半成品导入被阻断。
- 架构图：导入管线、数据模型、Web/Hermes 前台投影。
