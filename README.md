# Course2Knowledge Lite

Compile online video courses into local, runnable knowledge spaces.

Course2Knowledge Lite is not a conventional LMS, RAG demo, note app, or agent
framework. It treats a video course as a source of evidence, compiles that
evidence into a local course knowledge runtime, and projects the runtime through
an inspectable Web classroom plus an optional Hermes-native chat tool layer.

The core idea is simple:

```text
video course
  -> transcript and visual evidence
  -> lecture dossiers, notes, atoms, and gates
  -> local SQLite course runtime
  -> Web Lite classroom
  -> optional Hermes Lite tool frontdesk
```

The product is intentionally local-first. The SQLite store is the write
authority for the public release. Web Lite and Hermes Lite are frontdesk
projections over that same store, not separate data silos.

## Architecture Thesis

Course2Knowledge Lite introduces a course-to-knowledge runtime architecture:

- A course is not only downloaded or summarized; it is compiled into structured
  learning material.
- Evidence stays citeable through transcript segments, timestamps, source URLs,
  and visual evidence records.
- Generated lecture notes, knowledge atoms, review gates, and visual anchors are
  stored as local product data.
- Learner-facing interactions read the runtime instead of asking a model to
  improvise over raw video text.
- Chat is one projection of the knowledge runtime, not the product core.

This makes the system different from common categories:

- Not a plain RAG demo: retrieval and Q&A exist, but the main artifact is a
  reusable course knowledge runtime.
- Not an LMS: it does not manage institutions, enrollments, assignments, or
  grading.
- Not a note app: notes are downstream artifacts of course evidence, not the
  only representation.
- Not an agent framework: the optional Hermes layer calls native tools over the
  public store; it is not the business core.

## Runtime Shape

```text
Bilibili URL
  -> packages/bilibili-import
  -> temporary import SQLite store
  -> readiness and promotion gate
  -> packages/course-store SQLite runtime
  -> packages/qa and packages/guidance
  -> apps/web
  -> hermes/profile-template + hermes/plugins/course2knowledge-lite
```

### 1. Course Evidence Ingestion

The Bilibili importer is the retained real source adapter. It supports Bilibili
collection/list URLs, ordinary video URLs, and multi-page videos.

Imports first write to a temporary store. Promotion into the production SQLite
store is guarded:

- ready distinct new courses are merged;
- same-course reimports replace only that course when quality is not worse;
- probe subsets are not silently promoted;
- missing transcript, note, atom, or gate coverage blocks promotion honestly.

Authenticated Bilibili subtitles can use QR login, a one-shot pasted cookie, or
local remember-cookie storage. Cookie values are local runtime secrets and must
not be committed.

### 2. Course Knowledge Runtime

`packages/course-store` owns the local SQLite runtime:

- courses and lectures
- transcript segments
- lecture dossiers
- notes
- knowledge atoms and gates
- visual evidence
- bookmarks and reading progress
- chat threads, messages, and events

`packages/qa` answers from transcript evidence with citations. `packages/guidance`
builds read-only guided-learning payloads from public course evidence. Neither
package writes mastery scores, diagnoses, review queues, schedules, or private
learning-state records.

### 3. Web Lite Classroom

`apps/web` is the primary visual frontdesk. It is designed as a focused online
classroom with three modules:

- interaction: current course, current lecture, chat surface, evidence, and
  knowledge node state;
- course management: import, delete, inspect lectures, and view readiness;
- course notes: generated lecture material, local notes, bookmarks, and reading
  progress.

Web Lite is the surface to inspect whether the course runtime is actually useful:
what imported, which lectures are ready, what atoms were generated, what evidence
can be cited, and what the learner has marked locally.

### 4. Optional Hermes Lite Tool Frontdesk

`hermes/profile-template` and `hermes/plugins/course2knowledge-lite` provide an
optional Hermes-native tool layer. The profile registers public tools such as:

- `collection_import_start`
- `import_status_get`
- `course_transcript_coverage_get`
- `knowledge_cards_generate`
- `lecture_reader_get`
- `learning_guide_get`
- `course_search`
- `course_question_answer`
- `course_visual_evidence_send`
- notes, bookmarks, and reading-progress tools

The Hermes Lite layer calls the same package APIs and the same SQLite store as
Web Lite. It exists so a chat frontdesk can invoke native course tools instead
of running scripts or guessing over raw files.

