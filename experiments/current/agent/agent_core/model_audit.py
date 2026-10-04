"""Optional local audit primitives. No environment, credentials or network reads."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import uuid

_PRIVATE = re.compile(
    r"^(?:authorization|headers?|http_headers|.*(?:api[_-]?key|secret|password|credential).*|"
    r"(?:access|refresh|auth|bearer)[_-]?token|token|reasoning.*|thinking.*|"
    r"truth|private[_ -]?seeds?|(?:full[_ -]?)?hidden[_ -]?card|full[_ -]?card)$", re.I)
_SECRET = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9._~+/=-]+|"
    r"AKIA[A-Z0-9]{16})\b", re.I)
_ASSIGNMENT = re.compile(
    r"\b(?:api[_-]?key|secret|password|credential|(?:access|auth|refresh)[_-]?token)"
    r"[\"']?\s*[:=]\s*[\"']?[^\s,;\"'}]+", re.I)
_URL = re.compile(r"https?://[^\s\"'<>]+", re.I)


def sanitize(value, known_secrets=()):
    """Copy JSON values, elide private fields, redact known/recognizable secrets.

    Ordinary visible content strings are retained byte-for-byte unless redaction
    is required. Non-finite numbers become null; unsupported objects are omitted.
    This is defensive filtering, not a general secret-classification service.
    """
    if isinstance(value, dict):
        return {sanitize(str(k), known_secrets): sanitize(v, known_secrets)
                for k, v in value.items() if not _PRIVATE.match(str(k))}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, known_secrets) for v in value]
    if isinstance(value, str):
        # A reply/field may itself be a JSON-encoded string containing JSON.
        # Unwrap only for filtering, and retain its original bytes if unchanged.
        try:
            decoded_text = json.loads(value)
            if isinstance(decoded_text, str):
                cleaned_text = sanitize(decoded_text, known_secrets)
                if cleaned_text != decoded_text:
                    return json.dumps(cleaned_text, ensure_ascii=False, allow_nan=False)
        except (ValueError, RecursionError):
            pass
        # Filter private JSON fields before lexical replacements can invalidate
        # the object. The same path handles prose/code fences around an object.
        match = re.search(r"\{.*\}|\[.*\]", value, re.S)
        if match:
            try:
                decoded = json.loads(match[0])
                cleaned = sanitize(decoded, known_secrets)
                if cleaned != decoded:
                    replacement = json.dumps(cleaned, ensure_ascii=False, allow_nan=False)
                    return (sanitize(value[:match.start()], known_secrets) + replacement +
                            sanitize(value[match.end():], known_secrets))
            except (ValueError, RecursionError):
                pass
        # If a malformed/wrapped reply still names private JSON fields, do not
        # guess their value boundaries or retain a potentially private fragment.
        if any(_PRIVATE.match(m[1]) for m in re.finditer(r'''["']([^"']+)["']\s*:''', value)):
            return "[REDACTED_PRIVATE_CONTENT]"
        text = value
        for secret in sorted((s for s in known_secrets if s), key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        text = _SECRET.sub("[REDACTED]", text)
        text = _ASSIGNMENT.sub("[REDACTED]", text)
        text = _URL.sub(lambda m: "[REDACTED_URL]" if "?" in m[0] or "@" in m[0] else m[0], text)
        return text
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value, (bool, int)):
        return value
    return None


class JsonlAuditSink:
    """Explicit exclusive stream, synchronous append + fsync; one sink per process.

    Caller owns the directory/path. Existing files are refused rather than
    overwritten. Sink errors propagate to the client, which stops new requests.
    """
    def __init__(self, path):
        self.path = Path(path)
        self._stream = self.path.open("x", encoding="utf-8")

    def __call__(self, event):
        record = sanitize(event)
        record["event_id"] = uuid.uuid4().hex
        line = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        self._stream.write(line)
        self._stream.flush()
        os.fsync(self._stream.fileno())

    def close(self):
        self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
