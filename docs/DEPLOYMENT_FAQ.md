# Deployment FAQ

这份 FAQ 记录 Course2Knowledge Lite 服务化部署中真实遇到过的问题。它不包含个人部署地址、密码、API key、cookie 或任何私有课程聊天内容。

## 1. 为什么 README 说需要 Node.js，但 Web 服务不是 Node 项目？

Web Lite 的常驻服务是 Python CLI 启动的：

```bash
course2knowledge-lite web
```

Node.js 主要用于发布前静态检查：

```bash
node --check apps/web/static/app.js
node --check docs/site.js
```

真实部署时遇到过的问题是：后端服务能启动，不代表前台 JS 没有语法错误。把 Node.js LTS 列为前置条件，是为了让部署者能在服务器或 CI 上直接检查前台静态资源，而不是等浏览器白屏后再排查。

## 2. 为什么必须先准备 Hermes gateway？

Web Lite 的课程浏览、笔记阅读和本地 API 可以独立工作，但学习助手的真实流式回复依赖 Hermes gateway。默认网关地址是：

```text
http://127.0.0.1:8642/v1/chat/completions
```

如果 Hermes 没有启动，聊天会进入 gateway unavailable 路径；这不是前台 mock，而是后端无法拿到真实 Hermes 流式输出。

建议先在服务器本机确认：

```bash
systemctl is-active course2knowledge-lite-hermes
ss -ltnp '( sport = :8642 )'
```

期望 Hermes 只监听本机：

```text
127.0.0.1:8642
```

不要把 Hermes gateway 暴露到公网。

## 3. 为什么 `git pull` 后页面还是旧的？

真实部署时踩过这个坑：仓库 HEAD 更新了，但 systemd 仍然运行旧进程，或者 editable install 没有重新安装运行时资源。

正确更新顺序是：

```bash
cd /opt/course2knowledge-lite
git fetch origin codex/decouple-hermes-lite
git checkout codex/decouple-hermes-lite
git pull --ff-only origin codex/decouple-hermes-lite
.venv/bin/python -m pip install -e .
systemctl restart course2knowledge-lite-hermes
systemctl restart course2knowledge-lite-web
```

然后检查：

```bash
git rev-parse --short HEAD
systemctl is-active course2knowledge-lite-web course2knowledge-lite-hermes
curl -s http://127.0.0.1:3014/static/app.js | grep '正在打开课程库'
```

如果最后一条命令看不到新文案，说明服务或静态资源仍然不是新版本。

## 4. 为什么 Web 是 `0.0.0.0:3014`，Hermes 是 `127.0.0.1:8642`？

这是部署边界，不是随便选的端口。

- Web Lite 是给浏览器访问的课堂前台，可以监听 `0.0.0.0:3014`。
- Hermes gateway 是后端内部工具入口，应只监听 `127.0.0.1:8642`。

验收命令：

```bash
ss -ltnp '( sport = :3014 or sport = :8642 )'
```

期望：

```text
0.0.0.0:3014
127.0.0.1:8642
```

如果 Hermes 暴露成 `0.0.0.0:8642`，应调整 systemd 或 Hermes 启动配置。

## 5. 为什么接口返回 429？

小 VPS 不适合无限并发跑 Hermes 对话。Course2Knowledge Lite 有一个聊天并发闸门，默认限制并发 chat stream，超限时返回明确提示：

```text
当前访客较多，Hermes 正在处理其他同学的对话，请稍后再试。
```

可通过环境变量调整：

```bash
COURSE2KNOWLEDGE_LITE_CHAT_CONCURRENCY=4
```

不要把并发数盲目调高。真正的瓶颈往往在模型供应商、Hermes gateway、服务器 CPU/内存和网络延迟。

## 6. 为什么不同访客的聊天不会串在一起？

受控体验模式下，前台会给每个浏览器会话分配 `visitor_session_id`，聊天线程、消息和事件写入独立访客通道：

```text
web:visitor:<visitor_session_id>
```

结束体验会调用：

```text
POST /api/chat/session/end
```

