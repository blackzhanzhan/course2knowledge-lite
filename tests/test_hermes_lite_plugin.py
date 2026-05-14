from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "hermes" / "plugins" / "course2knowledge-lite"


class FakeHermesContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, object]] = {}

    def register_tool(self, **kwargs) -> None:
        self.tools[str(kwargs["name"])] = dict(kwargs)


def load_plugin_module():
    module_name = "course2knowledge_lite_hermes_plugin"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Hermes Lite plugin module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def manifest_tool_names() -> list[str]:
    lines = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8").splitlines()
    names: list[str] = []
    in_tools = False
    for line in lines:
        stripped = line.strip()
        if stripped == "provides_tools:":
            in_tools = True
            continue
        if in_tools and stripped.startswith("- "):
            names.append(stripped[2:].strip())
    return names


class HermesLitePluginTests(unittest.TestCase):
    def test_plugin_registers_manifest_tools(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()

        module.register(ctx)

        self.assertEqual(sorted(ctx.tools), sorted(manifest_tool_names()))
        for tool_name, payload in ctx.tools.items():
            self.assertEqual(payload["toolset"], "course2knowledge-lite")
            self.assertIn("handler", payload)
            self.assertEqual(payload["schema"]["name"], tool_name)


if __name__ == "__main__":
    unittest.main()
