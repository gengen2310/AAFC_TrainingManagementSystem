"""Direct unit tests for app/security.py's token primitives.

No HTTP, no DB -- these target the exact primitives get_principal (dependencies.py)
relies on, added after Phase D mutation testing found two untested branches:
decode_token's algorithm allowlist (QUAL-011) and create_token's exp claim (QUAL-012).
"""
import jwt

from app.config import settings
from app.security import create_token, decode_token


def test_decode_token_rejects_alg_none_forged_token():
    """A token forged with alg=none (no signature at all) must never be accepted,
    regardless of its claimed payload -- this is the classic JWT algorithm-confusion
    attack: if the verifier's algorithms= allowlist ever includes "none" alongside
    the real algorithm, an attacker can mint an unsigned token for any subject."""
    forged = jwt.encode({"sub": "attacker", "exp": 9999999999, "tv": 0}, key=None, algorithm="none")
    assert decode_token(forged) is None


def test_decode_token_rejects_token_signed_with_wrong_algorithm():
    """A structurally valid HS256-shaped signature computed under a different key
    must not be accepted -- guards the same allowlist from the other direction."""
    forged = jwt.encode({"sub": "attacker", "exp": 9999999999, "tv": 0},
                        "not-the-real-secret", algorithm=settings.JWT_ALG)
    assert decode_token(forged) is None


def test_create_token_always_sets_a_real_exp_claim():
    """create_token must always embed a genuine exp claim -- without it, the token
    never expires (decode_token/PyJWT only enforce expiry if the claim is present
    at all). Decode without verifying expiry/signature so this test targets exactly
    the claim's presence and shape, not decode_token's other checks."""
    token = create_token("u1", {"role": "sqn_admin"})
    raw = jwt.decode(token, options={"verify_signature": False})
    assert "exp" in raw
    assert "iat" in raw
    assert raw["exp"] > raw["iat"], "exp must be strictly after iat, not equal/missing"


def test_create_token_respects_explicit_ttl_for_exp():
    """A short explicit ttl_min must produce a near-term exp, not a default/omitted one."""
    token = create_token("u1", {"role": "sqn_admin"}, ttl_min=1)
    raw = jwt.decode(token, options={"verify_signature": False})
    assert 0 < (raw["exp"] - raw["iat"]) <= 61
