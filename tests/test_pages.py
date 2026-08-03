"""Every page renders, is gated, and carries working navigation."""

import os
import unittest

from fastapi.testclient import TestClient

import config as cfg
import i18n
from app.main import app as fastapi_app
from tests.support import DikteTest

# httpx's TestClient will not carry a Secure cookie over plain http://testserver,
# so the session would never stick in tests. The env-var default is "1" for
# production TLS; tests opt out explicitly.
os.environ["DIKTE_COOKIE_SECURE"] = "0"


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

    def test_logout_works_via_post(self):
        resp = self.client.post("/logout", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.client.cookies.clear()
        resp = self.client.get("/api/history")
        self.assertEqual(resp.status_code, 401)

    def test_login_rate_limit_returns_429_after_failures(self):
        from app.routes import pages as pages_routes
        self.addCleanup(pages_routes._reset_login_failures)
        for _ in range(pages_routes.LOGIN_MAX_FAILURES):
            resp = self.client.post("/login", data={"password": "wrong"})
            self.assertEqual(resp.status_code, 200)
        resp = self.client.post("/login", data={"password": "wrong"})
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Too many failed attempts", resp.text)

    def test_dictation_page_wires_copy_and_download(self):
        body = self.client.get("/dictate").text
        self.assertIn('data-copy', body)
        self.assertIn('data-target="#text"', body)
        self.assertIn('data-download', body)
        self.assertIn('data-fmt="txt"', body)

    def test_dictation_page_has_record_controls(self):
        body = self.client.get("/dictate").text
        for marker in ('id="record"', "data-copy", "data-download", 'id="meter"'):
            self.assertIn(marker, body)
        self.assertIn('class="record-btn"', body)

    def test_css_carries_design_tokens(self):
        css = self.client.get("/static/app.css").text
        for token in ("--color-primary", "--color-accent", "--space-1",
                      "--radius-md", "--font-sans", "--duration-fast"):
            self.assertIn(token, css)

    def test_css_respects_reduced_motion(self):
        css = self.client.get("/static/app.css").text
        self.assertIn("prefers-reduced-motion", css)

    def test_css_has_focus_visible_rings(self):
        css = self.client.get("/static/app.css").text
        self.assertIn(":focus-visible", css)

    def test_nav_uses_svg_icons_not_emoji(self):
        body = self.client.get("/dictate").text
        self.assertIn("<svg", body)
        for emoji in ("\U0001F3A4", "\U0001F4C1", "\U0001F4CB", "\u2699\uFE0F"):
            self.assertNotIn(emoji, body)

    def test_login_page_has_auth_card(self):
        self.client.cookies.clear()
        resp = self.client.get("/login")
        body = resp.text
        self.assertEqual(resp.status_code, 200)
        self.assertIn('action="/login"', body)
        self.assertIn('name="password"', body)
        self.assertIn("auth-card", body)


    def test_files_page_has_dropzone_and_downloads(self):
        body = self.client.get("/files").text
        for marker in ("dropzone", "data-download", 'data-fmt="srt"'):
            self.assertIn(marker, body)

    def test_files_dropzone_is_keyboard_accessible(self):
        body = self.client.get("/files").text
        self.assertIn('tabindex="0"', body)
        self.assertIn('role="button"', body)

    def test_authenticated_pages_disable_caching(self):
        for path in ("/dictate", "/files", "/meetings", "/agent",
                     "/history", "/settings"):
            body = self.client.get(path).text
            self.assertIn('http-equiv="Cache-Control" content="no-store"', body, path)

    def test_meeting_detail_disable_caching(self):
        cfg.save_meeting({"base": "20260101-120000", "status": "done",
                          "title": "Toplantı", "model": "x"})
        body = self.client.get("/meetings/20260101-120000").text
        self.assertIn('http-equiv="Cache-Control" content="no-store"', body)

    def test_login_page_disable_caching(self):
        self.client.cookies.clear()
        body = self.client.get("/login").text
        self.assertIn('http-equiv="Cache-Control" content="no-store"', body)

    def test_meetings_page_has_action_buttons(self):
        cfg.save_meeting({"base": "20260101-120000", "status": "failed",
                          "title": "Eski toplantı", "model": "x"})
        body = self.client.get("/meetings").text
        for marker in ("data-retry", "data-del", "meeting-card"):
            self.assertIn(marker, body)

    def test_agent_page_has_chat_surface(self):
        body = self.client.get("/agent").text
        for marker in ("chat", "data-copy"):
            self.assertIn(marker, body)

    def test_history_page_has_bulk_actions(self):
        body = self.client.get("/history").text
        for marker in ("delete-selected", "row-check"):
            self.assertIn(marker, body)

    def test_settings_page_has_local_and_models_sections(self):
        body = self.client.get("/settings").text
        self.assertIn('name="transcribe_provider"', body)
        self.assertIn('name="cleanup_provider"', body)
        self.assertIn('name="local_model"', body)
        self.assertIn('name="ui_language"', body)
        self.assertIn('name="file_timestamps"', body)
        self.assertIn("data-models", body)

    def test_settings_page_uses_compact_grid_and_save_bar(self):
        body = self.client.get("/settings").text
        self.assertIn("settings-grid", body)
        self.assertIn("save-bar", body)
        self.assertIn('id="msg"', body)

    def test_settings_page_has_omniroute_credentials(self):
        body = self.client.get("/settings").text
        self.assertIn('name="assistant_omniroute_base_url"', body)
        self.assertIn('name="assistant_omniroute_model"', body)
        self.assertIn('name="assistant_omniroute_api_key"', body)

    def test_result_textareas_auto_grow_in_css(self):
        css = self.client.get("/static/app.css").text
        self.assertIn("min-height: 120px", css)
        self.assertIn("overflow: hidden", css)


if __name__ == "__main__":
    unittest.main()
