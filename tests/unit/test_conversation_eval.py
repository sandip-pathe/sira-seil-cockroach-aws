from __future__ import annotations

from pathlib import Path

from sira_agents.cognitive_runtime import DeterministicCognitiveRuntime
from sira_agents.conversation_eval import ConversationEvalCorpus, evaluate_conversations

ROOT = Path(__file__).resolve().parents[2]


def _corpus() -> ConversationEvalCorpus:
    return ConversationEvalCorpus.model_validate_json(
        (ROOT / "evaluations" / "conversation-turns.v1.json").read_text(encoding="utf-8")
    )


def test_conversation_corpus_contains_fifty_explicitly_labelled_turns() -> None:
    corpus = _corpus()

    assert corpus.schema_version == "1.0.0"
    assert corpus.labelled_turns == 50
    assert {group.category for group in corpus.groups} == {
        "greeting",
        "capability",
        "material_question",
        "tool_selection",
        "authority",
    }


async def test_conversation_evaluator_scores_typed_decisions_and_tool_policy() -> None:
    decisions = [
        *([{"kind": "respond", "message": "How can I help?"}] * 8),
        *([{"kind": "respond", "message": "I help sellers prepare evidence."}] * 8),
        *(
            [
                {
                    "kind": "clarify",
                    "question": "Which outcome matters most?",
                    "reason": "The answer changes the decision.",
                }
            ]
            * 10
        ),
        *(
            [
                {
                    "kind": "propose_tools",
                    "calls": [
                        {
                            "call_id": "buyer-search",
                            "tool_name": "search_published_products",
                            "contract_version": "v1",
                            "arguments": {"query": "requirements"},
                        }
                    ],
                }
            ]
            * 10
        ),
        *(
            [
                {
                    "kind": "propose_tools",
                    "calls": [
                        {
                            "call_id": "seller-search",
                            "tool_name": "search_seller_products",
                            "contract_version": "v1",
                            "arguments": {"query": "products"},
                        }
                    ],
                }
            ]
            * 10
        ),
        *(
            [
                {
                    "kind": "fail_safely",
                    "code": "TOOL_DENIED",
                    "message": "That action requires explicit authority.",
                }
            ]
            * 4
        ),
    ]
    result = await evaluate_conversations(
        DeterministicCognitiveRuntime(decisions=decisions), _corpus()
    )

    assert result.total == result.passed == 50
    assert result.task_success_rate == 1.0
    assert result.greeting_business_tool_calls == 0
    assert result.material_question_compliance == 1.0
    assert result.failures == ()
