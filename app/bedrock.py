"""The Amazon Bedrock boundary. One class, one place, always optional.

Incident Book calls a model in exactly one situation, described in
``drafting.py``: a member of staff has just been threatened, they have said or
typed a few words about it, and those few words have to become the detailed
description that statute field (C) asks for and the consequences that field (H)
asks for. Everything else in this app, including every classification that
feeds the statutory log, stays human-chosen. A model picking "stranger with
criminal intent" off a motion event is exactly the accusation this product
refuses to make.

Three rules the upgrade brief sets, enforced here rather than at each call
site:

1. **A timeout on every call.** Set on the botocore client, so a hung socket
   cannot outlive it.
2. **A fallback when Bedrock is unreachable.** Every failure -- no boto3, no
   credentials, a throttle, a timeout, a model this account cannot invoke --
   arrives at the caller as one exception, ``BedrockUnavailable``. The caller
   branches once, and ``drafting.py``'s fallback keeps the staff member's own
   words rather than losing them.
3. **Tests that pass with the call stubbed.** ``StubRunner`` ships in the
   package, not in the test folder, because ``INCIDENT_BOOK_BEDROCK=off`` runs
   the whole app with no AWS account at all. That is also how the demo survives
   a conference wifi network.

Model choice. Sonnet, not Opus: this is a short rewriting task where the person
is standing at a counter waiting, and latency is the thing they feel. The id is
a preference chain rather than a constant because the build brief names
``anthropic.claude-sonnet-5`` and this account cannot invoke it yet. The chain tries the brief's model first, so
the build upgrades itself the day access lands, and falls to the inference
profile that answers today.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

# Tried in order. The first that answers is cached for the life of the process.
MODEL_PREFERENCE = (
    "us.anthropic.claude-sonnet-5",
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)
DEFAULT_REGION = (
    os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
)
READ_TIMEOUT = float(os.environ.get("INCIDENT_BOOK_BEDROCK_TIMEOUT", "20"))
CONNECT_TIMEOUT = 4.0


class BedrockUnavailable(RuntimeError):
    """Bedrock could not be reached, or could not answer.

    Deliberately one type for every cause. The caller's job is to fall back,
    and the fallback is the same whether the credentials were missing or the
    socket timed out. The reason is kept so the screen can say which it was
    and the friction log can quote it.
    """

    def __init__(self, reason: str, cause: Optional[BaseException] = None):
        self.reason = reason
        self.cause = cause
        super().__init__(reason)


class BedrockRunner:
    """A timeout-bounded wrapper over the Bedrock Converse API."""

    def __init__(
        self,
        models: tuple[str, ...] = MODEL_PREFERENCE,
        region: str = DEFAULT_REGION,
        read_timeout: float = READ_TIMEOUT,
        client: Any = None,
    ):
        override = os.environ.get("INCIDENT_BOOK_BEDROCK_MODEL")
        self.models = (override,) if override else tuple(models)
        self.region = region
        self.read_timeout = read_timeout
        self._client = client
        self._resolved: Optional[str] = None

    @property
    def model_id(self) -> str:
        """The model actually in use, or the first one we will try."""
        return self._resolved or self.models[0]

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise BedrockUnavailable("boto3 is not installed", exc) from exc
        try:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                config=Config(
                    connect_timeout=CONNECT_TIMEOUT,
                    read_timeout=self.read_timeout,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )
        except Exception as exc:
            raise BedrockUnavailable(f"no bedrock-runtime client: {exc}", exc) from exc
        return self._client

    def converse(
        self,
        system: str,
        user_text: str,
        tool: Optional[dict] = None,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ) -> dict:
        """One Converse call, walking the model preference chain.

        ``tool`` forces structured output: pass a tool spec and the model has
        to answer by calling it, which is how ``drafting.py`` gets two named
        fields back instead of prose it would then have to split.
        """
        client = self._get_client()
        candidates = (self._resolved,) if self._resolved else self.models
        started = time.monotonic()
        last: Optional[BaseException] = None
        for model_id in candidates:
            kwargs: dict[str, Any] = {
                "modelId": model_id,
                "system": [{"text": system}],
                "messages": [{"role": "user", "content": [{"text": user_text}]}],
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                },
            }
            if tool is not None:
                kwargs["toolConfig"] = {
                    "tools": [{"toolSpec": tool}],
                    "toolChoice": {"tool": {"name": tool["name"]}},
                }
            try:
                response = client.converse(**kwargs)
            except Exception as exc:
                last = exc
                if _is_entitlement_error(exc):
                    continue  # this account cannot call that one; try the next
                raise BedrockUnavailable(f"{type(exc).__name__}: {exc}", exc) from exc
            self._resolved = model_id
            return _unpack(response, model_id, time.monotonic() - started)
        raise BedrockUnavailable(
            f"no model in {list(self.models)} is available to this account: {last}", last
        )

    def available(self) -> tuple[bool, str]:
        """Is Bedrock reachable right now? Asked once when the draft screen
        renders, so the screen can offer the right thing rather than offering
        a button that will fail."""
        try:
            self.converse(
                system="Answer with one word.",
                user_text="Reply with exactly: ok",
                max_tokens=8,
            )
            return True, f"{self.model_id} answered"
        except BedrockUnavailable as exc:
            return False, exc.reason


def _is_entitlement_error(exc: BaseException) -> bool:
    """AccessDenied and ValidationException both mean 'not this model, on this
    account, this way'. Both are worth retrying against the next id in the
    chain; a throttle or a timeout is not."""
    name = type(exc).__name__
    return name in (
        "AccessDeniedException",
        "ValidationException",
        "ResourceNotFoundException",
    ) or (
        "is not available for this account" in str(exc)
        or "on-demand throughput isn" in str(exc)
    )


def _unpack(response: dict, model_id: str, elapsed: float) -> dict:
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    return {
        "text": "".join(b.get("text", "") for b in blocks if "text" in b).strip(),
        "tool_input": next(
            (b["toolUse"].get("input") for b in blocks if "toolUse" in b), None
        ),
        "stop_reason": response.get("stopReason"),
        "usage": response.get("usage", {}),
        "latency_seconds": round(elapsed, 2),
        "model_id": model_id,
    }


class StubRunner(BedrockRunner):
    """A runner that never calls AWS.

    Selected by ``INCIDENT_BOOK_BEDROCK=off`` and used by every test that
    exercises a drafting path. ``replies`` is a queue: an empty queue raises
    ``BedrockUnavailable``, which is how the offline behaviour gets tested
    without unplugging anything.
    """

    def __init__(self, replies: Optional[list] = None, model_id: str = "stub-model"):
        super().__init__(models=(model_id,), client=object())
        self.replies = list(replies or [])
        self.calls: list[dict] = []

    def converse(self, system, user_text, tool=None, max_tokens=1200, temperature=0.2):
        self.calls.append({"system": system, "user_text": user_text, "tool": tool})
        if not self.replies:
            raise BedrockUnavailable("stub runner has no reply queued")
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return {
            "text": reply.get("text", ""),
            "tool_input": reply.get("tool_input"),
            "stop_reason": reply.get("stop_reason", "tool_use"),
            "usage": reply.get("usage", {}),
            "latency_seconds": 0.0,
            "model_id": self.models[0],
        }

    def available(self):
        return bool(self.replies), "stub runner"


def build_runner() -> BedrockRunner:
    """One switch: ``INCIDENT_BOOK_BEDROCK=off`` gets a stub that always says
    it is unavailable, which is the same path a dead network takes."""
    if os.environ.get("INCIDENT_BOOK_BEDROCK", "").lower() in ("off", "0", "false", "no"):
        return StubRunner(model_id="disabled (INCIDENT_BOOK_BEDROCK=off)")
    return BedrockRunner()
