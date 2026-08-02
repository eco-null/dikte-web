"""Every page renders, is gated, and carries working navigation."""

import unittest

from fastapi.testclient import TestClient

import config as cfg
import i18n
from app.main import app as fastapi_app
from tests.support import DikteTest


class PagesTest(DikteTest):
    def setUp(self):
        super().setUp()
        self.client = TestClient(fastapi_app)
        self.addCleanup(self.client.close)
        fastapi_app.state.conf = self.config()
        self.client.post("/login", data={"password": "test-password"})

    def test_every_page_renders_logged_in(self):
        for path in ("/dictate", "/files", "/meetings", "/agent",
                     "/history", "/settings"):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, path)

    def test_meeting_detail_404_for_unknown_base(self):
        resp = self.client.get("/meetings/19990101-000000")
        self.assertEqual(resp.status_code, 404)

    def test_nav_has_all_sections(self):
        body = self.client.get("/dictate").text
        for label in ("Dictation", "Files", "Minutes", "Agent",
                      "History", "Settings", "Log out"):
            self.assertIn(label, body)

    def test_html_lang_is_resolved_not_a_key(self):
        i18n.set_language("tr")
        self.addCleanup(i18n.set_language, "en")
        body = self.client.get("/dictate").text
        self.assertIn('lang="tr"', body)
        self.assertNotIn('lang="auto"', body)

    def test_settings_never_sends_masked_keys_as_values(self):
        conf = self.config(openai_api_key="sk-verysecret123")
        fastapi_app.state.conf = conf
        body = self.client.get("/settings").text
        self.assertNotIn('value="sk-', body)

    def test_logout_clears_the_session(self):
        resp = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.client.cookies.clear()
        resp = self.client.get("/api/history")
        self.assertEqual(resp.status_code, 401)

    def test_dictation_page_wires_copy_and_download(self):
        body = self.client.get("/dictate").text
        self.assertIn('data-copy', body)
        self.assertIn('data-target="#text"', body)
        self.assertIn('data-download', body)
        self.assertIn('data-fmt="txt"', body)


if __name__ == "__main__":
    unittest.main()
