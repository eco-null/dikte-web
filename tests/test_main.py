"""The FastAPI shell: auth gate, /healthz, static files."""

import unittest

from fastapi.testclient import TestClient

import config as cfg
from app.main import app as fastapi_app
from tests.support import DikteTest


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


if __name__ == "__main__":
    unittest.main()
