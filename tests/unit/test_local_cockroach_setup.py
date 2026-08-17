from pathlib import Path


def test_local_runtime_users_receive_narrow_hosted_roles() -> None:
    script = (Path(__file__).parents[2] / "scripts" / "cockroach-local.ps1").read_text(
        encoding="utf-8"
    )

    assert "GRANT sira_runtime, sira_api_tenant_bootstrap TO sira_app" in script
    assert (
        "GRANT sira_runtime, sira_qualification_worker, "
        "sira_worker_directory_reader TO sira_worker_app"
    ) in script
