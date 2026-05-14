# Course2Knowledge Lite

Turn online courses into interactive knowledge bases.

Course2Knowledge Lite is a public, trimmed product built from the idea that a
video course should not stay trapped as a timeline. It imports course material,
normalizes transcripts, builds structured lecture notes and knowledge cards, and
lets learners read, search, ask questions, bookmark, and track lightweight
progress.

This repository is intentionally focused. It is a course knowledge product, not
a full learning coach.

## Showcase Site

The public static site lives in [`docs/index.html`](docs/index.html). It is
designed for GitHub Pages and includes a real Web Lite showcase captured from a
local Bilibili collection import.

Use [`docs/SITE_MAP.md`](docs/SITE_MAP.md) for the page structure and content
contract.

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
- Build a local course knowledge store.
- Generate lecture notes, source-linked chunks, and knowledge cards.
- Provide a Web workspace for reading, search, notes, bookmarks, and progress.
- Provide a Feishu/Hermes Lite chat entry for import receipt, status, course
  lookup, and citation-based course Q&A.

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
  -> course knowledge store
  -> Web Lite workspace
  -> Feishu/Hermes Lite assistant
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
  course-store/     Local course knowledge records
  qa/               Citation-based course Q&A boundary
hermes/             Public Hermes Lite profile skeleton
docs/               Product and architecture documents
examples/           Safe demo fixtures
tests/              Boundary and smoke tests
data/               Local public runtime data, ignored by default later
```

## Current Status

The Lite repo has the public architecture, local Web Lite workspace,
Bilibili-course store, citation Q&A, public Hermes profile skeleton, deployment
smoke coverage, and GitHub Pages showcase scaffold. It deliberately excludes
private planning, scoring, feedback, and exercise-review loops.

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
