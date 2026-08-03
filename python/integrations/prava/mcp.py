"""Prava Pay OAuth 2.1 and Streamable HTTP MCP client.

Card credentials never cross this boundary. Shopping tools return only product,
quote, approval URL, status, and order references documented by Prava.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from integrations.errors import ProviderError, ProviderErrorCode

PRAVA_MCP_PROVIDER = "prava_mcp"
PRAVA_MCP_URL = "https://mcp.pay.prava.space/mcp"
PRAVA_OAUTH_ISSUER = "https://mcp.pay.prava.space/auth"
PRAVA_AUTHORIZE_URL = f"{PRAVA_OAUTH_ISSUER}/authorize"
PRAVA_TOKEN_URL = f"{PRAVA_OAUTH_ISSUER}/token"
PRAVA_REGISTRATION_URL = f"{PRAVA_OAUTH_ISSUER}/register"
PRAVA_MCP_SCOPES = ("payments:read", "payments:write", "checkout:run")
MCP_PROTOCOL_VERSION = "2025-06-18"


def _provider_error(operation: str, *, retryable: bool = False) -> ProviderError:
    return ProviderError(
        provider=PRAVA_MCP_PROVIDER,
        operation=operation,
        code=(ProviderErrorCode.UNAVAILABLE if retryable else ProviderErrorCode.INVALID_RESPONSE),
        retryable=retryable,
    )


class ConnectorCipher:
    """Context-derived authenticated encryption for OAuth material."""

    def __init__(self, root_secret: str) -> None:
        if len(root_secret.encode("utf-8")) < 32:
            raise ValueError("connector encryption requires at least 32 bytes of key material")
        key = base64.urlsafe_b64encode(
            hashlib.sha256(b"sira:prava-mcp-oauth:v1\x00" + root_secret.encode()).digest()
        )
        self._fernet = Fernet(key)

    def encrypt_json(self, value: dict[str, Any]) -> str:
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return self._fernet.encrypt(payload).decode()

    def decrypt_json(self, value: str) -> dict[str, Any]:
        try:
            payload = json.loads(self._fernet.decrypt(value.encode()))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
            raise ValueError("encrypted connector credential is invalid") from error
        if not isinstance(payload, dict):
            raise ValueError("encrypted connector credential is invalid")
        return payload


@dataclass(frozen=True, slots=True)
class PkceAuthorization:
    state: str
    verifier: str
    challenge: str

    @classmethod
    def create(cls) -> PkceAuthorization:
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        return cls(state=state, verifier=verifier, challenge=challenge)


@dataclass(frozen=True, slots=True)
class OAuthTokens:
    access_token: str
    refresh_token: str
    scopes: tuple[str, ...]
    expires_at: datetime

    def sealed_payload(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "scopes": list(self.scopes),
            "expires_at": self.expires_at.isoformat(),
        }


class PravaMcpOAuthClient:
    def __init__(self, *, timeout: float = 20.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False)

    async def register(self, *, redirect_uri: str) -> str:
        response = await self._client.post(
            PRAVA_REGISTRATION_URL,
            json={
                "client_name": "SIRA procurement agent",
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )
        if response.status_code not in {200, 201}:
            raise _provider_error("oauth_register", retryable=response.status_code >= 500)
        payload = response.json()
        client_id = payload.get("client_id") if isinstance(payload, dict) else None
        if not isinstance(client_id, str) or not client_id:
            raise _provider_error("oauth_register")
        return client_id

    @staticmethod
    def authorization_url(
        *, client_id: str, redirect_uri: str, pkce: PkceAuthorization
    ) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(PRAVA_MCP_SCOPES),
                "state": pkce.state,
                "code_challenge": pkce.challenge,
                "code_challenge_method": "S256",
                "resource": PRAVA_MCP_URL,
            }
        )
        return f"{PRAVA_AUTHORIZE_URL}?{query}"

    async def exchange(
        self, *, client_id: str, redirect_uri: str, code: str, verifier: str
    ) -> OAuthTokens:
        return await self._token_request(
            "oauth_exchange",
            {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": verifier,
                "resource": PRAVA_MCP_URL,
            },
        )

    async def refresh(self, *, client_id: str, refresh_token: str) -> OAuthTokens:
        return await self._token_request(
            "oauth_refresh",
            {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
                "resource": PRAVA_MCP_URL,
            },
        )

    async def _token_request(self, operation: str, data: dict[str, str]) -> OAuthTokens:
        response = await self._client.post(PRAVA_TOKEN_URL, data=data)
        if response.status_code != 200:
            raise _provider_error(operation, retryable=response.status_code >= 500)
        payload = response.json()
        if not isinstance(payload, dict):
            raise _provider_error(operation)
        access = payload.get("access_token")
        refresh = payload.get("refresh_token") or data.get("refresh_token")
        expires_in = payload.get("expires_in", 3600)
        scope = payload.get("scope", " ".join(PRAVA_MCP_SCOPES))
        if (
            not isinstance(access, str)
            or not access
            or not isinstance(refresh, str)
            or not refresh
            or not isinstance(expires_in, int)
            or not isinstance(scope, str)
        ):
            raise _provider_error(operation)
        return OAuthTokens(
            access_token=access,
            refresh_token=refresh,
            scopes=tuple(item for item in scope.split() if item),
            expires_at=datetime.now(UTC) + timedelta(seconds=max(60, expires_in)),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


class PravaMcpClient:
    """Small credential-firewall client for the five supported shopping tools."""

    _ALLOWED_TOOLS = frozenset(
        {
            "ping",
            "shop_search",
            "shop_product",
            "shop_quote",
            "create_payment_session",
            "get_payment_status",
            "shop_checkout",
            "shop_list_addresses",
        }
    )

    def __init__(self, *, access_token: str, timeout: float = 45.0) -> None:
        if not access_token:
            raise ValueError("Prava MCP access token is required")
        self._access_token = access_token
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False)
        self._session_id: str | None = None
        self._request_id = 0

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._ALLOWED_TOOLS:
            raise ValueError("Prava MCP tool is not allowed")
        if self._session_id is None:
            await self._initialize()
        result = await self._rpc(
            "tools/call", {"name": name, "arguments": arguments}, operation=name
        )
        if result.get("isError") is True:
            raise _provider_error(name)
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        try:
                            parsed = json.loads(text)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(parsed, dict):
                            return parsed
        raise _provider_error(name)

    async def _initialize(self) -> None:
        await self._rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "sira", "version": "0.1.0"},
            },
            operation="initialize",
        )
        await self._notify("notifications/initialized")

    async def _rpc(
        self, method: str, params: dict[str, Any], *, operation: str
    ) -> dict[str, Any]:
        self._request_id += 1
        response = await self._client.post(
            PRAVA_MCP_URL,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params,
            },
        )
        if response.status_code != 200:
            raise _provider_error(operation, retryable=response.status_code >= 500)
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        payload = self._response_payload(response)
        if "error" in payload or not isinstance(payload.get("result"), dict):
            raise _provider_error(operation)
        return payload["result"]

    async def _notify(self, method: str) -> None:
        response = await self._client.post(
            PRAVA_MCP_URL,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "method": method},
        )
        if response.status_code not in {200, 202, 204}:
            raise _provider_error("initialize")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any]:
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    if isinstance(payload, dict):
                        return payload
            raise _provider_error("mcp_response")
        payload = response.json()
        if not isinstance(payload, dict):
            raise _provider_error("mcp_response")
        return payload

    async def aclose(self) -> None:
        await self._client.aclose()
