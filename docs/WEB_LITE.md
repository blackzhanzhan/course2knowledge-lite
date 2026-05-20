# Web Lite

Web Lite is the primary visual classroom for the public Lite release. The
frontend is intentionally reduced to three modules:

- `互动`: the main chat surface, current course/lecture selector, transcript
  evidence, and knowledge node state.
- `课程管理`: import courses, select/delete local courses, inspect lectures,
  transcript coverage, and generated knowledge atoms.
- `课程笔记`: show real Markdown/Obsidian content only when it exists; otherwise
  honestly show that Markdown/Obsidian is not connected or generated, then show
  local SQLite notes and bookmarks.

The product should feel like a focused online school, not an operations
console. Chat is the main learning interaction. Side panels are context, not
extra workspaces.

## Current Local App

```bash
python apps/web/server.py --port 3014
```

It exposes:

- `/api/courses`
- `DELETE /api/courses?course_id=...`
- `/api/import`
- `/api/lectures`
- `/api/coverage`
- `/api/reader`
- `/api/cards`
- `/api/cards/generate`
- `/api/notes`
- `/api/bookmarks`
- `/api/progress`
- `/api/chat/stream`

The page reads the same child-local SQLite store as Hermes Lite and does not
call external private-runtime routes. JSON may be used only as seed/export or
migration compatibility. Web Lite is the primary public classroom; Hermes Lite
is a channel adapter over the same Lite Chat Core, not a separate public product
frontdoor.

## Knowledge Node State

Knowledge node state in the Web UI is intentionally lightweight. It may show
labels such as `待提问`, `已出现`, or `已读课时` from current cards, reading
progress, and in-memory chat signals. It is not a durable learning-state model,
does not write oral-check results, and does not import private mother-project
mastery or review semantics.

## Explicitly Out Of Scope

- extra top-level modules beyond `互动 / 课程管理 / 课程笔记`
- fake Markdown or fake Obsidian content
- formal Feishu frontdesk changes
- private mother-project web/runtime calls
- learner scoring
- learner diagnosis
- spaced-review state mutation
- study-plan automation
- exercise-review workflows
