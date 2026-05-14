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
- knowledge cards
- search and Q&A panel
- notes, bookmarks, and reading progress

Boundary:

- no automatic study-plan automation
- no learner scoring analysis
- no private state authority

### Feishu/Hermes Lite

Owned paths:

- `apps/feishu-lite/`
- `hermes/`

Purpose:

- receive a Bilibili URL
- return import receipt and status
- answer questions from course content
- look up courses, lectures, and knowledge cards

Boundary:

- keeps the Feishu channel
- removes protected learning-coach cognition
- does not copy protected orchestration files

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
- notes
- bookmarks
- reading progress

Boundary:

- local public product store only
- no private learning-state entities

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

## Flow

```text
Web or Feishu
  -> Bilibili import job
  -> transcript segments
  -> lecture notes and cards
  -> course knowledge store
  -> citation Q&A and reading workspace
```

## Architecture Invariants

- The public repository is independent from unrelated private development workspaces.
- No protected production evidence is required to run the public product.
- No protected orchestration or private study loop is copied here.
- Bilibili import is real; other platform adapters are out of scope.
- Web Lite and Feishu Lite are user surfaces, not hidden learning-state engines.
