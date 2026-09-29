"""Regression tests for the guarded live-data network boundary."""

import unittest
from unittest.mock import patch

from agent.tool_registry import ToolRisk, get_tool_spec
from agent.permissions import decide_action
from agent.permissions import ActionDecision
from tools.web import web_fetch, web_search
from tools.web_guard import UnsafeUrlError, validate_public_url
from tools.filesystem import list_workspace_files, read_workspace_file


class WebGuardTests(unittest.TestCase):
    def test_rejects_loopback_literal(self):
        with self.assertRaisesRegex(UnsafeUrlError, "loopback"):
            validate_public_url("http://127.0.0.1:8000/private")

    def test_rejects_private_dns_answer(self):
        with patch("tools.web_guard.socket.getaddrinfo", return_value=[(None, None, None, None, ("10.0.0.9", 443))]):
            with self.assertRaisesRegex(UnsafeUrlError, "private network"):
                validate_public_url("https://example.test/data")

    def test_accepts_public_dns_answers(self):
        with patch("tools.web_guard.socket.getaddrinfo", return_value=[(None, None, None, None, ("8.8.8.8", 443))]):
            validate_public_url("https://example.test/data")

    def test_excel_registry_metadata_marks_reads_and_writes(self):
        registry = {
            "read_range": {"description": "Read", "input_schema": {}},
            "write_cell": {"description": "Write", "input_schema": {}},
        }
        with patch("agent.tool_registry.SKILL_REGISTRY", registry):
            read_tool = get_tool_spec("read_range", visual_tool_names=set())
            write_tool = get_tool_spec("write_cell", visual_tool_names=set())

        self.assertEqual(ToolRisk.READ, read_tool.risk)
        self.assertEqual(ToolRisk.WRITE, write_tool.risk)

    def test_policy_allows_reads_but_holds_writes_while_planning(self):
        registry = {
            "read_range": {"description": "Read", "input_schema": {}},
            "write_cell": {"description": "Write", "input_schema": {}},
        }
        with patch("agent.tool_registry.SKILL_REGISTRY", registry):
            read = decide_action(get_tool_spec("read_range", visual_tool_names=set()), planning_only=True)
            write = decide_action(get_tool_spec("write_cell", visual_tool_names=set()), planning_only=True)

        self.assertTrue(read.allowed)
        self.assertFalse(write.allowed)
        self.assertTrue(write.needs_user)

    def test_web_fetch_strips_html_and_marks_content_untrusted(self):
        with patch("tools.web.get_public_content", return_value=(b"<html><body><h1>Rate</h1><script>bad()</script><p>42</p></body></html>", "https://example.test/rate", "text/html")):
            result = web_fetch("https://example.test/rate")

        self.assertEqual("Rate\n42", result["text"])
        self.assertIn("untrusted", result["trust_notice"])

    def test_web_search_returns_public_result_urls(self):
        page = b'''<a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fsource">Official source</a><div class="result__snippet">Current rate</div>'''
        with patch("tools.web.get_public_content", return_value=(page, "https://html.duckduckgo.com/html/?q=rate", "text/html")):
            result = web_search("current rate")

        self.assertEqual("https://example.com/source", result["results"][0]["url"])
        self.assertEqual("Official source", result["results"][0]["title"])

    def test_user_file_tools_cannot_escape_the_user_storage_root(self):
        with patch("tools.filesystem._storage_root", return_value=__import__("pathlib").Path("/tmp/xelora-test-storage")):
            with self.assertRaisesRegex(PermissionError, "escapes"):
                read_workspace_file(7, "../other-user/private.csv")

    def test_user_file_tools_read_only_user_directory(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            user_root = root / "7"
            user_root.mkdir()
            (user_root / "sales.csv").write_text("month,sales\nJan,12\n", encoding="utf-8")
            with patch("tools.filesystem._storage_root", return_value=root):
                listing = list_workspace_files(7)
                read = read_workspace_file(7, "sales.csv")

        self.assertEqual("sales.csv", listing["entries"][0]["path"])
        self.assertIn("Jan,12", read["text"])

    def test_unknown_actions_are_never_authorized(self):
        decision = decide_action(None, planning_only=False)

        self.assertEqual(
            ActionDecision(False, reason="Unknown tools are never executable.", status="tool_not_authorized"),
            decision,
        )
