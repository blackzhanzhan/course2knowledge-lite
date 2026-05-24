# Deployment

Course2Knowledge Lite is designed to be deployed in the simplest possible way:
install the package, run the Web workspace, and sync the public Hermes profile.

## 部署现实边界与 AI 辅助

Course2Knowledge Lite 目前是个人维护的公开版本，架构原创性较高：它不是传统 LMS、普通 RAG demo、笔记软件或通用 Agent 框架，而是把在线视频课程编译成本地 SQLite 课程知识运行时。因此，项目会优先保证本地单机链路、数据边界和可检查性，暂时不承诺成熟的一键云部署方案。

如果部署不顺利，请优先把问题缩小到可诊断材料：

- 操作系统、Python 版本、安装方式和启动命令；
- 终端错误日志或浏览器控制台错误；
- 使用的 store root、端口、B 站 URL 类型和是否需要登录态字幕；
- 是否设置了模型 API key，以及是否使用了二维码登录或 cookie 导入。

把这些信息交给 AI 辅助排查通常会更高效：让它先判断是环境依赖、端口占用、B 站字幕权限、模型配置、SQLite store 状态，还是 Web 前台资源问题；再按最小复现命令一步一步验证。这个建议不是把部署责任推给使用者，而是因为当前项目仍处于个人维护和架构探索阶段，AI 辅助能显著降低不同机器环境带来的排障成本。

## Recommended Path

1. Install Python 3.11 or newer.
2. From the repository root, install the package. Editable install is best for
   development:

```bash
pip install -e .
```

For release verification, use a non-editable install in a fresh environment:

```bash
python -m venv .venv-release
.venv-release/Scripts/python -m pip install .
```

3. Confirm the CLI is available:

```bash
course2knowledge-lite --help
```

4. Start the Web Lite workspace:

```bash
course2knowledge-lite web
```

The default URL is:

```text
http://127.0.0.1:3014/
```

The default local store root is `data/course-store/`. For a clean deployment
smoke, use a temporary store:

```bash
course2knowledge-lite web --store-root tmp/release-web-store
```

5. Sync the public Hermes profile:

```bash
course2knowledge-lite sync-profile --apply --create-profile
```

6. Run the Hermes profile smoke test:

```bash
course2knowledge-lite smoke-profile --profile-root <profile-root>
```

The smoke test registers the synced Hermes plugin and verifies import status,
Q&A, knowledge cards, `learning_guide_get`, visual evidence media replies,
notes, and reading progress against a temporary public course store.

## Public Demo Mode

For a resume or portfolio deployment, publish a prepared demo course store and
run Web Lite in read-only mode:

```bash
course2knowledge-lite web \
  --host 0.0.0.0 \
  --port 3014 \
  --store-root /opt/course2knowledge-lite/data/course-store \
  --public-demo
```

Public demo mode keeps the useful interactive surface online while disabling
course import, course deletion, Bilibili QR/cookie actions, note writes,
bookmark writes, progress writes, and knowledge-card regeneration. Visitors can
still select a course, read generated notes, inspect transcript evidence, and
chat through the configured Hermes gateway.

The demo SQLite store is runtime data, not release source. Do not commit it to
git. Upload it to the server as an operational artifact and keep real cookies,
API keys, Hermes private sessions, and local author data out of the repository.

## Bilibili Login State

Some Bilibili subtitles require a logged-in browser session. The Web import
panel supports:

- QR login through Bilibili's login flow.
- Manual cookie paste for a single import.
- Optional local remember-cookie storage under `.codex/auth/bilibili.json`.

The auth file is ignored by git. Do not commit it, copy it into docs, or paste
its values into issue reports. Status APIs expose only sanitized metadata such
as whether a cookie exists and which cookie names are present.

## Import Promotion Semantics

Imports first run against a temporary store and then pass a readiness gate before
production SQLite changes:

- distinct ready new course: merge that course into the production store;
- same-course reimport: replace only that course when readiness is not worse;
- lower-quality candidate: block promotion and keep existing data;
- `max_lectures` probe subset: keep it as a probe and do not auto-promote.

This keeps a one-lecture test import or a no-subtitle failure from overwriting a
real course.

## Model And Concurrency Notes

The lecture dossier compiler can use the deterministic fallback path or a model
provider. For DeepSeek-compatible model generation, set:

```bash
set COURSE2KNOWLEDGE_LITE_DOSSIER_API_KEY=...
```

or, for the DeepSeek default, `DEEPSEEK_API_KEY`. The importer emits a
`parallelism_resolved` event for large courses so release checks can confirm the
effective lecture and dossier concurrency profile without inspecting secrets.

## Deployment Modes

- Local single-machine deployment: the default and recommended mode.
- Editable source deployment: useful for development and iteration.
- Packaged install deployment: the intended public experience once packaging is
  published.
- GitHub Pages showcase: serve the static public site from `docs/`.

## GitHub Pages Showcase

The static product site requires no build step.

Recommended repository setting:

1. Open GitHub repository settings.
2. Go to Pages.
3. Set source to `Deploy from a branch`.
4. Set branch to `main`.
5. Set folder to `/docs`.

The entry page is:

```text
docs/index.html
```

The showcase screenshots in `docs/assets/demos/` were captured from real Web
Lite, API/store, and Hermes profile-smoke runs against the public demo course
store. They are static documentation assets, not runtime data.

## What Deployment Does Not Require

- Docker.
- Kubernetes.
- A remote backend.
- Private runtime files.
- Private production credentials or sessions.

## Release Precheck

Before tagging a release candidate, run:

```bash
python -m unittest tests.test_deployment
python -m unittest discover -s tests
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps
node --check apps/web/static/app.js
git diff --check
```

Then run the path and sensitive scans described in `docs/TESTING.md`. Test
fixtures may contain fake cookie names or sentinel values; real cookie values,
API keys, and machine-specific workspace paths must not appear in committed
release files.

## Notes

- The Web workspace reads the local course store only.
- Hermes profile sync copies the public profile template and plugin only.
- Use the profile path printed by `sync-profile` as `<profile-root>`.
- Windows Sandbox smoke uses a generated `.wsb` file under `tmp/`; the committed
  placeholder intentionally contains no host path.
