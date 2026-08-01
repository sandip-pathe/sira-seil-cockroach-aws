"""Real Senso REST adapter with verified, immutable folder scope."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, cast

import httpx

from integrations.common import AdapterDescriptor
from integrations.errors import ProviderError, ProviderErrorCode, raise_for_status
from integrations.security import HttpsUrlPolicy, validate_identifier
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
    SensoScopeVerification,
    SensoSearchRequest,
    SensoSearchResult,
)

SENSO_PROVIDER = "senso"
DEFAULT_SENSO_BASE_URL = "https://apiv2.senso.ai/api/v1"
DEFAULT_SENSO_HOSTS = frozenset({"apiv2.senso.ai"})
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)


def _object_payload(response: httpx.Response, *, operation: str) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        raise ProviderError(
            provider=SENSO_PROVIDER,
            operation=operation,
            code=ProviderErrorCode.INVALID_RESPONSE,
            retryable=False,
            status_code=response.status_code,
        ) from None
    return cast(Mapping[str, Any], payload)


def _list_payload(response: httpx.Response, *, operation: str) -> list[Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, list):
        raise ProviderError(
            provider=SENSO_PROVIDER,
            operation=operation,
            code=ProviderErrorCode.INVALID_RESPONSE,
            retryable=False,
            status_code=response.status_code,
        ) from None
    return payload


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class SensoRestAdapter:
    """Activated Senso query adapter bound to one verified folder scope.

    Senso documents grant read-back by configured key ID and effective folder ACLs,
    but does not document a cryptographic binding from the presented secret to that
    key ID.  Activation therefore records that limitation explicitly and proves the
    secret's effective access with both a positive and negative browse probe.
    """

    __slots__ = (
        "_api_key",
        "_base_url",
        "_client",
        "_descriptor",
        "_scope",
        "_verification",
    )
    _api_key: str
    _base_url: str
    _client: httpx.AsyncClient
    _descriptor: AdapterDescriptor
    _scope: SensoFolderScope
    _verification: SensoScopeVerification

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use await SensoRestAdapter.activate(...) for scoped activation")

    @classmethod
    async def activate(
        cls,
        *,
        api_key: str,
        scope: SensoFolderScope,
        outside_folder_node_id: str,
        base_url: str = DEFAULT_SENSO_BASE_URL,
        allowed_hosts: frozenset[str] = DEFAULT_SENSO_HOSTS,
        request_timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> Self:
        """Verify the configured grant and effective ACL before returning an adapter."""

        operation = "activate_scope"
        if not api_key.strip():
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None
        safe_outside_node = validate_identifier(
            outside_folder_node_id,
            provider=SENSO_PROVIDER,
            operation=operation,
        )
        if safe_outside_node == scope.folder_node_id:
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None

        policy = HttpsUrlPolicy(provider=SENSO_PROVIDER, allowed_hosts=allowed_hosts)
        adapter = object.__new__(cls)
        adapter._base_url = policy.validate(
            base_url,
            operation="configure",
            allow_query=False,
        ).rstrip("/")
        adapter._api_key = api_key
        adapter._client = httpx.AsyncClient(
            timeout=request_timeout,
            follow_redirects=False,
            trust_env=False,
        )
        adapter._descriptor = AdapterDescriptor.production(SENSO_PROVIDER)
        adapter._scope = scope
        try:
            adapter._verification = await adapter._verify_scope(safe_outside_node)
        except BaseException:
            await adapter._client.aclose()
            raise
        return adapter

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    @property
    def scope(self) -> SensoFolderScope:
        return self._scope

    @property
    def verification(self) -> SensoScopeVerification:
        return self._verification

    def __repr__(self) -> str:
        return (
            "SensoRestAdapter("
            f"base_url={self._base_url!r}, scope={self._scope!r}, api_key=<redacted>)"
        )

    async def _request_raw(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
    ) -> httpx.Response:
        transport_code: ProviderErrorCode | None = None
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                headers={"X-API-Key": self._api_key, "Accept": "application/json"},
                json=json,
                params=params,
            )
        except httpx.TimeoutException:
            transport_code = ProviderErrorCode.TIMEOUT
        except httpx.HTTPError:
            transport_code = ProviderErrorCode.UNAVAILABLE
        if transport_code is not None:
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=transport_code,
                retryable=True,
            ) from None
        return response

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        json: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
    ) -> httpx.Response:
        response = await self._request_raw(
            method,
            path,
            operation=operation,
            json=json,
            params=params,
        )
        raise_for_status(response.status_code, provider=SENSO_PROVIDER, operation=operation)
        return response

    async def _verify_scope(self, outside_folder_node_id: str) -> SensoScopeVerification:
        operation = "activate_scope"
        grants_response = await self._request(
            "GET",
            f"/org/api-keys/{self._scope.key_id}/kb-permissions",
            operation=operation,
        )
        raw_grants = _list_payload(grants_response, operation=operation)
        grants: list[SensoFolderGrant] = []
        try:
            for raw in raw_grants:
                if not isinstance(raw, dict):
                    raise TypeError
                node_id = raw["node_id"]
                role = raw["role"]
                if not isinstance(node_id, str) or not isinstance(role, str):
                    raise TypeError
                grants.append(
                    SensoFolderGrant(
                        node_id=node_id,
                        role=SensoFolderRole(role),
                    )
                )
        except (KeyError, TypeError, ValueError):
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None
        expected = (
            SensoFolderGrant(
                node_id=self._scope.folder_node_id,
                role=SensoFolderRole.VIEWER,
            ),
        )
        if tuple(grants) != expected:
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.CONFIGURATION_INVALID,
                retryable=False,
            ) from None

        allowed_response = await self._request(
            "GET",
            f"/org/kb/nodes/{self._scope.folder_node_id}/children",
            operation=operation,
        )
        allowed_payload = _object_payload(allowed_response, operation=operation)
        if not isinstance(allowed_payload.get("nodes"), list):
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None

        denied_response = await self._request_raw(
            "GET",
            f"/org/kb/nodes/{outside_folder_node_id}/children",
            operation=operation,
        )
        if denied_response.status_code not in {403, 404}:
            if 200 <= denied_response.status_code < 300:
                raise ProviderError(
                    provider=SENSO_PROVIDER,
                    operation=operation,
                    code=ProviderErrorCode.ACCESS_DENIED,
                    retryable=False,
                ) from None
            raise_for_status(
                denied_response.status_code,
                provider=SENSO_PROVIDER,
                operation=operation,
            )

        return SensoScopeVerification(
            scope=self._scope,
            direct_grants=tuple(grants),
            allowed_folder_browse_verified=True,
            denied_node_id=outside_folder_node_id,
            cross_folder_denial_verified=True,
        )

    def _assert_scope(self, scope: SensoFolderScope, *, operation: str) -> None:
        if scope != self._scope:
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.ACCESS_DENIED,
                retryable=False,
            ) from None

    async def search(self, request: SensoSearchRequest) -> SensoSearchResult:
        operation = "search"
        self._assert_scope(request.scope, operation=operation)
        response = await self._request(
            "POST",
            "/org/search",
            operation=operation,
            json={"query": request.query, "max_results": request.max_results},
        )
        payload = _object_payload(response, operation=operation)
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        hits: list[SensoEvidenceHit] = []
        try:
            for raw in raw_results:
                if not isinstance(raw, dict):
                    raise TypeError
                content_id = raw["content_id"]
                title = raw["title"]
                chunk_text = raw["chunk_text"]
                score = raw["score"]
                if (
                    not isinstance(content_id, str)
                    or not isinstance(title, str)
                    or not isinstance(chunk_text, str)
                    or not isinstance(score, (int, float))
                    or isinstance(score, bool)
                ):
                    raise TypeError
                hits.append(
                    SensoEvidenceHit(
                        content_id=content_id,
                        title=title,
                        chunk_text=chunk_text,
                        score=float(score),
                        source_version=_optional_int(raw.get("version")),
                    )
                )
        except (KeyError, TypeError, ValueError):
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None

        answer_value = payload.get("answer")
        answer = answer_value if isinstance(answer_value, str) else None
        total_results = _optional_int(payload.get("total_results"))
        return SensoSearchResult(
            answer=answer,
            hits=tuple(hits),
            total_results=total_results if total_results is not None else len(hits),
            processing_time_ms=_optional_int(payload.get("processing_time_ms")),
            scope=self._scope,
            adapter=self.descriptor,
        )

    async def browse(self, request: SensoBrowseRequest) -> SensoBrowseResult:
        operation = "browse"
        self._assert_scope(request.scope, operation=operation)
        safe_folder_id = validate_identifier(
            request.folder_node_id,
            provider=SENSO_PROVIDER,
            operation=operation,
        )
        response = await self._request(
            "GET",
            f"/org/kb/nodes/{safe_folder_id}/children",
            operation=operation,
        )
        payload = _object_payload(response, operation=operation)
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        nodes: list[SensoBrowseNode] = []
        try:
            for raw in raw_nodes:
                if not isinstance(raw, dict):
                    raise TypeError
                node_id = raw.get("kb_node_id", raw.get("id"))
                name = raw.get("name")
                node_type = raw.get("type")
                if not all(isinstance(value, str) for value in (node_id, name, node_type)):
                    raise TypeError
                nodes.append(
                    SensoBrowseNode(
                        node_id=cast(str, node_id),
                        name=cast(str, name),
                        node_type=cast(str, node_type),
                    )
                )
        except (TypeError, ValueError):
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None
        return SensoBrowseResult(
            folder_node_id=safe_folder_id,
            nodes=tuple(nodes),
            scope=self._scope,
            adapter=self.descriptor,
        )

    async def get_content_version(self, request: SensoContentVersionRequest) -> SensoContentVersion:
        operation = "get_content_version"
        self._assert_scope(request.scope, operation=operation)
        safe_node_id = validate_identifier(
            request.node_id,
            provider=SENSO_PROVIDER,
            operation=operation,
        )
        response = await self._request(
            "GET",
            f"/org/kb/nodes/{safe_node_id}/content",
            operation=operation,
            params={"version": request.version},
        )
        payload = _object_payload(response, operation=operation)
        try:
            title_value = payload.get("title", payload.get("name", ""))
            text_value = payload.get("text", payload.get("content", ""))
            returned_version = payload.get("version", request.version)
            if (
                not isinstance(title_value, str)
                or not isinstance(text_value, str)
                or not isinstance(returned_version, int)
                or isinstance(returned_version, bool)
            ):
                raise TypeError
            checksum_value = payload.get("checksum")
            checksum = checksum_value if isinstance(checksum_value, str) else None
            return SensoContentVersion(
                node_id=safe_node_id,
                version=returned_version,
                title=title_value,
                text=text_value,
                checksum=checksum,
                scope=self._scope,
                adapter=self.descriptor,
            )
        except (TypeError, ValueError):
            raise ProviderError(
                provider=SENSO_PROVIDER,
                operation=operation,
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from None

    async def aclose(self) -> None:
        await self._client.aclose()
