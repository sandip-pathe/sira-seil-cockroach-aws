import importlib.util
from pathlib import Path


def _load_probe_module():
    path = Path(__file__).parents[2] / "scripts" / "datahub_k0_probe.py"
    spec = importlib.util.spec_from_file_location("datahub_k0_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe_module()


def test_token_loader_reads_nested_datahub_profile_without_mutating_it(tmp_path: Path) -> None:
    profile = tmp_path / ".datahubenv"
    profile.write_text("gms:\n  server: http://localhost:8080\n  token: local-token\n")

    assert probe._token_from_datahub_env(profile) == "local-token"
    assert profile.read_text() == ("gms:\n  server: http://localhost:8080\n  token: local-token\n")


def test_pii_detection_supports_source_and_editable_field_tags() -> None:
    source = {"schemaMetadata": {"fields": [{"fieldPath": "email", "tags": ["PII"]}]}}
    editable = {"schemaMetadata": {"fields": [{"fieldPath": "email", "editedTags": ["PII"]}]}}
    absent = {"schemaMetadata": {"fields": [{"fieldPath": "email", "editedTags": []}]}}

    assert probe._email_has_pii(source)
    assert probe._email_has_pii(editable)
    assert not probe._email_has_pii(absent)


def test_exception_details_flattens_exception_groups() -> None:
    error = ExceptionGroup("outer", [ValueError("first"), RuntimeError("second")])

    assert probe._exception_details(error) == [
        {"type": "ValueError", "message": "first"},
        {"type": "RuntimeError", "message": "second"},
    ]
