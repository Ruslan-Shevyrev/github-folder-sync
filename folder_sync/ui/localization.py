"""Look up messages by key, with Russian as the fallback language."""

import re
from string import Formatter

from .translations import CATALOGS, DEFAULT_LANGUAGE, LANGUAGES


_language = DEFAULT_LANGUAGE
_default_messages = CATALOGS[DEFAULT_LANGUAGE].MESSAGES


def set_language(language):
    global _language
    _language = language if isinstance(language, str) and language in CATALOGS else DEFAULT_LANGUAGE


def tr(key, **values):
    messages = CATALOGS[_language].MESSAGES
    text = messages.get(key, _default_messages.get(key, key))
    return text.format(**values) if values else text


def error_text(message):
    """Translate rendered Git, settings and cache errors from older snapshots."""
    if _language == DEFAULT_LANGUAGE:
        return message
    key = _source_keys.get(message)
    if key is not None:
        return tr(key)
    for pattern, key in _error_patterns:
        match = pattern.fullmatch(message)
        if match:
            return tr(key, **match.groupdict())
    return message


_source_keys = {
    text: key for key, text in _default_messages.items() if key.startswith("error.")
}
_error_patterns = [
    (re.compile("".join(re.escape(text) + (f"(?P<{field}>.+?)" if field else "")
                        for text, field, _, _ in Formatter().parse(source))), key)
    for source, key in _source_keys.items()
    if "{" in source and "v{" not in source and "\n" not in source
]
