# Feishu/Hermes Lite

Feishu/Hermes Lite is the public chat surface.

It keeps the channel capability: a learner can send a Bilibili URL, ask about
course status, and ask questions about course content from Feishu.

## Allowed Replies

- import accepted
- import running
- import completed
- course list
- lecture list
- transcript coverage summary
- guided learning suggestion, walkthrough, self-check, or recap
- source-linked knowledge cards
- course-content answer with citations
- visual evidence explanation plus one `MEDIA:<path>` directive
- missing-evidence clarification
- lightweight progress acknowledgement

## Not Allowed

- protected learning-coach policy
- protected orchestration package
- automatic study-plan automation
- learner scoring analysis
- exercise-review workflow
- spaced-review state mutation
- task-completion automation
- production chat exports or production identifiers

## Hermes Profile Shape

The public Hermes profile is a small template:

- product name
- safe tool list
- import/status/Q&A boundaries
- no private production credentials

The template lives in `hermes/profile-template/`. Local setup is handled by
`scripts/sync_hermes_lite_profile.py`.

## Native Tool Boundary

The first public Hermes Lite toolset is `course2knowledge-lite`.

Tools:

- `collection_import_start`
- `import_status_get`
- `lecture_transcript_import`
- `lecture_transcript_import_by_ref`
- `lecture_transcript_source_probe`
- `manual_transcript_import`
- `course_transcript_coverage_get`
- `knowledge_cards_generate`
- `knowledge_card_list`
- `knowledge_card_get`
- `lecture_reader_get`
- `learning_guide_get`
- `course_search`
- `course_question_answer`
- `note_create`
- `note_list`
- `note_update`
- `note_delete`
- `bookmark_create`
- `bookmark_list`
- `bookmark_delete`
- `reading_progress_set`
- `reading_progress_get`
- `course_visual_evidence_send`

The tools call public package APIs and write to the child-local SQLite course
store. JSON may be used only as seed/export or migration compatibility. The
tools must not shell out to ad hoc scripts, read unrelated private profiles, or
mutate protected learning-state loops.

`course_visual_evidence_send` must select an existing public `VISUAL_EVIDENCE`
record. It cannot accept a naked local image path. The selected image must be
repo-local, public, present on disk, and tied to a course and lecture with an
explanation. The tool returns text plus exactly one `MEDIA:<path>` line for the
existing Hermes gateway media protocol.

Current guided-learning public-data smoke:

- tool: `learning_guide_get`
- mode: `self_check`
- result: source-linked questions from transcript/cards, with no grading,
  scoring, diagnosis, schedule, or review queue

Current visual public-data smoke:

- tool: `course_visual_evidence_send`
- course id: `course_e4af83f2c407`
- query: `Agent`
- selected visual id: `visual_rag_agent_flow`
- bound lecture: `course_e4af83f2c407::lecture::005`
- bound segment: `course_e4af83f2c407::lecture::005::manual::00001`
- media asset: `docs/assets/visual-evidence/rag-agent-flow.png`
- gateway reply: explanation text plus exactly one `MEDIA:<path>` line

Live Feishu/Lark gateway validation belongs to the public Lite profile
acceptance contract. Public docs should use the safe Lite profile and avoid
production chat exports.

## Rapid Message Behavior

If the gateway batches rapid Feishu messages into one assistant turn, Lite keeps
that as gateway behavior and handles it explicitly at the profile layer: the
assistant must open with
"BATCH: received multiple questions; answering in order. 收到多条快速问题，我会按收到顺序逐条回答。",
answer explicit labels in order (`主问题`, `Q1`, `追问1`, `Q2`, `追问2`, `Q3`,
`追问3`) before falling back to line order, and keep transcript citations scoped
to each question.

## Example User Requests

```text
Import this Bilibili course: <url>
What is the status of my import?
List lectures in this course.
What does lecture 3 say about attention?
Show me the source for that answer.
Mark lecture 3 as read.
Add a note to lecture 3.
Bookmark this transcript segment.
What should I read next?
Walk me through lecture 3.
Give me a few self-check questions.
Recap this lecture.
Show the visual evidence for Agent.
```
