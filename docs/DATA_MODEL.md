# Data Model

Course2Knowledge Lite 使用本地 SQLite 作为默认写入权威。数据模型围绕“课程证据 -> 编译对象 -> 前台交互”组织，而不是围绕聊天消息或向量检索组织。

默认本地 store：

```text
data/course-store/course2knowledge-lite.sqlite3
```

JSON 可以作为 seed、fixture、迁移输入或调试导出存在，但不再是正式写入权威。

## 1. 模型总览

```text
Course
  -> Lecture
    -> Transcript Segment
    -> Lecture Dossier
    -> Knowledge Atom / Card
    -> Gate
    -> Visual Evidence
    -> Note
    -> Bookmark
    -> Reading Progress

Import Run / Import Status
  -> Readiness
  -> Promotion Event

Chat Thread
  -> Message
  -> Event
```

实体分为三类：

- source entities：来自外部课程源，例如 course、lecture、transcript segment。
- derived entities：从课程证据编译，例如 dossier、knowledge atom、gate、visual evidence。
- learner-local entities：学习者本地写入，例如 note、bookmark、reading progress、chat thread。

公共 Lite 不包含私有学习教练实体，例如 mastery、diagnosis、review queue、exercise feedback。

## 2. Course

Course 表示一门导入课程。

典型字段：

- `course_id`
- `title`
- `source_url`
- `source_platform`
- `import_status`
- `created_at`
- `updated_at`

规则：

- `course_id` 是本地运行时身份，不应依赖平台标题。
- `source_platform` 当前主要为 `bilibili`。
- 同一课程重导入不应直接覆盖旧课程，必须经过 promotion decision。

## 3. Lecture

Lecture 表示课程中的一讲、一个视频或多 P 视频中的一个分片。

典型字段：

- `lecture_id`
- `course_id`
- `title`
- `source_url`
- `source_id`
- `sequence`
- `duration_seconds`
- `read_status`

规则：

- `sequence` 决定课程顺序。
- `source_id` 可以是 BV 号等平台局部标识。
- `read_status` 是轻量阅读状态，不代表掌握度。

## 4. Transcript Segment

Transcript Segment 是最重要的证据单元。

典型字段：

- `segment_id`
- `lecture_id`
- `start_seconds`
- `end_seconds`
- `text`

用途：

- 生成中文讲义。
- 生成知识原子和关口。
- 课程搜索。
- 引用式 Q&A。
- 视觉关键帧 anchor。

规则：

- 没有 transcript evidence 时，系统应明确说明证据不足。
- 不能用泛化模型记忆冒充课程证据。

## 5. Lecture Dossier

Lecture Dossier 表示一讲的编译结果，通常包含：

- 中文讲义。
- 结构化摘要。
- 课程上下文。
- anchor。
- knowledge atom 候选。
- gate 候选。

它是 derived entity，不是用户笔记。

规则：

- 应尽量由 transcript evidence 编译。
- 没有模型 key 时可以走 deterministic fallback，但不能宣传为模型质量等价。
- 生成内容应保持中文优先。

## 6. Knowledge Atom / Card

Knowledge Atom 或 Knowledge Card 表示课程中的知识节点。

典型字段：

- `card_id`
- `course_id`
- `lecture_id`
- `title`
- `body`
- `source_segment_ids`
- `tags`

规则：

- 必须能回到课程证据或讲义编译结果。
- 不应生成“通用百科式”节点来冒充本课程知识。
- 前台显示的节点状态是轻量学习状态，不是 mastery。

## 7. Gate

Gate 表示学习关口、自检点或收口问题。

典型信息：

- gate 标题。
- 对应 atom。
- 自检问题。
- 证据来源。
- 当前课时上下文。

规则：

- gate 的目的是帮助学习者收口，不是无限追问。
- 公共 Lite 不把 gate 结果写成掌握度诊断。

## 8. Visual Evidence

Visual Evidence 表示绑定课程和课时的视觉证据。

典型字段：

- `visual_id`
- `course_id`
- `lecture_id`
- `segment_id`
- `card_id`
- `title`
- `explanation`
- `image_path`
- `source_url`
- `provenance`
- `created_at`

