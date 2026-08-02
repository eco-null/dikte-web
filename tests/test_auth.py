"""One password, a signed session cookie, and a generated fallback."""

import os
import unittest
from unittest import mock

import config as cfg
from app import auth
from tests.support import DikteTest


class Auth(DikteTest):
    def test_password_reads_the_env(self):
        with mock.patch.dict(os.environ, {"DIKTE_WEB_PASSWORD": "secret"}):
            self.assertEqual(auth.password(), "secret")

    def test_generated_password_is_stored(self):
        # The env one from conftest would shadow the fallback path.
        with mock.patch.dict(os.environ, {}, clear=True):
            p1 = auth.password()
            p2 = auth.password()
        self.assertTrue(p1)
        self.assertEqual(p1, p2)  # aynı dosyadan okur
        self.assertEqual((cfg.DATA_DIR / "web_password").read_text().strip(), p1)

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
        # Backdate it past the window: the token's own timestamp is checked.
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
