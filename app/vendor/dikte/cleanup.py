"""Transkripti kimin temizlediği. (webapp)

Tek sağlayıcı OpenRouter. Masaüstünün Claude Code / Codex / yerel llama.cpp
yolları webapp'e taşınmaz.
"""

import api
from i18n import t

PROVIDERS = ("openrouter",)


class CleanupError(api.ApiError):
    pass


def provider(conf):
    chosen = conf["cleanup_provider"]
    return chosen if chosen in PROVIDERS else "openrouter"


def model(conf):
    return conf["cleanup_model"]


def run(text, conf, system_prompt, timeout=180, aborter=None):
    return api.cleanup(
        text, conf.openrouter_key(), conf["cleanup_model"], system_prompt,
        reasoning=conf["cleanup_reasoning"],
        base_url=conf["openrouter_base_url"], timeout=timeout, aborter=aborter,
    )
