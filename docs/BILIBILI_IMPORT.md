# Bilibili Import

Bilibili import is the retained real platform adapter for Course2Knowledge Lite.

## Responsibilities

- Validate Bilibili URLs.
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
