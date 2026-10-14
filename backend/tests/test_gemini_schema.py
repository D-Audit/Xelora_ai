"""Every tool schema must survive Gemini's stricter function-schema parser.

The Cua Driver's MCP tools use nullable ``"type": [..., "null"]`` fields; one
such schema made a whole Gemini turn fail with "'list' object has no
attribute 'upper'".
"""
from __future__ import annotations

import importlib.util
import unittest


def _has_google_genai() -> bool:
    try:
        return importlib.util.find_spec("google.genai") is not None
    except (ModuleNotFoundError, ValueError):
        return False

from agent.providers import _strip_unsupported_schema_keys as clean

ALLOWED_KEYS = {
    "type", "description", "title", "nullable", "enum", "format", "items", "properties",
    "required", "minItems", "maxItems", "minLength", "maxLength", "pattern", "minimum",
    "maximum", "minProperties", "maxProperties",
}
TYPES = {"string", "integer", "number", "boolean", "array", "object"}

# Shapes MCP servers (Cua included) commonly emit from Rust/TypeScript types.
MCP_STYLE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pid": {"type": "integer", "format": "int32"},
        "window_id": {"type": ["integer", "null"], "format": "uint32", "minimum": 0},
        "button": {"anyOf": [{"$ref": "#/$defs/Button"}, {"type": "null"}], "default": None},
        "modifiers": {"type": ["array", "null"], "items": {"type": "string", "enum": ["ctrl", "shift"]}},
        "point": {"$ref": "#/definitions/Point"},
        "mode": {"const": "element"},
        "count": {"enum": [1, 2, 3]},
        "region": {"allOf": [{"$ref": "#/definitions/Point"}, {"properties": {"w": {"type": "number"}}}]},
        "matrix": {"type": "array"},
        "anything": {},
        "loop": {"$ref": "#/$defs/Loop"},
    },
    "required": ["pid", "missing_field"],
    "$defs": {
        "Button": {"type": "string", "enum": ["left", "right"], "description": "Mouse button."},
        "Loop": {"type": "object", "properties": {"next": {"$ref": "#/$defs/Loop"}}},
    },
    "definitions": {
        "Point": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x"]},
    },
}


def _walk(test, schema, path="root"):
    test.assertIsInstance(schema, dict, path)
    test.assertIn(schema.get("type"), TYPES, path)
    test.assertLessEqual(set(schema), ALLOWED_KEYS, path)
    if "enum" in schema:
        test.assertEqual("string", schema["type"], path)
        test.assertTrue(all(isinstance(value, str) for value in schema["enum"]), path)
    if schema["type"] == "array":
        _walk(test, schema["items"], f"{path}[]")
    if schema["type"] == "object":
        for name, child in schema.get("properties", {}).items():
            _walk(test, child, f"{path}.{name}")
        test.assertLessEqual(set(schema.get("required", [])), set(schema.get("properties", {})), path)


class GeminiSchemaTests(unittest.TestCase):
    def test_mcp_style_schema_becomes_gemini_safe(self):
        cleaned = clean(MCP_STYLE)
        _walk(self, cleaned)
        props = cleaned["properties"]
        self.assertEqual({"type": "integer", "nullable": True, "minimum": 0}, props["window_id"])
        self.assertEqual("int32", props["pid"]["format"])
        self.assertEqual(["left", "right"], props["button"]["enum"])
        self.assertTrue(props["button"]["nullable"])
        self.assertEqual("array", props["modifiers"]["type"])
        self.assertEqual(["x"], props["point"]["required"])
        self.assertEqual(["element"], props["mode"]["enum"])
        self.assertEqual(["1", "2", "3"], props["count"]["enum"])
        self.assertEqual({"x", "y", "w"}, set(props["region"]["properties"]))
        self.assertEqual({"type": "string"}, props["matrix"]["items"])
        self.assertEqual(["pid"], cleaned["required"])

    def test_every_xelora_tool_schema_is_gemini_safe(self):
        from agent.providers import build_gemini_tools

        declarations = build_gemini_tools()[0]["function_declarations"]
        self.assertGreater(len(declarations), 50)
        for declaration in declarations:
            with self.subTest(tool=declaration["name"]):
                _walk(self, declaration["parameters"])

    def test_cleaning_is_idempotent(self):
        once = clean(MCP_STYLE)
        self.assertEqual(once, clean(once))

    @unittest.skipUnless(_has_google_genai(), "google-genai not installed")
    def test_google_sdk_accepts_cleaned_mcp_schema(self):
        from google.genai import types

        types.FunctionDeclaration(name="cua__click", description="Click.", parameters=clean(MCP_STYLE))


class GeminiToolObjectTests(unittest.TestCase):
    def test_one_rejected_declaration_is_dropped_not_the_turn(self):
        from agent.core import AgentTask
        from agent.providers import _gemini_tool_objects

        class FakeTypes:
            class FunctionDeclaration:
                def __init__(self, **kwargs):
                    if kwargs["name"] == "bad":
                        raise AttributeError("'list' object has no attribute 'upper'")
                    self.name = kwargs["name"]

            class Tool:
                def __init__(self, function_declarations):
                    self.function_declarations = function_declarations

        task = AgentTask("x")
        tools = _gemini_tool_objects(task, FakeTypes, [{"function_declarations": [
            {"name": "good", "parameters": {}}, {"name": "bad", "parameters": {}},
        ]}])
        self.assertEqual(["good"], [d.name for d in tools[0].function_declarations])
        self.assertEqual(["bad"], task.gemini_skipped_tools)
        self.assertTrue(any("'bad'" in line for line in task.progress_log))


class HeartbeatTests(unittest.TestCase):
    def test_slow_steps_report_progress_and_fast_steps_stay_quiet(self):
        import time
        from unittest.mock import patch

        from agent import core

        task = core.AgentTask("x")
        with patch.object(core, "HEARTBEAT_FIRST_SECONDS", 0.05), patch.object(core, "HEARTBEAT_EVERY_SECONDS", 0.05):
            with core._heartbeat(task, "Planning the next step with the AI"):
                time.sleep(0.18)
            beats = [line for line in task.progress_log if line.startswith("⏳")]
            self.assertGreaterEqual(len(beats), 2)
            self.assertIn("Planning the next step with the AI", beats[0])
            time.sleep(0.12)
            self.assertEqual(len(beats), len([l for l in task.progress_log if l.startswith("⏳")]))

        quiet = core.AgentTask("y")
        with core._heartbeat(quiet, "fast"):
            pass
        self.assertEqual([], quiet.progress_log)

    def test_live_status_names_the_current_step_and_restores_the_outer_one(self):
        from agent import core
        from agent.reveal import progress_snapshot

        task = core.AgentTask("x")
        with core._heartbeat(task, "Reading your workbook"):
            with core._heartbeat(task, "Opening Excel"):
                self.assertEqual("Opening Excel", task.live_status)
            self.assertEqual("Reading your workbook", task.live_status)
            snapshot = progress_snapshot(task.structured_steps, False, None, None, task.live_status)
            self.assertEqual("Reading your workbook", snapshot["current_task"])
        self.assertIsNone(task.live_status)
        self.assertEqual("Done", progress_snapshot([], True, None, None, "Opening Excel")["current_task"])

    def test_labels_name_the_action(self):
        from agent.core import _action_label

        self.assertEqual("Working in Excel: Writing a data table", _action_label("write_table"))
        self.assertEqual("Researching on the web", _action_label("web_search"))
        self.assertEqual("Checking the Excel window", _action_label("cua__get_window_state"))


if __name__ == "__main__":
    unittest.main()
