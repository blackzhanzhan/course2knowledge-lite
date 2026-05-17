# Web Lite

Web Lite is the primary visual classroom for the public Lite release. Its first
screen is a relaxed online-school frontdoor: chat with the learning assistant as
the main classroom action, while lesson progress and knowledge atom candidates
stay in the side panel.

## Screens

- Today's classroom
- Learning assistant chat
- Lecture reader
- Guided learning
- Quick transcript search
- Citation Q&A
- Course library
- Import status
- Knowledge cards
- Notes
- Bookmarks
- Reading progress
- Adapter information for Hermes Lite

## Expected Experience

The learner lands in a classroom, sees the selected course and lesson, follows
evidence-grounded guidance, and can immediately ask the learning assistant
questions backed by the same child-local course store. Transcript segments are
available as supporting evidence below the conversation. The side panel carries
lesson selection, reading progress, read-only guidance, and knowledge atom
candidates derived from existing `KNOWLEDGE_CARD` records.

Knowledge atom candidate state in the Web UI is intentionally lightweight. It
may show labels such as `待提问`, `已出现`, or `已读课时` from current cards,
reading progress, and in-memory chat signals. It is not a durable learning-state
model, does not write oral-check results, and does not import private mother
project mastery or review semantics.

The Web product should not ask the learner to think in cockpit/admin terms.
The default page focuses on the next useful classroom action. Search and
citation Q&A are available inside the classroom next to the assistant.

Guided learning in Web Lite means:

- continue from the next useful transcript-backed lecture
- walk through the current lecture with goals, evidence segments, cards, and
  visuals
- answer lightweight self-check questions with source evidence
- recap what to review without scoring the learner

## Current Local App

The current Web Lite workspace is a small local app:

```bash
python apps/web/server.py --port 3014
```

It exposes:

- `/api/courses`
- `/api/import`
- `/api/lectures`
- `/api/coverage`
- `/api/reader`
- `/api/cards`
- `/api/cards/generate`
- `/api/guide`
- `/api/search`
- `/api/qa`
- `/api/notes`
- `/api/bookmarks`
- `/api/progress`

The page reads the same child-local SQLite store as Hermes Lite and does not
call external private-runtime routes. JSON may be used only as seed/export or
migration compatibility. Web Lite is the primary public classroom; Hermes Lite
is a channel adapter over the same Lite Chat Core, not a separate public product
frontdoor. Web Lite must not call mother-project web, Feishu Base, planning,
feedback, scoring, diagnosis, or queue-completion paths.

The import panel owns these stable demo selectors:

- `#import-url`
- `#import-button`
- `#import-receipt`

Visual evidence is read from public child-local records only. Web Lite may show
the same evidence that Hermes Lite can explain and send, but it must not load
private note systems, production chat exports, or unrelated workspace files.

## Real Demo Acceptance

The current public demo case uses:

- source URL: `https://space.bilibili.com/1112988584/lists/7726472?type=season`
- course id: `course_e4af83f2c407`
- expanded lectures: `30`
- transcript-backed lectures: `3`
- transcript segments: `9`

The in-app browser acceptance run on `http://127.0.0.1:3014/` verified:

- `#import-url`, `#import-button`, and `#import-receipt` render after reload.
- the online classroom opens one public demo course with 30 lecture options.
- the learning assistant is visible from the classroom and uses
  `/api/chat/stream`.
- the `RAG Agent` search returns 5 transcript hits.
- Q&A returns an answered state with 5 citations from the same local store.
- Guided Learning renders continue, self-check, and recap modes from
  transcript-backed lecture evidence without mutating reading progress.

Evidence screenshots are stored under ignored `tmp/lite-demo-capability/`.

## Explicitly Out Of Scope

- automatic day-plan automation
- calendar scheduling
- answer-quality analysis
- learner scoring
- learner diagnosis
- spaced-review state mutation
- study-plan automation
- exercise-review workflows

## Design Direction

This should feel like a focused online school, not a marketing landing page and
not an operations console. The first screen should be useful: a classroom with
the current lesson, guidance, and an assistant ready to answer from evidence.
