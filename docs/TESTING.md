# Testing

## Boundary Tests

The public repository should keep tests that prove private behavior has not
leaked into the Lite product.

Recommended scans:

```bash
rg -n "exam-prep|official-account|protected production export|private learning loop" .
```

## Product Tests

Future implementation slices should add:

- Bilibili URL validation tests.
- Transcript normalization tests.
- Course store CRUD tests.
- Citation retrieval tests.
- Q&A missing-evidence tests.
- Hermes Lite tool registration and handler tests.
- Hermes Lite public profile template and sync tests.
- Hermes Lite synced-profile smoke tests.
- Web build tests.
- Feishu Lite command tests.

## Acceptance Rule

Public tests should prove Course2Knowledge Lite works as an interactive course
knowledge product, not as a closed-loop learning coach.
