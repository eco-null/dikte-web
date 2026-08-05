

import unittest

import config as cfg
from app import settings as web
from tests.support import DikteTest

class Settings(DikteTest):
    def test_present_masks_keys(self):
        conf = self.config(transcribe_openai_key="sk-verysecret123")
        out = web.present(conf)
        self.assertNotIn("sk-verysecret123", out["transcribe_openai_key"])

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
        conf = self.config(transcribe_openai_key="sk-keep")
        web.apply(conf, {"transcribe_openai_key": ""})
        self.assertEqual(conf["transcribe_openai_key"], "sk-keep")

    def test_a_masked_field_can_still_be_replaced(self):
        conf = self.config(transcribe_openai_key="sk-old")
        web.apply(conf, {"transcribe_openai_key": "sk-new"})
        self.assertEqual(conf["transcribe_openai_key"], "sk-new")

    def test_apply_ignores_a_masked_value_that_is_the_stored_redaction(self):
        conf = self.config(transcribe_openai_key="sk-verysecret123")
        shown = web.present(conf)["transcribe_openai_key"]
        web.apply(conf, {"transcribe_openai_key": shown})
        self.assertEqual(conf["transcribe_openai_key"], "sk-verysecret123")

    def test_apply_still_replaces_with_a_fresh_key(self):
        conf = self.config(transcribe_openai_key="sk-verysecret123")
        web.apply(conf, {"transcribe_openai_key": "sk-brandnew456"})
        self.assertEqual(conf["transcribe_openai_key"], "sk-brandnew456")

    def test_unknown_keys_are_ignored(self):
        conf = self.config()
        web.apply(conf, {"made_up_key": "x"})
        self.assertNotIn("made_up_key", conf.data)

    def test_apply_saves(self):
        conf = self.config()
        web.apply(conf, {"cleanup_prompt": "some/prompt"})
        self.assertEqual(cfg.Config()["cleanup_prompt"], "some/prompt")

    def test_an_invalid_number_is_ignored(self):
        conf = self.config(silence_db=-40.0)
        web.apply(conf, {"silence_db": "not-a-number"})
        self.assertEqual(conf["silence_db"], -40.0)

    def test_web_fields_include_the_local_surface(self):
        for key in ("transcribe_provider", "cleanup_provider", "assistant_provider",
                    "transcribe_local_model", "transcribe_local_threads",
                    "transcribe_local_gpu", "transcribe_local_preload",
                    "cleanup_local_model", "cleanup_local_context",
                    "cleanup_local_reasoning", "assistant_local_model",
                    "assistant_local_context", "assistant_local_reasoning",
                    "mic_target", "keep_audio", "file_timestamps",
                    "file_cleanup", "meeting_max_seconds"):
            self.assertIn(key, web.WEB_FIELDS)

    def test_transcribe_provider_offers_local(self):
        self.assertIn("local", web.WEB_FIELDS["transcribe_provider"][1])

    def test_cleanup_provider_offers_local(self):
        self.assertIn("local", web.WEB_FIELDS["cleanup_provider"][1])

    def test_web_fields_cover_per_service_schema(self):
        for key in ("transcribe_provider", "cleanup_provider", "assistant_provider",
                    "transcribe_openai_url", "transcribe_openai_key",
                    "transcribe_openai_model", "transcribe_omniroute_url",
                    "cleanup_groq_key", "cleanup_local_model",
                    "assistant_openrouter_url", "assistant_omniroute_key"):
            self.assertIn(key, web.WEB_FIELDS)

    def test_all_five_providers_in_every_service(self):
        for svc in ("transcribe", "cleanup", "assistant"):
            self.assertIn("openai", web.WEB_FIELDS[f"{svc}_provider"][1])
            self.assertIn("groq", web.WEB_FIELDS[f"{svc}_provider"][1])
            self.assertIn("openrouter", web.WEB_FIELDS[f"{svc}_provider"][1])
            self.assertIn("omniroute", web.WEB_FIELDS[f"{svc}_provider"][1])
            self.assertIn("local", web.WEB_FIELDS[f"{svc}_provider"][1])

    def test_every_provider_key_field_is_masked(self):
        for key, (kind, _) in web.WEB_FIELDS.items():
            if key.endswith("_key"):
                self.assertIn(key, web.MASKED)

if __name__ == "__main__":
    unittest.main()
