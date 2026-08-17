from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _python_files(relative: str) -> tuple[Path, ...]:
    return tuple((ROOT / relative).rglob("*.py"))


def _assert_no_imports(relative: str, forbidden_roots: set[str]) -> None:
    violations: list[str] = []
    for path in _python_files(relative):
        for imported in _imports(path):
            root = imported.split(".", 1)[0]
            if root in forbidden_roots:
                violations.append(f"{path.relative_to(ROOT)} -> {imported}")
    assert not violations, "architecture boundary violations:\n" + "\n".join(violations)


def test_domain_is_independent_of_adapters_and_frameworks() -> None:
    _assert_no_imports(
        "python/domain",
        {
            "boto3",
            "fastapi",
            "integrations",
            "openai",
            "persistence",
            "sira_agentcore",
            "sira_api",
            "sira_worker",
            "sqlalchemy",
        },
    )


def test_agents_do_not_depend_on_transport_or_worker_layers() -> None:
    _assert_no_imports(
        "python/agents",
        {"fastapi", "persistence", "sira_agentcore", "sira_api", "sira_worker", "sqlalchemy"},
    )


def test_active_agent_runtime_has_no_duplicate_openai_sdk() -> None:
    _assert_no_imports("python/agents", {"agents", "openai"})
    _assert_no_imports("services/api", {"agents", "openai"})
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = [
        *project["project"]["dependencies"],
        *project["project"]["optional-dependencies"]["dev"],
    ]
    assert not any(str(item).startswith(("openai", "openai-agents")) for item in declared)


def test_persistence_does_not_depend_on_transport_or_worker_layers() -> None:
    _assert_no_imports(
        "python/persistence",
        {"fastapi", "integrations", "sira_agentcore", "sira_api", "sira_worker"},
    )
