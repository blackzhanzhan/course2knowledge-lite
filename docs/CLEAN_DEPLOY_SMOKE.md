# Clean Deployment Smoke

This checklist verifies the public child project outside the current editable
development environment.

## WSL / Linux

Use a clean WSL or Linux shell with Python 3.11+:

```bash
python3 -m venv /tmp/course2knowledge-lite-smoke/venv
/tmp/course2knowledge-lite-smoke/venv/bin/python -m pip install .
/tmp/course2knowledge-lite-smoke/venv/bin/course2knowledge-lite --version
```

The current verified WSL evidence is stored under ignored runtime artifacts:

- `tmp/deploy-smoke-wsl/20260516-0128/wsl-run-artifacts/wsl-summary.json`
- `tmp/deploy-smoke-wsl/20260516-0128/wsl-run-artifacts/smoke-report.json`

## Pure Windows

For Windows Sandbox or a clean Windows VM, run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\deploy_smoke_windows.ps1
```

The script performs:

- non-editable `pip install .`
- `course2knowledge-lite --version`
- temporary Hermes profile sync
- Hermes profile smoke test
- Web startup and `/api/courses` check

If Windows Sandbox is enabled, open:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\run_sandbox_smoke.ps1
```

The runner opens `scripts/Course2KnowledgeLiteSandbox.wsb`, maps this public
child repo read-only into the sandbox, and polls
`tmp/deploy-smoke-windows/sandbox-output/latest/windows-summary.json`.
When the summary is detected, the Sandbox window is intentionally left open.
Close it manually with the window close button after the runner reports success.

Do not force-kill `WindowsSandbox.exe` or `vmwp.exe` while a smoke run is active.
That closes the host-to-sandbox remote session abruptly and Windows shows
`0x80072746` disconnect dialogs even when the project smoke itself has already
written a passing summary. Guest-side automatic shutdown can produce the same
disconnect dialog in Windows Sandbox, so the default smoke flow keeps the window
open and requires a normal manual close. If a Sandbox window is still open, close
it normally before starting another run. The runner refuses to start when an
existing Sandbox session is detected.

## Current Windows Evidence

The current verified Windows Sandbox evidence is stored under ignored runtime
artifacts:

- `tmp/deploy-smoke-windows/sandbox-output/latest/windows-summary.json`
- `tmp/deploy-smoke-windows/sandbox-output/latest/interaction-report.json`
