from __future__ import annotations

import string

from sira_api.callback_state import BrowserReturnStateSigner


def test_browser_return_state_is_opaque_signed_and_hash_only() -> None:
    signer = BrowserReturnStateSigner(
        "unit-test-browser-return-signing-key"  # pragma: allowlist secret
    )

    state = signer.issue()

    assert signer.verify(state) is True
    assert "org_" not in state
    assert "pi_" not in state
    assert "pays_" not in state
    assert signer.digest(state).startswith("sha256:")
    assert state not in signer.digest(state)
    assert signer.verify(f"{state[:-1]}A") is False
    assert signer.verify("br1.not-a-valid-signature.value") is False

    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_"
    alternate_last_character = alphabet[alphabet.index(state[-1]) ^ 1]
    noncanonical_signature = f"{state[:-1]}{alternate_last_character}"
    assert signer.verify(noncanonical_signature) is False


def test_browser_return_state_requires_a_long_signing_key() -> None:
    try:
        BrowserReturnStateSigner("too-short")  # pragma: allowlist secret
    except ValueError as error:
        assert "32 bytes" in str(error)
    else:
        raise AssertionError("short signing keys must fail closed")
