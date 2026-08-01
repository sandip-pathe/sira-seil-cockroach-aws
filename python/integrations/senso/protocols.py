"""Typed port implemented by Senso production and development adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from integrations.common import AdapterDescriptor
from integrations.senso.models import (
    SensoBrowseRequest,
    SensoBrowseResult,
    SensoContentVersion,
    SensoContentVersionRequest,
    SensoFolderScope,
    SensoSearchRequest,
    SensoSearchResult,
)


@runtime_checkable
class SensoEvidenceProvider(Protocol):
    @property
    def descriptor(self) -> AdapterDescriptor: ...

    @property
    def scope(self) -> SensoFolderScope: ...

    async def search(self, request: SensoSearchRequest) -> SensoSearchResult: ...

    async def browse(self, request: SensoBrowseRequest) -> SensoBrowseResult: ...

    async def get_content_version(
        self, request: SensoContentVersionRequest
    ) -> SensoContentVersion: ...

    async def aclose(self) -> None: ...
