#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "hermes" / "profile-template"
PLUGIN_ROOT = REPO_ROOT / "hermes" / "plugins"
PLUGIN_NAME = "course2knowledge-lite"
METADATA_FILE = "course2knowledge_lite_repo_root.json"
DEFAULT_PROFILE = "course2knowledge-lite"
ENABLED_TOOLS = [
    "studio_office_teaching_route",
    "collection_import_start",
    "import_status_get",
    "lecture_transcript_import",
    "lecture_transcript_import_by_ref",
    "lecture_transcript_source_probe",
    "manual_transcript_import",
    "course_transcript_coverage_get",
    "knowledge_cards_generate",
    "knowledge_card_list",
    "knowledge_card_get",
    "course_visual_evidence_send",
    "lecture_reader_get",
    "learning_guide_get",
    "course_search",
    "course_question_answer",
    "note_create",
    "note_list",
    "note_update",
    "note_delete",
    "bookmark_create",
    "bookmark_list",
    "bookmark_delete",
    "reading_progress_set",
    "reading_progress_get",
]


BASE_CONFIG: dict[str, Any] = {
    "agent": {"reasoning_effort": "low", "verbose": False},
    "platform_toolsets": {"feishu": [PLUGIN_NAME], "api_server": [PLUGIN_NAME]},
    "plugins": {"enabled": [PLUGIN_NAME]},
    "platforms": {
        "feishu": {
            "enabled": True,
            "extra": {
                "domain": "feishu",
                "connection_mode": "websocket",
                "media_batch_delay_seconds": 2.5,
                "text_batch_delay_seconds": 0.6,
            },
        }
    },
    "display": {
        "tool_progress": "all",
        "interim_assistant_messages": True,
        "background_process_notifications": "all",
        "busy_input_mode": "queue",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync the public Course2Knowledge Lite Hermes profile.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-root", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--create-profile", action="store_true")
    parser.add_argument("--use-codex-config", action="store_true")
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--key-env", default="OPENAI_API_KEY")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def _profile_root(profile: str, explicit_root: str = "") -> Path:
    if explicit_root.strip():
        return Path(explicit_root).expanduser().resolve()
    return Path.home() / ".hermes" / "profiles" / str(profile or DEFAULT_PROFILE).strip()


def _copy_tree_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        destination = target / child.name
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text or any(char in text for char in ":#{}[],&*?|-<>=!%@`"):
        return json.dumps(text)
    return text


def _dump_yaml(payload: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_dump_yaml(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    lines.append(_dump_yaml(item, indent + 4))
                else:
                    lines.append(f"{prefix}  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return "\n".join(line for line in lines if line != "") + "\n"


def _transport_for_wire_api(wire_api: str) -> str:
    cleaned = str(wire_api or "").strip()
    if cleaned == "responses":
        return "codex_responses"
    return cleaned or "codex_responses"


def _explicit_model_config(
    *,
    provider: str,
    model: str,
    base_url: str,
    key_env: str,
    wire_api: str = "responses",
) -> dict[str, Any]:
    provider = provider.strip()
    model = model.strip()
    base_url = base_url.strip()
    key_env = key_env.strip() or "OPENAI_API_KEY"
    if not provider and not model and not base_url:
        return {}
    if not provider or not model or not base_url:
        raise RuntimeError("--provider, --model, and --base-url must be supplied together")
    transport = _transport_for_wire_api(wire_api)
    return {
        "model": {"default": model, "provider": provider},
        "providers": {
            provider: {
                "name": provider,
                "api": base_url,
                "key_env": key_env,
                "default_model": model,
                "api_mode": transport,
                "transport": transport,
            }
        },
    }


def _codex_model_config(*, key_env: str) -> dict[str, Any]:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists():
        raise RuntimeError(f"Codex config is missing: {config_path}")
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    provider = str(payload.get("model_provider") or "").strip()
    model = str(payload.get("model") or "").strip()
    provider_payload = (payload.get("model_providers") or {}).get(provider) or {}
    base_url = str(provider_payload.get("base_url") or "").strip()
    wire_api = str(provider_payload.get("wire_api") or "").strip()
    if not provider or not model or not base_url:
        raise RuntimeError("Codex config must define model_provider, model, and provider base_url")
    return _explicit_model_config(
        provider=provider,
        model=model,
        base_url=base_url,
        key_env=key_env,
        wire_api=wire_api,
    )


def _merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _write_plugin_metadata(plugin_dir: Path) -> Path:
    metadata_path = plugin_dir / METADATA_FILE
    metadata_path.write_text(
        json.dumps(
            {
                "repo_root": str(REPO_ROOT),
                "plugin": PLUGIN_NAME,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return metadata_path


def build_config(
    *,
    use_codex_config: bool = False,
    provider: str = "",
    model: str = "",
    base_url: str = "",
    key_env: str = "OPENAI_API_KEY",
) -> dict[str, Any]:
    if use_codex_config:
        model_config = _codex_model_config(key_env=key_env)
    else:
        model_config = _explicit_model_config(
            provider=provider,
            model=model,
            base_url=base_url,
            key_env=key_env,
        )
    return _merge_dict(dict(BASE_CONFIG), model_config)


def sync_profile(
    *,
    profile: str = DEFAULT_PROFILE,
    profile_root: str = "",
    apply: bool = False,
    create_profile: bool = False,
    use_codex_config: bool = False,
    provider: str = "",
    model: str = "",
    base_url: str = "",
    key_env: str = "OPENAI_API_KEY",
) -> dict[str, Any]:
    target_root = _profile_root(profile, profile_root)
    config = build_config(
        use_codex_config=use_codex_config,
        provider=provider,
        model=model,
        base_url=base_url,
        key_env=key_env,
    )
    report: dict[str, Any] = {
        "profile": profile,
        "profile_root": str(target_root),
        "apply": apply,
        "create_profile": create_profile,
        "template_root": str(TEMPLATE_ROOT),
        "plugin_source_root": str(PLUGIN_ROOT / PLUGIN_NAME),
        "plugin_target_root": str(target_root / "plugins" / PLUGIN_NAME),
        "config_target": str(target_root / "config.yaml"),
        "toolset": PLUGIN_NAME,
        "enabled_tools": ENABLED_TOOLS,
        "writes_secret_values": False,
        "uses_codex_config": use_codex_config,
        "status": "dry_run",
    }
    if not apply:
        return report

    if not target_root.exists():
        if not create_profile:
            raise RuntimeError(f"Hermes profile is missing: {target_root}")
        target_root.mkdir(parents=True, exist_ok=True)

    (target_root / "workspace").mkdir(parents=True, exist_ok=True)
    (target_root / "SOUL.md").write_text(
        (TEMPLATE_ROOT / "SOUL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target_root / "workspace" / "AGENTS.md").write_text(
        (TEMPLATE_ROOT / "workspace" / "AGENTS.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target_root / "config.yaml").write_text(_dump_yaml(config), encoding="utf-8")
    plugin_target = target_root / "plugins" / PLUGIN_NAME
    _copy_tree_contents(PLUGIN_ROOT / PLUGIN_NAME, plugin_target)
    metadata_path = _write_plugin_metadata(plugin_target)
    report["plugin_metadata"] = str(metadata_path)
    report["status"] = "applied"
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
        output_path = Path(str(args.output)).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
