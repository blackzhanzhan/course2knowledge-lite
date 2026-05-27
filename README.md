# Course2Knowledge Lite

把 B 站课程编译成一个可对话、可复习、可推进的本地 AI 学习运行时。

Course2Knowledge Lite 不是 LMS、普通 RAG demo、笔记软件、视频下载器，也不是通用 Agent 框架。它把一门 B 站视频课当作证据源，经过字幕、视觉证据、中文讲义、知识原子和学习关口的编译，落到本地 SQLite 课程运行时，再由 Web Lite 课堂和可选 Hermes Lite 工具前台读取。

[技术档案](https://blackzhanzhan.github.io/course2knowledge-lite/) · [技术白皮书](docs/TECHNICAL_WHITEPAPER.md) · [部署说明](docs/DEPLOYMENT.md) · [部署 FAQ](docs/DEPLOYMENT_FAQ.md) · [测试说明](docs/TESTING.md)

## 工程证据

- 演示视频：<https://www.bilibili.com/video/BV1Q8Gd6VEiu/>
- GitHub Pages 技术档案：<https://blackzhanzhan.github.io/course2knowledge-lite/>
- 测试验收：当前发布线曾在干净发布目录中通过 `python -m unittest discover -s tests`（**124 tests OK**）和 `python -m unittest tests.test_deployment`（**3 deployment tests OK**），并完成 wheel build、Web JS / docs JS syntax check 与发布树敏感信息排除检查。
- 部署形态：支持本地 editable install、fresh venv 发布验证、Web Lite 课堂、Hermes Lite profile sync / smoke，以及 public-demo 受控体验模式部署（支持受控导入前 5P）；服务化运行通过 SQLite 课程 store、Hermes gateway 与 systemd 长驻服务组合完成。

## 30 秒理解这个项目

如果只看三件事：

1. 它把在线视频课编译成 SQLite 课程运行时，而不是只生成摘要或向量切片。
2. 它用知识原子和学习关口描述学习进度，而不是只做一次性问答。
3. Web Lite 和 Hermes Lite 读取同一份 runtime，课程证据、聊天状态和学习推进不会分裂成两套系统。

## 和常见方案的区别

| 方案 | 通常解决什么 | Course2Knowledge Lite 的边界 |
| --- | --- | --- |
| 普通 RAG 知识库 | 把资料切片、召回、生成答案 | 也支持检索和问答，但核心产物是课程运行时：证据、讲义、原子、关口和状态 |
| 笔记 / 摘要工具 | 把视频转成文字、摘要或 Markdown | 讲义只是下游表达，仍要回到课程证据、学习关口和 SQLite 状态 |
| LMS / 网校系统 | 管理班级、作业、成绩和教务流程 | 不做教务；关注单人学习过程中的课程编译、带学和状态推进 |
| Agent 框架 | 定义工具调用、任务编排和对话流程 | Hermes 只是工具前台；业务权威在本地 SQLite runtime |

![Course2Knowledge Lite 总体架构](docs/assets/readme/technical-dossier-architecture.png)

## 核心设计

- `课程运行时`：课程不只是视频列表，而是 course、lecture、字幕片段、讲义、知识原子、关口、视觉证据、聊天线程和阅读状态的组合。
- `Staging + Promotion`：导入先写临时 SQLite store，通过 readiness gate 后才合并到正式 store，避免半成品污染课程库。
- `学习关口`：AI 对话不是无限陪聊，而是围绕知识原子判断当前是否理解、是否需要追问、是否可以推进。
- `双前台同源`：Web Lite 和 Hermes Lite 不维护两套数据；它们读取或调用同一个本地课程 runtime。

## 它解决什么问题

很多课程工具只停在三件事：下载视频、转写字幕、生成摘要。Course2Knowledge Lite 的目标不同：它把课程编译成可以反复学习、检查、问答和扩展的本地运行时。

- 课程不只是视频列表，而是 course、lecture、字幕片段、讲义、知识原子、关口、视觉证据和学习记录的组合。
- 回答问题不直接依赖模型即兴发挥，而是优先回到本地课程证据。
- 前台不是数据权威。Web Lite 和 Hermes Lite 都只是同一份 SQLite store 的投影。
- 导入不是“一边跑一边污染正式库”，而是先落临时库，再通过 readiness / promotion gate 合并。

## 它不是什么

- 不是 LMS：不处理机构、班级、作业、成绩和教务流程。
- 不是普通 RAG demo：检索与问答存在，但核心产物是可复用的课程知识运行时。
- 不是笔记软件：笔记是课程证据的下游表达，不是唯一状态。
- 不是视频下载器：重点不在保存视频，而在把课程证据编译成可学习对象。
- 不是 Agent 框架：Hermes 是可选工具前台，业务权威仍然在本地 SQLite runtime。

## 前台形态

Web Lite 是主课堂前台，收敛成三个模块：互动、课程管理、课程笔记。截图来自本地真实 Web Lite 前台的安全空状态，不包含 cookie、私密聊天或本地课程数据。

![Web Lite 课堂前台](docs/assets/readme/web-lite-classroom.png)

## 核心架构

```text
Bilibili Course URL
  -> Import Adapter
  -> Temporary SQLite Store
  -> Transcript / Visual Evidence
  -> Lecture Dossier
  -> Knowledge Atoms / Gates
  -> Readiness + Promotion Gate
  -> Production SQLite Course Runtime
  -> Web Lite Classroom
  -> optional Hermes Lite Tools
```

这条链路里最重要的设计是“先编译，再交互”：

- `Source`：支持 B 站合集、系列课、普通视频和多 P 视频。
- `Staging`：导入先写临时 SQLite store，避免半成品进入正式课程库。
- `Compiler`：生成字幕证据、视觉证据、中文讲义、知识原子和关口。
- `Runtime Authority`：正式 SQLite store 是本地写入权威。
- `Frontdesk Projection`：Web Lite 与 Hermes Lite 只读取或调用同一个 runtime。

## 能做什么

- 从 B 站课程 URL 展开有序 lecture。
- 获取字幕证据，并保留时间戳、来源 URL 和片段引用。
- 生成中文讲义、知识原子、学习关口和可选视觉证据。
- 用 readiness gate 检查导入是否完整，阻断缺字幕、缺讲义、缺原子、缺关口的半成品。
- 在 Web Lite 中进行课程导入、课程选择、聊天带学、知识节点查看、笔记阅读、书签和阅读进度记录。
- 通过 Hermes Lite 工具前台访问同一份本地课程 store。
- 将聊天线程、消息和事件持久化到 SQLite。

## 快速开始

要求：

- Python 3.11 或更新版本。
- 真实 B 站导入需要网络访问。

安装并启动：

```bash
pip install -e .
course2knowledge-lite web
```

默认地址：

```text
http://127.0.0.1:3014/
```

指定临时 store 运行：

```bash
course2knowledge-lite web --store-root tmp/release-web-store
```

## 服务化部署

如果要验证它不是只能本地跑的玩具，可以把 Web Lite、SQLite 课程 store 和 Hermes gateway 组成一个可复现的服务化运行形态。更完整的 systemd、验收和排障细节见 [部署说明](docs/DEPLOYMENT.md)，真实踩坑记录见 [部署 FAQ](docs/DEPLOYMENT_FAQ.md)。

<details>
<summary>展开查看最小服务化部署步骤</summary>

前置条件：

- Linux 服务器或本机 Linux 环境，建议使用 systemd 管理长期进程。
- Python 3.11+、`venv`、`pip`、`git`、`curl`。
- Node.js LTS 环境，用于 `node --check apps/web/static/app.js`、`node --check docs/site.js` 等前端/文档静态检查。Web 服务本身不是 Node 常驻服务。
- 可用的 Hermes agent/gateway 环境。Web Lite 默认通过 `HERMES_WEB_GATEWAY_URL=http://127.0.0.1:8642/v1/chat/completions` 调用 Hermes。
- 一份已准备好的 SQLite 课程 store。真实 B 站导入还需要网络访问；部分字幕需要扫码登录或 cookie。
- 模型供应商密钥只放在服务器本地环境文件里，不写入仓库、README、截图或 issue。

最小服务化部署路径：

```bash
git clone https://github.com/blackzhanzhan/course2knowledge-lite.git /opt/course2knowledge-lite
cd /opt/course2knowledge-lite
python3.11 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e .
```

先做基础检查：

```bash
.venv/bin/course2knowledge-lite --help
node --check apps/web/static/app.js
node --check docs/site.js
```

同步 Hermes Lite profile，并做一次工具面 smoke：

```bash
.venv/bin/course2knowledge-lite sync-profile --apply --create-profile
.venv/bin/course2knowledge-lite smoke-profile --profile-root <profile-root>
```

启动 Hermes gateway。下面的命令假设 Hermes 已单独安装在 `/opt/hermes-agent/venv`，实际路径按你的机器调整：

```bash
/opt/hermes-agent/venv/bin/hermes \
  --profile course2knowledge-lite \
  gateway run \
  --replace \
  --accept-hooks
```

启动 Web Lite。`--public-demo` 是历史参数名，实际含义是“只读体验模式”：关闭导入、删除、Cookie、笔记、书签和进度写入，只保留课程浏览、笔记阅读和 Hermes 学习对话。这个模式不要求把访问地址写进仓库文档。

```bash
HERMES_WEB_GATEWAY_URL=http://127.0.0.1:8642/v1/chat/completions \
.venv/bin/course2knowledge-lite web \
  --host 0.0.0.0 \
  --port 3014 \
  --store-root /opt/course2knowledge-lite/data/course-store \
  --public-demo
```

建议把 Web 与 Hermes 分成两个 systemd 服务：

- `course2knowledge-lite-web`：开放 Web Lite 课堂端口。
- `course2knowledge-lite-hermes`：只在服务器本机监听 Hermes gateway。

期望端口边界：

```text
Web Lite       0.0.0.0:3014
Hermes gateway 127.0.0.1:8642
```

每次更新后不要只 `git pull`，还要重新安装 editable 包并重启服务：

```bash
cd /opt/course2knowledge-lite
git fetch origin codex/decouple-hermes-lite
git checkout codex/decouple-hermes-lite
git pull --ff-only origin codex/decouple-hermes-lite
.venv/bin/python -m pip install -e .
systemctl restart course2knowledge-lite-hermes
systemctl restart course2knowledge-lite-web
```

验收顺序：

```bash
git rev-parse --short HEAD
systemctl is-active course2knowledge-lite-web course2knowledge-lite-hermes
ss -ltnp '( sport = :3014 or sport = :8642 )'
curl -s http://127.0.0.1:3014/api/runtime
curl -s http://127.0.0.1:3014/api/courses
```

再用一个真实 SSE 聊天请求确认 Web、SQLite chat store 和 Hermes gateway 已串起来。`course_id` 与 `lecture_sequence` 按你的课程 store 替换：

```bash
curl -N http://127.0.0.1:3014/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "course_id": "<course-id>",
    "lecture_sequence": 1,
    "message": "我想从零开始学习这一讲",
    "visitor_session_id": "deploy_check"
  }'
```

部署现实说明：这个项目目前仍是个人维护的原创架构，重点是把“课程编译成本地知识运行时”这条链路跑通，而不是提供一套成熟的一键云部署方案。如果你在不同系统、Python 环境、Node.js 环境、Hermes gateway、网络条件或 B 站登录态上遇到部署问题，建议把错误日志、系统环境、启动命令和当前配置整理出来，让 AI 辅助你逐步排查。更多工程化细节见 [部署说明](docs/DEPLOYMENT.md) 与 [部署 FAQ](docs/DEPLOYMENT_FAQ.md)。

导入测试 URL 示例：

```text
https://space.bilibili.com/1112988584/lists/7726472?type=season
```

</details>

## B 站登录态

当前版本支持三种登录态路径：

- 二维码登录：在 Web Lite 导入面板扫码获取字幕所需登录态。
- 单次 cookie：只用于当前导入，不持久化。
- remember-cookie：用户显式选择后保存到本机 `.codex/auth/`，该目录被 git 忽略。

仓库、文档、截图和测试证据都不应包含真实 cookie、二维码密钥、API key 或生产聊天内容。

## Hermes 的位置

Hermes Lite 是可选工具前台，不是核心业务运行时。它注册一组课程原生工具，调用的仍然是公共 package API 和同一个 SQLite store。

典型工具包括：

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

这使聊天前台可以通过工具访问课程对象，而不是猜测文件、拼 prompt 或维护另一套数据。

## 核心代码地图

| 路径 | 作用 |
| --- | --- |
| `src/course2knowledge_lite/cli.py` | CLI 入口，启动 Web、同步 Hermes profile、运行 smoke。 |
| `apps/web/server.py` | Web Lite 本地服务器、导入 API、聊天 SSE、B 站登录态、安全错误展示。 |
| `apps/web/static/app.js` | 三模块前台交互：互动、课程管理、课程笔记。 |
| `packages/bilibili-import/src/course2knowledge_lite_bilibili/collection.py` | B 站合集、系列课、普通视频、多 P 视频展开。 |
| `packages/bilibili-import/src/course2knowledge_lite_bilibili/subtitles.py` | B 站字幕探测、获取与 cookie 脱敏。 |
| `packages/bilibili-import/src/course2knowledge_lite_bilibili/handoff.py` | 导入管线：写入临时 store、生成讲义/原子/关口/视觉证据、产出 readiness。 |
| `packages/bilibili-import/src/course2knowledge_lite_bilibili/parallelism.py` | 导入并发策略，控制讲义编译与请求扇出。 |
| `packages/course-store/src/course2knowledge_lite_store/sqlite_store.py` | SQLite 数据模型与 store API。 |
| `packages/course-store/src/course2knowledge_lite_store/lecture_dossier.py` | 中文讲义、知识原子和关口生成入口。 |
| `packages/course-store/src/course2knowledge_lite_store/dossier_core/` | 可迁移的课程 dossier 编译核心。 |
| `packages/course-store/src/course2knowledge_lite_store/chat.py` | Lite Chat Core 与聊天事件持久化。 |
| `hermes/plugins/course2knowledge-lite/tools.py` | Hermes Lite 工具注册与工具处理器。 |

## 数据边界

发布包应该包含：

- Python package 与 CLI。
- Web Lite 静态资源。
- Hermes Lite profile template 与 plugin。
- docs 中使用的截图和视觉证据素材。
- 测试 fixture 与安全示例。

发布包不应该包含：

- `data/course-store/` 下的真实 SQLite 运行数据。
- `tmp/` 下的临时导入 store。
- `.codex/auth/` 或任何 B 站登录材料。
- API key、模型供应商 secret、生产聊天导出、母项目私有状态。

## 测试

常用发布前检查：

```bash
python -m unittest tests.test_deployment
python -m unittest discover -s tests
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps --no-cache-dir
node --check apps/web/static/app.js
node --check docs/site.js
git diff --check
```

当前发布线曾在干净发布目录中通过：

- `python -m unittest discover -s tests`：124 tests OK。
- `python -m unittest tests.test_deployment`：3 tests OK。
- wheel build：passed。
- Web JS 与 docs JS syntax check：passed。
- 发布树排除了本地 SQLite、`tmp/`、`.codex/auth/` 和运行时生成关键帧。

## 文档入口

- [GitHub Pages 技术档案](https://blackzhanzhan.github.io/course2knowledge-lite/)
- [技术白皮书](docs/TECHNICAL_WHITEPAPER.md)
- [架构说明](docs/ARCHITECTURE.md)
- [数据模型](docs/DATA_MODEL.md)
- [Web Lite](docs/WEB_LITE.md)
- [Feishu/Hermes Lite](docs/FEISHU_LITE.md)
- [Bilibili Import](docs/BILIBILI_IMPORT.md)
- [部署说明](docs/DEPLOYMENT.md)
- [部署 FAQ](docs/DEPLOYMENT_FAQ.md)
- [测试说明](docs/TESTING.md)
