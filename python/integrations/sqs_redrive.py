"""Safe SQS DLQ inspection and native redrive operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class SqsRedriveClient(Protocol):
    def get_queue_attributes(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def list_message_move_tasks(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def start_message_move_task(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def cancel_message_move_task(self, **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class DlqStatus:
    queue_arn: str
    visible_messages: int
    in_flight_messages: int
    delayed_messages: int
    tasks: tuple[dict[str, Any], ...]


@dataclass(slots=True)
class SqsDlqOperator:
    client: SqsRedriveClient
    dlq_url: str

    def status(self) -> DlqStatus:
        attributes = self.client.get_queue_attributes(
            QueueUrl=self.dlq_url,
            AttributeNames=[
                "QueueArn",
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ],
        ).get("Attributes", {})
        if not isinstance(attributes, Mapping):
            raise RuntimeError("SQS did not return queue attributes")
        queue_arn = str(attributes.get("QueueArn", ""))
        if not queue_arn.startswith("arn:"):
            raise RuntimeError("SQS did not return the DLQ ARN")
        task_payload = self.client.list_message_move_tasks(SourceArn=queue_arn, MaxResults=10)
        raw_tasks = task_payload.get("Results", [])
        tasks = tuple(dict(task) for task in raw_tasks if isinstance(task, Mapping))
        return DlqStatus(
            queue_arn=queue_arn,
            visible_messages=_count(attributes, "ApproximateNumberOfMessages"),
            in_flight_messages=_count(attributes, "ApproximateNumberOfMessagesNotVisible"),
            delayed_messages=_count(attributes, "ApproximateNumberOfMessagesDelayed"),
            tasks=tasks,
        )

    def start(
        self,
        *,
        max_messages_per_second: int,
        destination_arn: str | None = None,
    ) -> str:
        if not 1 <= max_messages_per_second <= 500:
            raise ValueError("redrive rate must be between 1 and 500 messages per second")
        source_arn = self.status().queue_arn
        request: dict[str, Any] = {
            "SourceArn": source_arn,
            "MaxNumberOfMessagesPerSecond": max_messages_per_second,
        }
        if destination_arn:
            if not destination_arn.startswith("arn:"):
                raise ValueError("destination ARN is invalid")
            request["DestinationArn"] = destination_arn
        response = self.client.start_message_move_task(**request)
        task_handle = str(response.get("TaskHandle", ""))
        if not task_handle:
            raise RuntimeError("SQS did not return a redrive task handle")
        return task_handle

    def cancel(self, task_handle: str) -> int:
        if not task_handle.strip():
            raise ValueError("task handle is required")
        source_arn = self.status().queue_arn
        response = self.client.cancel_message_move_task(
            SourceArn=source_arn,
            TaskHandle=task_handle,
        )
        value = response.get("ApproximateNumberOfMessagesMoved", 0)
        return int(value)


def _count(attributes: Mapping[str, Any], name: str) -> int:
    try:
        value = int(str(attributes.get(name, "0")))
    except ValueError as exc:
        raise RuntimeError(f"SQS returned an invalid {name}") from exc
    if value < 0:
        raise RuntimeError(f"SQS returned an invalid {name}")
    return value
