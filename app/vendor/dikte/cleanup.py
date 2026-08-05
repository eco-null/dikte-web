"""Transkripti kimin temizlediği. (webapp)

Beş sağlayıcı: openai, groq, openrouter, omniroute ve yerel llama.cpp (local).
Yerel yol, masaüstünün llama.cpp kurulumunu webapp'e taşır; diğer masaüstü
yolları taşınmaz.
"""

import api
import ggml
from i18n import t

PROVIDERS = ("openai", "groq", "openrouter", "omniroute", "local")


class CleanupError(api.ApiError):
    pass


def provider(conf):
    chosen = conf["cleanup_provider"]
    return chosen if chosen in PROVIDERS else "openrouter"


def model(conf):
    return conf[f"cleanup_{provider(conf)}_model"]


def run(text, conf, system_prompt, timeout=180, aborter=None):
    name = provider(conf)
    if name == "local":
        target = conf.cleanup_target()
        return api.cleanup(
            text, api_key="", model=target.model, system_prompt=system_prompt,
            reasoning=conf["cleanup_local_reasoning"],
            base_url=api.serving(ggml.llm), timeout=timeout,
            provider="local-llm", service=t("Local llama.cpp"),
            aborter=aborter,
        )
    target = conf.cleanup_target()
    key_required = name != "omniroute"
    if key_required and not target.api_key:
        raise api.ApiError(t("{service} API key is empty. Add it in Settings.",
                             service=target.service))
    return api.cleanup(
        text, api_key=target.api_key, model=target.model,
        system_prompt=system_prompt, reasoning=conf["cleanup_reasoning"],
        base_url=target.base_url, timeout=timeout,
        provider=name, service=target.service, aborter=aborter,
    )
