from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sira_api.identity import IdentityProviderUnavailable, IntrospectionIdentityAdapter

NOW = datetime(2026, 8, 2, 16, 0, tzinfo=UTC)
TOKEN = "opaque-user-token"  # pragma: allowlist secret
CLIENT_SECRET = "identity-client-secret"  # pragma: allowlist secret


def _claims(**changes: object) -> dict[str, object]:
    claims: dict[str, object] = {
        "active": True,
        "iss": "https://identity.example.test/",
        "aud": ["sira-api"],
        "exp": NOW.timestamp() + 300,
        "auth_time": NOW.timestamp() - 30,
        "acr": "urn:example:mfa",
        "sub": "usr_verified_buyer",
        "organization_id": "org_verified_buyer",
        "roles": ["can_view_context", "can_submit_request"],
        "identity_kind": "HUMAN",
        "party": "BUYER",
    }
    claims.update(changes)
    return claims


def _adapter(
    handler: httpx.AsyncBaseTransport,
) -> IntrospectionIdentityAdapter:
    return IntrospectionIdentityAdapter(
        introspection_url="https://identity.example.test/oauth/introspect",
        client_id="sira-api",
        client_secret=CLIENT_SECRET,
        expected_issuer="https://identity.example.test/",
        expected_audience="sira-api",
        allowed_roles=frozenset(
            {"can_view_context", "can_submit_request", "can_approve_purchase"}
        ),
        step_up_acr_values=frozenset({"urn:example:mfa"}),
        client=httpx.AsyncClient(transport=handler),
        now=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_introspection_identity_binds_tenant_roles_and_recent_step_up() -> None:
    seen: dict[str, str] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["Authorization"]
        seen["body"] = request.content.decode()
        return httpx.Response(200, json=_claims())

    client = httpx.MockTransport(respond)
    principal = await _adapter(client).authenticate(TOKEN)

    assert principal is not None
    assert principal.organization_id == "org_verified_buyer"
    assert principal.actor_id == "usr_verified_buyer"
    assert principal.roles == frozenset({"can_view_context", "can_submit_request"})
    assert principal.step_up_verified is True
    assert seen["authorization"].startswith("Basic ")
    assert "token=opaque-user-token" in seen["body"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"active": False},
        {"iss": "https://attacker.example/"},
        {"aud": "other-api"},
        {"exp": NOW.timestamp() - 1},
        {"roles": ["can_view_context", "root"]},
        {"identity_kind": "HUMAN", "party": "ADMIN"},
    ],
)
async def test_introspection_rejects_untrusted_authority_claims(
    changes: dict[str, object],
) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=_claims(**changes)))

    assert await _adapter(transport).authenticate(TOKEN) is None


@pytest.mark.asyncio
async def test_step_up_requires_expected_acr_and_recent_authentication() -> None:
    stale = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json=_claims(auth_time=NOW.timestamp() - 601),
        )
    )

    principal = await _adapter(stale).authenticate(TOKEN)

    assert principal is not None
    assert principal.step_up_verified is False


@pytest.mark.asyncio
async def test_identity_outage_raises_only_safe_error() -> None:
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("upstream failed")

    with pytest.raises(IdentityProviderUnavailable) as captured:
        await _adapter(httpx.MockTransport(fail)).authenticate(TOKEN)

    assert str(captured.value) == "identity provider unavailable"
    assert captured.value.__context__ is None
    assert TOKEN not in repr(captured.value)
    assert CLIENT_SECRET not in repr(captured.value)


def test_introspection_requires_https_and_an_explicit_role_allowlist() -> None:
    with pytest.raises(ValueError, match="HTTPS endpoint"):
        IntrospectionIdentityAdapter(
            introspection_url="http://identity.example.test/introspect",
            client_id="sira-api",
            client_secret=CLIENT_SECRET,
            expected_issuer="https://identity.example.test/",
            expected_audience="sira-api",
            allowed_roles=frozenset({"can_view_context"}),
        )
    with pytest.raises(ValueError, match="role allowlist"):
        IntrospectionIdentityAdapter(
            introspection_url="https://identity.example.test/introspect",
            client_id="sira-api",
            client_secret=CLIENT_SECRET,
            expected_issuer="https://identity.example.test/",
            expected_audience="sira-api",
            allowed_roles=frozenset(),
        )