它只清空当前访客的聊天记录，不删除课程、讲义、知识原子、字幕证据或视觉证据。

验收方式：

```bash
curl -s 'http://127.0.0.1:3014/api/chat/history?course_id=<course-id>&visitor_session_id=a'
curl -s 'http://127.0.0.1:3014/api/chat/history?course_id=<course-id>&visitor_session_id=b'
```

两个 visitor 不应看到彼此的历史。

## 7. 为什么 `/api/runtime` 正常，但聊天没有回复？

`/api/runtime` 只证明 Web 服务在线，不证明 Hermes 链路可用。聊天链路还需要：

- Hermes gateway active。
- `HERMES_WEB_GATEWAY_URL` 指向正确地址。
- Hermes profile 已同步并能调用 `course2knowledge-lite` tools。
- 模型供应商密钥在服务器本地环境中可用。
- Web 服务和 Hermes 服务读取同一份课程 store。

建议按顺序查：

```bash
systemctl is-active course2knowledge-lite-web course2knowledge-lite-hermes
journalctl -u course2knowledge-lite-hermes -n 80 --no-pager
journalctl -u course2knowledge-lite-web -n 80 --no-pager
curl -s http://127.0.0.1:3014/api/courses
```

如果 Hermes 日志里没有真实模型调用或 tool 调用，优先排查 Hermes profile 和模型密钥。

## 8. 为什么课程导入慢？

课程导入不是简单抓列表。完整导入会展开 B 站课程、拉字幕、生成中文讲义、知识原子、关口和可选视觉证据，再经过 readiness / promotion gate 合并到正式 SQLite store。

项目有并发策略，但不会无限扇出。相关实现见：

```text
packages/bilibili-import/src/course2knowledge_lite_bilibili/parallelism.py
```

如果只是部署展示，建议先在本机或服务器后台准备好课程 store，再用只读体验模式提供浏览和聊天。

## 9. 为什么 B 站字幕拿不到？

常见原因：

- 视频本身没有字幕。
- 字幕需要登录态。
- Cookie 过期或二维码登录态过期。
- B 站风控、网络环境或地区访问限制。

Web Lite 支持三种登录态路径：

- 扫码登录。
- 单次手动 Cookie。
- 显式 remember-cookie，保存到本机 `.codex/auth/`。

`.codex/auth/` 已被 git 忽略。不要把真实 cookie 写入文档、截图、issue 或测试 fixture。

## 10. 部署文档里的 `--public-demo` 是不是一定表示公开地址？

不是。`--public-demo` 是历史参数名，实际语义是“只读体验模式”：

- 禁止课程导入。
- 禁止删除课程。
- 禁止 B 站 Cookie/二维码操作。
- 禁止笔记、书签、阅读进度和知识卡片写入。
- 保留课程浏览、课程笔记和 Hermes 学习对话。

它可以用于本机演示、内网部署、作品集部署或其他受控访问环境。是否公开地址，是运维和访问控制问题，不是该参数本身的含义。

## 11. 如何证明部署后跑的是新版本？

不要只看页面刷新。按三层验收：

```bash
git rev-parse --short HEAD
systemctl is-active course2knowledge-lite-web course2knowledge-lite-hermes
curl -s http://127.0.0.1:3014/static/app.js | grep 'Lite Runtime'
```

如果 HEAD 是新的、服务 active、静态资源里也能查到新文案，才说明部署真正生效。

## 12. 可以用 AI 辅助部署排障吗？

可以，而且很适合这个项目。建议把以下信息整理给 AI：

- 操作系统与 Python/Node.js 版本。
- `git rev-parse --short HEAD`。
- `systemctl status` 和 `journalctl` 关键日志。
- `ss -ltnp` 端口监听结果。
- `/api/runtime`、`/api/courses`、`/api/chat/stream` 的返回。
- 是否使用 B 站登录态、是否有模型 API key、是否跑了 Hermes profile smoke。

不要提供真实密码、cookie、API key、个人部署地址或私有聊天记录。排障应基于结构化日志和脱敏配置完成。
