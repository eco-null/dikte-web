import config as cfg

WEB_FIELDS = {
    "ui_language": ("select", ["auto", "tr", "en"]),
    "transcribe_provider": ("select", ["openai", "groq", "openrouter", "local"]),
    "transcribe_model": ("str", []),
    "groq_transcribe_model": ("str", []),
    "openrouter_transcribe_model": ("str", []),
    "openai_api_key": ("str", []),
    "groq_api_key": ("str", []),
    "openrouter_api_key": ("str", []),
    "language": ("select", ["auto", "tr", "en"]),
    "transcribe_prompt": ("str", []),
    "cleanup_enabled": ("bool", []),
    "cleanup_provider": ("select", ["openrouter", "local-llm"]),
    "cleanup_model": ("str", []),
    "cleanup_reasoning": ("str", []),
    "cleanup_prompt": ("str", []),
    "local_model": ("str", []),
    "local_threads": ("int", []),
    "local_gpu": ("bool", []),
    "local_preload": ("bool", []),
    "local_llm_model": ("str", []),
    "local_llm_threads": ("int", []),
    "local_llm_gpu": ("bool", []),
    "local_llm_context": ("int", []),
    "local_llm_preload": ("bool", []),
    "local_llm_reasoning": ("str", []),
    "mic_target": ("str", []),
    "keep_audio": ("bool", []),
    "max_seconds": ("int", []),
    "skip_silent": ("bool", []),
    "silence_db": ("float", []),
    "speech_margin_db": ("float", []),
    "min_voiced_seconds": ("float", []),
    "filter_hallucinations": ("bool", []),
    "history_limit": ("int", []),
    "file_timestamps": ("bool", []),
    "file_cleanup": ("bool", []),
    "file_cleanup_prompt": ("str", []),
    "meeting_cleanup": ("bool", []),
    "meeting_model": ("str", []),
    "meeting_reasoning": ("str", []),
    "meeting_prompt": ("str", []),
    "meeting_max_seconds": ("int", []),
    "meeting_keep_audio": ("bool", []),
    "meeting_self_name": ("str", []),
    "meeting_other_name": ("str", []),
    "meeting_participants": ("str", []),
    "assistant_provider": ("select", ["openrouter", "omniroute"]),
    "assistant_openrouter_model": ("str", []),
    "assistant_omniroute_base_url": ("str", []),
    "assistant_omniroute_model": ("str", []),
    "assistant_omniroute_api_key": ("str", []),
    "assistant_reasoning": ("str", []),
    "assistant_prompt": ("str", []),
    "assistant_session_minutes": ("int", []),
    "assistant_timeout": ("int", []),
}

MASKED = {"openai_api_key", "groq_api_key", "openrouter_api_key",
          "assistant_omniroute_api_key"}


def _coerce(key, raw):
    kind = WEB_FIELDS[key][0]
    if kind == "bool":
        return str(raw).lower() in ("1", "true", "on", "yes")
    if kind == "int":
        text = str(raw).strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None
    if kind == "float":
        text = str(raw).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return str(raw).strip()


def redact(key, value):
    if key in MASKED and value:
        return f"{value[:3]}…{value[-3:]}" if len(value) > 8 else "••••"
    return value


def present(conf):
    return {key: redact(key, conf[key]) for key in WEB_FIELDS}


def apply(conf, updates):
    for key, raw in (updates or {}).items():
        if key not in WEB_FIELDS:
            continue
        if key in MASKED and str(raw).strip() == redact(key, conf[key]):
            continue
        if key in MASKED and not str(raw).strip():
            continue
        value = _coerce(key, raw)
        if value is None:
            continue
        conf[key] = value
    conf.save()
