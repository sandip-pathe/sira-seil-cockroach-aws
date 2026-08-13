from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from scripts import qualification_dlq

from integrations.sqs_redrive import SqsDlqOperator


@dataclass
class FakeRedriveClient:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    attributes: dict[str, str] = field(
        default_factory=lambda: {
            "QueueArn": "arn:aws:sqs:us-east-1:111111111111:sira-dlq.fifo",
            "ApproximateNumberOfMessages": "3",
            "ApproximateNumberOfMessagesNotVisible": "1",
            "ApproximateNumberOfMessagesDelayed": "0",
        }
    )

    def get_queue_attributes(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("attributes", kwargs))
        return {"Attributes": self.attributes}

    def list_message_move_tasks(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list", kwargs))
        return {"Results": [{"Status": "RUNNING", "TaskHandle": "task-1"}]}

    def start_message_move_task(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("start", kwargs))
        return {"TaskHandle": "task-2"}

    def cancel_message_move_task(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("cancel", kwargs))
        return {"ApproximateNumberOfMessagesMoved": 2}


def test_dlq_status_does_not_read_message_payloads() -> None:
    client = FakeRedriveClient()
    operator = SqsDlqOperator(client=client, dlq_url="https://sqs.example/dlq")
    status = operator.status()
    assert status.visible_messages == 3
    assert status.in_flight_messages == 1
    assert status.tasks[0]["Status"] == "RUNNING"
    assert [name for name, _ in client.calls] == ["attributes", "list"]


def test_dlq_start_and_cancel_use_native_move_tasks() -> None:
    client = FakeRedriveClient()
    operator = SqsDlqOperator(client=client, dlq_url="https://sqs.example/dlq")
    assert operator.start(max_messages_per_second=5) == "task-2"
    start_request = next(kwargs for name, kwargs in client.calls if name == "start")
    assert start_request == {
        "SourceArn": client.attributes["QueueArn"],
        "MaxNumberOfMessagesPerSecond": 5,
    }
    assert operator.cancel("task-2") == 2
    cancel_request = next(kwargs for name, kwargs in client.calls if name == "cancel")
    assert cancel_request["TaskHandle"] == "task-2"


def test_dlq_operations_fail_closed_on_invalid_provider_metadata() -> None:
    client = FakeRedriveClient()
    operator = SqsDlqOperator(client=client, dlq_url="https://sqs.example/dlq")
    for rate in (0, 501):
        with pytest.raises(ValueError, match="between 1 and 500"):
            operator.start(max_messages_per_second=rate)
    with pytest.raises(ValueError, match="destination ARN"):
        operator.start(max_messages_per_second=1, destination_arn="queue-name")
    with pytest.raises(ValueError, match="task handle"):
        operator.cancel(" ")
    client.attributes["ApproximateNumberOfMessages"] = "invalid"
    with pytest.raises(RuntimeError, match="invalid ApproximateNumberOfMessages"):
        operator.status()


def test_dlq_cli_defaults_mutations_to_dry_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeRedriveClient()
    monkeypatch.setattr(qualification_dlq, "create_aws_client", lambda *_args, **_kwargs: client)
    result = qualification_dlq.main(
        [
            "--region",
            "us-east-1",
            "--dlq-url",
            "https://sqs.example/dlq",
            "start",
            "--max-rate",
            "5",
        ]
    )
    assert result == 0
    assert '"executed": false' in capsys.readouterr().out
    assert not any(name == "start" for name, _ in client.calls)
