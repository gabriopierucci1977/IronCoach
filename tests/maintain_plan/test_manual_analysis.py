from datetime import datetime, timezone
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import sqlite3
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from backend.maintain_plan.manual_analysis import (
    MAX_ANALYSIS_LENGTH, analysis_database_path, load_manual_analysis, save_manual_analysis,
)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / "archive.sqlite3"
        self.archive.write_bytes(b"activity archive must stay unchanged")
        self.repository = SimpleNamespace(
            database_path=self.archive,
            get_actual_session=lambda key: SimpleNamespace(subject_ref="a") if key == "s" else None,
        )

    def test_read_does_not_create_a_store(self):
        self.assertIsNone(load_manual_analysis(self.repository, "a", "s"))
        self.assertFalse(analysis_database_path(self.repository).exists())

    def test_save_reload_and_preserve_previous_version_and_archive(self):
        before = self.archive.read_bytes()
        save_manual_analysis(self.repository, "a", "s", "Prima analisi")
        save_manual_analysis(self.repository, "a", "s", "Analisi aggiornata")
        saved = load_manual_analysis(self.repository, "a", "s")
        self.assertEqual(saved["text"], "Analisi aggiornata")
        self.assertEqual(saved["origin"], "chatgpt_manual")
        with sqlite3.connect(analysis_database_path(self.repository)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM manual_session_analyses").fetchone()[0], 2)
        self.assertEqual(before, self.archive.read_bytes())

    def test_another_subject_or_session_cannot_save_or_read(self):
        for subject, session in (("b", "s"), ("a", "other"), ("A", "s")):
            with self.assertRaises(ValueError):
                save_manual_analysis(self.repository, subject, session, "Parere")
            with self.assertRaises(ValueError):
                load_manual_analysis(self.repository, subject, session)
        self.assertFalse(analysis_database_path(self.repository).exists())

    def test_empty_and_oversized_text_never_create_a_store(self):
        for text in ("  ", "x" * (MAX_ANALYSIS_LENGTH + 1)):
            with self.assertRaises(ValueError):
                save_manual_analysis(self.repository, "a", "s", text)
        self.assertFalse(analysis_database_path(self.repository).exists())


class BrowserTests(unittest.TestCase):
    def setUp(self):
        from backend.maintain_plan.coach_web import make_handler
        from backend.maintain_plan.repository import MaintainPlanRepository
        from tests.maintain_plan.fixtures import RUN_SESSION
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repository = MaintainPlanRepository(Path(self.temp.name) / "archive.db")
        self.repository.create_actual_session(RUN_SESSION)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(str(self.repository.database_path),
                                         action_token="manual-test", environment={}))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        host, port = self.server.server_address
        self.origin = f"http://{host}:{port}"
        self.connection = http.client.HTTPConnection(host, port)
        self.addCleanup(self.connection.close)
        self.headers = {"Origin": self.origin, "Cookie": "ironcoach_action=manual-test",
                        "Content-Type": "application/x-www-form-urlencoded"}

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, values=None, headers=None):
        body = urlencode(values) if values else None
        self.connection.request(method, path, body, headers or {})
        response = self.connection.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode()

    def test_get_and_save_reload_work_without_api_and_escape_saved_text(self):
        url = "/?subject=athlete-1&session=session-1"
        before = self.repository.get_actual_session("session-1")
        with patch("backend.maintain_plan.coach_web.ai_comment", side_effect=AssertionError("API forbidden")):
            status, _, page = self.request("GET", url)
            self.assertEqual(status, 200)
            self.assertIn("Copia richiesta", page)
            self.assertIn("Apri ChatGPT", page)
            self.assertIn("Salva parere nella seduta", page)
            self.assertFalse(analysis_database_path(self.repository).exists())
            values = {"operation": "save_manual_analysis", "subject": "athlete-1",
                      "session": "session-1", "action_token": "manual-test",
                      "analysis_text": "Ottima seduta\n<script>alert(1)</script>"}
            status, headers, _ = self.request("POST", "/", values, self.headers)
            self.assertEqual(status, 303)
            self.assertIn("#manual-analysis", headers["Location"])
            status, _, page = self.request("GET", url)
            self.assertEqual(status, 200)
            self.assertIn("Parere salvato", page)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
            self.assertNotIn("<script>alert(1)</script>", page)
        self.assertEqual(before, self.repository.get_actual_session("session-1"))
        self.assertEqual(self.repository.list_prescription_mappings(), ())

    def test_cross_origin_or_invalid_token_or_wrong_subject_does_not_save(self):
        values = {"operation": "save_manual_analysis", "subject": "athlete-1",
                  "session": "session-1", "action_token": "manual-test", "analysis_text": "Parere"}
        status, _, _ = self.request("POST", "/", values, dict(self.headers, Origin="https://foreign.example"))
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/", dict(values, action_token="wrong"), self.headers)
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/", dict(values, subject="another-athlete"), self.headers)
        self.assertEqual(status, 400)
        self.assertFalse(analysis_database_path(self.repository).exists())


if __name__ == "__main__":
    unittest.main()
