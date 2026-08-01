"""Deterministic buyer-policy evaluation and SolutionPlan ordering."""

from .counterfactual import build_counterfactual
from .demo import DemoDecision, evaluate_demo
from .evaluation import evaluate_candidate, evaluate_candidate_set
from .models import (
    BuyerConstraint,
    CandidateDefinition,
    CandidateResult,
    Counterfactual,
    PreferenceResult,
    SellerAntiFitRule,
    SolutionPlan,
)
from .ranking import rank_solution_plans, ranking_key, select_winner

__all__ = [
    "BuyerConstraint",
    "CandidateDefinition",
    "CandidateResult",
    "Counterfactual",
    "DemoDecision",
    "PreferenceResult",
    "SellerAntiFitRule",
    "SolutionPlan",
    "build_counterfactual",
    "evaluate_candidate",
    "evaluate_candidate_set",
    "evaluate_demo",
    "rank_solution_plans",
    "ranking_key",
    "select_winner",
]
