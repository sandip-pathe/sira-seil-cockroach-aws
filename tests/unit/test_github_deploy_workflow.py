from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-aws.yml"


def test_aws_deploy_workflow_is_manual_oidc_only_and_verifies_before_deploy() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    events = workflow.get("on", workflow.get(True))
    assert events == {"workflow_dispatch": None}
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
    job = workflow["jobs"]["verify-and-deploy"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    rendered_steps = str(job["steps"])
    assert "aws-actions/configure-aws-credentials@v6.2.3" in rendered_steps
    assert "AWS_DEPLOY_ROLE_ARN" in rendered_steps
    assert "astral-sh/setup-uv@v7.2.1" in rendered_steps
    assert "uv sync --frozen" in rendered_steps
    assert "pnpm --dir infra/aws test" in rendered_steps
    assert "scripts/deployment_preflight.py" in rendered_steps
    assert "cdk deploy Sira-hackathon" in rendered_steps
    assert "AWS_ACCESS_KEY_ID" not in text
    assert "AWS_SECRET_ACCESS_KEY" not in text
