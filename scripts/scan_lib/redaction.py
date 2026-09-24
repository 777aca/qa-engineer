"""在采集和落盘边界移除凭据，不保留凭据前缀。"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE = re.compile(r"password|passwd|pwd|secret|token|authorization|cookie|api[-_]?key|credential", re.I)


class Redactor:
    def __init__(self, secrets: list[str] | None = None):
        self.secrets = set(secrets or []) - {""}

    def remember(self, secret: str) -> None:
        if not isinstance(secret, str):
            raise ValueError("凭据值必须是字符串")
        if secret:
            self.secrets.add(secret)

    def text(self, value: str) -> str:
        for secret in sorted(self.secrets, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>;,]+", "Bearer [REDACTED]", value)
        value = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED]", value)
        value = re.sub(
            r'''(?ix)(["']?(?:password|passwd|pwd|secret|(?:access[_-]?|refresh[_-]?)?token|authorization|cookie|api[_-]?key)["']?\s*[:=]\s*)("[^"\n]*"|'[^'\n]*'|[^\s&,;]+)''',
            lambda match: match.group(1) + "[REDACTED]", value,
        )
        return re.sub(r"https?://[^\s<>\"']+", lambda match: self.url(match.group(0)), value)

    def url(self, value: str) -> str:
        try:
            parts = urlsplit(value)
            host = parts.netloc.rsplit("@", 1)[-1]
            query = urlencode([(key, "[REDACTED]" if SENSITIVE.search(key) else val)
                               for key, val in parse_qsl(parts.query, keep_blank_values=True)])
            return urlunsplit((parts.scheme, host, parts.path, query, ""))
        except ValueError:
            return "[INVALID URL]"

    def clean(self, value: object) -> object:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {str(key): "[REDACTED]" if SENSITIVE.search(str(key)) else self.clean(item)
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.clean(item) for item in value]
        return value
