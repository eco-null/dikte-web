import meeting

LEVEL_FRAMES = 1024
RATE = 16000
CHUNK_SECONDS = LEVEL_FRAMES / RATE


def series(wav_path):
    return meeting.rms_series(wav_path)
