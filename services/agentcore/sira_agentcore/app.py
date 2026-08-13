"""HTTP contract for the stateless AgentCore qualification evaluator."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sira_agents.bedrock_runtime import BedrockGuardrail, create_bedrock_client
from sira_agents.experiment import ExperimentResult, ExperimentSpec
from sira_worker.bedrock_qualification_eval import (
    BedrockQualificationEvalCase,
    evaluate_bedrock_qualification,
)

from domain import content_hash

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS = ROOT / "evaluations" / "bedrock-qualification-cases.json"


class AgentCoreExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: str
    experiment: ExperimentSpec


app = FastAPI(title="SIRA AgentCore Evaluator", docs_url=None, redoc_url=None)


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


@app.post("/invocations", response_model=ExperimentResult)
async def invoke(request: AgentCoreExperimentRequest) -> ExperimentResult:
    """Evaluate one committed synthetic case; never retain conversation memory."""

    if request.contract != "sira.product-experiment.v1":
        raise HTTPException(status_code=422, detail="unsupported experiment contract")
    case = _load_case(request.experiment.fixture_id)
    if request.experiment.candidate_id not in case.evidence_by_product:
        raise HTTPException(status_code=422, detail="candidate is absent from fixture")

    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("BEDROCK_CHAT_MODEL_ID", "amazon.nova-micro-v1:0")
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
    guardrail_version = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "")
    guardrail = (
        BedrockGuardrail(guardrail_id, guardrail_version)
        if guardrail_id and guardrail_version
        else None
    )
    results = await evaluate_bedrock_qualification(
        client=create_bedrock_client(region=region),
        model_id=model_id,
        cases=(case,),
        guardrail=guardrail,
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
