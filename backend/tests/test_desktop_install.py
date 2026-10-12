"""The packaged desktop agent: read-only install directory and Excel engine.

Xelora Desktop installs under Program Files, which the user cannot write to,
and runs its own Python where pywin32 may fail to load. Both used to surface
as cryptic task failures ("[WinError 5] Access is denied: ...knowledge\\data"
and "'NoneType' object has no attribute 'apps'").
"""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import local_agent
from agent.core import AgentTask, run_task
from skills import excel_shared

BACKEND = Path(__file__).resolve().parents[1]


class WritableDataDirTests(unittest.TestCase):
    def test_agent_keeps_runtime_data_out_of_the_install_directory(self):
        with tempfile.TemporaryDirectory() as local_app_data, \
                patch.dict(os.environ, {"LOCALAPPDATA": local_app_data}):
            os.environ.pop("XELORA_DATA_DIR", None)
            local_agent.configure_environment("https://api.example.com", "xa_tok")
            self.assertEqual(os.path.join(local_app_data, "Xelora", "data"), os.environ["XELORA_DATA_DIR"])

    def test_knowledge_and_reports_follow_the_data_dir_and_import_writes_nothing(self):
        import knowledge.rag as rag
        import reporting.pdf_generator as pdf_generator

        with tempfile.TemporaryDirectory() as data_dir, \
                patch.dict(os.environ, {"XELORA_DATA_DIR": data_dir}):
            try:
                importlib.reload(rag)
                importlib.reload(pdf_generator)
                self.assertEqual(os.path.join(data_dir, "knowledge"), rag.DATA_DIR)
                self.assertEqual(Path(data_dir) / "reports", pdf_generator.REPORTS_DIR)
                self.assertFalse(os.path.exists(rag.DATA_DIR), "import must not create the folder")

                kb = rag.KnowledgeBase(user_id=7)
                kb.add_document("notes.txt", "quarterly revenue by region")
                self.assertTrue(os.path.isfile(os.path.join(data_dir, "knowledge", "user_7.pkl")))
            finally:
                os.environ.pop("XELORA_DATA_DIR", None)
                importlib.reload(rag)
                importlib.reload(pdf_generator)


class ExcelEngineTests(unittest.TestCase):
    def test_missing_engine_names_the_cause_instead_of_a_nonetype_error(self):
        with patch.object(excel_shared.xw.engines, "active", None), \
                patch("sys.platform", "win32"), \
                patch.dict("sys.modules", {"xlwings._xlwindows": None}):
            with self.assertRaises(excel_shared.ExcelUnavailableError) as raised:
                excel_shared.require_excel_engine()
        self.assertIn("pywin32", str(raised.exception))

    def test_new_workbook_task_stops_cleanly_when_excel_is_unavailable(self):
        task = AgentTask("create a table of 4 rows and 3 columns")
        unavailable = excel_shared.ExcelUnavailableError("pywin32 failed to load: DLL load failed")
        with patch("agent.core._route_needs_workbook", return_value=True), \
                patch.object(config, "VISUAL_ONLY_MODE", False), \
                patch.object(excel_shared, "start_task_workbook", side_effect=unavailable):
            run_task(task)
        self.assertTrue(task.is_done)
        self.assertIn("could not start Excel", task.final_response)
        self.assertIn("pywin32", task.final_response)


class SkillLibraryTests(unittest.TestCase):
    def test_every_skill_folder_loads(self):
        """A skill that fails to load is skipped at runtime, silently removing
        that Excel capability from the agent."""
        from skills import loader
        from skills.base import SKILL_REGISTRY

        folders = {
            path.name for path in Path(loader.LIBRARY_DIR).iterdir()
            if path.is_dir() and not path.name.startswith(("_", "."))
        }
        self.assertGreater(len(folders), 50)
        self.assertEqual(set(), folders - set(SKILL_REGISTRY), "skill folders that failed to load")

    def test_windows_line_endings_still_load(self):
        """Git on Windows checks files out with CRLF line endings."""
        from skills import loader

        with tempfile.TemporaryDirectory() as library:
            folder = Path(library) / "crlf_skill"
            folder.mkdir()
            (folder / "SKILL.md").write_bytes(
                b"---\r\nname: crlf_skill\r\ndescription: test\r\ncategory: read\r\n---\r\n"
                b"```json\r\n{\"type\": \"object\", \"properties\": {}}\r\n```\r\n"
            )
            (folder / "impl.py").write_bytes(b"def run():\r\n    return {'verified': True}\r\n")
            with patch.object(loader, "LIBRARY_DIR", library), \
                    patch.dict(loader.SKILL_REGISTRY, {}, clear=True):
                loader.load_all()
                self.assertIn("crlf_skill", loader.SKILL_REGISTRY)


if __name__ == "__main__":
    unittest.main()
