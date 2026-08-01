"""Credential-free, folder-scoped Senso request and response models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from integrations.common import AdapterDescriptor


def _is_safe_identifier(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 255
        and all(character.isalnum() or character in "_-" for character in value)
    )


class SensoFolderRole(StrEnum):
    """Knowledge-base roles documented by Senso for scoped query keys."""

    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"


class SensoKeyIdentityBinding(StrEnum):
    """How strongly Senso documents the runtime secret-to-key-id relationship."""

    NOT_DOCUMENTED = "not_documented"


@dataclass(frozen=True, slots=True)
class SensoFolderScope:
    """Immutable, non-secret identity and purpose for one Senso query key."""

    key_id: str
    folder_node_id: str
    purpose: str

    def __post_init__(self) -> None:
        if not _is_safe_identifier(self.key_id):
            raise ValueError("key_id must be a safe provider identifier")
        if not _is_safe_identifier(self.folder_node_id):
            raise ValueError("folder_node_id must be a safe provider identifier")
        if not _is_safe_identifier(self.purpose):
            raise ValueError("purpose must be a stable identifier")


@dataclass(frozen=True, slots=True)
class SensoFolderGrant:
    node_id: str
    role: SensoFolderRole

    def __post_init__(self) -> None:
        if not _is_safe_identifier(self.node_id):
            raise ValueError("node_id must be a safe provider identifier")


@dataclass(frozen=True, slots=True)
class SensoScopeVerification:
    """Successful supported proof of a runtime key's effective KB isolation.

    Senso documents grant read-back by configured key ID, but no endpoint that
    binds the presented secret to that ID.  The explicit binding value keeps that
    provider limitation visible while the runtime secret is independently tested
    for allowed-folder access and cross-folder denial.
    """

    scope: SensoFolderScope
    direct_grants: tuple[SensoFolderGrant, ...]
    allowed_folder_browse_verified: bool
    denied_node_id: str
    cross_folder_denial_verified: bool
    key_identity_binding: SensoKeyIdentityBinding = SensoKeyIdentityBinding.NOT_DOCUMENTED

    def __post_init__(self) -> None:
        expected_grants = (
            SensoFolderGrant(
                node_id=self.scope.folder_node_id,
                role=SensoFolderRole.VIEWER,
            ),
        )
        if self.direct_grants != expected_grants:
            raise ValueError("verification requires one exact viewer folder grant")
        if not self.allowed_folder_browse_verified or not self.cross_folder_denial_verified:
            raise ValueError("verification requires positive and negative access probes")
        if not _is_safe_identifier(self.denied_node_id):
            raise ValueError("denied_node_id must be a safe provider identifier")
        if self.denied_node_id == self.scope.folder_node_id:
            raise ValueError("denied node must be outside the allowed folder")


@dataclass(frozen=True, slots=True)
class SensoSearchRequest:
    query: str
    scope: SensoFolderScope
    max_results: int = 5

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= self.max_results <= 50:
            raise ValueError("max_results must be between 1 and 50")


@dataclass(frozen=True, slots=True)
class SensoBrowseRequest:
    folder_node_id: str
    scope: SensoFolderScope

    def __post_init__(self) -> None:
        if not _is_safe_identifier(self.folder_node_id):
            raise ValueError("folder_node_id must be a safe provider identifier")


@dataclass(frozen=True, slots=True)
class SensoContentVersionRequest:
    node_id: str
    version: int
    scope: SensoFolderScope

    def __post_init__(self) -> None:
        if not _is_safe_identifier(self.node_id) or self.version < 1:
            raise ValueError("node_id and positive version are required")


@dataclass(frozen=True, slots=True)
class SensoEvidenceHit:
    """A retrievable source chunk, not an independently verified product claim."""

    content_id: str
    title: str
    chunk_text: str
    score: float
    source_version: int | None = None

    def __post_init__(self) -> None:
        if not self.content_id:
            raise ValueError("content_id must not be empty")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SensoSearchResult:
    """Provider search output with provenance; it does not assert truth verification."""

    answer: str | None
    hits: tuple[SensoEvidenceHit, ...]
    total_results: int
    processing_time_ms: int | None
    scope: SensoFolderScope
    adapter: AdapterDescriptor
    truth_verified: bool = False

    def __post_init__(self) -> None:
        if self.truth_verified:
            raise ValueError("Senso retrieval cannot independently verify claim truth")


@dataclass(frozen=True, slots=True)
class SensoBrowseNode:
    node_id: str
    name: str
    node_type: str

    def __post_init__(self) -> None:
        if not _is_safe_identifier(self.node_id) or not self.name or not self.node_type:
            raise ValueError("browse nodes require an id, name, and type")


@dataclass(frozen=True, slots=True)
class SensoBrowseResult:
    folder_node_id: str
    nodes: tuple[SensoBrowseNode, ...]
    scope: SensoFolderScope
    adapter: AdapterDescriptor


@dataclass(frozen=True, slots=True)
class SensoContentVersion:
    node_id: str
    version: int
    title: str
    text: str
    checksum: str | None
    scope: SensoFolderScope
    adapter: AdapterDescriptor

    def __post_init__(self) -> None:
        if not self.node_id or self.version < 1:
            raise ValueError("node_id and positive version are required")
