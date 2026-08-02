"""The slice of settings the webapp presents and how it applies edits."""

import unittest

import config as cfg
from app import settings as web
from tests.support import DikteTest


class Settings(DikteTest):
    def test_present_masks_keys(self):
        conf = self.config(openai_api_key="sk-verysecret123")
        out = web.present(conf)
        self.assertNotIn("sk-verysecret123", out["openai_api_key"])

    def test_present_covers_every_field(self):
        conf = self.config()
        out = web.present(conf)
        self.assertEqual(set(out), set(web.WEB_FIELDS))

    def test_apply_coerces_types(self):
        conf = self.config()
        web.apply(conf, {"cleanup_enabled": "on",
                         "history_limit": "42",
                         "silence_db": "-50.5"})
        self.assertIs(conf["cleanup_enabled"], True)
        self.assertEqual(conf["history_limit"], 42)
        self.assertEqual(conf["silence_db"], -50.5)

    def test_masked_field_left_empty_keeps_the_stored_key(self):
        conf = self.config(openai_api_key="sk-keep")
        web.apply(conf, {"openai_api_key": ""})
        self.assertEqual(conf["openai_api_key"], "sk-keep")

    def test_a_masked_field_can_still_be_replaced(self):
        conf = self.config(openai_api_key="sk-old")
        web.apply(conf, {"openai_api_key": "sk-new"})
        self.assertEqual(conf["openai_api_key"], "sk-new")

    def test_unknown_keys_are_ignored(self):
        conf = self.config()
        web.apply(conf, {"made_up_key": "x"})
        self.assertNotIn("made_up_key", conf.data)

    def test_apply_saves(self):
        conf = self.config()
        web.apply(conf, {"cleanup_model": "some/model"})
        self.assertEqual(cfg.Config()["cleanup_model"], "some/model")

    def test_an_invalid_number_is_ignored(self):
        conf = self.config(silence_db=-40.0)
        web.apply(conf, {"silence_db": "not-a-number"})
        self.assertEqual(conf["silence_db"], -40.0)


if __name__ == "__main__":
    unittest.main()
