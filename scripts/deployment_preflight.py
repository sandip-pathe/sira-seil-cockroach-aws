"""Validate AWS and Cockroach runtime configuration before CDK deploy."""

# ruff: noqa: T201 -- emits one sanitized operator report.

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from integrations.deployment_preflight import build_preflight_result  # noqa: E402


def _client(service: str, *, region: str, profile: str | None) -> Any:
    import boto3  # type: ignore[import-untyped]

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client(service, region_name=region)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="hackathon")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE") or None)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "deployment.json",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    sts = _client("sts", region=arguments.region, profile=arguments.profile)
    secrets = _client("secretsmanager", region=arguments.region, profile=arguments.profile)
    identity = sts.get_caller_identity()
    secret_name = f"sira-{arguments.stage}/runtime"
    secret = secrets.get_secret_value(SecretId=secret_name)
    value = json.loads(str(secret.get("SecretString", "")))
    if not isinstance(value, dict):
        raise ValueError("runtime secret must contain one JSON object")
    result = build_preflight_result(
        account_id=str(identity.get("Account", "")),
        configured_region=arguments.region,
        caller_region=str(secrets.meta.region_name),
        stage=arguments.stage,
        runtime_secret=value,
        secret_arn=str(secret.get("ARN", "")),
    )
    report = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **asdict(result),
        "secret_name": secret_name,
        "secret_values_persisted": False,
        "caller_identity_persisted": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"status": result.status, "artifact": str(arguments.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
