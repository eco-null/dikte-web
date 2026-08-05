

import io
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import config as cfg
from app import auth
from app.main import app as fastapi_app
from tests.support import DikteTest

os.environ["DIKTE_COOKIE_SECURE"] = "0"

class Auth(DikteTest):
    def test_password_reads_the_env(self):
        with mock.patch.dict(os.environ, {"DIKTE_WEB_PASSWORD": "secret"}):
            self.assertEqual(auth.password(), "secret")

    def test_generated_password_is_stored(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            p1 = auth.password()
            p2 = auth.password()
        self.assertTrue(p1)
        self.assertEqual(p1, p2)
        self.assertEqual((cfg.DATA_DIR / "web_password").read_text().strip(), p1)

    def test_generated_password_is_0600_and_not_printed(self):
        captured = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch("sys.stderr", captured):
            p1 = auth.password()
            p2 = auth.password()
        self.assertTrue(p1)
        self.assertEqual(p1, p2)
        self.assertEqual(captured.getvalue(), "",
                         "generated password must not be logged")
        if os.name != "nt":
            mode = (cfg.DATA_DIR / "web_password").stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_login_cookie_is_secure_when_enabled(self):
        with mock.patch.dict(os.environ, {"DIKTE_COOKIE_SECURE": "1"}):
            with TestClient(fastapi_app) as client:
                resp = client.post("/login", data={"password": "test-password"},
                                   follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        header = resp.headers["set-cookie"]
        self.assertIn("Secure", header)
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=lax", header)

    def test_login_cookie_secure_can_be_disabled(self):
        with mock.patch.dict(os.environ, {"DIKTE_COOKIE_SECURE": "0"}):
            with TestClient(fastapi_app) as client:
                resp = client.post("/login", data={"password": "test-password"},
                                   follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertNotIn("Secure", resp.headers["set-cookie"])

    def test_a_session_round_trips(self):
        token = auth.new_session()
        self.assertTrue(auth.check(token))

    def test_a_forged_token_is_rejected(self):
        token = auth.new_session()
        self.assertFalse(auth.check(token + "x"))

    def test_an_empty_token_is_rejected(self):
        self.assertFalse(auth.check(""))

    def test_an_expired_session_is_rejected(self):
        token = auth.new_session()
        value, sig = token.rsplit(".", 1)
        old = f"{float(value.split('.', 1)[0]) - 8 * 24 * 3600}.{value.split('.', 1)[1]}.{sig}"
        self.assertFalse(auth.check(old))

    def test_a_token_with_no_separator_is_rejected(self):
        self.assertFalse(auth.check("justgarbage"))

    def test_a_token_with_too_few_parts_is_rejected(self):
        self.assertFalse(auth.check("12345.onlytimestamp"))

    def test_a_token_with_a_bad_signature_is_rejected(self):
        token = auth.new_session()
        value, sig = token.rsplit(".", 1)
        wrong = f"{value}.{'0' * len(sig)}"
        self.assertFalse(auth.check(wrong))

    def test_a_non_numeric_timestamp_is_rejected(self):
        value, sig = auth.new_session().rsplit(".", 1)
        bogus_value = f"not-a-number.{value.split('.', 1)[1]}"
        bogus = f"{bogus_value}.{auth._sig(bogus_value)}"
        self.assertFalse(auth.check(bogus))

if __name__ == "__main__":
    unittest.main()
