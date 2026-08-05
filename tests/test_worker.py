

import unittest
from unittest import mock

import api
import assistant
import cleanup
import worker
from tests.support import (DikteTest, fake_urlopen, make_wav, silence,
                           speech, url_error)

class Pipeline(DikteTest):
    def conf(self, **over):
        values = {"transcribe_provider": "openai",
                  "transcribe_openai_key": "sk-test",
                  "cleanup_openrouter_key": "sk-clean",
                  "skip_silent": True, "cleanup_enabled": False}
        values.update(over)
        return self.config(**values)

    def test_silence_is_refused_without_an_api_call(self):
        clip = make_wav(self.path("silent.wav"), silence(1.0))
        p = worker.Pipeline(self.conf())
        with mock.patch("api.transcribe") as transcribe:
            with self.assertRaises(api.ApiError) as cm:
                p.run(clip, 1.0, [0.0] * 10)
        transcribe.assert_not_called()
        self.assertIn("No speech detected", str(cm.exception))

    def test_a_recording_comes_back_as_text(self):
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        p = worker.Pipeline(self.conf())
        stages = []
        p.stage.connect(stages.append)
        with fake_urlopen({"text": "merhaba dünya"}):
            raw, text, warning = p.run(clip, 1.0, [0.0005] * 40 + [0.2] * 20)
        self.assertEqual(text, "merhaba dünya")
        self.assertIn("Transcribing…", stages)

    def test_cleanup_failure_keeps_the_transcript_as_warning(self):
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        p = worker.Pipeline(self.conf(cleanup_enabled=True))
        with fake_urlopen({"text": "ham metin"}, url_error("boom")):
            raw, text, warning = p.run(clip, 1.0, [0.0005] * 40 + [0.2] * 20)
        self.assertEqual(text, "ham metin")
        self.assertTrue(warning)

    def test_history_is_appended(self):
        import config as cfg
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        p = worker.Pipeline(self.conf())
        with fake_urlopen({"text": "kayıt"}):
            p.run(clip, 1.0, [0.0005] * 40 + [0.2] * 20)
        self.assertEqual(len(cfg.read_history()), 1)

class ProviderKeys(DikteTest):
    """A job needs only its own provider's key: setting transcribe_groq_key
    must not make a groq dictation ask OpenAI for one, and an OmniRoute job
    must run with no key at all."""

    # (provider, the key value, the bearer token the request should carry)
    HOSTED = (
        ("openai", "sk-oai", "Bearer sk-oai"),
        ("groq", "gsk-groq", "Bearer gsk-groq"),
        ("openrouter", "sk-or", "Bearer sk-or"),
        ("omniroute", None, None),
    )

    def conf_for(self, service, provider, key, **extra):
        values = {f"{service}_provider": provider}
        if key:
            values[f"{service}_{provider}_key"] = key
        values.update(extra)
        return self.config(**values)

    def check_token(self, calls, expected):
        if expected is None:
            self.assertIsNone(calls[0].get_header("Authorization"))
        else:
            self.assertEqual(calls[0].get_header("Authorization"), expected)

    def test_each_provider_dictates_with_its_own_key(self):
        for provider, key, expected in self.HOSTED:
            with self.subTest(provider=provider):
                clip = make_wav(self.path("clip.wav"), speech(1.0))
                conf = self.conf_for("transcribe", provider, key,
                                     skip_silent=True, cleanup_enabled=False)
                with fake_urlopen({"text": "merhaba"}) as calls:
                    raw, text, warning = worker.Pipeline(conf).run(
                        clip, 1.0, [0.0005] * 40 + [0.2] * 20)
                self.assertEqual(text, "merhaba")
                self.check_token(calls, expected)

    def test_each_provider_cleans_up_with_its_own_key(self):
        reply = {"choices": [{"message": {"content": "temiz"}}]}
        for provider, key, expected in self.HOSTED:
            with self.subTest(provider=provider):
                conf = self.conf_for("cleanup", provider, key)
                with fake_urlopen(reply) as calls:
                    text = cleanup.run("ham metin", conf, "temizle")
                self.assertEqual(text, "temiz")
                self.check_token(calls, expected)

    def test_each_provider_answers_with_its_own_key(self):
        reply = {"choices": [{"message": {"content": "cevap"}}]}
        for provider, key, expected in self.HOSTED:
            with self.subTest(provider=provider):
                conf = self.conf_for("assistant", provider, key)
                with fake_urlopen(reply) as calls:
                    answer, _ = assistant.ask("selam", conf)
                self.assertEqual(answer, "cevap")
                self.check_token(calls, expected)

    def test_the_local_llm_takes_no_key(self):
        conf = self.config(assistant_provider="local",
                           assistant_local_model="gemma.gguf")
        with mock.patch("api.serving", return_value="http://127.0.0.1:9001/v1"), \
                fake_urlopen({"choices": [{"message": {"content": "cevap"}}]}) as calls:
            answer, _ = assistant.ask("selam", conf)
        self.assertEqual(answer, "cevap")
        self.assertIsNone(calls[0].get_header("Authorization"))

    def test_a_missing_key_is_reported_for_the_provider_that_lacks_it(self):
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        with self.assertRaises(api.ApiError) as caught:
            worker.Pipeline(self.config(transcribe_provider="groq",
                                        skip_silent=True, cleanup_enabled=False)) \
                .run(clip, 1.0, [0.0005] * 40 + [0.2] * 20)
        self.assertIn("Groq", str(caught.exception))
        self.assertNotIn("OpenAI", str(caught.exception))

if __name__ == "__main__":
    unittest.main()
