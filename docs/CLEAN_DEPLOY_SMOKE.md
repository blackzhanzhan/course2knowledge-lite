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

```text
scripts/Course2KnowledgeLiteSandbox.wsb
```

The WSB file maps this public child repo read-only into the sandbox and runs the
same PowerShell smoke script.

## Current Windows Carrier Status

On the current machine, pure Windows execution is not yet proven because the
available carriers are disabled or absent:

- Windows Sandbox feature: disabled
- Hyper-V feature: disabled
- VirtualBox/VMware/QEMU commands: absent
- Docker Desktop: present, but running Linux containers, which does not satisfy
  pure Windows deployment proof
