

import unittest
from unittest import mock

import api
import assistant
from tests.support import DikteTest

class AssistantProvider(DikteTest):
    def test_omniroute_uses_its_own_key_and_base_url(self):
        conf = self.config(
            assistant_provider="omniroute",
            assistant_omniroute_base_url="http://127.0.0.1:20128/v1",
            assistant_omniroute_api_key="sk-omni",
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
            assistant_omniroute_base_url="http://127.0.0.1:20128/v1",
            assistant_omniroute_api_key="",
        )
        with mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "")
        self.assertIs(kwargs["key_required"], False)

    def test_openrouter_uses_openrouter_key_and_requires_it(self):
        conf = self.config(
            assistant_provider="openrouter",
            openrouter_api_key="sk-or",
            assistant_openrouter_model="some/model",
        )
        with mock.patch("api.chat", return_value="cevap") as chat:
            assistant.ask("soru", conf)
        args, kwargs = chat.call_args
        self.assertEqual(args[1], "sk-or")
        self.assertIs(kwargs["key_required"], True)
        self.assertEqual(kwargs["provider"], "openrouter")

if __name__ == "__main__":
    unittest.main()
