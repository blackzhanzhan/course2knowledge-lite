from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "sync_hermes_lite_profile.py"
SMOKE_SCRIPT_PATH = ROOT / "scripts" / "smoke_hermes_lite_profile.py"
TEMPLATE_ROOT = ROOT / "hermes" / "profile-template"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_hermes_lite_profile", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load sync_hermes_lite_profile.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("smoke_hermes_lite_profile", SMOKE_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load smoke_hermes_lite_profile.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HermesLiteProfileTests(unittest.TestCase):
    def test_profile_template_is_public_lite_only(self) -> None:
        combined = "\n".join(
            [
                (TEMPLATE_ROOT / "SOUL.md").read_text(encoding="utf-8"),
                (TEMPLATE_ROOT / "workspace" / "AGENTS.md").read_text(encoding="utf-8"),
                (TEMPLATE_ROOT / "config.overlay.yaml").read_text(encoding="utf-8"),
            ]
        )
        self.assertIn("course2knowledge-lite", combined)
        self.assertIn("collection_import_start", combined)
        self.assertIn("course_transcript_coverage_get", combined)
        self.assertIn("knowledge_cards_generate", combined)
        self.assertIn("course_visual_evidence_send", combined)
        self.assertIn("learning_guide_get", combined)
        self.assertIn("api_server", combined)
        self.assertIn("MULTI-QUESTION HARD RULE", combined)
        self.assertIn("BATCH: received multiple questions; answering in order.", combined)
        self.assertIn("收到多条快速问题，我会按收到顺序逐条回答。", combined)
        blocked_terms = [
            "learning" + "-os-importer",
            "practice" + "_recap",
            "mastery" + "_level",
            "review" + "_stage",
            "queue" + "_item_complete",
            "DASHSCOPE" + "_API_KEY",
            "BILIBILI" + "_COOKIE=",
            "OPENAI" + "_API_KEY=",
            "SQUAREAPI" + "_API_KEY",
        ]
        for term in blocked_terms:
            self.assertNotIn(term, combined)

    def test_sync_profile_writes_template_plugin_and_metadata_without_secrets(self) -> None:
        sync_module = load_sync_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            report = sync_module.sync_profile(
                profile_root=temp_dir,
                apply=True,
                create_profile=True,
                provider="local-provider",
                model="local-model",
                base_url="https://example.invalid/v1",
                key_env="COURSE2KNOWLEDGE_TEST_KEY",
            )
            target = Path(temp_dir)
            self.assertEqual(report["status"], "applied")
            self.assertFalse(report["writes_secret_values"])
            self.assertTrue((target / "SOUL.md").exists())
            self.assertTrue((target / "workspace" / "AGENTS.md").exists())
            self.assertTrue((target / "config.yaml").exists())
            self.assertTrue((target / "plugins" / "course2knowledge-lite" / "__init__.py").exists())
            metadata = json.loads(
                (target / "plugins" / "course2knowledge-lite" / "course2knowledge_lite_repo_root.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(Path(metadata["repo_root"]).resolve(), ROOT.resolve())
            config_text = (target / "config.yaml").read_text(encoding="utf-8")
            self.assertIn("course2knowledge-lite", config_text)
            self.assertIn("api_server:", config_text)
            self.assertIn("host: 127.0.0.1", config_text)
            self.assertIn("port: 8642", config_text)
            self.assertIn('model_name: "course2knowledge-lite"', config_text)
            self.assertIn("COURSE2KNOWLEDGE_TEST_KEY", config_text)
            self.assertIn("api_mode: chat_completions", config_text)
            self.assertIn("transport: chat_completions", config_text)
            self.assertFalse((target / ".env").exists())
            self.assertIn("knowledge_cards_generate", report["enabled_tools"])

    def test_sync_profile_can_explicitly_write_responses_wire_api(self) -> None:
        sync_module = load_sync_module()
        config = sync_module.build_config(
            provider="responses-provider",
            model="responses-model",
            base_url="https://example.invalid/v1",
            key_env="RESPONSES_TEST_KEY",
            wire_api="responses",
        )

        provider_config = config["providers"]["responses-provider"]
        self.assertEqual(provider_config["api_mode"], "codex_responses")
        self.assertEqual(provider_config["transport"], "codex_responses")

    def test_synced_profile_plugin_registers_tools_from_profile_copy(self) -> None:
        sync_module = load_sync_module()
        smoke_module = load_smoke_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            sync_module.sync_profile(
                profile_root=temp_dir,
                apply=True,
                create_profile=True,
                provider="local-provider",
                model="local-model",
                base_url="https://example.invalid/v1",
                key_env="COURSE2KNOWLEDGE_TEST_KEY",
            )
            report = smoke_module.smoke_profile(temp_dir)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["toolset"], "course2knowledge-lite")
        self.assertEqual(
            report["registered_tools"],
            [
                "bookmark_create",
                "bookmark_delete",
                "bookmark_list",
                "collection_import_start",
                "course_question_answer",
                "course_search",
                "course_transcript_coverage_get",
                "course_visual_evidence_send",
                "import_status_get",
                "knowledge_card_get",
                "knowledge_card_list",
                "knowledge_cards_generate",
                "learning_guide_get",
                "lecture_reader_get",
                "lecture_transcript_import",
                "lecture_transcript_import_by_ref",
                "lecture_transcript_source_probe",
                "manual_transcript_import",
                "note_create",
                "note_delete",
                "note_list",
                "note_update",
                "reading_progress_get",
                "reading_progress_set",
                "studio_office_teaching_route",
            ],
        )
        self.assertEqual(report["sample_tool_status"], "completed")
        self.assertEqual(report["sample_import_stage"], "collection_expanded")
        self.assertEqual(report["sample_qa_status"], "answered")
        self.assertEqual(report["sample_qa_citation_count"], 1)
        self.assertEqual(report["sample_card_count"], 1)
        self.assertEqual(report["sample_generated_card_count"], 1)
        self.assertEqual(report["sample_guide_status"], "completed")
        self.assertEqual(report["sample_guide_mode"], "self_check")
        self.assertEqual(report["sample_guide_question_count"], 1)
        self.assertEqual(report["sample_visual_status"], "completed")
        self.assertEqual(report["sample_visual_media_count"], 1)
        self.assertEqual(report["sample_note_status"], "completed")
        self.assertEqual(report["sample_progress_status"], "read")


if __name__ == "__main__":
    unittest.main()