When this repository is run inside the parent Learning OS workspace, Web chat
may also be connected to a parent Hermes teaching adapter for integration work.
That bridge is a development integration path, not a standalone public package
dependency and not the core Course2Knowledge Lite architecture.

## Quick Start

Requirements:

- Python 3.11 or newer
- Network access for live Bilibili imports

Install from the repository root:

```bash
pip install -e .
course2knowledge-lite --help
```

Start Web Lite:

```bash
course2knowledge-lite web
```

Open:

```text
http://127.0.0.1:3014/
```

By default, Web Lite writes local runtime data under:

```text
data/course-store/
```

Use a separate store for release or smoke testing:

```bash
course2knowledge-lite web --store-root tmp/release-web-store
```

## Import A Bilibili Course

Paste a supported Bilibili course URL into the Web import panel, for example:

```text
https://space.bilibili.com/1112988584/lists/7726472?type=season
```

The importer will:

1. expand the course into ordered lectures;
2. fetch available subtitle/transcript evidence;
3. compile Chinese lecture notes, knowledge atoms, gates, and optional visual
   keyframes;
4. evaluate readiness;
5. merge or block promotion into the production SQLite store.

For subtitles that require login, use the Web panel's QR login or paste a local
browser cookie for the current import. Optional remembered login state is stored
only on the local machine under `.codex/auth/`, which is ignored by git.

## Optional Hermes Profile

Sync the public Hermes Lite profile:

```bash
course2knowledge-lite sync-profile --apply --create-profile
```

Smoke-test the synced profile:

```bash
course2knowledge-lite smoke-profile --profile-root %USERPROFILE%\\.hermes\\profiles\\course2knowledge-lite
```

The smoke test verifies that the public profile registers the Lite toolset and
can call import/status, reader, guided learning, Q&A, visual evidence, notes,
bookmarks, and reading-progress tools against a local store.

## Package Layout

```text
pyproject.toml       installable package and runtime asset map
src/                 CLI and installed-runtime shims
apps/web/            primary Web Lite classroom
apps/feishu-lite/    public chat-entry notes and boundary docs
packages/
  bilibili-import/   Bilibili URL expansion, subtitle fetch, import handoff
  course-store/      SQLite runtime, dossiers, atoms, visual evidence, chat data
  guidance/          read-only guided-learning DTOs
  qa/                citation-based transcript Q&A
hermes/              optional Hermes Lite profile template and plugin
docs/                product, architecture, deployment, and showcase docs
examples/            safe demo fixtures
tests/               unit, boundary, profile, Web, and deployment tests
data/                local runtime data placeholder; real runtime data is ignored
```

## Deployment Package

The release package should include:

- the Python wheel for `course2knowledge-lite`;
- the source archive generated by GitHub;
- the `docs/` GitHub Pages showcase;
- the packaged Web runtime assets;
- the packaged Hermes Lite profile template and plugin;
- public visual evidence assets used by tests and docs.

The release package must not include:

- local SQLite runtime data from `data/course-store/`;
- temporary import stores under `tmp/`;
- `.codex/auth/` or any Bilibili login material;
- API keys or model-provider secrets;
- production chat exports, private identifiers, or parent-workspace runtime
  evidence.

## Testing

Focused release checks:

```bash
python -m unittest tests.test_deployment
python -m unittest discover -s tests
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps --no-cache-dir
node --check apps/web/static/app.js
git diff --check
```

The current release precheck evidence is tracked in the parent development
runtime under:

```text
dev_repo/public_lite_release_precheck_rpr3_20260520.json
```

That evidence is not required to run the package. It records the local release
candidate checks used before publishing.

## Boundaries

Course2Knowledge Lite deliberately excludes:

- automatic study-plan automation;
- mastery scoring and diagnosis;
- spaced-review queues;
- exercise-review workflows;
- private production chat logs;
- private parent-workspace credentials or runtime state;
- remote backend requirements.

The public release is a local course knowledge runtime with inspectable Web UI
and optional Hermes-native tool access. That is the architecture boundary.

## Start Here

- [Showcase Site](docs/index.html)
- [Product Boundary](docs/PRODUCT_BOUNDARY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data Model](docs/DATA_MODEL.md)
- [Web Lite](docs/WEB_LITE.md)
- [Feishu/Hermes Lite](docs/FEISHU_LITE.md)
- [Bilibili Import](docs/BILIBILI_IMPORT.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Testing](docs/TESTING.md)
