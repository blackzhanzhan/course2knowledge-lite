# Web Lite

Web Lite is the primary visual workspace.

## Screens

- Course library
- Import status
- Lecture reader
- Knowledge cards
- Search
- Course Q&A
- Notes
- Bookmarks
- Reading progress

## Expected Experience

The learner can import a course, open a lecture, read structured notes, inspect
source citations, ask course questions, and keep lightweight reading state.

## Current Local App

The current Web Lite workspace is a small local app:

```bash
python apps/web/server.py --port 3014
```

It exposes:

- `/api/courses`
- `/api/lectures`
- `/api/reader`
- `/api/search`
- `/api/qa`
- `/api/notes`
- `/api/bookmarks`
- `/api/progress`

The page reads the same child local JSON store as Hermes Lite and does not call
private Learning OS routes.

## Explicitly Out Of Scope

- automatic day-plan automation
- calendar scheduling
- answer-quality analysis
- learner scoring
- spaced-review state mutation
- exercise-review workflows

## Design Direction

This should feel like a focused course workspace, not a marketing landing page.
The first screen should be useful: a course library or import/status view.
