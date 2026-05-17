# Hermes Lite Profile

This directory contains a public Hermes profile template for Course2Knowledge
Lite.

It must not contain production credentials, protected orchestration files, or
protected production evidence.

## Plugin

`plugins/course2knowledge-lite/` is the public Hermes-native tool surface. It
registers only Lite tools that call the shared Lite Chat Core where Web and
Hermes chat behavior overlaps, plus public package APIs and the child-local
SQLite course store.

Current tools:

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

These tools are package API wrappers, not shell-script entrypoints. A real
Feishu/Lark frontdesk profile can call them through Hermes after profile setup.

## Profile Template

`profile-template/` contains public `SOUL.md`, `workspace/AGENTS.md`, and
`config.overlay.yaml` files. They enable only the `course2knowledge-lite`
toolset and do not contain production credentials.

Use `scripts/sync_hermes_lite_profile.py` to copy the template and plugin into a
local Hermes profile. The script may read model endpoint settings from Codex
config when `--use-codex-config` is passed, but it never writes secret values to
the repository.

For package-style setup, the top-level CLI also exposes:

```bash
course2knowledge-lite sync-profile --apply --create-profile
course2knowledge-lite smoke-profile --profile-root %USERPROFILE%\\.hermes\\profiles\\course2knowledge-lite
```
