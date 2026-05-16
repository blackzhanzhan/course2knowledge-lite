# Feishu Lite App

Public Feishu/Hermes chat entry for Bilibili import, status, course lookup, and
course-content Q&A.

Current native tool surface:

- `collection_import_start` starts a Bilibili collection import into the local
  SQLite course store.
- `import_status_get` reads a local import status record.
- `lecture_transcript_import` imports one lecture's available Bilibili subtitles
  as transcript segments.

This is a Hermes-native tool boundary. The public app should call tools through
Hermes instead of asking an agent to run scripts.

Recommended setup:

```bash
course2knowledge-lite sync-profile --apply --create-profile
```
