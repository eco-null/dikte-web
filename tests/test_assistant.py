
import os
import unittest
from unittest import mock

import api
import assistant
from tests.support import DikteTest


class AssistantProvider(DikteTest):
    def test_omniroute_uses_its_own_key_and_base_url(self):
        conf = self.config(
            assistant_provider="omniroute",
            assistant_omniroute_url="http://127.0.0.1:20128/v1",
            assistant_omniroute_key="sk-omni",
            assistant_omniroute_model="local-model",
        )
        with mock.patch("api.chat", return_value="cevap") as chat:
            answer, _warning = assistant.ask("soru", conf)
        self.assertEqual(answer, "cevap")
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "sk-omni")
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:20128/v1")
        self.assertIs(kwargs["key_required"], False)
        self.assertEqual(kwargs["provider"], "omniroute")

    def test_omniroute_without_a_key_still_works(self):
        conf = self.config(
            assistant_provider="omniroute",
            assistant_omniroute_url="http://127.0.0.1:20128/v1",
            assistant_omniroute_key="",
        )
        with mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "")
        self.assertIs(kwargs["key_required"], False)

    def test_openrouter_uses_openrouter_key_and_requires_it(self):
        conf = self.config(
            assistant_provider="openrouter",
            assistant_openrouter_key="sk-or",
            assistant_openrouter_model="some/model",
        )
        with mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "sk-or")
        self.assertIs(kwargs["key_required"], True)
        self.assertEqual(kwargs["provider"], "openrouter")

    def test_openai_provider_uses_assistant_keys(self):
        conf = self.config(assistant_provider="openai",
                           assistant_openai_url="http://127.0.0.1:9001/v1",
                           assistant_openai_key="sk-o",
                           assistant_openai_model="m-o")
        with mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "sk-o")
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:9001/v1")
        self.assertEqual(kwargs["model"], "m-o")
        self.assertIs(kwargs["key_required"], True)

    def test_omniroute_ignores_old_env_and_uses_setting(self):
        conf = self.config(assistant_provider="omniroute",
                           assistant_omniroute_url="http://127.0.0.1:7777/v1",
                           assistant_omniroute_key="sk-a",
                           assistant_omniroute_model="m-a")
        with mock.patch.dict(os.environ, {"OMNIROUTE_BASE_URL": "http://evil.example/v1"}), \
                mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(kwargs["base_url"], "http://127.0.0.1:7777/v1")
        self.assertNotIn("evil.example", kwargs["base_url"])

    def test_groq_provider(self):
        conf = self.config(assistant_provider="groq",
                           assistant_groq_url="http://127.0.0.1:9002/v1",
                           assistant_groq_key="sk-g",
                           assistant_groq_model="m-g")
        with mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "sk-g")
        self.assertEqual(kwargs["provider"], "groq")

    def test_local_provider_uses_llama(self):
        conf = self.config(assistant_provider="local",
                           assistant_local_model="gemma.gguf",
                           assistant_local_reasoning="none")
        with mock.patch("api.serving", return_value="http://127.0.0.1:9001/v1") as svc, \
                mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertIn("127.0.0.1:9001", kwargs["base_url"])
        self.assertEqual(kwargs["reasoning"], "none")
        self.assertEqual(kwargs["model"], "gemma.gguf")
        self.assertIs(kwargs["key_required"], False)

    def test_openrouter_key_falls_back_to_env(self):
        conf = self.config(assistant_provider="openrouter",
                           assistant_openrouter_key="",
                           assistant_openrouter_model="m")
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-env"}), \
                mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "sk-env")


if __name__ == "__main__":
    unittest.main()
