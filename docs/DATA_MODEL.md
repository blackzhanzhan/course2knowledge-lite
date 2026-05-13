# Data Model

Course2Knowledge Lite uses a lightweight local product model.

## Entities

### COURSE

Represents one imported course.

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

Fields:

- `lecture_id`
- `course_id`
- `title`
- `source_url`
- `sequence`
- `duration_seconds`
- `read_status`

### TRANSCRIPT_SEGMENT

Represents a timestamped text segment.

Fields:

- `segment_id`
- `lecture_id`
- `start_seconds`
- `end_seconds`
- `text`

### KNOWLEDGE_CARD

Represents a concept, definition, summary, or cited explanation.

Fields:

- `card_id`
- `course_id`
- `lecture_id`
- `title`
- `body`
- `source_segment_ids`
- `tags`

### NOTE

Represents learner-authored notes.

Fields:

- `note_id`
- `course_id`
- `lecture_id`
- `body`
- `created_at`
- `updated_at`

### BOOKMARK

Represents a saved lecture, segment, or card.

Fields:

- `bookmark_id`
- `target_type`
- `target_id`
- `created_at`

### READING_PROGRESS

Represents lightweight progress only.

Fields:

- `course_id`
- `lecture_id`
- `status`
- `last_opened_at`

Allowed statuses:

- `not_started`
- `reading`
- `read`

## Excluded Entities

The public data model does not include private learning-coach state, assessment
state, feedback state, or scheduling state.

