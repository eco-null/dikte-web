"""Yüklenen kaydın RMS serisi: VAD sessizlik kontrolü için.

16 kHz mono WAV üzerinde meeting.rms_series kullanır; blok boyutu worker ile
aynı (1024 örnek) olduğundan CHUNK_SECONDS uyumludur.
"""

import meeting

LEVEL_FRAMES = 1024
RATE = 16000
CHUNK_SECONDS = LEVEL_FRAMES / RATE


def series(wav_path):
    return meeting.rms_series(wav_path)
