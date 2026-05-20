# Course2Knowledge Lite

把在线视频课程编译成一个本地可运行的知识空间。

Course2Knowledge Lite 不是传统 LMS、普通 RAG Demo、笔记软件，也不是通用 Agent 框架。它的核心想法是：把一门视频课当作证据源，经过字幕、视觉证据、讲义、知识原子和关口的编译，落到本地 SQLite 课程运行时，再由 Web Lite 课堂和可选的 Hermes Lite 工具前台来使用。

```text
视频课程
  -> 字幕与视觉证据
  -> 讲义、笔记、知识原子、关口
  -> 本地 SQLite 课程运行时
  -> Web Lite 课堂
  -> 可选 Hermes Lite 工具前台
```

这个项目是 local-first 的：公共版本的写入权威是本地 SQLite。Web Lite 和 Hermes Lite 都只是同一份课程运行时上的前台投影，不是两套数据孤岛。

## 架构主张

Course2Knowledge Lite 更接近一种“课程到知识运行时”的架构：

- 课程不是只被下载、转写或总结，而是被编译成可复用的学习材料。
- 证据保留可引用性，包括字幕片段、时间戳、来源 URL 和视觉证据记录。
- 讲义、知识原子、关口、视觉锚点会成为本地产品数据，而不是一次性 prompt 结果。
- 学习交互读取课程运行时，而不是让模型直接对原始视频文本即兴发挥。
- 聊天只是使用知识运行时的一种入口，不是产品核心。

因此它和常见范式的区别是：

- 不是普通 RAG Demo：检索与问答存在，但核心产物是可复用的课程知识运行时。
- 不是 LMS：不处理机构、班级、作业、成绩和教务流程。
- 不是笔记软件：笔记是课程证据的下游产物，不是唯一表达。
- 不是 Agent 框架：可选 Hermes 层只是调用公共 SQLite store 上的原生工具，不承担业务核心。

## 运行时形态

```text
Bilibili URL
  -> packages/bilibili-import
  -> 临时导入 SQLite store
  -> readiness / promotion gate
  -> packages/course-store SQLite runtime
  -> packages/qa 与 packages/guidance
  -> apps/web
  -> hermes/profile-template + hermes/plugins/course2knowledge-lite
```

### 1. 课程证据导入

`packages/bilibili-import` 是公共版本保留的真实平台适配器，支持：

- B 站合集 / 列表 URL；
- 普通视频 URL；
- 多 P 视频；
- 登录态字幕获取，包括二维码登录、一次性粘贴 cookie、仅本机保存的 remember-cookie。

导入不会直接写生产 store，而是先写临时 store，再经过入库保护：

- 新课程完整可用时合并入生产 SQLite；
- 同课程重导入时，只在质量不倒退的情况下替换该课程；
- `max_lectures` 之类的探测导入不会静默覆盖正式课程；
- 字幕、笔记、知识原子、关口缺失时，会诚实阻断 promotion。

真实 cookie、二维码状态、API key 都是本机运行时秘密，不能进入仓库、文档或测试证据。

### 2. 课程知识运行时

`packages/course-store` 负责本地 SQLite 数据模型，主要实体包括：

- course / lecture；
- transcript segment；
- lecture dossier；
- note；
- knowledge atom / gate；
- visual evidence；
- bookmark / reading progress；
- chat thread / message / event。

`packages/qa` 基于字幕证据做带引用问答；`packages/guidance` 从公共课程证据生成只读带学 payload。公共 Lite 不写入母项目里的 mastery、diagnosis、review queue、feedback、exercise-review 等私有学习状态。

### 3. Web Lite 课堂

`apps/web` 是主要可视化前台，目标不是控制台，而是轻量线上学校界面。当前交互收敛为三个模块：

- 互动模块：当前课程、当前视频、聊天、证据、知识节点状态；
- 课程管理：导入、删除、查看视频列表、查看 readiness；
- 课程笔记：生成讲义、本地笔记、书签、阅读进度。

Web Lite 用来检查课程运行时是否真的有用：导入了什么、哪些讲可用、生成了哪些知识原子、能引用哪些证据、学习者本地标记了什么。

### 4. 可选 Hermes Lite 工具前台

`hermes/profile-template` 和 `hermes/plugins/course2knowledge-lite` 提供可选 Hermes 原生工具层。它注册的公共工具包括：

- `collection_import_start`
- `import_status_get`
- `course_transcript_coverage_get`
- `knowledge_cards_generate`
- `lecture_reader_get`
- `learning_guide_get`
- `course_search`
- `course_question_answer`
- `course_visual_evidence_send`
- notes / bookmarks / reading-progress 相关工具

