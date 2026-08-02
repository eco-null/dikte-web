"""Who cleans the transcript up, and what they are asked.

The webapp keeps only the OpenRouter path. The CLI and local llama.cpp paths
that the desktop had are not carried over, so the tests here check that what
reaches OpenRouter is one request built from the settings.
"""

import unittest
from unittest import mock

import api
import cleanup
from tests.support import DikteTest, fake_urlopen, sent_json
from tests.test_api import chat_reply


class Provider(DikteTest):
    def test_the_default_is_still_openrouter(self):
        self.assertEqual(cleanup.provider(self.config()), "openrouter")

    def test_a_provider_this_version_does_not_have(self):
        self.assertEqual(
            cleanup.provider(self.config(cleanup_provider="ollama")), "openrouter")

    def test_each_one_is_recognised(self):
        for name in cleanup.PROVIDERS:
            with self.subTest(name=name):
                self.assertEqual(
                    cleanup.provider(self.config(cleanup_provider=name)), name)

    def test_the_model_named_in_the_history_is_the_one_that_did_it(self):
        self.assertEqual(cleanup.model(self.config(cleanup_model="some/model")),
                         "some/model")


class OpenRouter(DikteTest):
    def test_it_is_still_one_request_with_the_settings_as_they_were(self):
        conf = self.config(openrouter_api_key="sk-or-test",
                           cleanup_model="some/model", cleanup_reasoning="low")
        with fake_urlopen(chat_reply("Done.")) as calls:
            self.assertEqual(cleanup.run("uh, done", conf, "the rules"), "Done.")
        self.assertEqual(len(calls), 1)
        payload = sent_json(calls[0])
        self.assertEqual(payload["model"], "some/model")
        self.assertEqual(payload["messages"][0],
                         {"role": "system", "content": "the rules"})
        self.assertEqual(payload["messages"][1],
                         {"role": "user",
                          "content": "<transcript>\nuh, done\n</transcript>"})
        self.assertEqual(payload["reasoning"], {"effort": "low", "exclude": True})

    def test_the_request_goes_to_the_openrouter_address(self):
        conf = self.config(openrouter_api_key="sk-or-test")
        with fake_urlopen(chat_reply("Done.")) as calls:
            cleanup.run("uh, done", conf, "the rules")
        self.assertEqual(calls[0].full_url,
                         "https://openrouter.ai/api/v1/chat/completions")

    def test_no_thinking_setting_means_no_reasoning_block(self):
        conf = self.config(openrouter_api_key="sk-or-test")
        with fake_urlopen(chat_reply("Done.")) as calls:
            cleanup.run("uh, done", conf, "the rules")
        self.assertNotIn("reasoning", sent_json(calls[0]))

    def test_an_answer_of_nothing_is_a_failure(self):
        conf = self.config(openrouter_api_key="sk-or-test")
        with fake_urlopen(chat_reply("")):
            with self.assertRaises(api.ApiError) as caught:
                cleanup.run("uh, done", conf, "the rules")
        self.assertIn("empty", str(caught.exception))

    def test_a_failure_is_the_same_kind_the_chain_already_catches(self):
        # worker, the file transcriber and the meeting all keep the raw
        # transcript when an ApiError comes out of here.
        self.assertTrue(issubclass(cleanup.CleanupError, api.ApiError))


class LocalLLM(DikteTest):
    def test_provider_accepts_local_llm(self):
        conf = self.config(cleanup_provider="local-llm")
        self.assertEqual(cleanup.provider(conf), "local-llm")

    def test_run_uses_the_local_server_when_configured(self):
        from unittest import mock
        conf = self.config(cleanup_provider="local-llm",
                           local_llm_model="gemma-3-4b-it.gguf")
        with mock.patch("api.serving", return_value="http://127.0.0.1:7777/v1") as svc, \
                mock.patch("api.cleanup", return_value="temiz metin") as cl:
            out = cleanup.run("raw metin", conf, "sysprompt")
        self.assertEqual(out, "temiz metin")
        _, kwargs = cl.call_args
        self.assertEqual(kwargs["provider"], "local-llm")
        self.assertIn("127.0.0.1:7777", kwargs["base_url"])


if __name__ == "__main__":
    unittest.main()
