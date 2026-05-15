# Web Lite

Web Lite is the primary visual workspace.

## Screens

- Course library
- Import status
- Lecture reader
- Guided learning
- Knowledge cards
- Search
- Course Q&A
- Notes
- Bookmarks
- Reading progress

## Expected Experience

The learner can import a course, open a lecture, follow evidence-grounded
guidance, read structured notes, inspect source citations, ask course questions,
and keep lightweight reading state.

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
- `/api/visual-evidence`
- `/api/guide`
- `/api/search`
- `/api/qa`
- `/api/notes`
- `/api/bookmarks`
- `/api/progress`

The page reads the same child local JSON store as Hermes Lite and does not call
external private-runtime routes.

The import panel owns these stable demo selectors:

- `#import-url`
- `#import-button`
- `#import-receipt`

Visual evidence is read from public child-local records only. Web Lite may show
the same evidence that Feishu/Hermes Lite can explain and send, but it must not
load private note systems, production chat exports, or unrelated workspace
files.

## Real Demo Acceptance

The current public demo case uses:

- source URL: `https://space.bilibili.com/1112988584/lists/7726472?type=season`
- course id: `course_e4af83f2c407`
- expanded lectures: `30`
- transcript-backed lectures: `3`
- transcript segments: `9`

The in-app browser acceptance run on `http://127.0.0.1:3014/` verified:

- `#import-url`, `#import-button`, and `#import-receipt` render after reload.
- the course library opens one public demo course with 30 lecture options.
- the reader opens a transcript-backed lecture.
- the `RAG Agent` search returns 5 transcript hits.
- Q&A returns an answered state with 5 citations from the same local store.

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

This should feel like a focused course workspace, not a marketing landing page.
The first screen should be useful: a course library or import/status view.
