# Hermes Lite Profile

This directory contains a public Hermes profile template for Course2Knowledge
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

## Profile Template

`profile-template/` contains public `SOUL.md`, `workspace/AGENTS.md`, and
`config.overlay.yaml` files. They enable only the `course2knowledge-lite`
toolset and do not contain production credentials.

Use `scripts/sync_hermes_lite_profile.py` to copy the template and plugin into a
local Hermes profile. The script may read model endpoint settings from Codex
config when `--use-codex-config` is passed, but it never writes secret values to
the repository.
