"""Labelled evaluation for typed SIRA/SEIL cognitive decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from sira_agents.kernel_models import ContextManifest, Party, Principal, TurnDecision


class ConversationEvalGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    principal: Principal
    category: str
    prompts: tuple[str, ...] = Field(min_length=1)
    allowed_kinds: frozenset[str]
    expected_tool: str | None = None
    forbid_tools: bool = False
    require_single_question: bool = False


class ConversationEvalCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    groups: tuple[ConversationEvalGroup, ...]

    @property
    def labelled_turns(self) -> int:
        return sum(len(group.prompts) for group in self.groups)


class DecisionRuntime(Protocol):
    async def decide(self, manifest: ContextManifest) -> TurnDecision: ...


@dataclass(frozen=True, slots=True)
class ConversationEvalResult:
    total: int
    passed: int
    greeting_business_tool_calls: int
    material_questions: int
    material_questions_compliant: int
    failures: tuple[dict[str, Any], ...]

    @property
    def task_success_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def material_question_compliance(self) -> float:
        if not self.material_questions:
            return 0.0
        return self.material_questions_compliant / self.material_questions

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "task_success_rate": self.task_success_rate,
            "greeting_business_tool_calls": self.greeting_business_tool_calls,
            "material_questions": self.material_questions,
            "material_questions_compliant": self.material_questions_compliant,
            "material_question_compliance": self.material_question_compliance,
            "failures": list(self.failures),
        }


def _manifest(group: ConversationEvalGroup, prompt: str, index: int) -> ContextManifest:
    party = Party.BUYER if group.principal is Principal.SIRA else Party.SELLER
    purpose = "software_selection" if party is Party.BUYER else "seller_evidence"
    tools = (
        ("search_published_products",)
        if group.principal is Principal.SIRA
        else ("search_seller_products",)
    )
    contracts = tuple(
        {
            "name": name,
            "contract_version": "v1",
            "description": "Search only records visible to this authenticated principal.",
            "risk": "read",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        }
        for name in tools
    )
    return ContextManifest(
        principal=group.principal,
        party=party,
        organization_id=f"eval-{group.principal.value.lower()}",
        actor_id=f"eval-actor-{group.principal.value.lower()}",
        purpose=purpose,
        conversation_id=f"eval-{group.id}",
        turn_id=f"eval-{group.id}-{index}",
        current_message=prompt,
        available_tools=tools,
        tool_contracts=contracts,
    ).sealed()


async def evaluate_conversations(
    runtime: DecisionRuntime, corpus: ConversationEvalCorpus
) -> ConversationEvalResult:
    passed = 0
    greeting_business_tool_calls = 0
    material_questions = 0
    material_questions_compliant = 0
    failures: list[dict[str, Any]] = []
    for group in corpus.groups:
        for index, prompt in enumerate(group.prompts):
            failure: list[str] = []
            try:
                decision = await runtime.decide(_manifest(group, prompt, index))
                document = decision.model_dump(mode="json")
            except Exception as error:
                failures.append(
                    {
                        "case_id": f"{group.id}:{index}",
                        "reasons": [f"runtime_error:{type(error).__name__}"],
                    }
                )
                continue
            kind = str(document["kind"])
            calls = document.get("calls", []) if kind == "propose_tools" else []
            tool_names = [str(call.get("tool_name")) for call in calls]
            if kind not in group.allowed_kinds:
                failure.append(f"unexpected_kind:{kind}")
            if group.expected_tool and tool_names != [group.expected_tool]:
                failure.append(f"unexpected_tool_set:{','.join(tool_names)}")
            if group.forbid_tools and tool_names:
                failure.append("unexpected_tool")
            if group.category == "greeting":
                greeting_business_tool_calls += len(tool_names)
            if group.require_single_question:
                material_questions += 1
                question = str(document.get("question") or "")
                compliant = (
                    kind == "clarify" and question.endswith("?") and question.count("?") == 1
                )
                if compliant:
                    material_questions_compliant += 1
                else:
                    failure.append("material_question_not_focused")
            if failure:
                failures.append({"case_id": f"{group.id}:{index}", "reasons": failure})
            else:
                passed += 1
    return ConversationEvalResult(
        total=corpus.labelled_turns,
        passed=passed,
        greeting_business_tool_calls=greeting_business_tool_calls,
        material_questions=material_questions,
        material_questions_compliant=material_questions_compliant,
        failures=tuple(failures),
    )
