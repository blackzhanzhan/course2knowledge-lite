# Deployment

Course2Knowledge Lite is designed to be deployed in the simplest possible way:
install the package, run the Web workspace, and sync the public Hermes profile.

## Recommended Path

1. Install Python 3.11 or newer.
2. From the repository root, install the package. Editable install is best for
   development:

```bash
pip install -e .
```

For release verification, use a non-editable install in a fresh environment:

```bash
python -m venv .venv-release
.venv-release/Scripts/python -m pip install .
```

3. Confirm the CLI is available:

```bash
course2knowledge-lite --help
```

4. Start the Web Lite workspace:

```bash
course2knowledge-lite web
```

The default URL is:

```text
http://127.0.0.1:3014/
```

The default local store root is `data/course-store/`. For a clean deployment
smoke, use a temporary store:

```bash
course2knowledge-lite web --store-root tmp/release-web-store
```

5. Sync the public Hermes profile:

```bash
course2knowledge-lite sync-profile --apply --create-profile
```

6. Run the Hermes profile smoke test:

```bash
course2knowledge-lite smoke-profile --profile-root <profile-root>
```

The smoke test registers the synced Hermes plugin and verifies import status,
Q&A, knowledge cards, `learning_guide_get`, visual evidence media replies,
notes, and reading progress against a temporary public course store.

## Bilibili Login State

Some Bilibili subtitles require a logged-in browser session. The Web import
panel supports:

- QR login through Bilibili's login flow.
- Manual cookie paste for a single import.
- Optional local remember-cookie storage under `.codex/auth/bilibili.json`.

The auth file is ignored by git. Do not commit it, copy it into docs, or paste
its values into issue reports. Status APIs expose only sanitized metadata such
as whether a cookie exists and which cookie names are present.

## Import Promotion Semantics

Imports first run against a temporary store and then pass a readiness gate before
production SQLite changes:

- distinct ready new course: merge that course into the production store;
- same-course reimport: replace only that course when readiness is not worse;
- lower-quality candidate: block promotion and keep existing data;
- `max_lectures` probe subset: keep it as a probe and do not auto-promote.

This keeps a one-lecture test import or a no-subtitle failure from overwriting a
real course.

## Model And Concurrency Notes

The lecture dossier compiler can use the deterministic fallback path or a model
provider. For DeepSeek-compatible model generation, set:

```bash
set COURSE2KNOWLEDGE_LITE_DOSSIER_API_KEY=...
```

or, for the DeepSeek default, `DEEPSEEK_API_KEY`. The importer emits a
`parallelism_resolved` event for large courses so release checks can confirm the
effective lecture and dossier concurrency profile without inspecting secrets.

## Deployment Modes

- Local single-machine deployment: the default and recommended mode.
- Editable source deployment: useful for development and iteration.
- Packaged install deployment: the intended public experience once packaging is
  published.
- GitHub Pages showcase: serve the static public site from `docs/`.

## GitHub Pages Showcase

The static product site requires no build step.

Recommended repository setting:

1. Open GitHub repository settings.
2. Go to Pages.
3. Set source to `Deploy from a branch`.
4. Set branch to `main`.
5. Set folder to `/docs`.

The entry page is:

```text
docs/index.html
```

The showcase screenshots in `docs/assets/demos/` were captured from real Web
Lite, API/store, and Hermes profile-smoke runs against the public demo course
store. They are static documentation assets, not runtime data.

## What Deployment Does Not Require

- Docker.
- Kubernetes.
- A remote backend.
- Private runtime files.
- Private production credentials or sessions.

## Release Precheck

Before tagging a release candidate, run:

```bash
python -m unittest tests.test_deployment
python -m unittest discover -s tests
python -m pip wheel . -w tmp/release-precheck/wheelhouse --no-deps
node --check apps/web/static/app.js
git diff --check
```

Then run the path and sensitive scans described in `docs/TESTING.md`. Test
fixtures may contain fake cookie names or sentinel values; real cookie values,
API keys, and machine-specific workspace paths must not appear in committed
release files.

## Notes

- The Web workspace reads the local course store only.
- Hermes profile sync copies the public profile template and plugin only.
- Use the profile path printed by `sync-profile` as `<profile-root>`.
- Windows Sandbox smoke uses a generated `.wsb` file under `tmp/`; the committed
  placeholder intentionally contains no host path.
