# Testing

## Boundary Tests

The public repository should keep tests that prove private behavior has not
leaked into the Lite product.

Recommended scans:

```bash
rg -n "exam-prep|official-account|protected production export|private learning loop" .
```

## Product Tests

Current acceptance commands:

```bash
python -m unittest discover -s tests
python -m unittest tests.test_web_lite tests.test_course_store_skeleton tests.test_hermes_lite_plugin tests.test_hermes_lite_profile
git diff --check
```

The LDC-4 public case also verifies the running Web app at
`http://127.0.0.1:3014/` and the Hermes Lite `course_visual_evidence_send` tool
against the child-local public store.

Product tests cover:

- Bilibili URL validation tests.
- Transcript normalization tests.
- Course store CRUD tests.
- Citation retrieval tests.
- Q&A answer and missing-evidence tests.
- Hermes Lite tool registration, reader, search, Q&A, and visual-evidence
  handler tests.
- Hermes Lite public profile template and sync tests.
- Hermes Lite synced-profile smoke tests.
- Web build tests.
- Feishu Lite command tests.

## Acceptance Rule

Public tests should prove Course2Knowledge Lite works as an interactive course
knowledge product, not as a closed-loop learning coach.
