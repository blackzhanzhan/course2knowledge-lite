# Course2Knowledge Lite

Turn online courses into guided, interactive knowledge workspaces.

Course2Knowledge Lite is a public, trimmed product built from the idea that a
video course should not stay trapped as a timeline. It imports course material,
normalizes transcripts, builds structured lecture notes and knowledge cards, and
lets learners continue through a course, follow lecture walkthroughs, self-check
against cited evidence, read, search, ask questions, bookmark, and track
lightweight progress.

This repository is intentionally focused. It is a course knowledge product, not
a full learning coach.

## Showcase And Technical Dossier

The public static site lives in [`docs/index.html`](docs/index.html). It is
designed for GitHub Pages as both a project showcase and a technical dossier
entry. The site defaults to Chinese, includes an English toggle, and uses real
case screenshots from the public Lite runtime. The first screen explains the
system slice:

```text
Bilibili Collection
  -> Transcript Evidence
  -> Course Knowledge Store
  -> Web Lite + Feishu/Hermes Lite
```

The site intentionally foregrounds the dual-frontdesk design: Web Lite is the
inspectable reading workspace, while Feishu/Hermes Lite is the conversational
workspace over the same public course store.

Use [`docs/SITE_MAP.md`](docs/SITE_MAP.md) for the page structure and
[`docs/SHOWCASE_SHOT_LIST.md`](docs/SHOWCASE_SHOT_LIST.md) for the real evidence
capture contract. The current showcase carries 16 real evidence slots from the
Web Lite, API/store, visual-evidence, and Hermes Lite profile-smoke surfaces.
Real production chat is not used as public evidence; that gap remains explicitly
labelled until a safe Lite chat capture exists.

## Quick Start

```bash
pip install -e .
course2knowledge-lite --help
course2knowledge-lite web
```

To sync the public Hermes profile:

```bash
course2knowledge-lite sync-profile --apply --create-profile
course2knowledge-lite smoke-profile --profile-root %USERPROFILE%\\.hermes\\profiles\\course2knowledge-lite
```

## What It Does

- Import Bilibili course videos and transcripts.
- Build a local SQLite course knowledge store.
- Generate lecture notes, source-linked chunks, and knowledge cards.
- Provide a Web workspace for guided reading, search, notes, bookmarks, and
  progress.
- Provide a Feishu/Hermes Lite chat entry for import receipt, status, course
  lookup, guided learning, and citation-based course Q&A.
- Send selected public visual evidence with an explanation through the existing
  Hermes `MEDIA:<path>` reply protocol.

## What It Does Not Do

- No automatic study-plan automation.
- No learner scoring loop.
- No exercise-review workflow.
- No protected orchestration package.
- No production chat exports, production identifiers, or secrets.

## Product Shape

```text
Bilibili URL
  -> import job
  -> transcript segments
  -> lecture notes and knowledge cards
  -> SQLite course knowledge store
  -> guided learning + Web Lite workspace + Feishu/Hermes Lite assistant
```

## Repository Layout

```text
pyproject.toml     Installable public package entry
src/               CLI and installer shims
apps/
  web/              Web Lite workspace
  feishu-lite/      Feishu/Hermes Lite chat entry
packages/
  bilibili-import/  Bilibili import boundary
  course-store/     Local SQLite course knowledge records
  guidance/          Read-only guided-learning DTOs
  qa/               Citation-based course Q&A boundary
hermes/             Public Hermes Lite profile skeleton
docs/               Product and architecture documents
examples/           Safe demo fixtures
tests/              Boundary and smoke tests
data/               Local public runtime data, ignored by default later
```

## Current Status

The Lite repo has the public architecture, local Web Lite workspace,
Bilibili-course store, read-only guided learning, citation Q&A, public Hermes
profile skeleton, deployment smoke coverage, child-local visual evidence, and
GitHub Pages showcase scaffold. It deliberately excludes private planning,
scoring, feedback, and exercise-review loops.

## Start Here

- [Showcase Site](docs/index.html)
- [Static Site Map](docs/SITE_MAP.md)
- [Product Boundary](docs/PRODUCT_BOUNDARY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Web Lite](docs/WEB_LITE.md)
- [Feishu Lite](docs/FEISHU_LITE.md)
- [Bilibili Import](docs/BILIBILI_IMPORT.md)
- [Data Model](docs/DATA_MODEL.md)
- [Testing](docs/TESTING.md)
- [Deployment](docs/DEPLOYMENT.md)