Hermes Lite 调用的是同一套 package API 和同一个 SQLite store。它的意义是让聊天前台能够调用课程原生工具，而不是跑脚本或猜测文件内容。

在母项目 Learning OS 工作区内，Web chat 也可以接入母项目 Hermes teaching adapter 做集成验证。这是开发集成路径，不是公共包依赖，也不是 Course2Knowledge Lite 的核心架构。

## 快速开始

要求：

- Python 3.11 或更新版本；
- 真实 B 站导入需要网络访问。

安装：

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

默认本地数据目录：

```text
data/course-store/
```

如果只是做发布或 smoke 测试，可以指定临时 store：

```bash
course2knowledge-lite web --store-root tmp/release-web-store
```

## 导入 B 站课程

在 Web 导入面板粘贴支持的 B 站课程 URL，例如：

```text
https://space.bilibili.com/1112988584/lists/7726472?type=season
```

导入流程会：

1. 展开课程为有序 lecture；
2. 获取可用字幕 / transcript evidence；
3. 生成中文讲义、知识原子、关口，以及可选视觉关键帧；
4. 评估 readiness；
5. 合并或阻断 promotion 到生产 SQLite store。

如果字幕需要登录态，可以使用 Web 面板二维码登录，也可以为单次导入粘贴浏览器 cookie。可选 remember-cookie 只保存在本机 `.codex/auth/` 下，并被 git 忽略。

## 同步 Hermes Profile

同步公共 Hermes Lite profile：

```bash
course2knowledge-lite sync-profile --apply --create-profile
```

运行 profile smoke：

```bash
course2knowledge-lite smoke-profile --profile-root %USERPROFILE%\\.hermes\\profiles\\course2knowledge-lite
```

smoke 会验证 Lite toolset 能针对本地 store 调用导入状态、reader、guided learning、Q&A、视觉证据、笔记、书签和阅读进度工具。

## 目录结构

```text
pyproject.toml       安装包与运行时资源映射
src/                 CLI 与 installed-runtime shim
apps/web/            Web Lite 课堂
apps/feishu-lite/    公共聊天入口边界说明
packages/
  bilibili-import/   B 站 URL 展开、字幕获取、导入 handoff
  course-store/      SQLite 运行时、dossier、atoms、视觉证据、聊天数据
  guidance/          只读带学 DTO
  qa/                基于证据引用的课程问答
hermes/              可选 Hermes Lite profile template 与 plugin
docs/                产品、架构、部署、测试文档
examples/            安全 demo fixture
tests/               单测、边界测试、profile smoke、Web 测试
data/                本地运行数据占位；真实数据被忽略
```

## 发布包内容

发布包应该包含：

- `course2knowledge-lite` Python wheel；
- GitHub source archive；
- Web runtime assets；
- Hermes Lite profile template 与 plugin；
- docs 中公开使用的视觉证据素材。

发布包不应该包含：

- `data/course-store/` 下的本地 SQLite 数据；
- `tmp/` 下的临时导入 store；
- `.codex/auth/` 或任何 B 站登录材料；
- API key 或模型供应商 secret；
- 生产聊天导出、私有标识符、母项目运行时证据。

## 测试

发布前建议运行：

```bash
python -m unittest tests.test_deployment
python -m unittest discover -s tests
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps --no-cache-dir
node --check apps/web/static/app.js
git diff --check
```

当前 `v0.1.0` 发布前在干净发布目录中验证过：

- `python -m unittest discover -s tests`：118 tests OK；
- `python -m unittest tests.test_deployment`：3 tests OK；
- `python -m pip wheel . --no-deps --no-cache-dir`：wheel built；
- `node --check apps/web/static/app.js`：passed；
- 发布树排除了本地 SQLite、`tmp/`、`.codex/auth/` 和运行时生成关键帧。

## 边界

Course2Knowledge Lite 暂不包含：

- 自动学习计划；
- mastery scoring / diagnosis；
- spaced-review queue；
- exercise-review workflow；
- 私有生产聊天日志；
- 母项目私有凭证或运行时状态；
- 远程后端依赖。

公共版本的边界就是：本地课程知识运行时 + 可检查的 Web UI + 可选 Hermes 原生工具访问。

## 入口文档

- [产品边界](docs/PRODUCT_BOUNDARY.md)
- [架构说明](docs/ARCHITECTURE.md)
- [数据模型](docs/DATA_MODEL.md)
- [Web Lite](docs/WEB_LITE.md)
- [Feishu/Hermes Lite](docs/FEISHU_LITE.md)
- [Bilibili Import](docs/BILIBILI_IMPORT.md)
- [部署说明](docs/DEPLOYMENT.md)
- [测试说明](docs/TESTING.md)
