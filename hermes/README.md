# Hermes Lite Profile

This directory will contain a public Hermes profile template for Course2Knowledge
Lite.

It must not contain production credentials, protected orchestration files, or
protected production evidence.

## Plugin

`plugins/course2knowledge-lite/` is the public Hermes-native tool surface. It
registers only Lite tools that call public package APIs and a local JSON course
store.

Current tools:

- `collection_import_start`
- `import_status_get`
- `lecture_transcript_import`

These tools are package API wrappers, not shell-script entrypoints. A real
Feishu/Lark frontdesk profile can call them through Hermes after profile setup.
