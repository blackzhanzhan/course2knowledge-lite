# Data Model

Course2Knowledge Lite uses a lightweight local product model.

The default local authority is SQLite:

```text
data/course-store/course2knowledge-lite.sqlite3
```

JSON files may still appear as public seed data, fixtures, migration input, or
export/debug artifacts, but they are not the default write authority after the
SQLite migration.

## Entities

### COURSE

Represents one imported course.

SQLite table: `courses`

Fields:

- `course_id`
- `title`
- `source_url`
- `source_platform`
- `import_status`
- `created_at`
- `updated_at`

### LECTURE

Represents one course lecture or video.

SQLite table: `lectures`

Fields:

- `lecture_id`
- `course_id`
- `title`
- `source_url`
- `source_id`
- `sequence`
- `duration_seconds`
- `read_status`

`source_id` is the platform-local identifier, such as a Bilibili BV id.

### TRANSCRIPT_SEGMENT

Represents a timestamped text segment.

SQLite table: `transcript_segments`

Fields:

- `segment_id`
- `lecture_id`
- `start_seconds`
- `end_seconds`
- `text`

Transcript segments are source evidence for later notes, cards, search, and
citation Q&A.

### KNOWLEDGE_CARD

Represents a concept, definition, summary, or cited explanation.
Current generated cards are conservative source cards: each card is derived
from one transcript segment and must retain `source_segment_ids`.

SQLite table: `knowledge_cards`

Fields:

- `card_id`
- `course_id`
- `lecture_id`
- `title`
- `body`
- `source_segment_ids`
- `tags`

### VISUAL_EVIDENCE

Represents a public image that can be shown in Web Lite or sent by
Feishu/Hermes Lite with an explanation.

SQLite table: `visual_evidence`

Fields:

- `visual_id`
- `course_id`
- `lecture_id`
- `segment_id`
- `card_id`
- `title`
- `explanation`
- `image_path`
- `source_url`
- `provenance`
- `created_at`

`image_path` must be a repo-local public asset path. Visual evidence cannot be
created from a naked user-supplied local path and cannot point outside this
repository.

### NOTE

Represents learner-authored notes.

SQLite table: `notes`

Fields:

- `note_id`
- `course_id`
- `lecture_id`
- `body`
- `created_at`
- `updated_at`

### BOOKMARK

Represents a saved lecture, segment, or card.

SQLite table: `bookmarks`

Fields:

- `bookmark_id`
- `target_type`
- `target_id`
- `created_at`

### READING_PROGRESS

Represents lightweight progress only.

SQLite table: `reading_progress`

Fields:

- `course_id`
- `lecture_id`
- `status`
- `last_opened_at`

Allowed statuses:

- `not_started`
- `reading`
- `read`

### IMPORT_STATUS

Represents the lightweight import status for a local course import.

SQLite table: `import_statuses`

Fields:

- `import_id`
- `course_id`
- `source_url`
- `source_platform`
- `status`
- `stage`
- `total_lectures`
- `completed_lectures`
- `failed_lectures`
- `created_at`
- `updated_at`

Initial collection expansion uses `status=accepted` and
`stage=collection_expanded`.

## Excluded Entities

The public data model does not include private learning-coach state, assessment
state, feedback state, scheduling state, mastery state, review stage, queue
completion, or diagnosis/writeback state.
