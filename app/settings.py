import config as cfg

_SERVICES = ("transcribe", "cleanup", "assistant", "meeting")
_PROVIDERS = ("openai", "groq", "openrouter", "omniroute")


def _provider_fields(service, providers, local_extra):
    fields = {}
    fields[f"{service}_provider"] = ("select", list(providers) + ["local"])
    for p in providers:
        fields[f"{service}_{p}_url"] = ("str", [])
        fields[f"{service}_{p}_key"] = ("str", [])
        fields[f"{service}_{p}_model"] = ("str", [])
    fields[f"{service}_local_model"] = ("str", [])
    fields[f"{service}_local_threads"] = ("int", [])
    fields[f"{service}_local_gpu"] = ("bool", [])
    fields[f"{service}_local_preload"] = ("bool", [])
    for k in local_extra:
        fields[f"{service}_local_{k}"] = ("str", [])
    return fields


WEB_FIELDS = {
    "ui_language": ("select", ["auto", "tr", "en"]),
    "language": ("select", ["auto", "tr", "en"]),
    "transcribe_prompt": ("str", []),
    "skip_silent": ("bool", []),
    "silence_db": ("float", []),
    "speech_margin_db": ("float", []),
    "min_voiced_seconds": ("float", []),
    "filter_hallucinations": ("bool", []),
    "history_limit": ("int", []),
    "mic_target": ("str", []),
    "keep_audio": ("bool", []),
    "max_seconds": ("int", []),
    "file_timestamps": ("bool", []),
    "file_cleanup": ("bool", []),
    "file_cleanup_prompt": ("str", []),
    "cleanup_enabled": ("bool", []),
    "cleanup_reasoning": ("str", []),
    "cleanup_prompt": ("str", []),
    "meeting_cleanup": ("bool", []),
    "meeting_model": ("str", []),
    "meeting_reasoning": ("str", []),
    "meeting_prompt": ("str", []),
    "meeting_max_seconds": ("int", []),
    "meeting_keep_audio": ("bool", []),
    "meeting_self_name": ("str", []),
    "meeting_other_name": ("str", []),
    "meeting_participants": ("str", []),
    "assistant_reasoning": ("str", []),
    "assistant_prompt": ("str", []),
    "assistant_session_minutes": ("int", []),
    "assistant_timeout": ("int", []),
**_provider_fields("transcribe", _PROVIDERS, []),
**_provider_fields("cleanup", _PROVIDERS, ["context", "reasoning"]),
**_provider_fields("assistant", _PROVIDERS, ["context", "reasoning"]),
**_provider_fields("meeting", _PROVIDERS, []),
}

MASKED = {key for key in WEB_FIELDS if key.endswith("_key")}


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
