"""Natural, user-safe projections of durable runtime decisions."""

from __future__ import annotations

from dataclasses import dataclass

from sira_agents.kernel_models import (
    Clarify,
    Complete,
    FailSafely,
    RequestApproval,
    Respond,
    TurnDecision,
    UserEvent,
    WaitForExternal,
)


@dataclass(frozen=True, slots=True)
class ComposedResponse:
    message: str
    event: UserEvent
    terminal_status: str


class ResponseComposer:
    """Keep provider, tool, checkpoint, and internal state language out of chat."""

    def compose(self, decision: TurnDecision) -> ComposedResponse:
        if isinstance(decision, Respond):
            return ComposedResponse(
                decision.message,
                UserEvent(kind="work_completed", message="A response is ready."),
                "COMPLETED",
            )
        if isinstance(decision, Clarify):
            return ComposedResponse(
                decision.question,
                UserEvent(kind="clarification_needed", message=decision.reason),
                "WAITING",
            )
        if isinstance(decision, RequestApproval):
            return ComposedResponse(
                decision.summary,
                UserEvent(kind="approval_needed", message=decision.summary),
                "WAITING",
            )
        if isinstance(decision, WaitForExternal):
            return ComposedResponse(
                "I'm waiting for the requested information. Your confirmed work is saved.",
                UserEvent(kind="waiting", message=decision.reason),
                "WAITING",
            )
        if isinstance(decision, Complete):
            return ComposedResponse(
                decision.message,
                UserEvent(kind="work_completed", message="The requested work is complete."),
                "COMPLETED",
            )
        if isinstance(decision, FailSafely):
            return ComposedResponse(
                decision.message,
                UserEvent(
                    kind="could_not_complete",
                    message=decision.message,
                    retryable=decision.retryable,
                ),
                "FAILED",
            )
        raise TypeError("tool proposals must be executed before composing a response")
