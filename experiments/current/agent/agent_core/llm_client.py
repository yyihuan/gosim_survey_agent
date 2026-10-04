"""A tiny OpenAI-compatible chat client, configured through environment variables.
Defaults to the Kimi Coding Plan endpoint, since that is what this example ships with;
any other OpenAI-compatible `/chat/completions` endpoint works too by overriding the
base URL and model:

    OPENAI_BASE_URL   default https://api.kimi.com/coding/v1 (see README for the
                      api.kimi.ai alternative for accounts outside mainland China)
    OPENAI_MODEL      default "k3"
    OPENAI_API_KEY    bearer token (KIMI_API_KEY is also accepted)

See https://www.kimi.com/code/docs/en/ for the Kimi Coding Plan API. This client never
sets or overrides the HTTP User-Agent header -- whatever Python's standard library
sends by default is left alone.

Every call has a timeout (default 12 s) and the whole run has a total time budget
(default 300 s) and a call cap (default 100), so the two LLM-advised planning steps
stay well inside the 900 s wall clock. A call that fails or times out is retried up to
`max_retries` times; if all of those fail, that one planning step falls back to its
rule-based answer for this night -- the next night's calls still go through normally.

Standard library only (urllib) so the example has zero third-party dependencies.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Optional

from .model_audit import sanitize

DEFAULT_BASE_URL = "https://api.kimi.com/coding/v1"
DEFAULT_MODEL = "k3"
_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


def _reject_constant(value: str):
    raise ValueError(f"non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON number exceeds finite float range")
    return number


def _load_json(text: str):
    return json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float)


class MissingAPIKeyError(RuntimeError):
    pass


def require_api_key() -> None:
    """Raise MissingAPIKeyError if neither OPENAI_API_KEY nor KIMI_API_KEY is set.
    Called once at process startup, before reading anything from stdin."""
    if os.environ.get("USE_LLM", "1") == "0":
        return
    if not (os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("KIMI_API_KEY", "").strip()):
        raise MissingAPIKeyError("missing API key: set OPENAI_API_KEY")


class LLMClient:
    def __init__(self, log=lambda text: None, call_timeout_seconds: float = 12.0,
                 total_budget_seconds: float = 300.0, max_calls: int = 100, max_retries: int = 3,
                 *, audit_sink=None, transport=None):
        self.log = log
        self.enabled = os.environ.get("USE_LLM", "1") != "0"
        self.base_url = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/") or DEFAULT_BASE_URL
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("KIMI_API_KEY", "").strip()
        self.model = os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
        self.call_timeout_seconds = call_timeout_seconds
        self.total_budget_seconds = total_budget_seconds
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.spent_seconds = 0.0
        self.calls_made = 0
        self.transport_calls_made = 0
        self.audit_sink = audit_sink
        self.transport = transport
        self.audit_failed = False
        self.last_question_id = None
        self.last_request_id = None
        self._attempt_record = {}

    def _known_secrets(self):
        try:
            url = urllib.parse.urlsplit(self.base_url)
        except ValueError:
            return (self.api_key,)
        return (self.api_key, url.password,
                *(v for _, v in urllib.parse.parse_qsl(url.query)))

    def safe_text(self, text):
        return sanitize(text, self._known_secrets())

    def _audit(self, event):
        if self.audit_sink is None:
            return True
        if self.audit_failed:
            return False
        try:
            record = {"schema_version": "model-audit-v1",
                      "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                      "transport_mode": "offline" if not self.enabled else
                                        "fake" if self.transport is not None else "provider",
                      "question_id": self.last_question_id,
                      "request_id": self.last_request_id,
                      "calls_made": self.calls_made,
                      "transport_calls_made": self.transport_calls_made, **event}
            self.audit_sink(sanitize(record, self._known_secrets()))
            return True
        except Exception:
            # Never stringify a sink exception; it may include the input or a URL.
            self.audit_failed = True
            self.log("llm: audit sink failed; further model requests disabled")
            return False

    def audit_consumption(self, *, question_id, request_id, context, outcome, reason,
                          accepted_fields=(), rejected_fields=()):
        """Planner consumption is separate from the transport's parsed result."""
        self._audit({"event_type": "model_consumption", "question_id": question_id,
                     "request_id": request_id, "context": context, "outcome": outcome,
                     "reason": reason, "accepted_fields": list(accepted_fields),
                     "rejected_fields": list(rejected_fields)})

    def _budget_left(self, wallclock_remaining_seconds: float) -> float:
        # Never let a model call eat into the last minute of wall clock, and never
        # exceed this run's own LLM time allowance.
        values = (wallclock_remaining_seconds, self.call_timeout_seconds,
                  self.total_budget_seconds, self.spent_seconds)
        try:
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in values):
                return 0.0
        except OverflowError:
            return 0.0
        return min(self.call_timeout_seconds, self.total_budget_seconds - self.spent_seconds,
                   max(0.0, wallclock_remaining_seconds - 60.0))

    def _attempt(self, system_prompt: str, user_payload: dict, timeout: float) -> dict:
        """One HTTP attempt. Raises on any problem; the caller retries or gives up."""
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            "temperature": 0,
            "max_tokens": 250,
        }
        body = json.dumps(request_body).encode("utf-8")
        self._attempt_record["parse_status"] = "not_received"
        if not self._audit({"event_type": "model_request", "request": request_body,
                            "timeout_seconds": timeout,
                            "attempt_number": self._attempt_record["attempt_number"]}):
            raise ValueError("audit unavailable")
        request = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
        )
        self.transport_calls_made += 1
        with (self.transport or urllib.request.urlopen)(request, timeout=timeout) as response:
            self._attempt_record["parse_status"] = "invalid_envelope"
            data = _load_json(response.read().decode("utf-8"))
        if isinstance(data, dict) and isinstance(data.get("usage"), dict):
            usage = {k: v for k, v in data["usage"].items()
                     if k in ("prompt_tokens", "completion_tokens", "total_tokens")
                     and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
            self._attempt_record["usage"] = usage or None
        text = data["choices"][0]["message"]["content"]
        self._attempt_record["parse_status"] = "invalid_content"
        if not isinstance(text, str):
            raise ValueError("model content was not text")
        self._attempt_record["raw_content"] = text
        self._attempt_record["parse_status"] = "invalid_json"
        try:
            parsed = _load_json(text)
        except json.JSONDecodeError:
            # Retain support for prose/code fences around an object, but never
            # unwrap a syntactically valid array or scalar as an object.
            match = _JSON_OBJECT.search(text)
            if not match:
                raise ValueError("no JSON object in model reply")
            parsed = _load_json(match.group(0))
        if not isinstance(parsed, dict):
            self._attempt_record["parse_status"] = "not_object"
            raise ValueError("model reply was not a JSON object")
        self._attempt_record.update(parsed=parsed, parse_status="parsed")
        return parsed

    def ask_json(self, system_prompt: str, user_payload: dict, wallclock_remaining_seconds: float) -> Optional[dict]:
        """One planning question, answered as exactly one JSON object. Retries up to
        `max_retries` times on failure; returns None once the budget/call cap/retries
        are exhausted, so the caller's rule-based answer can take over for this step."""
        self.last_question_id = uuid.uuid4().hex
        self.last_request_id = None
        def skipped(reason):
            self._audit({"event_type": "model_skipped", "reason": reason,
                         "raw_content": None, "parsed": None, "usage": None})
            return None
        if self.audit_failed:
            return None
        if not self.enabled:
            return skipped("offline")
        # The input is a snapshot, not a fresh allowance for every retry.
        if self._budget_left(wallclock_remaining_seconds) < 1.5:
            self.log("llm: LLM time budget exhausted; using the rule-based path")
            return skipped("time_budget_exhausted")
        question_started = time.monotonic()
        last_error: Optional[Exception] = None
        for _attempt_number in range(self.max_retries):
            if self.calls_made >= self.max_calls:
                self.log("llm: call cap reached for this run; using the rule-based path")
                return skipped("call_cap_reached")
            elapsed = max(0.0, time.monotonic() - question_started)
            timeout = self._budget_left(max(0.0, wallclock_remaining_seconds - elapsed))
            if timeout < 1.5:
                self.log("llm: LLM time budget exhausted; using the rule-based path")
                return skipped("time_budget_exhausted")
            started = time.monotonic()
            self.calls_made += 1
            self.last_request_id = uuid.uuid4().hex
            self._attempt_record = {"attempt_number": _attempt_number + 1,
                                    "raw_content": None, "parsed": None, "usage": None,
                                    "parse_status": "not_received"}
            answer = None
            failure = None
            try:
                answer = self._attempt(system_prompt, user_payload, timeout)
                if time.monotonic() - started > timeout:
                    raise TimeoutError("model reply arrived after its allowance")
            except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError,
                    OverflowError, RecursionError) as exc:
                last_error = exc
                failure = type(exc).__name__
            finally:
                latency = time.monotonic() - started
                self.spent_seconds += latency
                audited = self._audit({"event_type": "model_result", **self._attempt_record,
                                       "latency_seconds": latency, "spent_seconds": self.spent_seconds,
                                       "outcome": "success" if failure is None else "failed",
                                       "error_type": failure,
                                       "reason": "reply_accepted" if failure is None else
                                                 "attempt_failed"})
            if not audited or self.audit_failed:
                return None
            if failure is None:
                return answer
        self.log(f"llm: call failed after {self.max_retries} attempts ({type(last_error).__name__}); "
                 "this step falls back to its rule-based answer")
        return None
