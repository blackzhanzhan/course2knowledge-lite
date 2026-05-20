from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def test_sandbox_runner_generates_portable_config_without_committed_host_paths(self) -> None:
        runner = ROOT / "scripts" / "run_sandbox_smoke.ps1"
        placeholder = ROOT / "scripts" / "Course2KnowledgeLiteSandbox.wsb"
        runner_text = runner.read_text(encoding="utf-8")
        placeholder_text = placeholder.read_text(encoding="utf-8")

        self.assertIn("New-Course2KnowledgeLiteSandboxConfig", runner_text)
        self.assertIn("$GeneratedSandboxConfig", runner_text)
        self.assertIn("-ResolvedRepoRoot $RepoRoot", runner_text)
        self.assertIn("portable placeholder", placeholder_text)

        committed = placeholder_text
        self.assertNotIn(str(ROOT), committed)
        self.assertNotRegex(committed, r"[A-Z]:\\[^<\n]*learning_os[^<\n]*course2knowledge-lite")

    def test_cli_help_exposes_deployment_entrypoints(self) -> None:
        result = _run_installed_command(ROOT, ["--help"])
        self.assertIn("sync-profile", result.stdout)
        self.assertIn("smoke-profile", result.stdout)
        self.assertIn("web", result.stdout)

    def test_profile_sync_and_smoke_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_root = Path(temp_dir) / "profile"
            sync_output = Path(temp_dir) / "sync.json"
            smoke_output = Path(temp_dir) / "smoke.json"

            sync_result = _run_installed_command(
                ROOT,
                [
                    "sync-profile",
                    "--apply",
                    "--create-profile",
                    "--profile-root",
                    str(profile_root),
                    "--output",
                    str(sync_output),
                ],
            )
            smoke_result = _run_installed_command(
                ROOT,
                [
                    "smoke-profile",
                    "--profile-root",
                    str(profile_root),
                    "--output",
                    str(smoke_output),
                ],
            )

            sync_payload = json.loads(sync_output.read_text(encoding="utf-8"))
            smoke_payload = json.loads(smoke_output.read_text(encoding="utf-8"))

        self.assertEqual(sync_payload["status"], "applied")
        self.assertEqual(smoke_payload["status"], "passed")
        self.assertEqual(smoke_payload["toolset"], "course2knowledge-lite")
        self.assertIn("knowledge_cards_generate", sync_payload["enabled_tools"])
        self.assertIn("sample_qa_status", smoke_payload)
        self.assertIn("sample_progress_status", smoke_payload)
        self.assertIn("course2knowledge-lite", sync_result.stdout)
        self.assertIn("course2knowledge-lite", smoke_result.stdout)


def _run_installed_command(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_root = Path(temp_dir) / "venv"
        python_exe = _venv_python(venv_root)
        subprocess.run([sys.executable, "-m", "venv", str(venv_root)], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run([str(python_exe), "-m", "pip", "install", str(repo_root)], cwd=repo_root, check=True, capture_output=True, text=True)
        return subprocess.run(
            [str(_venv_script(venv_root)), *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONUTF8": "1"},
        )


def _venv_python(venv_root: Path) -> Path:
    return venv_root / "Scripts" / "python.exe"


def _venv_script(venv_root: Path) -> Path:
    return venv_root / "Scripts" / "course2knowledge-lite.exe"
