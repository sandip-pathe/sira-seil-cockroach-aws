"""Principal-locked AgentCore boundary for SIRA/SEIL typed decisions."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, model_validator
from sira_agents.bedrock_runtime import (
    BedrockConverseRuntime,
    BedrockGuardrail,
    create_bedrock_client,
)
from sira_agents.cognitive_runtime import BedrockCognitiveRuntime
from sira_agents.experiment import ExperimentResult, ExperimentSpec
from sira_agents.kernel_models import ContextManifest, Party, Principal, TurnDecisionEnvelope
from sira_agents.runtime_ticket import InMemoryReplayGuard, RuntimeTicketCodec, RuntimeTicketError
from sira_worker.bedrock_qualification_eval import (
    BedrockQualificationEvalCase,
    evaluate_bedrock_qualification,
)

from domain import content_hash

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS = ROOT / "evaluations" / "bedrock-qualification-cases.json"


class AgentCoreInvocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: str
    ticket: str | None = None
    manifest: ContextManifest | None = None
    experiment: ExperimentSpec | None = None

    @model_validator(mode="after")
    def validate_contract_payload(self) -> AgentCoreInvocationRequest:
        if self.contract == "sira.cognitive-turn.v1":
            if self.ticket is None or self.manifest is None or self.experiment is not None:
                raise ValueError("cognitive invocation requires only ticket and manifest")
        elif self.contract == "sira.product-experiment.v1":
            if self.experiment is None or self.ticket is not None or self.manifest is not None:
                raise ValueError("experiment invocation requires only experiment")
        else:
            raise ValueError("unsupported AgentCore invocation contract")
        return self


# Compatibility name for the committed experiment harness.
AgentCoreExperimentRequest = AgentCoreInvocationRequest


app = FastAPI(title="SIRA AgentCore Evaluator", docs_url=None, redoc_url=None)
_replay_guard = InMemoryReplayGuard()


def _load_case(fixture_id: str) -> BedrockQualificationEvalCase:
    corpus_path = Path(os.environ.get("SIRA_EXPERIMENT_CORPUS", str(DEFAULT_CORPUS)))
    document = json.loads(corpus_path.read_text(encoding="utf-8"))
    for item in document.get("cases", []):
        if item.get("id") == fixture_id:
            return BedrockQualificationEvalCase.model_validate(item)
    raise HTTPException(status_code=422, detail="unknown experiment fixture")


@app.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "Healthy"}


def _principal() -> Principal:
    try:
        return Principal(os.environ["AGENT_PRINCIPAL"].strip().upper())
    except (KeyError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail="runtime principal is not configured"
        ) from error


def _guardrail() -> BedrockGuardrail | None:
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
    guardrail_version = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "")
    return (
        BedrockGuardrail(guardrail_id, guardrail_version)
        if guardrail_id and guardrail_version
        else None
    )


@lru_cache(maxsize=1)
def _ticket_signing_key() -> bytes:
    direct = os.environ.get("RUNTIME_TICKET_SIGNING_KEY", "")
    if direct:
        key = direct.encode()
    else:
        secret_arn = os.environ.get("RUNTIME_SECRET_ARN", "")
        if not secret_arn:
            raise HTTPException(status_code=503, detail="runtime ticket secret is not configured")
        import boto3  # type: ignore[import-untyped]

        response: dict[str, Any] = boto3.client(
            "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1")
        ).get_secret_value(SecretId=secret_arn)
        try:
            secret = json.loads(str(response["SecretString"]))
            key = str(secret["RUNTIME_TICKET_SIGNING_KEY"]).encode()
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=503, detail="runtime ticket secret is invalid"
            ) from error
    if len(key) < 32:
        raise HTTPException(status_code=503, detail="runtime ticket key is too short")
    return key


async def _cognitive_turn(request: AgentCoreInvocationRequest) -> TurnDecisionEnvelope:
    assert request.ticket is not None and request.manifest is not None
    principal = _principal()
    party = Party.BUYER if principal is Principal.SIRA else Party.SELLER
    audience = os.environ.get("AGENT_RUNTIME_AUDIENCE", "")
    if not audience:
        raise HTTPException(status_code=503, detail="runtime audience is not configured")
    try:
        claims = await RuntimeTicketCodec(_ticket_signing_key()).verify(
            request.ticket,
            expected_principal=principal,
            expected_party=party,
            expected_organization_id=request.manifest.organization_id,
            expected_purpose=request.manifest.purpose,
            expected_audience=audience,
            replay_guard=_replay_guard,
        )
    except RuntimeTicketError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    manifest = request.manifest
    if manifest.principal is not principal or manifest.party is not party:
        raise HTTPException(status_code=403, detail="manifest targets another runtime principal")
    if set(manifest.available_tools).difference(claims.allowed_tools):
        raise HTTPException(status_code=403, detail="manifest exceeds ticket tool scope")
    runtime = BedrockCognitiveRuntime(
        BedrockConverseRuntime(
            client=create_bedrock_client(region=os.environ.get("AWS_REGION", "us-east-1")),
            model_id=os.environ.get("BEDROCK_CHAT_MODEL_ID", "amazon.nova-micro-v1:0"),
            guardrail=_guardrail(),
            max_turns=3,
            max_tokens=manifest.budget.max_output_tokens,
            timeout_seconds=manifest.budget.timeout_seconds,
        )
    )
    return TurnDecisionEnvelope(decision=await runtime.decide(manifest))


async def _experiment(experiment: ExperimentSpec) -> ExperimentResult:
    """Evaluate one committed synthetic case; never retain conversation memory."""

    case = _load_case(experiment.fixture_id)
    if experiment.candidate_id not in case.evidence_by_product:
        raise HTTPException(status_code=422, detail="candidate is absent from fixture")

    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("BEDROCK_CHAT_MODEL_ID", "amazon.nova-micro-v1:0")
    results = await evaluate_bedrock_qualification(
        client=create_bedrock_client(region=region),
        model_id=model_id,
        cases=(case,),
        guardrail=_guardrail(),
    )
    result = results[0]
    observations = [
        {"signal": "structured_output", "value": result.structured_output_valid, "source": case.id},
        {
            "signal": "all_candidates_inspected",
            "value": result.inspected_every_candidate,
            "source": case.id,
        },
        {"signal": "grounded_output", "value": result.grounded, "source": case.id},
        {
            "signal": "expected_product_match",
            "value": result.expected_product_match,
            "source": case.id,
        },
    ]
    limitations = ["synthetic labelled fixture; not a production accuracy estimate"]
    if result.failure_category:
        limitations.append(f"failure_category:{result.failure_category}")
    document = {
        "status": "COMPLETED",
        "observations": observations,
        "limitations": limitations,
        "logs_reference": None,
    }
    return ExperimentResult.model_validate({**document, "artifact_hash": content_hash(document)})


@app.post("/invocations", response_model=TurnDecisionEnvelope | ExperimentResult)
async def invoke(
    request: AgentCoreInvocationRequest,
) -> TurnDecisionEnvelope | ExperimentResult:
    if request.contract == "sira.cognitive-turn.v1":
        return await _cognitive_turn(request)
    assert request.experiment is not None
    if _principal() is not Principal.SIRA:
        raise HTTPException(status_code=403, detail="experiments run only on SIRA")
    return await _experiment(request.experiment)
