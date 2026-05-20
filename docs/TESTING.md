# Testing

## Boundary Tests

The public repository should keep tests that prove private behavior has not
leaked into the Lite product.

Recommended scans:

```bash
rg -n "exam-prep|official-account|protected production export|private learning loop" .
```

Release-sensitive scans should also check for local host paths and credential
material while excluding ignored runtime output:

```bash
rg -n --hidden -g '!**/.git/**' -g '!tmp/**' -g '!data/**' \
  "C:\\\\Users\\\\|C:/Users/|C:\\\\csptr|C:/csptr|SESSDATA|bili_jct|DedeUserID|OPENAI_API_KEY|DEEPSEEK_API_KEY|sk-[A-Za-z0-9_-]{20,}" .
```

Expected allowed hits include placeholder UI text, environment-variable names,
and fake test fixtures such as `SESSDATA=secret-session`. Real cookie values,
API keys, private workspace paths, and production chat identifiers are release
blockers.

## Product Tests

Current acceptance commands:

```bash
python -m unittest discover -s tests
python -m unittest tests.test_guidance tests.test_web_lite tests.test_course_store_skeleton tests.test_hermes_lite_plugin tests.test_hermes_lite_profile
python -m unittest tests.test_deployment
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps
node --check apps/web/static/app.js
git diff --check
```

The LDC-4 public case also verifies the running Web app at
`http://127.0.0.1:3014/`, the Web guided-learning panel, and the Hermes Lite
`learning_guide_get` / `course_visual_evidence_send` tools against the
child-local public store.

Product tests cover:

- Bilibili URL validation tests.
- Transcript normalization tests.
- Course store CRUD tests.
- Citation retrieval tests.
- Q&A answer and missing-evidence tests.
- Guided learning derivation tests for continue-learning, lecture walkthrough,
  self-check, and recap modes.
- Hermes Lite tool registration, reader, guided learning, search, Q&A, and
  visual-evidence handler tests.
- Hermes Lite public profile template and sync tests.
- Hermes Lite synced-profile smoke tests.
- Web build tests.
- Feishu Lite command tests.
- Deployment smoke tests that install the package in a fresh virtual
  environment, sync the public Hermes profile, and run the profile smoke.
- Portable Windows Sandbox runner checks that committed files do not contain
  host-specific workspace paths.

## Acceptance Rule

Public tests should prove Course2Knowledge Lite works as an interactive course
knowledge product with public guided learning, not as a closed-loop learning
coach.

Guided learning acceptance must prove that the feature is a read-only organizer
over course evidence. It may recommend what lecture to inspect next, outline one
lecture, and ask self-check questions with citations. It must not create day
plans, schedules, mastery scores, diagnoses, spaced-review queues, or exercise
feedback.
