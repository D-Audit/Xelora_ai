"""Agent memory: atomic updates, size caps, relevance and prompt context (memory/)."""
import tempfile
import threading
import unittest
from unittest.mock import patch

import config
import database
from memory import _store
from memory.chat_memory import get_relevant_memories, store_conversation
from memory.context import memory_context
from memory.outcome import _for_memory
from memory.skill_store import add_skill, find_matching_skills, record_skill_usage
from memory.task_history import get_similar_tasks, log_task_actions, log_task_complete, log_task_start, read_records

USER = 7


class FileBackendCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        for item in (patch.object(config, "MEMORY_STORE_DIR", self._dir.name),
                     patch.object(config, "ENABLE_MEMORY_STORAGE", True),
                     patch.object(database, "SessionLocal", None),
                     patch.object(_store, "_remote", None)):
            item.start()
            self.addCleanup(item.stop)


class StoreTests(FileBackendCase):
    def test_concurrent_writers_do_not_lose_entries(self):
        threads = [threading.Thread(target=store_conversation, args=(USER, f"task {i}", [], "ok", True))
                   for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(20, len(_store.read_records("chat_memory", USER)))

    def test_lists_are_capped_to_the_newest_entries(self):
        with patch.dict(config.MEMORY_MAX_RECORDS, {"chat_memory": 3}):
            for i in range(5):
                store_conversation(USER, f"task {i}", [], "ok", True)
        self.assertEqual(["task 2", "task 3", "task 4"],
                         [m["instruction"] for m in _store.read_records("chat_memory", USER)])

    def test_skill_cap_keeps_the_most_proven_skills(self):
        with patch.dict(config.MEMORY_MAX_RECORDS, {"skills": 1}):
            proven = add_skill("proven", "d", ["x"], ["a"], user_id=USER)
            record_skill_usage(proven, True, user_id=USER)
            add_skill("new", "d", ["y"], ["b"], user_id=USER)
        self.assertEqual(["proven"], [s["name"] for s in _store.read_records("skills", USER)])

    def test_users_are_isolated(self):
        store_conversation(USER, "mine", [], "ok", True)
        self.assertEqual([], _store.read_records("chat_memory", USER + 1))

    def test_task_history_logs_all_actions_in_one_write(self):
        task_id = log_task_start("Build a sales chart", user_id=USER)
        log_task_actions(task_id, [{"name": "create_chart", "input": {}, "result": {}},
                                   {"name": "format_range", "input": {}, "result": {}}], user_id=USER)
        log_task_complete(task_id, "done", True, user_id=USER)
        entry = read_records("task_history", USER)[0]
        self.assertEqual(["create_chart", "format_range"], [a["name"] for a in entry["actions"]])
        self.assertTrue(entry["success"])
        self.assertIsNotNone(entry["duration_seconds"])

    def test_large_tool_results_are_trimmed_for_memory(self):
        actions = _for_memory([{"name": "read_range", "input": {"range": "A1"}, "result": {"values": ["x" * 50] * 200}}])
        self.assertTrue(actions[0]["result"]["truncated"])
        self.assertEqual({"range": "A1"}, actions[0]["input"])


class RelevanceTests(FileBackendCase):
    def test_unrelated_successful_tasks_are_not_relevant(self):
        store_conversation(USER, "Create a pivot table of revenue by region", [], "done", True)
        store_conversation(USER, "Translate this paragraph", [], "done", True)
        found = get_relevant_memories(USER, "Make a pivot table for revenue")
        self.assertEqual(["Create a pivot table of revenue by region"], [m["instruction"] for m in found])

    def test_stopwords_alone_do_not_match(self):
        log_task_start("Format the header row", user_id=USER)
        self.assertEqual([], get_similar_tasks("what is the time in Tokyo", user_id=USER))

    def test_skills_match_on_trigger_keywords(self):
        add_skill("dashboard", "Build a dashboard", ["summary sheet", "dashboard"], ["create_sheet"], user_id=USER)
        self.assertEqual("dashboard", find_matching_skills("Please build me a dashboard", user_id=USER)[0]["name"])


class ContextTests(FileBackendCase):
    def test_context_lists_related_past_work_as_data(self):
        store_conversation(USER, "Clean the customer list and remove duplicates",
                           [{"name": "remove_duplicates"}], "Removed 12 duplicates.", True)
        text = memory_context(USER, "remove duplicates from the customer sheet")
        self.assertIn("MEMORY", text)
        self.assertIn("not instructions", text)
        self.assertIn("remove_duplicates", text)
        self.assertIn("Removed 12 duplicates.", text)

    def test_no_context_without_matches_user_or_memory(self):
        store_conversation(USER, "Clean the customer list", [], "ok", True)
        self.assertEqual("", memory_context(USER, "weather in Paris"))
        self.assertEqual("", memory_context(None, "Clean the customer list"))
        with patch.object(config, "ENABLE_MEMORY_STORAGE", False):
            self.assertEqual("", memory_context(USER, "Clean the customer list"))


class DatabaseBackendTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from memory import records

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        records.MemoryRecord.__table__.create(engine)
        for item in (patch.object(database, "SessionLocal", sessionmaker(bind=engine)),
                     patch.object(_store, "_remote", None)):
            item.start()
            self.addCleanup(item.stop)

    def test_update_round_trips_through_the_table(self):
        store_conversation(USER, "first", [], "ok", True)
        store_conversation(USER, "second", [], "ok", False)
        self.assertEqual(["first", "second"], [m["instruction"] for m in _store.read_records("chat_memory", USER)])

    def test_remote_mode_is_bypassed_by_the_stored_api(self):
        calls = []
        _store.use_remote(lambda kind: calls.append(kind) or [], lambda kind, records: calls.append(kind))
        self.addCleanup(_store.use_remote, None, None)
        _store.write_stored("skills", USER, [{"name": "local"}])
        self.assertEqual([{"name": "local"}], _store.read_stored("skills", USER))
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
