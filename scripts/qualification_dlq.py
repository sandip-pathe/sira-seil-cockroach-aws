"""Inspect or explicitly operate the qualification SQS dead-letter queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from integrations.aws_services import create_aws_client  # noqa: E402
from integrations.sqs_redrive import SqsDlqOperator, SqsRedriveClient  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and safely redrive the qualification DLQ without reading payloads."
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--dlq-url", required=True)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    start = subcommands.add_parser("start")
    start.add_argument("--max-rate", type=int, default=10)
    start.add_argument("--destination-arn")
    start.add_argument("--execute", action="store_true")
    cancel = subcommands.add_parser("cancel")
    cancel.add_argument("--task-handle", required=True)
    cancel.add_argument("--execute", action="store_true")
    return parser


def _status_payload(operator: SqsDlqOperator) -> dict[str, Any]:
    status = operator.status()
    return {
        "queue_arn": status.queue_arn,
        "visible_messages": status.visible_messages,
        "in_flight_messages": status.in_flight_messages,
        "delayed_messages": status.delayed_messages,
        "tasks": list(status.tasks),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    client = cast(
        SqsRedriveClient,
        create_aws_client("sqs", region=args.region, profile=args.profile),
    )
    operator = SqsDlqOperator(client=client, dlq_url=args.dlq_url)
    payload: dict[str, Any]
    if args.command == "status":
        payload = {"action": "STATUS", **_status_payload(operator)}
    elif not args.execute:
        payload = {
            "action": args.command.upper(),
            "executed": False,
            "reason": "dry_run_requires_execute_flag",
            **_status_payload(operator),
        }
    elif args.command == "start":
        payload = {
            "action": "START",
            "executed": True,
            "task_handle": operator.start(
                max_messages_per_second=args.max_rate,
                destination_arn=args.destination_arn,
            ),
        }
    else:
        payload = {
            "action": "CANCEL",
            "executed": True,
            "approximate_messages_moved": operator.cancel(args.task_handle),
        }
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
