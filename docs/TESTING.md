# Testing

Course2Knowledge Lite 的测试目标不是只证明“代码能跑”，而是证明公共子项目没有偏离边界：

- 能把课程导入本地课程运行时。
- 能用 SQLite 持久化和查询。
- Web Lite 与 Hermes Lite 读取同一 store。
- 导入失败和 promotion blocked 能被解释。
- 发布包不包含私密数据。

## 1. 快速发布前检查

推荐在发布前运行：

```bash
python -m unittest tests.test_deployment
python -m unittest discover -s tests
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps --no-cache-dir
node --check apps/web/static/app.js
node --check docs/site.js
git diff --check
```

其中：

- `tests.test_deployment` 验证包安装、profile sync 和 smoke。
- `unittest discover` 覆盖导入、store、Web、Hermes、QA、guidance。
- `pip wheel` 验证发布包可构建。
- `node --check` 验证前端和 docs JS 语法。
- `git diff --check` 防止空白错误。

## 2. 边界扫描

公共仓库必须避免泄露私有凭证、运行时数据和母项目状态。

建议扫描：

```bash
rg -n --hidden -g '!**/.git/**' -g '!tmp/**' -g '!data/**' \
  "<local user path patterns>|<Bilibili cookie names>|<model API key patterns>" .
```

允许出现：

- 环境变量名称。
- 假 cookie fixture。
- sentinel 测试值。
- 文档中提醒不要提交的字面量。

不允许出现：

- 真实 cookie 值。
- 真实 API key。
- 本机用户绝对路径。
- 生产聊天标识符。
- `.codex/auth/` 内容。
- 本地 SQLite 数据库。

## 3. 产品能力测试

测试应覆盖这些能力：

- B 站 URL 解析和课程展开。
- 普通视频、多 P、合集、系列课。
- 字幕获取和 transcript segment 归一化。
- cookie 脱敏。
- course / lecture / transcript CRUD。
- lecture dossier 编译。
- knowledge atom / gate 生成。
- visual evidence 绑定和 unavailable reason。
- readiness summary。
- promotion decision。
- note / bookmark / reading progress。
- chat thread / message / event。
- QA missing-evidence 行为。
- Hermes tool registration。
- Web API 行为。

## 4. 导入管线测试

导入测试不应只看“有没有返回 completed”。

至少要验证：

- 导入先写临时 store。
- candidate readiness 可以被读取。
- ready 新课程会 merge。
- 同课程重导入不倒退才 replace。
- `max_lectures` probe 不会自动覆盖正式课程。
- 缺字幕、缺 notes、缺 atoms、缺 gates 时 promotion blocked。
- 前台状态能解释 blocked 原因。

建议检查字段：

- `lecture_count`
- `ready_lecture_count`
- `missing_lecture_count`
- `transcript_ready_count`
- `note_ready_count`
- `atom_ready_count`
- `gate_ready_count`
- `promotion_decision`
- `auth_source`
- `cookie_present`

## 5. Web Lite 测试

Web Lite 测试应证明它是课堂前台，不是 mock 控制台。

关注点：

- 首页只有三个主模块：互动、课程管理、课程笔记。
- 没有课程时展示诚实空状态。
- 课程选择后能切换 lecture。
- Enter 发送，Shift + Enter 换行。
- 发送按钮位置清晰。
- 聊天流式输出可见。
- 知识节点状态来自当前课程数据。
- 导入错误和进度可以解释。
- 笔记和书签能持久化。

本地启动：

```bash
course2knowledge-lite web
```

默认地址：

```text
http://127.0.0.1:3014/
```

## 6. Hermes Lite 测试

Hermes Lite 测试应证明工具调用同一 SQLite store，而不是跑脚本或读私有状态。

关注工具：

- `collection_import_start`
- `import_status_get`
- `course_transcript_coverage_get`
- `knowledge_cards_generate`
- `lecture_reader_get`
- `learning_guide_get`
- `course_search`
- `course_question_answer`
- `course_visual_evidence_send`
- notes / bookmarks / reading-progress 工具

同步 profile：

```bash
course2knowledge-lite sync-profile --apply --create-profile
```

运行 smoke：

```bash
course2knowledge-lite smoke-profile --profile-root <profile-root>
```

验收点：

- 工具注册成功。
- 工具读取 child-local SQLite store。
- visual evidence 返回解释和一个 `MEDIA:<path>`。
- Q&A 没有证据时明确说明。
- 不写 mastery、diagnosis、review queue。

## 7. 截图验证

公开截图分三类：

- real frontend：真实 Web Lite 前台截图。
- technical page：GitHub Pages 技术档案截图。
- demo fixture：明确标注的安全演示素材。

截图不能包含：

- 真实 cookie。
- 二维码密钥。
- API key。
- 私密聊天。
- 本地用户路径。
- 未公开课程数据。

如果 README 或 docs 使用截图，应验证：

- 图片路径存在。
- GitHub raw 能访问。
- GitHub README 或 Pages 渲染能加载。

## 8. 文档链接测试

README 和 GitHub Pages 会链接多个 docs。发布前至少检查：

- `docs/TECHNICAL_WHITEPAPER.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/WEB_LITE.md`
- `docs/FEISHU_LITE.md`
- `docs/BILIBILI_IMPORT.md`
- `docs/DEPLOYMENT.md`
- `docs/TESTING.md`

这些文档不能只是占位标题，应能解释自己的边界、入口、测试方式和风险。

## 9. 部署 smoke

部署 smoke 应验证：

- fresh venv 能安装 package。
- CLI 可用。
- Web Lite 能启动。
- profile sync 可用。
- smoke profile 可运行。
- 发布包不依赖本机私有路径。

推荐：

```bash
python -m venv .venv-release
.venv-release/Scripts/python -m pip install .
.venv-release/Scripts/course2knowledge-lite --help
```

Windows Sandbox smoke 可以生成 `.wsb` 到 `tmp/`，但提交文件不能包含 host-specific path。

## 10. 失败分类

测试失败时先分类：

| 类型 | 常见原因 |
| --- | --- |
| 环境失败 | Python 版本、venv、依赖安装、端口占用。 |
| 平台失败 | B 站 URL、字幕权限、登录态、网络。 |
| 模型失败 | API key、provider、并发限流。 |
| Store 失败 | SQLite schema、迁移、临时 store、promotion。 |
| Web 失败 | JS 语法、API 状态、空状态、截图路径。 |
| 发布失败 | 文件缺失、敏感信息、host path、wheel 包资源。 |

部署不顺时，建议把环境、命令、日志和失败分类交给 AI 辅助排查。这个项目架构原创性较高，排障时把问题拆成上述层级通常比泛泛搜索更有效。

## 11. 验收规则

公共测试应证明 Course2Knowledge Lite 是一个可运行的课程知识产品：

- 它可以导入课程。
- 它可以保存课程证据。
- 它可以生成并展示课程知识对象。
- 它可以通过 Web 和 Hermes 访问同一 store。
- 它可以诚实处理失败。
- 它不会泄露私有状态。

测试不需要证明公共 Lite 已经是完整学习教练。公共版没有 mastery、diagnosis、spaced-review queue 和 exercise-review workflow。
