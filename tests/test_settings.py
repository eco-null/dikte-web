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

    def test_apply_ignores_a_masked_value_that_is_the_stored_redaction(self):
        conf = self.config(openai_api_key="sk-verysecret123")
        shown = web.present(conf)["openai_api_key"]          # e.g. sk-…123
        web.apply(conf, {"openai_api_key": shown})
        self.assertEqual(conf["openai_api_key"], "sk-verysecret123")

    def test_apply_still_replaces_with_a_fresh_key(self):
        conf = self.config(openai_api_key="sk-verysecret123")
        web.apply(conf, {"openai_api_key": "sk-brandnew456"})
        self.assertEqual(conf["openai_api_key"], "sk-brandnew456")

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

    def test_web_fields_include_the_local_surface(self):
        for key in ("transcribe_provider", "cleanup_provider", "local_model",
                    "local_threads", "local_gpu", "local_preload",
                    "local_llm_model", "local_llm_context",
                    "mic_target", "keep_audio", "file_timestamps",
                    "file_cleanup", "meeting_max_seconds"):
            self.assertIn(key, web.WEB_FIELDS)

    def test_transcribe_provider_offers_local(self):
        self.assertIn("local", web.WEB_FIELDS["transcribe_provider"][1])

    def test_cleanup_provider_offers_local_llm(self):
        self.assertIn("local-llm", web.WEB_FIELDS["cleanup_provider"][1])


if __name__ == "__main__":
    unittest.main()
