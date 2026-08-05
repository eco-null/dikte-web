

import unittest

import app.rms as rms
from tests.support import DikteTest, make_wav, silence, speech, tone

class Rms(DikteTest):
    def test_silence_is_near_zero(self):
        wav = make_wav(self.path("silence.wav"), silence(1.0))
        self.assertLess(max(rms.series(wav)), 0.02)

    def test_speech_reads_high(self):
        wav = make_wav(self.path("speech.wav"), speech(1.0))
        self.assertGreater(max(rms.series(wav)), 0.1)

    def test_series_length_is_blocks(self):
        wav = make_wav(self.path("tone.wav"), tone(1.0))
        series = rms.series(wav)
        self.assertEqual(len(series), 16)

    def test_values_stay_in_unit_range(self):
        wav = make_wav(self.path("loud.wav"), tone(1.0, amplitude=32767))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in rms.series(wav)))

    def test_a_missing_file_raises(self):
        with self.assertRaises(OSError):
            rms.series(str(self.path("nope.wav")))

if __name__ == "__main__":
    unittest.main()
