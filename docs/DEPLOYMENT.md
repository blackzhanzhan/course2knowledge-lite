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
course2knowledge-lite smoke-profile --profile-root %USERPROFILE%\\.hermes\\profiles\\course2knowledge-lite
```

## Deployment Modes

- Local single-machine deployment: the default and recommended mode.
- Editable source deployment: useful for development and iteration.
- Packaged install deployment: the intended public experience once packaging is
  published.

## What Deployment Does Not Require

- Docker.
- Kubernetes.
- A remote backend.
- Private Learning OS runtime files.
- Private production credentials or sessions.

## Notes

- The Web workspace reads the local course store only.
- Hermes profile sync copies the public profile template and plugin only.
- If you are on Windows PowerShell, replace `%USERPROFILE%` with `$env:USERPROFILE`.
