"""Transkripti kimin temizlediği. (webapp)

İki sağlayıcı: OpenRouter ve yerel llama.cpp (local-llm). Yerel yol, masaüstünün
llama.cpp kurulumunu webapp'e taşır; diğer masaüstü yolları taşınmaz.
"""

import api
import ggml
from i18n import t

PROVIDERS = ("openrouter", "local-llm")


class CleanupError(api.ApiError):
    pass


def provider(conf):
    chosen = conf["cleanup_provider"]
    return chosen if chosen in PROVIDERS else "openrouter"


def model(conf):
    return conf["cleanup_model"]


def run(text, conf, system_prompt, timeout=180, aborter=None):
    if provider(conf) == "local-llm":
        return api.cleanup(
            text, "", conf["local_llm_model"], system_prompt,
            reasoning=conf["local_llm_reasoning"],
            base_url=api.serving(ggml.llm), timeout=timeout,
            provider="local-llm", service=t("Local llama.cpp"),
            aborter=aborter,
        )
    return api.cleanup(
        text, conf.openrouter_key(), conf["cleanup_model"], system_prompt,
        reasoning=conf["cleanup_reasoning"],
        base_url=conf["openrouter_base_url"], timeout=timeout, aborter=aborter,
    )
