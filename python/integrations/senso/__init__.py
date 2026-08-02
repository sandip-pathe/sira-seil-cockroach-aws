"""Senso evidence retrieval adapters."""

from integrations.senso.fixtures import DevelopmentFixtureSensoAdapter
from integrations.senso.ingestion import (
    AcceptedSensoFact,
    BuyerFactExtractor,
    FactExtractionRun,
    SensoFactProposal,
    SensoIngestionResult,
    ingest_senso_buyer_facts,
)
from integrations.senso.models import (
    SensoBrowseNode,
    SensoBrowseRequest,
    SensoBrowseResult,
    SensoContentVersion,
    SensoContentVersionRequest,
    SensoEvidenceHit,
    SensoFolderGrant,
    SensoFolderRole,
    SensoFolderScope,
    SensoKeyIdentityBinding,
    SensoScopeVerification,
    SensoSearchRequest,
    SensoSearchResult,
)
from integrations.senso.protocols import SensoEvidenceProvider
from integrations.senso.rest import SensoRestAdapter

__all__ = [
    "AcceptedSensoFact",
    "BuyerFactExtractor",
    "DevelopmentFixtureSensoAdapter",
    "FactExtractionRun",
    "SensoBrowseNode",
    "SensoBrowseRequest",
    "SensoBrowseResult",
    "SensoContentVersion",
    "SensoContentVersionRequest",
    "SensoEvidenceHit",
    "SensoEvidenceProvider",
    "SensoFactProposal",
    "SensoFolderGrant",
    "SensoFolderRole",
    "SensoFolderScope",
    "SensoIngestionResult",
    "SensoKeyIdentityBinding",
    "SensoRestAdapter",
    "SensoScopeVerification",
    "SensoSearchRequest",
    "SensoSearchResult",
    "ingest_senso_buyer_facts",
]
