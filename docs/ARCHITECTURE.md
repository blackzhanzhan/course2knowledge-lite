# Architecture

Course2Knowledge Lite 的架构可以概括为：

```text
Source -> Staging -> Compiler -> Runtime Authority -> Frontdesk Projection
```

它不是“前端 + 后端 + 模型”的普通三层应用，也不是“文档切片 + 向量库 + 聊天框”的普通 RAG demo。它的内核是本地 SQLite 课程知识运行时。

## 1. 架构命题

在线视频课程的原始形态是线性媒体。Course2Knowledge Lite 先把课程编译成稳定对象，再让前台使用这些对象。

这意味着：

- 课程先被展开为 lecture 序列。
- 每讲先被归一化为 transcript evidence。
- 讲义、知识原子、关口和视觉证据是编译产物。
- readiness 决定是否可以晋升到正式 store。
- Web Lite 和 Hermes Lite 都只是 runtime 的前台投影。

## 2. 总体流程

```text
Bilibili Course URL
  -> Import Adapter
  -> Temporary SQLite Store
  -> Transcript Evidence
  -> Visual Evidence
  -> Lecture Dossier
  -> Knowledge Atoms / Gates
  -> Readiness + Promotion Gate
  -> Production SQLite Course Runtime
  -> Web Lite Classroom
  -> optional Hermes Lite Tools
```

## 3. Source 层

Source 层负责把外部课程入口变成内部 lecture 引用。

当前真实 source provider：

- B 站合集 / 列表。
- B 站系列课。
- 普通视频。
- 多 P 视频。

关键职责：

- 解析 URL。
- 展开课程结构。
- 保留 lecture 顺序。
- 保留 source URL、BV 等平台标识。
- 探测字幕和登录态需求。

边界：

- B 站是当前公共版唯一真实平台适配器。
- 新平台需要新公共合同。
- Source 层不生成学习状态。

## 4. Staging 层

Staging 层使用临时 SQLite store 承接导入候选。

为什么需要 staging：

- 真实课程导入可能失败。
- 字幕可能需要登录态。
- 某些 lecture 可能缺字幕。
- 模型生成可能失败或超时。
- 探测导入可能只导入一讲。
- 半成品不能污染正式课程库。

Staging 的输出不是“正式课程”，而是 candidate course。candidate 只有通过 readiness 和 promotion gate 后才能进入生产 store。

## 5. Compiler 层

Compiler 层把课程证据编译成学习对象。

主要输入：

- lecture metadata。
- transcript segments。
- source URL。
- 可选视觉素材。

主要输出：

- lecture dossier。
- 中文讲义。
- knowledge atoms。
- gates。
- visual evidence。
- import artifacts。

关键设计：

- 讲义和知识节点应优先回到字幕证据。
- 没有模型 key 时可以 fallback，但要诚实标注质量边界。
- 视觉证据要绑定 course 和 lecture，不能只是裸图片路径。

## 6. Runtime Authority 层

Production SQLite Course Runtime 是业务权威源。

它保存：

- course / lecture。
- transcript segment。
- lecture dossier。
- knowledge atom / gate。
- visual evidence。
- note / bookmark / reading progress。
- chat thread / message / event。
- import status。

它不保存：

- 真实 cookie。
- API key。
- 母项目私有学习状态。
- 生产聊天导出。
- mastery、diagnosis、review queue。

## 7. Readiness 与 Promotion Gate

Readiness 是课程候选质量摘要。

检查维度包括：

- 课程是否有 lecture。
- lecture 是否有 transcript。
- 是否生成中文讲义。
- 是否生成 knowledge atoms。
- 是否生成 gates。
- 可选视觉证据是否可用或有明确 unavailable reason。

Promotion Gate 决定候选是否进入生产 store：

- ready 新课程：合并。
- 同课程重导入且不倒退：替换该课程。
- 质量更差：阻断。
- 探测子集：阻断自动晋升。

这就是为什么前台有时会看到“promotion blocked”：这可能是保护性阻断，不一定是导入崩溃。

## 8. Frontdesk Projection 层

前台是投影，不是内核。

### Web Lite

Web Lite 是主要视觉课堂：

- 互动模块。
- 课程管理。
- 课程笔记。

它通过 HTTP API 读取和写入本地 SQLite store。

### Hermes Lite

Hermes Lite 是可选工具前台：

- import status。
- transcript coverage。
- knowledge cards。
- lecture reader。
- learning guide。
- search。
- Q&A。
- visual evidence。
- notes/bookmarks/progress。

它调用公共 package API，不维护第二套 store。

## 9. 容器和职责

| 容器 | 路径 | 职责 |
| --- | --- | --- |
| CLI | `src/course2knowledge_lite/cli.py` | 启动 Web、同步 profile、运行 smoke。 |
| Web | `apps/web/` | 本地课堂前台和 HTTP API。 |
| Bilibili Import | `packages/bilibili-import/` | URL 展开、字幕获取、导入 handoff。 |
| Course Store | `packages/course-store/` | SQLite runtime、实体、dossier、chat、visual evidence。 |
| QA | `packages/qa/` | 基于证据的引用式问答。 |
| Guidance | `packages/guidance/` | 只读带学 payload。 |
| Hermes Lite | `hermes/` | 可选工具前台和 profile template。 |
| Docs | `docs/` | 技术档案、部署、测试、边界说明。 |

## 10. 关键调用链

### Web 导入

```text
用户粘贴 B 站 URL
  -> apps/web/server.py /api/import
  -> build_bilibili_json_fetcher
  -> import_collection_pipeline_to_store
  -> temporary SQLite store
  -> readiness
  -> promotion decision
  -> production SQLite store
  -> Web import status
```

### 聊天问答

```text
用户提问
  -> Web chat stream 或 Hermes tool
  -> course context
  -> course search / QA / guidance
  -> transcript evidence
  -> streamed answer / tool result
  -> chat message + event persistence
```

### 讲义和知识节点

```text
Transcript Segments
  -> lecture_dossier.py
  -> dossier_core/
  -> Chinese lecture note
  -> knowledge atoms
  -> gates
  -> readiness
```

## 11. 架构不变式

- SQLite 是本地写入权威。
- Web Lite 和 Hermes Lite 共享同一 store。
- B 站是当前唯一真实 source provider。
- 导入必须经过 staging 和 promotion。
- 公共前台不能依赖母项目私有运行时。
- 视觉证据必须绑定课程和课时。
- 聊天不拥有课程状态。
- 公共版不写私有学习教练状态。
- 发布包不包含本机秘密和运行时私有数据。

## 12. 为什么这不是普通 RAG

普通 RAG 重点在：

```text
document -> chunks -> embedding -> retrieval -> answer
```

Course2Knowledge Lite 的重点在：

```text
course -> lecture -> evidence -> dossier -> atoms/gates -> readiness -> runtime -> frontdesks
```

检索和问答只是 runtime 的下游能力。真正的架构创新是：把课程变成可检查、可晋升、可复用、可被多个前台共享的本地知识运行时。
