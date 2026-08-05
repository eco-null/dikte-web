

import unittest
from unittest import mock

import api
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

if __name__ == "__main__":
    unittest.main()
