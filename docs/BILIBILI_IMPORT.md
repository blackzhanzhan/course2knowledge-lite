# Bilibili Import

Bilibili import is the retained real platform adapter for Course2Knowledge Lite.

## Responsibilities

- Validate Bilibili URLs.
- Expand Bilibili collection URLs into ordered video references.
- Read video or collection metadata.
- Fetch available transcripts or subtitle sources.
- Normalize transcript segments.
- Emit import status.
- Write course, lecture, and transcript records into the course knowledge store.

## Non-Goals

- No private multi-provider import matrix.
- No private source-provider promotion gates.
- No protected production evidence copying.
- No platform credential material in the repository.

## Import States

- `accepted`
- `running`
- `completed`
- `failed`

The Web import API also exposes internal stages such as `collection_expand`,
`lecture_compile`, `ready_gate`, `merged_new_course`,
`replaced_same_course`, `promotion_blocked`, and `blocked_probe_subset`.
These are status explanations, not separate user commands.

## Evidence Rule

Generated notes and Q&A must cite transcript segments or generated lecture
artifacts. If no relevant evidence exists, the assistant should say so.

## Collection Expander Contract

The collection expander is only an entry adapter. It returns:

- `sequence`
- `bvid`
- `title`
- `source_url`

Every returned video then follows the normal single-video import path.

The first local store handoff writes those video references as a course skeleton:

- one course record
- ordered lecture records
- one import status record

Transcript fetching remains a later stage.

The current importer accepts Bilibili collection/list URLs and ordinary video
URLs. Multi-page videos are expanded into ordered lectures before transcript
fetching.

## Transcript Segment Handoff

For a single lecture video URL, the importer can fetch available Bilibili
subtitles and write timestamped `TRANSCRIPT_SEGMENT` records to the local course
store.

The Feishu/Hermes Lite frontdesk can also import a lecture transcript by local
course reference. After a collection import returns an `import_id`, the user may
ask for a sequence such as "import the transcript for lecture 1". The frontdesk
uses `lecture_transcript_import_by_ref` to resolve the stored lecture from the
child-local SQLite store and then runs the normal single-video transcript handoff.

Before importing, the frontdesk can call `lecture_transcript_source_probe` to
check whether a stored Bilibili lecture exposes public subtitle metadata and
whether a local `BILIBILI_COOKIE` is present. The probe does not return cookie
values and does not write transcript records.

If Bilibili subtitles are unavailable, the user can paste transcript text into
the frontdesk. `manual_transcript_import` splits that user-provided text into
local `TRANSCRIPT_SEGMENT` records for the selected lecture. This is an explicit
manual source path, not ASR and not a fallback to a private import pipeline.

Some Bilibili subtitle metadata is visible only to an authenticated browser
session. Public Lite never stores credentials in the repository. If a course
requires authenticated subtitles, use one of these local-only routes:

- scan the QR code in the Web import panel;
- paste a browser cookie for the current import;
- choose remember-cookie storage, which writes only to
  `.codex/auth/bilibili.json` on the local machine;
- or set `BILIBILI_COOKIE` in the local runtime environment.

APIs and evidence logs must not echo cookie values. They may record sanitized
signals such as `cookie_present`, `auth_source`, or cookie names.

## Readiness And Promotion

Full imports write into a temporary SQLite store first. Promotion to the local
production store is guarded:

- a new ready course is merged as an additional course;
- a same-course reimport replaces only that course when the candidate is not
  worse than the existing course;
- candidates with missing transcripts, notes, atoms, or gates are blocked;
- `max_lectures` probe imports do not auto-promote.

The status card should distinguish a failed import from a successful temporary
import that was intentionally blocked by promotion protection.

## Notes And Atoms

Transcript-backed imports generate Chinese lecture notes, knowledge atoms,
review gates, and optional visual-keyframe artifacts when media is available.
When model credentials are absent, the deterministic fallback remains honest
about being a fallback and should not be described as full model-quality parity.

This is still child-local course ingestion. It does not write private Learning
OS planning, mastery, diagnosis, exercise-review, queue-completion, or feedback
state.
