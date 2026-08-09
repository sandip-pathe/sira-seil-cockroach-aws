"""DataHub-causal proof kernel for SIRA + SEIL."""

from .manifest_v0 import compile_manifest, evaluate_campaign
from .models import CampaignDecision, EnvironmentObservation, EvaluationManifest

__all__ = [
    "CampaignDecision",
    "EnvironmentObservation",
    "EvaluationManifest",
    "compile_manifest",
    "evaluate_campaign",
]
