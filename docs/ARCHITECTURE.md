# Architecture

## System Context

Course2Knowledge Lite turns a video course into an interactive knowledge base.
It keeps two user-facing surfaces:

- Web Lite for reading, browsing, searching, and lightweight management.
- Feishu/Hermes Lite for chat-based import and course Q&A.

The system keeps real Bilibili import as the public platform adapter.

## Containers

### Web Lite

Owned path: `apps/web/`

Purpose:

- course library
- import dashboard
- lecture reader
- guided learning workspace
- knowledge cards
- search and Q&A panel
- notes, bookmarks, and reading progress

Boundary:

- no automatic study-plan automation
- no learner scoring analysis
- no private state authority
- guided learning is evidence organization, not a planner or evaluator

### Feishu/Hermes Lite

Owned paths:

- `apps/feishu-lite/`
- `hermes/`

Purpose:

- receive a Bilibili URL
- return import receipt and status
- answer questions from course content
- guide a learner through the current course or lecture from public evidence
- send selected public visual evidence with an explanation through
  `MEDIA:<path>`
- look up courses, lectures, and knowledge cards

Boundary:

- keeps the Feishu channel
- removes protected learning-coach cognition
- does not copy protected orchestration files
- does not create private plans, diagnoses, scores, or review queues

### Bilibili Import Runtime

Owned path: `packages/bilibili-import/`

Purpose:

- validate Bilibili URLs
- fetch metadata and transcripts when available
- normalize transcript segments
- create import status records

Boundary:

- Bilibili is the only real platform adapter in the public release.
- Additional source providers require a future public contract.

### Course Knowledge Store

Owned path: `packages/course-store/`

Purpose:

- course records
- lecture records
- transcript segments
- knowledge cards
- visual evidence records
- notes
- bookmarks
- reading progress

Boundary:

- local public product store only
- SQLite is the default child-local authority
- JSON is seed/export/migration compatibility only
- no private learning-state entities

### Visual Evidence Store

Owned paths:

- `packages/course-store/`
- `docs/assets/visual-evidence/`

Purpose:

- bind public repo-local images to a course and lecture
- preserve explanation and provenance for each image
- support Web reading/demo views and Feishu/Hermes Lite image replies

Boundary:

- no naked local image paths
- no repo-external files
- no private note-system or production chat evidence
- image replies reuse Hermes `MEDIA:<path>` and do not change gateway behavior

### Citation Q&A

Owned path: `packages/qa/`

Purpose:

- retrieve course evidence
- answer with citations
- explain when evidence is missing

Boundary:

- answers from course evidence
- does not score the learner
- does not mutate progress based on answer quality

### Guided Learning Layer

Owned path:

- `packages/guidance/`

Purpose:

- suggest the next useful lecture from existing lecture order and reading
  progress
- build a short walkthrough for one lecture from transcript segments, knowledge
  cards, and public visual evidence
- generate lightweight self-check questions with source evidence
- summarize what to review next without scoring or diagnosis

Boundary:

- derived at request time from the public local course store
- no durable guided session entity
- no calendar, schedule, day plan, spaced-review queue, or task queue
- no mastery, scoring, diagnosis, answer-quality grade, or exercise feedback
- no private learning-coach cognition from the parent project

## Flow

```text
Web or Feishu
  -> Bilibili import job
  -> transcript segments
  -> lecture notes and cards
  -> visual evidence
  -> SQLite course knowledge store
  -> citation Q&A, guided learning, and reading workspace
```

## Architecture Invariants

- The public repository is independent from unrelated private development workspaces.
- No protected production evidence is required to run the public product.
- No protected orchestration or private study loop is copied here.
- Bilibili import is real; other platform adapters are out of scope.
- Web Lite and Feishu Lite are user surfaces, not hidden learning-state engines.
- Web Lite and Feishu Lite must share the same child-local SQLite course store.
- Visual evidence is public course evidence only; it is not planning,
  feedback, scoring, mastery, review, or queue-completion state.
- Guided learning is a read-only public evidence organizer. It may say what to
  read next and how to inspect a lecture, but it must not become planning,
  feedback, scoring, mastery, diagnosis, review scheduling, or queue-completion
  state.
