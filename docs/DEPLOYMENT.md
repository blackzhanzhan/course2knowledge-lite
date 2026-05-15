# Deployment

Course2Knowledge Lite is designed to be deployed in the simplest possible way:
install the package, run the Web workspace, and sync the public Hermes profile.

## Recommended Path

1. Install Python 3.11 or newer.
2. From the repository root, install the package in editable mode:

```bash
pip install -e .
```

3. Confirm the CLI is available:

```bash
course2knowledge-lite --help
```

4. Start the Web Lite workspace:

```bash
course2knowledge-lite web
```

5. Sync the public Hermes profile:

```bash
course2knowledge-lite sync-profile --apply --create-profile
```

6. Run the Hermes profile smoke test:

```bash
course2knowledge-lite smoke-profile --profile-root <profile-root>
```

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

## Notes

- The Web workspace reads the local course store only.
- Hermes profile sync copies the public profile template and plugin only.
- Use the profile path printed by `sync-profile` as `<profile-root>`.
