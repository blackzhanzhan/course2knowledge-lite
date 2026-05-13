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

## Transcript Segment Handoff

For a single lecture video URL, the importer can fetch available Bilibili
subtitles and write timestamped `TRANSCRIPT_SEGMENT` records to the local course
store.

Some Bilibili subtitle metadata is visible only to an authenticated browser
session. Public Lite never stores credentials in the repository. If a course
requires authenticated subtitles, set `BILIBILI_COOKIE` in the local runtime
environment and rerun the import.

This is still source ingestion only. It does not generate lecture notes,
knowledge cards, Q&A answers, review items, or learning feedback.
