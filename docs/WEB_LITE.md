---
layout: technical
title: Web Lite 课堂
permalink: /web-lite/
---
# Web Lite

Web Lite 是 Course2Knowledge Lite 的主要可视化课堂前台。它的目标不是做一个控制台，而是让学习者进入一门本地课程后，能直接聊天、查看知识节点、管理课程、阅读讲义和记录轻量学习状态。

核心原则：

```text
聊天是主交互
侧栏是上下文
课程管理是入口
课程笔记是证据阅读面
SQLite store 是唯一写入权威
```

## 1. 前台定位

Web Lite 面向一个很具体的问题：

> 当一门 B 站课程已经被导入并编译为本地课程知识运行时后，学习者如何在一个简单界面里开始学？

因此 Web Lite 不应该长成运维后台。它应尽量收敛为三个模块：

- `互动`：对话框、当前课程、当前课时、知识节点状态、本节证据。
- `课程管理`：导入、删除、课程列表、课时列表、readiness、导入错误。
- `课程笔记`：中文讲义、本地笔记、书签、阅读进度。

任何新增模块都要先证明它不能自然落入这三个模块。

## 2. 互动模块

互动模块是第一屏主角。学习者进入后应该能立刻看懂：

- 现在选中哪门课程。
- 现在选中哪一讲。
- 是否可以开始聊天。
- 当前知识节点处于什么状态。
- 本节课有哪些字幕证据或视觉证据。

聊天应优先围绕当前课程和当前课时工作。它不应该像搜索引擎一样对任何问题泛泛回答，而应该读取本地课程运行时，尽量回到字幕、讲义、知识原子、关口和视觉证据。

### 输入行为

- Enter 发送。
- Shift + Enter 换行。
- 发送按钮位于聊天栏下方或附近，移动端也应清晰。
- 没有选择课程时，应提示先导入或选择课程，而不是假装可用。

### 知识节点状态

侧栏可以展示知识原子和关口的轻量状态，例如：

- 待学习。
- 已出现。
- 当前聚焦。
- 已读课时。
- 需要证据。

这些状态来自当前 SQLite store、阅读进度和聊天事件，不等同于 mastery scoring。公共版不能把它伪装成学习者已经掌握。

## 3. 课程管理模块

课程管理负责把课程带入系统，并让导入状态可解释。

应支持：

- 粘贴 B 站合集、系列课、普通视频、多 P 视频 URL。
- 二维码登录获取 B 站登录态字幕。
- 单次 cookie 导入。
- remember-cookie 本机保存。
- 查看导入进度、阶段、错误和 promotion 结果。
- 删除本地课程。
- 选择课程和课时。
- 查看 readiness 摘要。

导入进度不能只显示“失败”或“未完成”。前台应尽量解释：

- 是 URL 展开失败。
- 是字幕缺失。
- 是登录态不足。
- 是模型配置缺失。
- 是讲义/原子/关口生成失败。
- 是临时 store 成功但 promotion 被保护性阻断。

## 4. 课程笔记模块

课程笔记负责呈现课程证据和学习者本地记录。

应支持：

- 显示当前课时中文讲义。
- 显示本地 note。
- 创建、更新、删除本地 note。
- 创建和删除 bookmark。
- 设置阅读进度。
- 在没有讲义或笔记时诚实显示空状态。

不能显示假的 Markdown、假的 Obsidian 内容或 mock 讲义。没有数据就是没有数据，应引导用户重新导入或查看 readiness。

## 5. Web 与 SQLite 的关系

Web Lite 不应该维护第二套课程状态。它的所有正式数据都应来自 SQLite store：

```text
apps/web/static/app.js
  -> apps/web/server.py
  -> packages/course-store SQLiteCourseStore
  -> data/course-store/course2knowledge-lite.sqlite3
```

JSON 可以作为 seed、fixture、调试导出或迁移输入，但不能成为正式写入权威。

## 6. Web 与 Hermes 的关系

Web Lite 和 Hermes Lite 应共享同一课程运行时：

```text
Web Lite chat
  -> Web API / Lite Chat Core
  -> local SQLite store

Hermes Lite tool
  -> course2knowledge-lite public package API
  -> local SQLite store
```

Web 不应该依赖私有母项目运行时才能完成公共功能。母项目 Hermes teaching adapter 可以作为开发集成验证路径，但公共 Lite 的稳定边界仍是 child-local SQLite runtime。

## 7. 主要 API 表面

当前 Web Lite 的 API 关注本地课程运行时：

| API | 用途 |
| --- | --- |
| `/api/courses` | 列出课程、读取课程摘要。 |
| `DELETE /api/courses?course_id=...` | 删除本地课程。 |
| `/api/import` | 启动 B 站课程导入。 |
| `/api/import/status` | 查询导入进度和 promotion 结果。 |
| `/api/readiness` | 读取课程 readiness。 |
| `/api/lectures` | 列出课程课时。 |
| `/api/coverage` | 查看字幕覆盖。 |
| `/api/reader` | 读取讲义和当前课时内容。 |
| `/api/cards` | 列出知识节点。 |
| `/api/cards/generate` | 触发知识节点生成。 |
| `/api/notes` | 管理本地笔记。 |
| `/api/bookmarks` | 管理书签。 |
| `/api/progress` | 管理阅读进度。 |
| `/api/chat/history` | 读取聊天历史。 |
| `/api/chat/stream` | 流式聊天输出。 |
| `/api/bilibili/login/qrcode` | 启动二维码登录。 |
| `/api/bilibili/cookie/save` | 本机保存 B 站 cookie。 |

这些 API 不应该回传真实 cookie、二维码密钥或 API key。

## 8. 错误和空状态

Web Lite 的错误设计要服务学习者，而不是只暴露异常栈。

推荐做法：

- 展示当前阶段：展开课程、获取字幕、编译讲义、生成原子、promotion。
- 展示失败原因：权限、网络、字幕、模型、store、未知异常。
- 展示下一步动作：扫码登录、粘贴 cookie、换 URL、检查模型 key、重试单讲。
- 保留技术详情入口，便于开发者复制给 AI 辅助排查。

不推荐：

- 只有“失败”。
- 只有“未完成”。
- 失败后仍展示旧知识原子，让用户误以为新管线生效。
- 静默使用 mock 数据。

## 9. 真实截图规则

公开截图必须遵守：

- 来自真实 Web Lite 前台或明确标注为 demo fixture。
- 不包含真实 cookie、API key、二维码密钥。
- 不包含私密聊天和个人课程数据。
- 不把空状态伪装成已完成课程。
- 课程数据如果来自本地 store，应确保可公开。

README 中的 Web Lite 截图是安全空状态截图，用来展示前台结构，不用于证明导入质量。

## 10. 不变式

Web Lite 必须保持这些不变式：

- 三模块优先，不扩散成多栏目控制台。
- 聊天是学习交互入口，不是搜索框皮肤。
- SQLite store 是正式数据权威。
- Hermes Lite 是可选工具前台，不是另一套产品状态。
- 没有真实数据时展示诚实空状态。
- 不从公共前台泄露本机密钥、cookie 或母项目私有状态。