允许 provenance：

- `generated_keyframe`：从课程源视频提取的真实关键帧。
- `demo_visual`：公开 demo fixture，只能用于文档或 smoke，不能替代真实课程关键帧。

规则：

- `image_path` 必须是仓库内公开路径或发布包安全资产。
- 不能记录裸本地绝对路径。
- 媒体不可用时应记录 unavailable reason，而不是造占位图。

## 9. Note

Note 表示学习者本地笔记。

典型字段：

- `note_id`
- `course_id`
- `lecture_id`
- `body`
- `created_at`
- `updated_at`

规则：

- note 是 learner-local entity。
- note 不应被系统当成课程源证据，除非明确标注为用户输入。

## 10. Bookmark

Bookmark 表示学习者保存的目标。

典型字段：

- `bookmark_id`
- `target_type`
- `target_id`
- `created_at`

可指向：

- lecture。
- transcript segment。
- knowledge card。
- visual evidence。

## 11. Reading Progress

Reading Progress 是轻量阅读状态。

典型字段：

- `course_id`
- `lecture_id`
- `status`
- `last_opened_at`

允许状态：

- `not_started`
- `reading`
- `read`

规则：

- 只表示阅读进度。
- 不等同于掌握、理解、通过考试或完成学习关口。

## 12. Import Status / Import Run

Import Status 表示导入过程和状态解释。

典型字段：

- `import_id`
- `course_id`
- `source_url`
- `source_platform`
- `status`
- `stage`
- `total_lectures`
- `completed_lectures`
- `failed_lectures`
- `created_at`
- `updated_at`

典型 status：

- `accepted`
- `running`
- `completed`
- `partial`
- `failed`

典型 stage：

- `collection_expand`
- `lecture_compile`
- `ready_gate`
- `merged_new_course`
- `replaced_same_course`
- `promotion_blocked`
- `blocked_probe_subset`

规则：

- stage 是解释性状态，不是用户命令。
- 前台应展示失败原因和下一步建议。

## 13. Readiness

Readiness 是从 store 派生出的质量判断，不一定是一张独立表。

关键维度：

- `lecture_count`
- `ready_lecture_count`
- `missing_lecture_count`
- `transcript_ready_count`
- `note_ready_count`
- `atom_ready_count`
- `gate_ready_count`

规则：

- readiness 用来决定 promotion。
- readiness 不代表学习者学习完成。
- readiness 应区分“课程没准备好”和“学习者没学完”。

## 14. Promotion

Promotion 表示临时导入 store 到生产 store 的晋升决策。

典型决策：

- 新课程 ready：合并为新 course。
- 同课程 ready 且不倒退：替换该 course。
- 质量更差：阻断。
- `max_lectures` 探测子集：阻断自动晋升。

规则：

- 生产 store 不应被半成品污染。
- promotion blocked 是保护性成功，不一定是导入崩溃。

## 15. Chat Thread / Message / Event

聊天数据用于前台持久化。

Thread：

- `thread_id`
- `course_id`
- `lecture_id`
- `channel`
- `created_at`
- `updated_at`

Message：

- `message_id`
- `thread_id`
- `role`
- `content`
- `created_at`

Event：

- `event_id`
- `thread_id`
- `event_type`
- `payload`
- `created_at`

规则：

- chat 是学习交互入口，不是课程数据权威。
- 工具调用、流式 delta、错误和证据事件可以进入 event。
- 不应发布真实生产聊天导出。

## 16. 排除实体

公共 Lite 明确不包含：

- mastery score。
- diagnosis。
- review stage。
- spaced-review queue。
- exercise feedback。
- task completion。
- calendar plan。
- private learning journal。
- private mother-project state。

如果未来引入这些实体，需要 ER/data-model amendment，而不能静默加入。

## 17. 数据安全不变式

- SQLite 本地数据默认不进入 git。
- `tmp/` 导入 store 不进入发布包。
- `.codex/auth/` 不进入发布包。
- 真实 cookie、API key、本地绝对路径不能写入 docs 或测试证据。
- 公开截图不能包含私密聊天或真实账号登录态。
