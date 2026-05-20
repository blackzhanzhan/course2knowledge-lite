from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="course2knowledge-lite", description="Course2Knowledge Lite CLI")
    subparsers = parser.add_subparsers(dest="command")

    web = subparsers.add_parser("web", help="Run the Web Lite workspace")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=3014)
    web.add_argument("--store-root", default=str(_repo_root() / "data" / "course-store"))

    sync = subparsers.add_parser("sync-profile", help="Sync the public Hermes Lite profile")
    sync.add_argument("--profile", default="course2knowledge-lite")
    sync.add_argument("--profile-root", default="")
    sync.add_argument("--apply", action="store_true")
    sync.add_argument("--create-profile", action="store_true")
    sync.add_argument("--use-codex-config", action="store_true")
    sync.add_argument("--provider", default="")
    sync.add_argument("--model", default="")
    sync.add_argument("--base-url", default="")
    sync.add_argument("--key-env", default="OPENAI_API_KEY")
    sync.add_argument("--output", default="")

    smoke = subparsers.add_parser("smoke-profile", help="Smoke-test a synced Hermes Lite profile")
    smoke.add_argument("--profile-root", required=True)
    smoke.add_argument("--output", default="")

    interaction = subparsers.add_parser("interaction-smoke", help="Run a Web + Hermes Lite interaction smoke")
    interaction.add_argument("--repo-root", default="")
    interaction.add_argument("--store-root", required=True)
    interaction.add_argument("--profile-root", required=True)
    interaction.add_argument("--output", default="")
    interaction.add_argument("--port", type=int, default=3191)

    parser.add_argument("--version", action="version", version="course2knowledge-lite 0.1.0")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "web":
        from public_release.course2knowledge_lite_apps_web_server import main as web_main

        return web_main(["--host", args.host, "--port", str(args.port), "--store-root", args.store_root])
    if args.command == "sync-profile":
        from public_release.course2knowledge_lite_sync_hermes_profile import sync_profile

        report = sync_profile(
            profile=str(args.profile),
            profile_root=str(args.profile_root),
            apply=bool(args.apply),
            create_profile=bool(args.create_profile),
            use_codex_config=bool(args.use_codex_config),
            provider=str(args.provider),
            model=str(args.model),
            base_url=str(args.base_url),
            key_env=str(args.key_env),
        )
        if str(args.output or "").strip():
            Path(args.output).expanduser().resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_json(report)
        return 0
    if args.command == "smoke-profile":
        from public_release.course2knowledge_lite_smoke_hermes_profile import smoke_profile

        report = smoke_profile(args.profile_root)
        if str(args.output or "").strip():
            Path(args.output).expanduser().resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_json(report)
        return 0
    if args.command == "interaction-smoke":
        from public_release.course2knowledge_lite_deploy_interaction_smoke import run_interaction_smoke

        report = run_interaction_smoke(
            repo_root=str(args.repo_root or _repo_root()),
            store_root=str(args.store_root),
            profile_root=str(args.profile_root),
            output=str(args.output),
            port=int(args.port),
        )
        _print_json(report)
        return 0

    parser.print_help()
    return 0
