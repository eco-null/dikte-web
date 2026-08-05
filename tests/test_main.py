

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import config as cfg
from app.main import app as fastapi_app
from tests.support import DikteTest

os.environ["DIKTE_COOKIE_SECURE"] = "0"

class MainTest(DikteTest):
    def setUp(self):
        super().setUp()
        self.client = TestClient(fastapi_app)
        self.addCleanup(self.client.close)
        fastapi_app.state.conf = self.config()

    def test_healthz_is_public_and_ok(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

    def test_static_css_is_public(self):
        resp = self.client.get("/static/app.css")
        self.assertEqual(resp.status_code, 200)

    def test_api_requires_login(self):
        resp = self.client.get("/api/history")
        self.assertEqual(resp.status_code, 401)

    def test_page_redirects_to_login(self):
        resp = self.client.get("/dictate", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/login")

    def test_login_page_is_public(self):
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)

    def test_root_redirects_to_dictate(self):
        self.client.post("/login", data={"password": "test-password"})
        resp = self.client.get("/", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/dictate")

    def test_healthz_hides_internal_error_details(self):
        with mock.patch.object(cfg, "Config", side_effect=RuntimeError("boom")):
            resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.json(),
                         {"ok": False, "error": "settings unavailable"})
        self.assertNotIn("boom", resp.text)

    def test_markdown_filter_strips_script(self):
        render = fastapi_app.state.templates.env.filters["markdown"]
        html = render('<script>alert(1)</script>**bold** '
                      '<img src=x onerror=alert(2)>')
        self.assertNotIn("<script", html)
        self.assertNotIn("onerror", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_mutating_request_with_mismatched_origin_is_rejected(self):
        self.client.post("/login", data={"password": "test-password"})
        resp = self.client.post("/api/history/clear",
                                headers={"Origin": "https://evil.example"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["detail"], "Forbidden: cross-site request")

    def test_mutating_request_with_no_origin_is_allowed(self):
        self.client.post("/login", data={"password": "test-password"})
        resp = self.client.post("/api/history/clear")
        self.assertEqual(resp.status_code, 200)

    def test_same_origin_mutating_request_is_allowed(self):
        self.client.post("/login", data={"password": "test-password"})
        resp = self.client.post("/api/history/clear",
                                headers={"Origin": "http://testserver"})
        self.assertEqual(resp.status_code, 200)

    def test_mutating_request_behind_a_proxy_matching_forwarded_host(self):
        self.client.post("/login", data={"password": "test-password"})
        resp = self.client.post(
            "/api/history/clear",
            headers={"Origin": "https://dikte.example.com",
                     "X-Forwarded-Host": "dikte.example.com"})
        self.assertEqual(resp.status_code, 200)

    def test_mutating_request_behind_a_proxy_matching_forwarded_header(self):
        self.client.post("/login", data={"password": "test-password"})
        resp = self.client.post(
            "/api/history/clear",
            headers={"Origin": "https://dikte.example.com",
                     "Forwarded": "host=dikte.example.com"})
        self.assertEqual(resp.status_code, 200)

    def test_mutating_request_whose_host_header_was_rewritten_still_works(self):
        # A proxy that rewrites Host to the internal name must not break
        # same-origin checks when X-Forwarded-Host carries the public name.
        self.client.post("/login", data={"password": "test-password"})
        resp = self.client.post(
            "/api/history/clear",
            headers={"Host": "dikte-web:8000",
                     "Origin": "https://dikte.example.com",
                     "X-Forwarded-Host": "dikte.example.com"})
        self.assertEqual(resp.status_code, 200)

if __name__ == "__main__":
    unittest.main()
