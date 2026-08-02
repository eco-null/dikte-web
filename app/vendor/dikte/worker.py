"""Dikte zinciri: transcribe → cleanup → sonuç. (webapp)

Pano, yapıştırma, audio.py ve Qt yoktur. Pipeline senkron `run()` döndürür ve
aşamaları `stage` sinyaliyle yayar. `ask=True` transkripti ajan'a gönderir.
"""

import os
import sys
import time

import api
import assistant
import cleanup
import config as cfg
import i18n
import vad
from i18n import t
from .signals import Signal

LEVEL_FRAMES = 1024      # meeting.rms_series ile aynı blok
RATE = 16000
CHUNK_SECONDS = LEVEL_FRAMES / RATE


class Pipeline:
    stage = Signal()

    def __init__(self, conf):
        self.conf = conf

    def run(self, wav_path, duration, rms_values=(), ask=False):
        """Zinciri çağıran thread'de çalıştırır; (raw, text, warning) döndürür.

        Başarısızlıkta api.ApiError fırlatır; cleanup hatası transkripti
        korur ve warning olarak raporlar (dikte felsefesi).
        """
        conf = self.conf
        started = time.monotonic()
        raw = ""

        if conf["skip_silent"]:
            stats = vad.analyse(rms_values, CHUNK_SECONDS, conf["speech_margin_db"])
            if vad.is_silent(stats, conf["silence_db"], conf["speech_margin_db"],
                             conf["min_voiced_seconds"]):
                self._discard(wav_path)
                raise api.ApiError(t("No speech detected ({level} dB)",
                                     level=round(stats["speech_db"])))

        self.stage.emit(t("Transcribing…"))
        target = conf.transcribe_target()
        raw = api.transcribe(target, wav_path, language=conf["language"],
                             prompt=conf["transcribe_prompt"])

        if conf["filter_hallucinations"] and vad.looks_like_hallucination(raw, duration):
            self._discard(wav_path)
            raise api.ApiError(t("Discarded a stock phrase: “{text}”", text=raw[:60]))

        text = raw
        warning = ""
        if (conf["assistant_cleanup"] if ask else conf["cleanup_enabled"]):
            self.stage.emit(t("Cleaning up…"))
            try:
                text = cleanup.run(raw, conf, conf.cleanup_prompt())
            except api.ApiError as exc:
                text = raw
                warning = str(exc)
                print(f"dikte: cleanup failed: {exc}", file=sys.stderr)

        question = ""
        if ask:
            question = text
            self.stage.emit(t("Asking {name}…", name=i18n.name(
                assistant.display_name(conf), "dative")))
            text, denied = assistant.ask(question, conf, on_stage=self.stage.emit)
            warning = "\n".join(x for x in (warning, denied) if x)

        cfg.append_history({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": round(duration, 1),
            "elapsed": round(time.monotonic() - started, 1),
            "model": target.model,
            "cleanup_model": cleanup.model(conf) if conf["cleanup_enabled"] else "",
            "cleanup_error": warning,
            "mode": "ask" if ask else "",
            "question": question,
            "assistant_model": conf["assistant_model"] if ask else "",
            "raw": raw,
            "text": text,
        })
        try:
            cfg.trim_history(conf["history_limit"])
        except OSError as exc:
            print(f"dikte: could not trim the history: {exc}", file=sys.stderr)
        self._discard(wav_path)
        return raw, text, warning

    def _discard(self, wav_path):
        if not os.path.exists(wav_path):
            return
        try:
            os.unlink(wav_path)
        except OSError:
            pass
