from urllib.parse import parse_qs, urlsplit

import pytest

from integrations.prava.mcp import ConnectorCipher, PkceAuthorization, PravaMcpOAuthClient


def test_connector_cipher_round_trip_and_tamper_rejection() -> None:
    cipher = ConnectorCipher("a" * 32)
    sealed = cipher.encrypt_json({"access_token": "private", "refresh_token": "private-too"})

    assert "private" not in sealed
    assert cipher.decrypt_json(sealed)["access_token"] == "private"
    with pytest.raises(ValueError, match="invalid"):
        cipher.decrypt_json(sealed[:-1] + ("A" if sealed[-1] != "A" else "B"))


def test_prava_authorization_uses_pkce_and_exact_redirect() -> None:
    pkce = PkceAuthorization.create()
    redirect = "https://sira-seil.vercel.app/prava/connect/return"
    url = PravaMcpOAuthClient.authorization_url(
        client_id="client-id", redirect_uri=redirect, pkce=pkce
    )
    query = parse_qs(urlsplit(url).query)

    assert query["redirect_uri"] == [redirect]
    assert query["state"] == [pkce.state]
    assert query["code_challenge"] == [pkce.challenge]
    assert query["code_challenge_method"] == ["S256"]
