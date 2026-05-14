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
- course-content answer with citations
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
- `lecture_reader_get`
- `course_search`
- `course_question_answer`

The tools call public package APIs and write to a local JSON course store. They
must not shell out to ad hoc scripts, read unrelated private profiles, or
mutate protected learning-state loops.

Live Feishu/Lark gateway validation belongs to the public Lite profile
acceptance contract.

## Example User Requests

```text
Import this Bilibili course: <url>
What is the status of my import?
List lectures in this course.
What does lecture 3 say about attention?
Show me the source for that answer.
Mark lecture 3 as read.
```
