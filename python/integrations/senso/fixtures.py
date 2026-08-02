"""Explicitly non-production Senso fixture adapter."""

from __future__ import annotations

from integrations.common import AdapterDescriptor
from integrations.errors import ProviderError, ProviderErrorCode
from integrations.senso.models import (
    SensoBrowseRequest,
    SensoBrowseResult,
    SensoContentVersion,
    SensoContentVersionRequest,
    SensoEvidenceHit,
    SensoFolderScope,
    SensoSearchRequest,
    SensoSearchResult,
)


class DevelopmentFixtureSensoAdapter:
    """Deterministic evidence for local development; never a production verifier."""

    __slots__ = ("_descriptor", "_hits", "_scope", "_versions")

    def __init__(
        self,
        *,
        scope: SensoFolderScope,
        hits: tuple[SensoEvidenceHit, ...] = (),
        content_versions: tuple[SensoContentVersion, ...] = (),
    ) -> None:
        self._scope = scope
        self._hits = hits
        self._versions = {(item.node_id, item.version): item for item in content_versions}
        self._descriptor = AdapterDescriptor.development_fixture("senso_fixture")

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    @property
    def scope(self) -> SensoFolderScope:
        return self._scope

    def _assert_scope(self, scope: SensoFolderScope, *, operation: str) -> None:
        if scope != self._scope:
            raise ProviderError(
                provider=self.descriptor.provider,
                operation=operation,
                code=ProviderErrorCode.ACCESS_DENIED,
                retryable=False,
            ) from None

    async def search(self, request: SensoSearchRequest) -> SensoSearchResult:
        self._assert_scope(request.scope, operation="search")
        selected = self._hits[: request.max_results]
        return SensoSearchResult(
            answer=None,
            hits=selected,
            total_results=len(selected),
            processing_time_ms=0,
            scope=self.scope,
            adapter=self.descriptor,
            truth_verified=False,
        )

    async def browse(self, request: SensoBrowseRequest) -> SensoBrowseResult:
        self._assert_scope(request.scope, operation="browse")
        return SensoBrowseResult(
            folder_node_id=request.folder_node_id,
            nodes=(),
            scope=self.scope,
            adapter=self.descriptor,
        )

    async def get_content_version(self, request: SensoContentVersionRequest) -> SensoContentVersion:
        self._assert_scope(request.scope, operation="get_content_version")
        version = self._versions.get((request.node_id, request.version))
        if version is not None:
            if version.scope != self.scope or version.adapter != self.descriptor:
                raise ValueError("fixture content version must carry this adapter scope and mode")
            return version
        raise ProviderError(
            provider=self.descriptor.provider,
            operation="get_content_version",
            code=ProviderErrorCode.FIXTURE_ONLY,
            retryable=False,
        ) from None

    async def aclose(self) -> None:
        return None
