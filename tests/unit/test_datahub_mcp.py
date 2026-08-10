from types import SimpleNamespace

import pytest

from proof import datahub_mcp


def test_server_parameters_disable_external_telemetry(monkeypatch) -> None:
    monkeypatch.setattr(datahub_mcp.shutil, "which", lambda _: "uvx")

    parameters = datahub_mcp.server_parameters("local-token")

    assert parameters.env is not None
    assert parameters.env["DATAHUB_TELEMETRY_ENABLED"] == "false"


@pytest.mark.asyncio
async def test_stable_reader_records_both_physical_reads(monkeypatch) -> None:
    recorded_attempts: list[int] = []

    async def stable_read(_session: object, *, attempts: int = 1):
        recorded_attempts.append(attempts)
        return SimpleNamespace(semantic_hash="sha256:stable", read_attempts=attempts)

    monkeypatch.setattr(datahub_mcp, "read_once", stable_read)

    observation = await datahub_mcp.read_stable(object())  # type: ignore[arg-type]

    assert recorded_attempts == [1, 2]
    assert observation.read_attempts == 2
